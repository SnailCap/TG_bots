from __future__ import annotations

from dataclasses import dataclass

from core.interaction.ui.binding import process
from core.interaction.ui.components.process.base.base_process import Process
from core.interaction.ui.keyboard.button_ref import ButtonRef
from core.shared.normalize.strings import normalize_required_str
from core.shared.normalize.telegram import html_link

HELPER_PROCESS_KEY = "helper"

HELPER_STEP_ASK_BUNDLE = "helper_ask_bundle"
HELPER_STEP_RESULT = "helper_result"
HELPER_STEP_PRESETS = "helper_presets"
HELPER_STEP_PRESET_URL = "helper_preset_url"
HELPER_STEP_PRESET_CREATE = "helper_preset_create"
HELPER_STEP_PRESET_EDIT_SELECT = "helper_preset_edit_select"
HELPER_STEP_PRESET_DELETE_SELECT = "helper_preset_delete_select"
HELPER_STEP_PRESET_EDIT = "helper_preset_edit"
HELPER_STEP_PRESET_EDIT_TEXT = "helper_preset_edit_text"
HELPER_STEP_EDIT_TEXT = "helper_edit_text"
HELPER_STEP_EDIT_URL = "helper_edit_url"
HELPER_STEP_EDIT_WIDTH = "helper_edit_width"
HELPER_STEP_RESTART = "helper_restart"

HELPER_TEXT_KEY = "text"
HELPER_URL_KEY = "url"
HELPER_WIDTH_KEY = "width"
HELPER_MODE_KEY = "mode"
HELPER_ERROR_TEXT_KEY = "error_text"

HELPER_PAYLOAD_TEXT_KEY = "text"
HELPER_PAYLOAD_URL_KEY = "url"
HELPER_PAYLOAD_TOP_WIDTH_KEY = "top_width"
HELPER_PAYLOAD_BOTTOM_WIDTH_KEY = "bottom_width"
HELPER_PAYLOAD_MODE_KEY = "mode"
HELPER_PAYLOAD_ACTIVE_PRESET_ID_KEY = "active_preset_id"
HELPER_PAYLOAD_PRESET_EDIT_MODE_KEY = "preset_edit_mode"

HELPER_SETTINGS_STATE_KEY = "helper_settings"
HELPER_SETTINGS_BASE_LENGTH_KEY = "base_length"
HELPER_SETTINGS_BOTTOM_EXTRA_KEY = "bottom_extra_symbols"
HELPER_SETTINGS_SELECTED_TEXT_KEY = "selected_text"

HELPER_PRESET_EDIT_MODE_LENGTH = "length"
HELPER_PRESET_EDIT_MODE_BOTTOM = "bottom"

HELPER_MODE_BOTH = "both"
HELPER_MODE_TOP = "top"
HELPER_MODE_BOTTOM = "bottom"

# Temporary filler for clickable area width. Replace with the invisible symbol later.
HELPER_FILLER_CHAR = "‎ "

HELPER_DEFAULT_SETTINGS: dict[str, int] = {
    HELPER_SETTINGS_BASE_LENGTH_KEY: 15,
    HELPER_SETTINGS_BOTTOM_EXTRA_KEY: 0,
}

HELPER_PRESET_PREVIEW_TEXT = "Пример"
HELPER_PRESET_PREVIEW_URL = "https://example.com"


@dataclass(frozen=True, slots=True)
class HelperDraft:
    text: str
    url: str
    top_width: int
    bottom_width: int
    mode: str = HELPER_MODE_BOTH


