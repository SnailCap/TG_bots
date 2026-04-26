from __future__ import annotations

from core.runtime.builders.bot_runtime_builder import BotRuntimeBuilder
from core.runtime.builders.built_runtime import BuiltRuntime
from core.services.identity.provider import DbIdentityProvider

from pipubot.routing.helper_start_page_resolver import HelperStartPageResolver
from pipubot.runtime.ensure_tables_plugin import EnsureTablesPlugin
from pipubot.runtime.helper_preset_schema_plugin import HelperPresetSchemaPlugin
from pipubot.runtime.pipubot_runtime_setup import (
    build_pipubot_config,
    build_pipubot_services,
)


def build_helper_runtime() -> BuiltRuntime:
    config = build_pipubot_config(file=__file__)

    return (
        BotRuntimeBuilder(config)
        .with_ptb()
        .with_standard_interaction(start_page_resolver=HelperStartPageResolver())
        .with_db()
        .with_plugin(
            EnsureTablesPlugin(
                import_modules=(
                    "core.db.models",
                    "pipubot.domains.tutoring.models",
                    "pipubot.domains.helper.models",
                )
            )
        )
        .with_plugin(HelperPresetSchemaPlugin())
        .with_ui_bindings(
            "pipubot.ui.components.pages.helper",
            "pipubot.ui.components.processes.helper",
        )
        .with_identity(DbIdentityProvider())
        .extend_services(lambda base: build_pipubot_services(base, config=config))
        .with_runtime_services()
        .with_dispatcher()
        .build()
    )
