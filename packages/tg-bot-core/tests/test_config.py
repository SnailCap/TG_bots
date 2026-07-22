from __future__ import annotations

from tg_bot_core import BotConfig


def test_config_reads_project_dotenv_without_overriding_process_environment(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / ".env").write_text("OTHER=value\nBOT_TOKEN=from-project-env\n", encoding="utf-8")
    monkeypatch.delenv("BOT_TOKEN", raising=False)

    configured = BotConfig.from_env(project_root=tmp_path)

    assert configured.token == "from-project-env"

    monkeypatch.setenv("BOT_TOKEN", "from-process-env")
    assert BotConfig.from_env(project_root=tmp_path).token == "from-process-env"