@process(HELPER_PROCESS_KEY)
class HelperProcess(Process):
    step_names = [HELPER_STEP_ASK_BUNDLE]

    async def handle_input(self, user_input) -> list:
        return []

    @property
    def allowed_step_names(self) -> list[str]:
        return [
            HELPER_STEP_ASK_BUNDLE,
            HELPER_STEP_RESULT,
            HELPER_STEP_PRESETS,
            HELPER_STEP_PRESET_URL,
            HELPER_STEP_PRESET_CREATE,
            HELPER_STEP_PRESET_EDIT_SELECT,
            HELPER_STEP_PRESET_DELETE_SELECT,
            HELPER_STEP_PRESET_EDIT,
            HELPER_STEP_PRESET_EDIT_TEXT,
            HELPER_STEP_EDIT_TEXT,
            HELPER_STEP_EDIT_URL,
            HELPER_STEP_EDIT_WIDTH,
            HELPER_STEP_RESTART,
        ]

    def get_settings(self, user_input) -> dict[str, object]:
        raw = user_input.state.get(HELPER_SETTINGS_STATE_KEY, {})
        normalized = self._normalize_settings(raw)
        user_input.state.set(HELPER_SETTINGS_STATE_KEY, normalized)
        return normalized

    def set_settings(self, user_input, settings: dict[str, object]) -> dict[str, object]:
        normalized = self._normalize_settings(settings)
        user_input.state.set(HELPER_SETTINGS_STATE_KEY, normalized)
        return normalized

    def get_active_preset_id(self, user_input) -> int | None:
        payload = user_input.state.get_process_payload(self._key())
        raw_value = payload.get(HELPER_PAYLOAD_ACTIVE_PRESET_ID_KEY)
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    def set_active_preset_id(self, user_input, preset_id: int | None) -> None:
        user_input.state.update_process_payload(
            self._key(),
            **{HELPER_PAYLOAD_ACTIVE_PRESET_ID_KEY: preset_id},
        )

    def get_preset_edit_mode(self, user_input) -> str:
        payload = user_input.state.get_process_payload(self._key())
        raw_mode = str(
            payload.get(
                HELPER_PAYLOAD_PRESET_EDIT_MODE_KEY,
                HELPER_PRESET_EDIT_MODE_LENGTH,
            )
            or HELPER_PRESET_EDIT_MODE_LENGTH
        ).strip()
        if raw_mode not in (HELPER_PRESET_EDIT_MODE_LENGTH, HELPER_PRESET_EDIT_MODE_BOTTOM):
            raw_mode = HELPER_PRESET_EDIT_MODE_LENGTH
        user_input.state.update_process_payload(
            self._key(),
            **{HELPER_PAYLOAD_PRESET_EDIT_MODE_KEY: raw_mode},
        )
        return raw_mode

    def set_preset_edit_mode(self, user_input, mode: str) -> str:
        if mode not in (HELPER_PRESET_EDIT_MODE_LENGTH, HELPER_PRESET_EDIT_MODE_BOTTOM):
            return self.get_preset_edit_mode(user_input)

        user_input.state.update_process_payload(
            self._key(),
            **{HELPER_PAYLOAD_PRESET_EDIT_MODE_KEY: mode},
        )
        return mode

    def build_draft_from_bundle(
        self,
        user_input,
        *,
        text: str,
        url: str,
        width: int | None = None,
    ) -> HelperDraft:
        settings = self.get_settings(user_input)
        target_width = max(
            1,
            int(settings[HELPER_SETTINGS_BASE_LENGTH_KEY]) if width is None else int(width),
        )
        top_width = max(0, target_width - len(text))
        top_total_width = len(text) + top_width
        bottom_width = max(
            1,
            top_total_width + int(settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY]),
        )

        return HelperDraft(
            text=text,
            url=url,
            top_width=top_width,
            bottom_width=bottom_width,
            mode=HELPER_MODE_BOTH,
        )

    def build_draft_from_active_preset(self, user_input, *, url: str) -> HelperDraft:
        settings = self.get_settings(user_input)
        return self.build_draft_from_bundle(
            user_input,
            text=str(settings[HELPER_SETTINGS_SELECTED_TEXT_KEY]),
            url=url,
            width=None,
        )

    def build_presets_keyboard_layout(self, *, preset_refs: list[ButtonRef]) -> list[list[ButtonRef]]:
        layout: list[list[ButtonRef]] = [
            [
                ButtonRef(key="helper_presets_add"),
                ButtonRef(key="helper_presets_edit"),
                ButtonRef(key="helper_presets_delete"),
            ]
        ]
        layout.extend([[ref] for ref in preset_refs])
        layout.append([ButtonRef(key="helper_presets_back")])
        return layout

    def build_preset_edit_select_keyboard_layout(
        self,
        *,
        preset_refs: list[ButtonRef],
        back_button_key: str = "helper_preset_edit_select_back",
    ) -> list[list[ButtonRef]]:
        layout: list[list[ButtonRef]] = [[ref] for ref in preset_refs]
        layout.append([ButtonRef(key=back_button_key)])
        return layout

    def build_preset_list_button_refs(
        self,
        *,
        presets: list[object],
        button_key: str,
        active_preset_id: int | None = None,
    ) -> list[ButtonRef]:
        refs: list[ButtonRef] = []
        for preset in presets:
            preset_id = getattr(preset, "id", None)
            preset_text = str(getattr(preset, "text", "") or "").strip()
            if preset_id is None or not preset_text:
                continue

            mark = "☑ " if active_preset_id == preset_id else ""
            refs.append(
                ButtonRef(
                    key=button_key,
                    vars={
                        "preset_id": preset_id,
                        "text": preset_text,
                        "mark": mark,
                    },
                )
            )
        return refs

    def build_preset_edit_keyboard_layout(self, mode: str) -> list[list[ButtonRef]]:
        mark_length = "☑" if mode == HELPER_PRESET_EDIT_MODE_LENGTH else "☐"
        mark_bottom = "☑" if mode == HELPER_PRESET_EDIT_MODE_BOTTOM else "☐"

        return [
            [
                ButtonRef(key="helper_preset_edit_save_exit"),
            ],
            [
                ButtonRef(key="helper_preset_edit_text"),
            ],
            [
                ButtonRef(key="helper_preset_edit_mode_length", vars={"mark": mark_length}),
                ButtonRef(key="helper_preset_edit_mode_bottom", vars={"mark": mark_bottom}),
            ],
            [
                ButtonRef(key="helper_width_delta_-3"),
                ButtonRef(key="helper_width_delta_-2"),
                ButtonRef(key="helper_width_delta_-1"),
                ButtonRef(key="helper_width_delta_+1"),
                ButtonRef(key="helper_width_delta_+2"),
                ButtonRef(key="helper_width_delta_+3"),
            ],
            [
                ButtonRef(key="helper_width_delta_-5"),
                ButtonRef(key="helper_width_delta_-10"),
                ButtonRef(key="helper_width_delta_-15"),
                ButtonRef(key="helper_width_delta_+5"),
                ButtonRef(key="helper_width_delta_+10"),
                ButtonRef(key="helper_width_delta_+15"),
            ],
            [
                ButtonRef(key="helper_preset_edit_back"),
            ],
        ]

    def get_draft(self, user_input) -> HelperDraft:
        payload = user_input.state.get_process_payload(self._key())

        text = str(payload.get(HELPER_PAYLOAD_TEXT_KEY, "") or "").strip()
        url = str(payload.get(HELPER_PAYLOAD_URL_KEY, "") or "").strip()
        raw_top_width = payload.get(HELPER_PAYLOAD_TOP_WIDTH_KEY, 0)
        raw_bottom_width = payload.get(HELPER_PAYLOAD_BOTTOM_WIDTH_KEY, 0)
        raw_mode = str(payload.get(HELPER_PAYLOAD_MODE_KEY, HELPER_MODE_BOTH) or HELPER_MODE_BOTH).strip()

        try:
            top_width = int(raw_top_width)
        except (TypeError, ValueError):
            top_width = 0

        try:
            bottom_width = int(raw_bottom_width)
        except (TypeError, ValueError):
            bottom_width = 0

        if raw_mode not in (HELPER_MODE_BOTH, HELPER_MODE_TOP, HELPER_MODE_BOTTOM):
            raw_mode = HELPER_MODE_BOTH

        return HelperDraft(
            text=text,
            url=url,
            top_width=top_width,
            bottom_width=bottom_width,
            mode=raw_mode,
        )

    @staticmethod
    def _normalize_settings(raw: object) -> dict[str, object]:
        settings: dict[str, object] = {
            HELPER_SETTINGS_BASE_LENGTH_KEY: HELPER_DEFAULT_SETTINGS[HELPER_SETTINGS_BASE_LENGTH_KEY],
            HELPER_SETTINGS_BOTTOM_EXTRA_KEY: HELPER_DEFAULT_SETTINGS[HELPER_SETTINGS_BOTTOM_EXTRA_KEY],
            HELPER_SETTINGS_SELECTED_TEXT_KEY: HELPER_PRESET_PREVIEW_TEXT,
        }
        if not isinstance(raw, dict):
            return settings

        for key, default_value in HELPER_DEFAULT_SETTINGS.items():
            value = raw.get(key, default_value)
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = default_value

            if key == HELPER_SETTINGS_BASE_LENGTH_KEY:
                settings[key] = max(1, parsed)
            else:
                settings[key] = parsed

        selected_text = str(raw.get(HELPER_SETTINGS_SELECTED_TEXT_KEY, HELPER_PRESET_PREVIEW_TEXT) or "").strip()
        settings[HELPER_SETTINGS_SELECTED_TEXT_KEY] = selected_text or HELPER_PRESET_PREVIEW_TEXT
        return settings

    def set_draft(self, user_input, draft: HelperDraft) -> None:
        user_input.state.update_process_payload(
            self._key(),
            **{
                HELPER_PAYLOAD_TEXT_KEY: draft.text,
                HELPER_PAYLOAD_URL_KEY: draft.url,
                HELPER_PAYLOAD_TOP_WIDTH_KEY: draft.top_width,
                HELPER_PAYLOAD_BOTTOM_WIDTH_KEY: draft.bottom_width,
                HELPER_PAYLOAD_MODE_KEY: draft.mode,
            },
        )

    def restart(self, user_input) -> None:
        key = self._key()
        state = user_input.state

        state.clear_process_state(key)
        state.set_active_process(key)
        state.set_step_key(key, HELPER_STEP_ASK_BUNDLE)

    def update_field(self, user_input, *, field_name: str, value: object) -> HelperDraft:
        draft = self.get_draft(user_input)

        if field_name == HELPER_TEXT_KEY:
            draft = HelperDraft(
                text=str(value),
                url=draft.url,
                top_width=draft.top_width,
                bottom_width=draft.bottom_width,
                mode=draft.mode,
            )
        elif field_name == HELPER_URL_KEY:
            draft = HelperDraft(
                text=draft.text,
                url=str(value),
                top_width=draft.top_width,
                bottom_width=draft.bottom_width,
                mode=draft.mode,
            )
        elif field_name == HELPER_WIDTH_KEY:
            width = int(value)
            draft = HelperDraft(
                text=draft.text,
                url=draft.url,
                top_width=width,
                bottom_width=width,
                mode=HELPER_MODE_BOTH,
            )
        else:
            raise KeyError(f"Unknown helper field: {field_name}")

        self.set_draft(user_input, draft)
        return draft

    def set_mode(self, user_input, mode: str) -> HelperDraft:
        draft = self.get_draft(user_input)
        if mode not in (HELPER_MODE_BOTH, HELPER_MODE_TOP, HELPER_MODE_BOTTOM):
            return draft

        updated = HelperDraft(
            text=draft.text,
            url=draft.url,
            top_width=draft.top_width,
            bottom_width=draft.bottom_width,
            mode=mode,
        )
        self.set_draft(user_input, updated)
        return updated

    def adjust_width(self, user_input, delta: int) -> HelperDraft:
        draft = self.get_draft(user_input)

        top_width = draft.top_width
        bottom_width = draft.bottom_width

        if draft.mode in (HELPER_MODE_BOTH, HELPER_MODE_TOP):
            top_width = max(0, top_width + delta)

        if draft.mode in (HELPER_MODE_BOTH, HELPER_MODE_BOTTOM):
            bottom_width = max(1, bottom_width + delta)

        updated = HelperDraft(
            text=draft.text,
            url=draft.url,
            top_width=top_width,
            bottom_width=bottom_width,
            mode=draft.mode,
        )
        self.set_draft(user_input, updated)
        return updated

    def adjust_preset_settings(self, user_input, delta: int) -> dict[str, object]:
        settings = self.get_settings(user_input)
        mode = self.get_preset_edit_mode(user_input)

        base_length = int(settings[HELPER_SETTINGS_BASE_LENGTH_KEY])
        bottom_compensation = int(settings[HELPER_SETTINGS_BOTTOM_EXTRA_KEY])

        if mode == HELPER_PRESET_EDIT_MODE_LENGTH:
            base_length = max(1, base_length + delta)
        if mode == HELPER_PRESET_EDIT_MODE_BOTTOM:
            bottom_compensation = bottom_compensation + delta

        return self.set_settings(
            user_input,
            {
                HELPER_SETTINGS_BASE_LENGTH_KEY: base_length,
                HELPER_SETTINGS_BOTTOM_EXTRA_KEY: bottom_compensation,
                HELPER_SETTINGS_SELECTED_TEXT_KEY: settings[HELPER_SETTINGS_SELECTED_TEXT_KEY],
            },
        )

    def apply_preset_settings(
        self,
        user_input,
        *,
        text: str,
        base_length: int,
        bottom_extra_symbols: int,
        preset_id: int | None = None,
    ) -> dict[str, object]:
        if preset_id is not None:
            self.set_active_preset_id(user_input, preset_id)

        return self.set_settings(
            user_input,
            {
                HELPER_SETTINGS_BASE_LENGTH_KEY: base_length,
                HELPER_SETTINGS_BOTTOM_EXTRA_KEY: bottom_extra_symbols,
                HELPER_SETTINGS_SELECTED_TEXT_KEY: text,
            },
        )

    def build_preset_preview_text(self, user_input) -> str:
        settings = self.get_settings(user_input)
        draft = self.build_draft_from_bundle(
            user_input,
            text=str(settings[HELPER_SETTINGS_SELECTED_TEXT_KEY]),
            url=HELPER_PRESET_PREVIEW_URL,
            width=None,
        )
        preview = self.build_result_text(draft)
        return "\n".join(f"{line}|" for line in preview.splitlines())

    def build_result_text(self, obj: HelperDraft) -> str:
        return self._build_link_block(obj, filler_char=HELPER_FILLER_CHAR)

    def _build_link_block(self, obj: HelperDraft, *, filler_char: str) -> str:
        label = normalize_required_str(obj.text, field_name="text")
        href = normalize_required_str(obj.url, field_name="url")

        top_width = max(0, int(obj.top_width))
        bottom_width = max(1, int(obj.bottom_width))

        first_line = label + (filler_char * top_width)
        second_line = filler_char * bottom_width

        return "\n".join(
            (
                html_link(first_line, href),
                html_link(second_line, href),
            )
        )

    def build_width_preview_text(self, obj: HelperDraft) -> str:
        preview = self._build_link_block(obj, filler_char=HELPER_FILLER_CHAR)
        return "\n".join(f"{line}|" for line in preview.splitlines())

    def build_width_keyboard_layout(self, obj: HelperDraft) -> list[list[ButtonRef]]:
        mark_both = "☑" if obj.mode == HELPER_MODE_BOTH else "☐"
        mark_top = "☑" if obj.mode == HELPER_MODE_TOP else "☐"
        mark_bottom = "☑" if obj.mode == HELPER_MODE_BOTTOM else "☐"

        return [
            [
                ButtonRef(key="helper_width_mode_bottom", vars={"mark": mark_bottom}),
                ButtonRef(key="helper_width_mode_both", vars={"mark": mark_both}),
                ButtonRef(key="helper_width_mode_top", vars={"mark": mark_top}),
            ],
            [
                ButtonRef(key="helper_width_delta_-3"),
                ButtonRef(key="helper_width_delta_-2"),
                ButtonRef(key="helper_width_delta_-1"),
                ButtonRef(key="helper_width_delta_+1"),
                ButtonRef(key="helper_width_delta_+2"),
                ButtonRef(key="helper_width_delta_+3"),
            ],
            [
                ButtonRef(key="helper_width_delta_-5"),
                ButtonRef(key="helper_width_delta_-10"),
                ButtonRef(key="helper_width_delta_-15"),
                ButtonRef(key="helper_width_delta_+5"),
                ButtonRef(key="helper_width_delta_+10"),
                ButtonRef(key="helper_width_delta_+15"),
            ],
            [
                ButtonRef(key="helper_width_back"),
            ],
        ]
