from __future__ import annotations

from typing import TYPE_CHECKING, cast

from core.interaction.ui.binding import get_default_ui_registry, step
from core.interaction.ui.components.process.base.base_step import Step
from pipubot.domains.helper import (
    SaveHelperPreset,
    UpdateHelperPreset,
    delete_helper_preset_service,
    get_helper_preset_by_id_service,
    list_helper_presets_service,
    match_helper_preset_by_text_service,
    save_helper_preset_service,
    update_helper_preset_service,
)

from .process import (
    HELPER_ERROR_TEXT_KEY,
    HELPER_MODE_BOTH,
    HELPER_MODE_BOTTOM,
    HELPER_MODE_TOP,
    HELPER_PRESET_EDIT_MODE_BOTTOM,
    HELPER_PRESET_EDIT_MODE_LENGTH,
    HELPER_PRESET_PREVIEW_TEXT,
    HELPER_PROCESS_KEY,
    HELPER_SETTINGS_BASE_LENGTH_KEY,
    HELPER_SETTINGS_BOTTOM_EXTRA_KEY,
    HELPER_SETTINGS_SELECTED_TEXT_KEY,
    HELPER_STEP_ASK_BUNDLE,
    HELPER_STEP_EDIT_TEXT,
    HELPER_STEP_EDIT_URL,
    HELPER_STEP_EDIT_WIDTH,
    HELPER_STEP_PRESETS,
    HELPER_STEP_PRESET_CREATE,
    HELPER_STEP_PRESET_DELETE_SELECT,
    HELPER_STEP_PRESET_EDIT,
    HELPER_STEP_PRESET_EDIT_SELECT,
    HELPER_STEP_PRESET_EDIT_TEXT,
    HELPER_STEP_PRESET_URL,
    HELPER_STEP_RESULT,
    HELPER_TEXT_KEY,
    HELPER_URL_KEY,
    HelperProcess,
)
from .scenario import HelperBundleScenario

if TYPE_CHECKING:
    from core.interaction.runtime.context.user_input import UserInput
    from core.interaction.types.template_context import TemplateContext
    from core.interaction.ui.components.process.base.effects import StepResult


class HelperStepBase(Step):
    def _get_process(self, user_input: UserInput) -> HelperProcess:
        proc_key = user_input.state.get_active_process()
        if proc_key != HELPER_PROCESS_KEY:
            raise RuntimeError(f"Active process '{proc_key}' is not helper.")

        registry = get_default_ui_registry()
        proc_cls = registry.get("process", proc_key)
        if proc_cls is None:
            raise RuntimeError(f"Unknown active process: '{proc_key}'")

        proc = proc_cls()
        if not isinstance(proc, HelperProcess):
            raise TypeError(
                f"Active process '{proc_key}' is not HelperProcess. "
                f"Got: {type(proc).__name__}"
            )

        return cast(HelperProcess, proc)

    def _set_error(self, user_input: UserInput, message: str) -> None:
        self._patch_payload(user_input, text_variables={HELPER_ERROR_TEXT_KEY: message})

    def _clear_error(self, user_input: UserInput) -> None:
        self._set_error(user_input, "")

    async def _update_active_preset(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        settings = proc.get_settings(user_input)
        preset_id = proc.get_active_preset_id(user_input)
        selected_text = str(settings[HELPER_SETTINGS_SELECTED_TEXT_KEY]).strip()
        if not selected_text or selected_text == HELPER_PRESET_PREVIEW_TEXT:
            return

        if preset_id is None:
            preset = await save_helper_preset_service(
                user_input.session,
                data=SaveHelperPreset(
                    owner_telegram_id=user_input.telegram_id,
                    text=selected_text,
                    base_length=int(settings[HELPER_SETTINGS_BASE_LENGTH_KEY]),
                    bottom_extra_symbols=int(settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY]),
                ),
            )
            proc.set_active_preset_id(user_input, preset.id)
            return

        await update_helper_preset_service(
            user_input.session,
            data=UpdateHelperPreset(
                owner_telegram_id=user_input.telegram_id,
                preset_id=preset_id,
                text=selected_text,
                base_length=int(settings[HELPER_SETTINGS_BASE_LENGTH_KEY]),
                bottom_extra_symbols=int(settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY]),
            ),
        )


