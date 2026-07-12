# Telegram Bot Studio / tg-bot-core v2

`tg-bot-core` 2.0 is an explicit, SQLite-first runtime for Telegram bots. Its
source lives in `packages/tg-bot-core/` and its Python import is `tg_bot_core`.
Bots declare a `BotModule` with flows, services, task handlers and schedules;
there are no plugins, decorator discovery, global registries, or legacy
`Page`/`Step`/`Process` runtime APIs.

Telegram Bot Studio is the local desktop editor for the v2 resource format. It
edits deployable files only: `resources/bot.json`, `resources/views/*.json` and
`resources/templates/*.txt`. A generated project runs independently of Studio.
`pipubot/` is left untouched as a legacy fixture and is not a v2 project.

Полное руководство по структуре ресурсов, flows, jobs и migration map:
[packages/tg-bot-core/README.md](packages/tg-bot-core/README.md).

## Quick start (Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
.\.venv\Scripts\python.exe -m pip install -e ".\packages\tg-bot-core[dev]"

Set-Location .\frontend
npm.cmd install
npm.cmd run dev
```

`npm.cmd run dev` opens Electron and starts the local backend at
`http://127.0.0.1:8000`. Use **Open project** for a v2 project or **Create v2
starter** for a standalone bot with a `home` view. To choose a different
interpreter, set `BOT_STUDIO_PYTHON` before starting the frontend.

The public bot entrypoint is deliberately small:

```python
app = BotApp(config=BotConfig.from_env(), module=module)
app.run()
```

Generated projects pin `tg-bot-core` to the Git `core-v2.0.0` tag. Create and
push that tag after committing this release before installing a generated
project on another machine or host.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests .\backend

Set-Location .\frontend
npm.cmd test
npm.cmd run build
```
