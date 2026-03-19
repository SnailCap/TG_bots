from __future__ import annotations

from typing import Generic, TypeVar, TYPE_CHECKING

from core.interaction.ui.binding import get_default_ui_registry
from core.interaction.ui.components.process.base.base_step import Step

from .base import ObjectInputProcess
from .constants import DEFAULT_ERROR_TEXT_KEY, InputFlowMode

if TYPE_CHECKING:
    from core.interaction.runtime.user_input import UserInput
    from core.interaction.ui.components.process.base.effects import StepResult


ObjectT = TypeVar("ObjectT")


class ObjectInputStepBase(Step, Generic[ObjectT]):
    def _get_active_process(self, user_input: UserInput) -> ObjectInputProcess[ObjectT]:
        proc_key = user_input.state.get_active_process()

        registry = get_default_ui_registry()
        proc_cls = registry.get("process", proc_key)
        if proc_cls is None:
            raise RuntimeError(f"Unknown active process: '{proc_key}'")

        proc = proc_cls()
        if not isinstance(proc, ObjectInputProcess):
            raise TypeError(
                f"Active process '{proc_key}' is not ObjectInputProcess. "
                f"Got: {type(proc).__name__}"
            )

        return proc

    def _validate_full_object(
        self,
        user_input: UserInput,
        *,
        proc: ObjectInputProcess[ObjectT],
        obj: ObjectT,
    ) -> list[str]:
        errors = proc.validator.validate(obj)
        errors.extend(proc.validate_object(user_input, obj))
        return errors

    def _set_error_text_vars(
        self,
        user_input: UserInput,
        *,
        errors: list[str] | None = None,
    ) -> None:
        text = ""
        if errors:
            text = "\n".join(f"• {e}" for e in errors)

        self._patch_payload(
            user_input,
            text_variables={DEFAULT_ERROR_TEXT_KEY: text},
        )

    def _build_object_text_vars(
        self,
        *,
        proc: ObjectInputProcess[ObjectT],
        obj: ObjectT,
        errors: list[str] | None = None,
    ) -> dict[str, str]:
        raw = proc.codec.as_mapping(obj)

        text_vars: dict[str, str] = {}
        for field_spec in proc.schema().fields:
            text_vars[field_spec.name] = field_spec.format_value(raw.get(field_spec.name))

        text_vars[DEFAULT_ERROR_TEXT_KEY] = (
            "\n".join(f"• {error}" for error in errors) if errors else ""
        )
        return text_vars

    def _set_object_text_vars(
        self,
        user_input: UserInput,
        *,
        proc: ObjectInputProcess[ObjectT],
        obj: ObjectT,
        errors: list[str] | None = None,
    ) -> None:
        self._patch_payload(
            user_input,
            text_variables=self._build_object_text_vars(
                proc=proc,
                obj=obj,
                errors=errors,
            ),
        )

    async def _submit_or_show_errors(
        self,
        user_input: UserInput,
        *,
        proc: ObjectInputProcess[ObjectT],
        obj: ObjectT,
        go_to_on_error: str | None,
    ) -> StepResult:
        store = proc.payload_store

        try:
            await proc.submit_object(user_input, obj)
        except Exception as e:
            submit_errors = proc.on_submit_error(user_input, obj=obj, error=e)
            store.set_errors(user_input, submit_errors)
            self._set_object_text_vars(
                user_input,
                proc=proc,
                obj=obj,
                errors=submit_errors,
            )
            if go_to_on_error is None:
                return None
            return self.go_to_step(go_to_on_error)

        store.clear_errors(user_input)
        return self.finish()


class InputObjectStep(ObjectInputStepBase[ObjectT], Generic[ObjectT]):
    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_active_process(user_input)
        store = proc.payload_store

        raw_text = (user_input.text or "").strip()
        parse_result = proc.scenario.parse(raw_text)

        if parse_result.errors:
            store.set_errors(user_input, parse_result.errors)
            self._set_error_text_vars(user_input, errors=parse_result.errors)
            return None

        build_result = proc.schema().build_object(parse_result.data.values)
        obj = build_result.obj

        errors = list(build_result.errors)
        errors.extend(self._validate_full_object(user_input, proc=proc, obj=obj))

        if errors:
            store.set_errors(user_input, errors)
            self._set_error_text_vars(user_input, errors=errors)
            return None

        store.save_object(user_input, obj)
        store.clear_errors(user_input)
        self._set_object_text_vars(
            user_input,
            proc=proc,
            obj=obj,
            errors=[],
        )

        next_step = proc.flow.next_after_input
        if next_step is None:
            return await self._submit_or_show_errors(
                user_input,
                proc=proc,
                obj=obj,
                go_to_on_error=None,
            )

        return self.go_to_step(next_step)


class EditObjectStep(ObjectInputStepBase[ObjectT], Generic[ObjectT]):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_active_process(user_input)
        store = proc.payload_store

        obj = store.load_object(user_input)
        errors = store.get_errors(user_input)

        self._set_object_text_vars(
            user_input,
            proc=proc,
            obj=obj,
            errors=errors,
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_active_process(user_input)
        store = proc.payload_store

        raw_text = (user_input.text or "").strip()
        parse_result = proc.scenario.parse(raw_text)

        if parse_result.errors:
            store.set_errors(user_input, parse_result.errors)
            self._set_error_text_vars(user_input, errors=parse_result.errors)
            return None

        build_result = proc.codec.patch_object(
            base=store.load_object(user_input),
            patch_values=parse_result.data.values,
        )
        obj = build_result.obj

        errors = list(build_result.errors)
        errors.extend(self._validate_full_object(user_input, proc=proc, obj=obj))

        if errors:
            store.set_errors(user_input, errors)
            self._set_object_text_vars(
                user_input,
                proc=proc,
                obj=obj,
                errors=errors,
            )
            return None

        store.save_object(user_input, obj)
        store.clear_errors(user_input)
        self._set_object_text_vars(
            user_input,
            proc=proc,
            obj=obj,
            errors=[],
        )

        next_step = proc.flow.next_after_edit
        if next_step is None:
            return await self._submit_or_show_errors(
                user_input,
                proc=proc,
                obj=obj,
                go_to_on_error=None,
            )

        return self.go_to_step(next_step)


class ConfirmObjectStep(ObjectInputStepBase[ObjectT], Generic[ObjectT]):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_active_process(user_input)
        store = proc.payload_store

        obj = store.load_object(user_input)
        errors = store.get_errors(user_input)

        self._set_object_text_vars(
            user_input,
            proc=proc,
            obj=obj,
            errors=errors,
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        proc = self._get_active_process(user_input)
        store = proc.payload_store
        callbacks = proc.confirm_callbacks()

        callback = user_input.step_callback

        if callback == callbacks.edit:
            return self.go_to_step(proc.edit_step_name)

        if callback != callbacks.confirm:
            return None

        obj = store.load_object(user_input)

        validation_errors = self._validate_full_object(user_input, proc=proc, obj=obj)
        if validation_errors:
            store.set_errors(user_input, validation_errors)
            self._set_object_text_vars(
                user_input,
                proc=proc,
                obj=obj,
                errors=validation_errors,
            )

            if proc.flow_mode() == InputFlowMode.INPUT_CONFIRM:
                return self.go_to_step(proc.input_step_name)

            return self.go_to_step(proc.edit_step_name)

        return await self._submit_or_show_errors(
            user_input,
            proc=proc,
            obj=obj,
            go_to_on_error=proc.edit_step_name,
        )