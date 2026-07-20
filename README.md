# Telegram Bot Studio

Telegram Bot Studio — локальный Electron/React-редактор автономных Python-ботов для Telegram. Studio создаёт и изменяет файлы проекта schema v3, помогает связать визуальные сущности с custom Python handlers и открыть их во внешней IDE. Во время работы самого бота Studio не участвует.

`tg-bot-core` — отдельный runtime-пакет из `packages/tg-bot-core/`. Он загружает project resources, валидирует application graph, маршрутизирует Telegram events, вызывает явно привязанные handlers и хранит sessions/jobs в SQLite.

Главный инвариант: созданная папка бота является самостоятельным deployable-проектом. Её можно передать через Git или скопировать на VPS, установить зависимости и запустить без `backend/`, `frontend/` и Electron.

## Архитектурные границы

- `resources/` — источник истины для views, flows/states, lifecycle hooks, commands/fallbacks, button actions, handler bindings, outcome routes и schedules.
- Custom handler возвращает `HandlerResult`; следующий view/state/task выбирает декларативная action/outcome route, а не Python handler.
- Handler разрешается только через запись в `resources/handlers.json`: decorators, import scanning и mutable registries не используются.
- Studio создаёт файл handler один раз и не переписывает существующий пользовательский код.
- Backend Studio и runtime используют общий loader/validator из `tg_bot_core.project`.
- Актуальная и единственная поддерживаемая версия project format — `schema_version: 3`; v2 compatibility layer отсутствует.

## Быстрый запуск Studio

Нужны Python 3.12 или 3.13 и Node.js/npm. Из корня репозитория в PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\packages\tg-bot-core[dev]"
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"

Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

В development-режиме Electron запускает локальный backend на `http://127.0.0.1:8000`. Интерпретатор можно задать через `BOT_STUDIO_PYTHON`; backend directory — через `BOT_STUDIO_BACKEND_DIR`. Для внешней IDE используются `BOT_STUDIO_IDE=system|vscode|jetbrains|custom` и, когда требуется, `BOT_STUDIO_IDE_EXECUTABLE`.

В Studio выберите **Create project** для нового schema v3 starter либо **Open project** для существующей папки. Созданный starter уже содержит resources, entrypoint, тест, `pyproject.toml`, `Dockerfile` и каталог persistent data.

## Быстрый запуск созданного бота

Ниже `my_bot` — Python package, выбранный при создании проекта:

```bash
cd my-bot
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m tg_bot_core validate .
python -m my_bot --validate
BOT_TOKEN="<telegram-token>" python -m my_bot
```

На Windows токен задаётся, например, через `$env:BOT_TOKEN = "<telegram-token>"`. Runtime сам не читает `.env`: файл нужно загрузить средствами shell/process manager либо экспортировать переменную. Состояние по умолчанию хранится в `data/runtime.sqlite3`.

Starter pin-ит core на Git tag `core-v3.0.0`; удалённая установка возможна только после публикации этого tag. Для production меняйте pin осознанно на протестированный tag или immutable commit.

## Структура репозитория

| Путь | Назначение |
| --- | --- |
| `packages/tg-bot-core/` | schema v3 loader/validator, runtime, SDK, PTB transport и SQLite jobs/sessions |
| `backend/` | локальный FastAPI control plane для файлов проекта и handler scaffolding |
| `frontend/` | Electron + React Studio, typed editors и безопасное открытие Python-файлов |
| `docs/` | архитектура, schema, custom-code workflow, deployment и migration notes |
| `pipubot/` | отдельный legacy fixture; это не schema v3 starter |

## Документация

- [Обзор архитектуры](docs/architecture/overview.md)
- [Project schema v3](docs/architecture/project-schema-v3.md)
- [Runtime dispatch](docs/architecture/runtime-dispatch.md)
- [Работа с custom code в Studio](docs/studio/custom-code-workflow.md)
- [Расширение schema/runtime](docs/development/extending-schema.md)
- [Развёртывание на VPS](docs/deployment/vps.md)
- [Переход с v2](docs/migration/v2-to-v3.md)
- [Руководство по core](packages/tg-bot-core/README.md)

## Проверки

Python:

```powershell
.\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests .\backend
```

Frontend/Electron:

```powershell
Set-Location .\frontend
npm.cmd test
npm.cmd run build
```

`npm.cmd run build` включает TypeScript check (`tsc --noEmit`). Отдельные lint-команды сейчас не настроены.
