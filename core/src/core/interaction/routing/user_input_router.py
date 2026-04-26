from __future__ import annotations

from core.interaction.contracts.start_page_resolver import StartPageResolver
from core.interaction.contracts.ui_builder import UiBuilder
from core.interaction.logging.user_data_logger import UserDataLogger
from core.interaction.routing.start_page_resolver import DefaultStartPageResolver
from core.interaction.runtime.context import NavKind, ServiceKind, UserInput
from core.interaction.ui import Page
from core.interaction.ui import ProcessCoordinator
from core.interaction.ui import ProcessEffect
from core.interaction.ui import get_default_ui_registry


class UnknownProcessKey(RuntimeError):
    pass


class UserInputRouter:
    def __init__(self, *, ui: UiBuilder, start_page: StartPageResolver | None = None):
        self._ui = ui
        self._start_page = start_page or DefaultStartPageResolver()
        self._process_coordinator = ProcessCoordinator(ui)

    async def handle_input(self, user_input: UserInput) -> None:
        async with UserDataLogger(user_input):
            # 1) Commands: reset the flow and open the start page
            if user_input.message.is_command:
                await self._handle_command(user_input)
                return

            # 2) Service callbacks: NAV / PRC control
            if user_input.callback_input.is_service:
                await self._handle_service_callback(user_input)
                return

            # 3) Any non-service input: an active process has priority
            if user_input.state.has_active_process():
                await self._handle_active_process(user_input)
                return

            # 4) Otherwise route to the current page
            await self._route_input_to_current_page(user_input)

    # -----------------------------
    # Commands
    # -----------------------------

    async def _handle_command(self, user_input: UserInput) -> None:
        user_input.state.cancel_current_process()
        await self._open_start_page(user_input, with_send=True)

    # -----------------------------
    # Active process
    # -----------------------------

    async def _handle_active_process(self, user_input: UserInput) -> None:
        ended = await self._process_coordinator.handle(user_input)
        if ended:
            await self._open_current_or_start_page(user_input)

    # -----------------------------
    # Service callbacks
    # -----------------------------

    async def _handle_service_callback(self, user_input: UserInput) -> None:
        service_kind = user_input.callback_input.service_kind

        if service_kind == ServiceKind.NAV and user_input.state.has_active_process():
            user_input.state.cancel_current_process()

        match service_kind:
            case ServiceKind.NAV:
                await self._handle_nav_callback(user_input)

            case ServiceKind.PRC_START:
                await self._start_process(user_input, user_input.callback_input.process.key)

            case ServiceKind.PRC_CMD:
                if user_input.state.has_active_process():
                    await self._handle_active_process(user_input)
                else:
                    await self._open_start_page(user_input)

            case ServiceKind.NONE:
                if user_input.state.has_active_process():
                    await self._handle_active_process(user_input)
                else:
                    await self._open_current_or_start_page(user_input)

    async def _handle_nav_callback(self, user_input: UserInput) -> None:
        nav = user_input.callback_input.nav

        match nav.kind:
            case NavKind.PREVIOUS:
                await self._open_previous_page(user_input)
                return

            case NavKind.CURRENT:
                await self._open_current_or_start_page(user_input)
                return

            case NavKind.HOME:
                await self._open_start_page(user_input)
                return

            case NavKind.TARGET:
                if nav.target:
                    await self._open_page(user_input, nav.target, push_history=True)
                    return

        await self._open_current_or_start_page(user_input)

    # -----------------------------
    # Processes
    # -----------------------------

    async def _start_process(self, user_input: UserInput, proc_key: str | None) -> None:
        if not proc_key:
            await self._open_start_page(user_input)
            return

        if user_input.state.has_active_process():
            user_input.state.cancel_current_process()

        try:
            proc = self._resolve_process(proc_key)
        except UnknownProcessKey:
            await self._open_start_page(user_input)
            return

        effects = await proc.start(user_input)
        await self._apply_process_effects(user_input, effects)

        if not user_input.state.has_active_process():
            await self._open_current_or_start_page(user_input)

    def _resolve_process(self, key: str):
        cls = get_default_ui_registry().get("process", key)
        if cls is None:
            available = sorted(get_default_ui_registry().all("process").keys())
            raise UnknownProcessKey(f"Unknown process key: '{key}'. Available: {available}")
        return cls()

    async def _apply_process_effects(self, user_input: UserInput, effects: list[ProcessEffect]) -> None:
        await self._process_coordinator.apply_effects(user_input, effects)

    # -----------------------------
    # Page routing/opening
    # -----------------------------

    async def _route_input_to_current_page(self, user_input: UserInput) -> None:
        current_page_name = user_input.state.get_current_page()
        if not current_page_name:
            await self._open_start_page(user_input, with_send=user_input.message.with_send_default)
            return

        page: Page = self._ui.build_page(current_page_name)
        await page.handle_input(user_input)

    async def _open_current_or_start_page(self, user_input: UserInput) -> None:
        current = user_input.state.get_current_page()
        if current:
            await self._open_page(
                user_input,
                current,
                with_send=user_input.message.with_send_default,
                push_history=False,
            )
        else:
            await self._open_start_page(user_input)

    async def _open_page(
        self,
        user_input: UserInput,
        page_name: str,
        *,
        with_send: bool | None = None,
        push_history: bool = True,
    ) -> bool:
        if with_send is None:
            with_send = user_input.message.with_send_default

        page: Page = self._ui.build_page(page_name)

        user_input.state.set_current_page(page_name)
        if push_history:
            user_input.state.push_page_to_history(page_name)

        await page.render(user_input, with_send=with_send)
        return True

    async def _open_previous_page(self, user_input: UserInput) -> None:
        history = user_input.state.get_page_history()
        if len(history) < 2:
            await self._open_start_page(user_input)
            return

        user_input.state.pop_last_page()

        history = user_input.state.get_page_history()
        if not history:
            user_input.state.reset_current_page()
            await self._open_start_page(user_input)
            return

        target = history[-1]
        await self._open_page(user_input, target, with_send=False, push_history=False)

    async def _open_start_page(self, user_input: UserInput, *, with_send: bool | None = None) -> None:
        await self._open_page(
            user_input,
            self._start_page.resolve(user_input),
            with_send=with_send,
            push_history=True,
        )