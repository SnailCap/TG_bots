from __future__ import annotations

from typing import Generic, TypeVar, TYPE_CHECKING

from core.interaction.ui.binding import get_default_ui_registry
from core.interaction.ui.components.process.base.base_step import Step

from .base import DraftCreateProcess

if TYPE_CHECKING:
    from core.interaction.input.user_input import UserInput
    from core.interaction.ui.components.process.base.effects import StepResult

DraftT = TypeVar("DraftT")


class DraftCreateStepBase(Step, Generic[DraftT]):
    def _get_active_process(self, user_input: UserInput) -> DraftCreateProcess[DraftT]:
        proc_key = user_input.state.get_active_process()

        registry = get_default_ui_registry()
        proc_cls = registry.get("process", proc_key)
        if proc_cls is None:
            raise RuntimeError(f"Unknown active process: '{proc_key}'")

        proc = proc_cls()
        if not isinstance(proc, DraftCreateProcess):
            raise TypeError(
                f"Active process '{proc_key}' is not DraftCreateProcess. "
                f"Got: {type(proc).__name__}"
            )

        return proc

    def _set_text_variables(
        self,
        user_input: UserInput,
        *,
        draft: DraftT,
        errors: list[str] | None = None,
    ) -> None:
        proc = self._get_active_process(user_input)
        text_vars = proc.presenter().build_text_variables(
            draft=draft,
            errors=errors,
        )
        self._patch_payload(user_input, text_variables=text_vars)

    def _validate_full_draft(
        self,
        user_input: UserInput,
        *,
        draft: DraftT,
    ) -> list[str]:
        proc = self._get_active_process(user_input)
        errors = proc.validator().validate(draft)
        errors.extend(proc.validate_draft(user_input, draft))
        return errors


class CollectDraftStep(DraftCreateStepBase[DraftT], Generic[DraftT]):
    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_active_process(user_input)
        parser = proc.parser()
        store = proc.payload_store()

        text = (user_input.text or "").strip()
        parse_result = parser.parse_initial(text)

        draft = parse_result.draft
        errors = list(parse_result.errors)
        errors.extend(self._validate_full_draft(user_input, draft=draft))

        if errors:
            store.set_errors(user_input, errors)
            self._set_text_variables(user_input, draft=draft, errors=errors)
            return None

        store.save_draft(user_input, draft)
        store.clear_errors(user_input)
        self._set_text_variables(user_input, draft=draft)
        return self.go_to_step(proc.confirm_step_name)


class EditDraftStep(DraftCreateStepBase[DraftT], Generic[DraftT]):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_active_process(user_input)
        store = proc.payload_store()

        draft = store.load_draft(user_input)
        self._set_text_variables(
            user_input,
            draft=draft,
            errors=store.get_errors(user_input),
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_active_process(user_input)
        parser = proc.parser()
        store = proc.payload_store()

        text = (user_input.text or "").strip()
        parse_result = parser.parse_patch(text)

        if parse_result.errors:
            current = store.load_draft(user_input)
            store.set_errors(user_input, parse_result.errors)
            self._set_text_variables(
                user_input,
                draft=current,
                errors=parse_result.errors,
            )
            return None

        updated = store.merge_with_saved(user_input, parse_result.draft)
        validation_errors = self._validate_full_draft(user_input, draft=updated)

        if validation_errors:
            store.set_errors(user_input, validation_errors)
            self._set_text_variables(
                user_input,
                draft=updated,
                errors=validation_errors,
            )
            return None

        store.save_draft(user_input, updated)
        store.clear_errors(user_input)
        self._set_text_variables(user_input, draft=updated)
        return self.go_to_step(proc.confirm_step_name)


class ConfirmDraftStep(DraftCreateStepBase[DraftT], Generic[DraftT]):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_active_process(user_input)
        store = proc.payload_store()

        draft = store.load_draft(user_input)
        self._set_text_variables(
            user_input,
            draft=draft,
            errors=store.get_errors(user_input),
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        print("RAW CALLBACK:", user_input.callback_data)
        print("STEP CALLBACK:", user_input.step_callback)
        print("IS SERVICE:", user_input.is_service_callback)
        print("SERVICE KIND:", user_input.service_kind)
        proc = self._get_active_process(user_input)
        store = proc.payload_store()
        callbacks = proc.confirm_callbacks()

        callback = user_input.step_callback

        if callback == callbacks.edit:
            return self.go_to_step(proc.edit_step_name)

        if callback != callbacks.confirm:
            return None

        draft = store.load_draft(user_input)

        validation_errors = self._validate_full_draft(user_input, draft=draft)
        if validation_errors:
            store.set_errors(user_input, validation_errors)
            self._set_text_variables(
                user_input,
                draft=draft,
                errors=validation_errors,
            )
            return self.go_to_step(proc.edit_step_name)

        try:
            await proc.submit_draft(user_input, draft)
        except Exception as e:
            errors = proc.on_submit_error(
                user_input,
                draft=draft,
                error=e,
            )
            store.set_errors(user_input, errors)
            self._set_text_variables(
                user_input,
                draft=draft,
                errors=errors,
            )
            return self.go_to_step(proc.edit_step_name)

        store.clear_errors(user_input)
        return self.finish()