@step(HELPER_STEP_ASK_BUNDLE)
class HelperAskBundleStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        settings = proc.get_settings(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "base_length": settings[HELPER_SETTINGS_BASE_LENGTH_KEY],
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_process(user_input)
        scenario = HelperBundleScenario()
        parse_result = scenario.parse(user_input.text or "")

        if parse_result.errors:
            self._set_error(user_input, "\n".join(f"• {e}" for e in parse_result.errors))
            return None

        text = str(parse_result.data.values["text"])
        url = str(parse_result.data.values["url"])
        raw_width = parse_result.data.values.get("width")

        preset = await match_helper_preset_by_text_service(
            user_input.session,
            owner_telegram_id=user_input.telegram_id,
            text=text,
        )
        if preset is not None:
            proc.apply_preset_settings(
                user_input,
                text=preset.text,
                base_length=preset.base_length,
                bottom_extra_symbols=preset.bottom_extra_symbols,
                preset_id=preset.id,
            )

        draft = proc.build_draft_from_bundle(
            user_input,
            text=text,
            url=url,
            width=int(raw_width) if raw_width is not None else None,
        )
        proc.set_draft(user_input, draft)
        self._clear_error(user_input)
        return self.go_to_step(HELPER_STEP_RESULT)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        if user_input.step_callback == "helper:presets":
            return self.go_to_step(HELPER_STEP_PRESETS)
        return None


@step(HELPER_STEP_PRESETS)
class HelperPresetsStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        self._clear_error(user_input)

    async def _provide_context(self, user_input: UserInput, ctx: TemplateContext) -> None:
        proc = self._get_process(user_input)
        presets = await list_helper_presets_service(
            user_input.session,
            owner_telegram_id=user_input.telegram_id,
        )
        ctx.keyboard["layout"] = proc.build_presets_keyboard_layout(
            preset_refs=proc.build_preset_list_button_refs(
                presets=presets,
                button_key="helper_presets_item",
            )
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback
        if callback is None:
            return None

        if callback == "helper:presets:back":
            return self.go_to_step(HELPER_STEP_ASK_BUNDLE)

        if callback == "helper:presets:add":
            return self.go_to_step(HELPER_STEP_PRESET_CREATE)

        if callback == "helper:presets:edit":
            return self.go_to_step(HELPER_STEP_PRESET_EDIT_SELECT)

        if callback == "helper:presets:delete":
            return self.go_to_step(HELPER_STEP_PRESET_DELETE_SELECT)

        if callback.startswith("helper:presets:use:"):
            raw_id = callback.removeprefix("helper:presets:use:")
            try:
                preset_id = int(raw_id)
            except ValueError:
                return None

            preset = await get_helper_preset_by_id_service(
                user_input.session,
                owner_telegram_id=user_input.telegram_id,
                preset_id=preset_id,
            )
            if preset is None:
                self._set_error(user_input, "Пресет не найден.")
                return None

            proc = self._get_process(user_input)
            proc.apply_preset_settings(
                user_input,
                text=preset.text,
                base_length=preset.base_length,
                bottom_extra_symbols=preset.bottom_extra_symbols,
                preset_id=preset.id,
            )
            self._clear_error(user_input)
            return self.go_to_step(HELPER_STEP_PRESET_URL)

        return None


@step(HELPER_STEP_PRESET_DELETE_SELECT)
class HelperPresetDeleteSelectStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        self._clear_error(user_input)

    async def _provide_context(self, user_input: UserInput, ctx: TemplateContext) -> None:
        proc = self._get_process(user_input)
        presets = await list_helper_presets_service(
            user_input.session,
            owner_telegram_id=user_input.telegram_id,
        )
        ctx.keyboard["layout"] = proc.build_preset_edit_select_keyboard_layout(
            preset_refs=proc.build_preset_list_button_refs(
                presets=presets,
                button_key="helper_preset_delete_select_item",
            ),
            back_button_key="helper_preset_delete_select_back",
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback
        if callback is None:
            return None

        if callback == "helper:preset:delete:select:back":
            return self.go_to_step(HELPER_STEP_PRESETS)

        if callback.startswith("helper:preset:delete:select:"):
            raw_id = callback.removeprefix("helper:preset:delete:select:")
            try:
                preset_id = int(raw_id)
            except ValueError:
                return None

            deleted = await delete_helper_preset_service(
                user_input.session,
                owner_telegram_id=user_input.telegram_id,
                preset_id=preset_id,
            )
            if not deleted:
                self._set_error(user_input, "Пресет не найден.")
            else:
                proc = self._get_process(user_input)
                if proc.get_active_preset_id(user_input) == preset_id:
                    proc.set_active_preset_id(user_input, None)
                self._clear_error(user_input)
            return self.go_to_step(HELPER_STEP_PRESET_DELETE_SELECT)

        return None


@step(HELPER_STEP_PRESET_URL)
class HelperPresetUrlStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        settings = proc.get_settings(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "selected_text": settings[HELPER_SETTINGS_SELECTED_TEXT_KEY],
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        url = str(user_input.text or "").strip()
        if not url:
            self._set_error(user_input, "Вставьте ссылку.")
            return None

        proc = self._get_process(user_input)
        draft = proc.build_draft_from_active_preset(user_input, url=url)
        proc.set_draft(user_input, draft)
        self._clear_error(user_input)
        return self.go_to_step(HELPER_STEP_RESULT)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        if user_input.step_callback == "helper:preset:url:back":
            return self.go_to_step(HELPER_STEP_PRESETS)
        return None


@step(HELPER_STEP_PRESET_CREATE)
class HelperPresetCreateStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_process(user_input)
        text = str(user_input.text or "").strip()
        if not text:
            self._set_error(user_input, "Введите текст пресета.")
            return None

        settings = proc.get_settings(user_input)

        preset = await save_helper_preset_service(
            user_input.session,
            data=SaveHelperPreset(
                owner_telegram_id=user_input.telegram_id,
                text=text,
                base_length=int(settings[HELPER_SETTINGS_BASE_LENGTH_KEY]),
                bottom_extra_symbols=int(settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY]),
            ),
        )
        proc.apply_preset_settings(
            user_input,
            text=preset.text,
            base_length=preset.base_length,
            bottom_extra_symbols=preset.bottom_extra_symbols,
            preset_id=preset.id,
        )
        proc.set_preset_edit_mode(user_input, HELPER_PRESET_EDIT_MODE_LENGTH)
        self._clear_error(user_input)
        return self.go_to_step(HELPER_STEP_PRESET_EDIT)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        if user_input.step_callback == "helper:preset:create:back":
            return self.go_to_step(HELPER_STEP_PRESETS)
        return None


@step(HELPER_STEP_PRESET_EDIT_SELECT)
class HelperPresetEditSelectStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        self._clear_error(user_input)

    async def _provide_context(self, user_input: UserInput, ctx: TemplateContext) -> None:
        proc = self._get_process(user_input)
        presets = await list_helper_presets_service(
            user_input.session,
            owner_telegram_id=user_input.telegram_id,
        )
        ctx.keyboard["layout"] = proc.build_preset_edit_select_keyboard_layout(
            preset_refs=proc.build_preset_list_button_refs(
                presets=presets,
                button_key="helper_preset_edit_select_item",
                active_preset_id=proc.get_active_preset_id(user_input),
            )
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback
        if callback is None:
            return None

        if callback == "helper:preset:edit:select:back":
            return self.go_to_step(HELPER_STEP_PRESETS)

        if callback.startswith("helper:preset:edit:select:"):
            raw_id = callback.removeprefix("helper:preset:edit:select:")
            try:
                preset_id = int(raw_id)
            except ValueError:
                return None

            preset = await get_helper_preset_by_id_service(
                user_input.session,
                owner_telegram_id=user_input.telegram_id,
                preset_id=preset_id,
            )
            if preset is None:
                self._set_error(user_input, "Пресет не найден.")
                return None

            proc = self._get_process(user_input)
            proc.apply_preset_settings(
                user_input,
                text=preset.text,
                base_length=preset.base_length,
                bottom_extra_symbols=preset.bottom_extra_symbols,
                preset_id=preset.id,
            )
            proc.set_preset_edit_mode(user_input, HELPER_PRESET_EDIT_MODE_LENGTH)
            self._clear_error(user_input)
            return self.go_to_step(HELPER_STEP_PRESET_EDIT)

        return None


@step(HELPER_STEP_PRESET_EDIT)
class HelperPresetEditStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        self._refresh(user_input)

    async def _provide_context(self, user_input: UserInput, ctx: TemplateContext) -> None:
        proc = self._get_process(user_input)
        settings = proc.get_settings(user_input)
        mode = proc.get_preset_edit_mode(user_input)

        ctx.text[HELPER_SETTINGS_SELECTED_TEXT_KEY] = settings[HELPER_SETTINGS_SELECTED_TEXT_KEY]
        ctx.text[HELPER_SETTINGS_BASE_LENGTH_KEY] = settings[HELPER_SETTINGS_BASE_LENGTH_KEY]
        ctx.text[HELPER_SETTINGS_BOTTOM_EXTRA_KEY] = settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY]
        ctx.text["preset_preview_text"] = proc.build_preset_preview_text(user_input)
        ctx.keyboard["layout"] = proc.build_preset_edit_keyboard_layout(mode)

    def _refresh(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        settings = proc.get_settings(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                HELPER_SETTINGS_SELECTED_TEXT_KEY: settings[HELPER_SETTINGS_SELECTED_TEXT_KEY],
                HELPER_SETTINGS_BASE_LENGTH_KEY: settings[HELPER_SETTINGS_BASE_LENGTH_KEY],
                HELPER_SETTINGS_BOTTOM_EXTRA_KEY: settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY],
                "preset_preview_text": proc.build_preset_preview_text(user_input),
            },
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback
        if callback is None:
            return None

        proc = self._get_process(user_input)

        if callback == "helper:preset:edit:back":
            return self.go_to_step(HELPER_STEP_PRESETS)

        if callback == "helper:preset:edit:text":
            return self.go_to_step(HELPER_STEP_PRESET_EDIT_TEXT)

        if callback == "helper:preset:edit:mode:length":
            proc.set_preset_edit_mode(user_input, HELPER_PRESET_EDIT_MODE_LENGTH)
            self._refresh(user_input)
            return self.go_to_step(HELPER_STEP_PRESET_EDIT)

        if callback == "helper:preset:edit:mode:bottom":
            proc.set_preset_edit_mode(user_input, HELPER_PRESET_EDIT_MODE_BOTTOM)
            self._refresh(user_input)
            return self.go_to_step(HELPER_STEP_PRESET_EDIT)

        if callback.startswith("helper:width:delta:"):
            raw_delta = callback.removeprefix("helper:width:delta:")
            try:
                delta = int(raw_delta)
            except ValueError:
                return None

            proc.adjust_preset_settings(user_input, delta)
            await self._update_active_preset(user_input)
            self._refresh(user_input)
            return self.go_to_step(HELPER_STEP_PRESET_EDIT)

        return None


@step(HELPER_STEP_PRESET_EDIT_TEXT)
class HelperPresetEditTextStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        settings = proc.get_settings(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "current_value": settings[HELPER_SETTINGS_SELECTED_TEXT_KEY],
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        proc = self._get_process(user_input)
        preset_id = proc.get_active_preset_id(user_input)
        if preset_id is None:
            self._set_error(user_input, "Сначала выберите пресет.")
            return None

        value = str(user_input.text or "").strip()
        if not value:
            self._set_error(user_input, "Введите новый текст.")
            return None

        settings = proc.get_settings(user_input)
        try:
            updated = await update_helper_preset_service(
                user_input.session,
                data=UpdateHelperPreset(
                    owner_telegram_id=user_input.telegram_id,
                    preset_id=preset_id,
                    text=value,
                    base_length=int(settings[HELPER_SETTINGS_BASE_LENGTH_KEY]),
                    bottom_extra_symbols=int(settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY]),
                ),
            )
        except ValueError as exc:
            self._set_error(user_input, str(exc))
            return None
        if updated is None:
            self._set_error(user_input, "Пресет не найден.")
            return None

        proc.apply_preset_settings(
            user_input,
            text=updated.text,
            base_length=updated.base_length,
            bottom_extra_symbols=updated.bottom_extra_symbols,
            preset_id=updated.id,
        )
        self._clear_error(user_input)
        return self.go_to_step(HELPER_STEP_PRESET_EDIT)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        if user_input.step_callback == "helper:preset:edit:text:back":
            return self.go_to_step(HELPER_STEP_PRESET_EDIT)
        return None


@step(HELPER_STEP_RESULT)
class HelperResultStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        draft = proc.get_draft(user_input)
        try:
            result_text = proc.build_result_text(draft)
        except Exception as exc:
            self._set_error(user_input, str(exc))
            return

        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "result_text": result_text,
            },
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback
        if callback is None:
            return None

        if callback == "helper:edit:text":
            return self.go_to_step(HELPER_STEP_EDIT_TEXT)

        if callback == "helper:edit:url":
            return self.go_to_step(HELPER_STEP_EDIT_URL)

        if callback == "helper:edit:width":
            return self.go_to_step(HELPER_STEP_EDIT_WIDTH)

        if callback == "helper:restart:with_preset":
            proc = self._get_process(user_input)
            proc.restart(user_input)
            return self.go_to_step(HELPER_STEP_PRESETS)

        if callback == "helper:restart":
            proc = self._get_process(user_input)
            proc.restart(user_input)
            return self.go_to_step(HELPER_STEP_ASK_BUNDLE)

        return None


@step(HELPER_STEP_EDIT_TEXT)
class HelperEditTextStep(HelperStepBase):
    field_name = HELPER_TEXT_KEY

    async def _on_start(self, user_input: UserInput) -> None:
        draft = self._get_process(user_input).get_draft(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "current_value": getattr(draft, self.field_name),
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        value = str(user_input.text or "").strip()
        if not value:
            self._set_error(user_input, "Введите новый текст.")
            return None

        proc = self._get_process(user_input)
        proc.update_field(user_input, field_name=HELPER_TEXT_KEY, value=value)
        self._clear_error(user_input)
        return self.go_to_step(HELPER_STEP_RESULT)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        if user_input.step_callback == "helper:edit:back":
            return self.go_to_step(HELPER_STEP_RESULT)
        return None


@step(HELPER_STEP_EDIT_URL)
class HelperEditUrlStep(HelperStepBase):
    field_name = HELPER_URL_KEY

    async def _on_start(self, user_input: UserInput) -> None:
        draft = self._get_process(user_input).get_draft(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "current_value": getattr(draft, self.field_name),
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        value = str(user_input.text or "").strip()
        if not value:
            self._set_error(user_input, "Введите новую ссылку.")
            return None

        proc = self._get_process(user_input)
        proc.update_field(user_input, field_name=HELPER_URL_KEY, value=value)
        self._clear_error(user_input)
        return self.go_to_step(HELPER_STEP_RESULT)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        if user_input.step_callback == "helper:edit:back":
            return self.go_to_step(HELPER_STEP_RESULT)
        return None


@step(HELPER_STEP_EDIT_WIDTH)
class HelperEditWidthStep(HelperStepBase):
    async def _on_start(self, user_input: UserInput) -> None:
        self._refresh_preview(user_input)

    async def _provide_context(self, user_input: UserInput, ctx: TemplateContext) -> None:
        proc = self._get_process(user_input)
        draft = proc.get_draft(user_input)

        ctx.text["result_text"] = proc.build_width_preview_text(draft)
        ctx.keyboard["layout"] = proc.build_width_keyboard_layout(draft)

    def _refresh_preview(self, user_input: UserInput) -> None:
        proc = self._get_process(user_input)
        draft = proc.get_draft(user_input)
        self._patch_payload(
            user_input,
            text_variables={
                HELPER_ERROR_TEXT_KEY: "",
                "result_text": proc.build_width_preview_text(draft),
            },
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        return None

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback
        if callback is None:
            return None

        proc = self._get_process(user_input)

        if callback == "helper:width:back":
            return self.go_to_step(HELPER_STEP_RESULT)

        if callback == "helper:width:mode:both":
            proc.set_mode(user_input, HELPER_MODE_BOTH)
            self._refresh_preview(user_input)
            return self.go_to_step(HELPER_STEP_EDIT_WIDTH)

        if callback == "helper:width:mode:top":
            proc.set_mode(user_input, HELPER_MODE_TOP)
            self._refresh_preview(user_input)
            return self.go_to_step(HELPER_STEP_EDIT_WIDTH)

        if callback == "helper:width:mode:bottom":
            proc.set_mode(user_input, HELPER_MODE_BOTTOM)
            self._refresh_preview(user_input)
            return self.go_to_step(HELPER_STEP_EDIT_WIDTH)

        if callback.startswith("helper:width:delta:"):
            raw_delta = callback.removeprefix("helper:width:delta:")
            try:
                delta = int(raw_delta)
            except ValueError:
                return None

            proc.adjust_width(user_input, delta)
            self._refresh_preview(user_input)
            return self.go_to_step(HELPER_STEP_EDIT_WIDTH)

        return None
