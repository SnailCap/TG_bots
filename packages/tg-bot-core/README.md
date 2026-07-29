# tg-bot-core 3.0

`tg-bot-core` — runtime и public custom-code SDK для автономных Telegram Bot Studio projects с `schema_version: 3`. Runtime читает декларативный application graph из `resources/`; пользовательский Python-код содержит handlers и services, но не регистрирует flows или transitions вручную.

Schema v2 намеренно не поддерживается. `FlowDefinition`, `FlowState`, public `Transition` и registry-объект `BotModule` не входят в v3 API.

## Установка

Поддерживается Python `>=3.12,<3.14`.

Из checkout репозитория:

```bash
python -m pip install -e "packages/tg-bot-core[dev]"
```

Сгенерированный Studio project содержит собственный `pyproject.toml`, который pin-ит core на release tag. Устанавливайте зависимости уже из папки такого проекта через `python -m pip install -e ".[dev]"`.

## Что делает core

- Загружает и валидирует manifest, views/templates, optional structured content, flows, commands, handlers и schedules через общий `tg_bot_core.project`.
- Компилирует rich content в Telegram `text + entities` с UTF-16 offsets и безопасным splitting.
- До начала polling проверяет весь graph и импортирует explicit handler bindings.
- Преобразует Telegram text/command/callback updates в typed events через PTB polling adapter.
- Выполняет built-in actions, flow lifecycle и declarative outcome routing.
- Передаёт custom-коду ограниченные typed contexts и проверяет `HandlerResult`.
- Сохраняет sessions, update deduplication, schedules, durable jobs и run history в SQLite.
- Управляет service lifecycle и корректной остановкой runtime-компонентов.

Studio не нужен ни одному из этих шагов.

## Минимальный проект

```text
my-bot/
├─ resources/
│  ├─ bot.json
│  ├─ handlers.json
│  ├─ commands.json
│  ├─ views/
│  ├─ content/                  # optional rich content JSON
│  ├─ flows/
│  ├─ schedules/
│  └─ templates/
├─ src/my_bot/
│  ├─ __init__.py
│  ├─ __main__.py
│  ├─ handlers/
│  └─ services/
├─ data/
├─ tests/
├─ pyproject.toml
└─ Dockerfile
```

Полный JSON contract описан в [project-schema-v3.md](../../docs/architecture/project-schema-v3.md), а independent content schema — в [Content Editor guide](../../docs/studio/content-editor.md).

## Public Content Engine

`tg_bot_core.content` предоставляет immutable document models и функции `parse_content_document`, `content_document_to_dict`, `normalize_content_document`, `validate_content_document`, `import_legacy_template`, `serialize_legacy_template`, `compile_content_document`, `compile_result_to_dict`, `import_telegram_message` и UTF-16 helpers. Content document имеет собственный `schemaVersion: 1`; optional `view.text.document` остаётся additive частью project schema v3.

Runtime использует structured document при наличии ссылки, иначе сохраняет прежний inline/template Jinja path. Compiler возвращает один или несколько messages с entities, warnings и errors. Telegram import принимает entity offsets в UTF-16 units. Подробности формата, compatibility projection и extension checklist находятся в [Content Editor guide](../../docs/studio/content-editor.md).

## Entrypoint

Application graph не собирается в Python. Entrypoint только задаёт runtime config, services и при необходимости custom transport:

```python
from pathlib import Path

from tg_bot_core import BotApp, BotConfig


root = Path(__file__).resolve().parents[2]
app = BotApp(
    config=BotConfig.from_env(project_root=root),
    services=[],
)
app.run()
```

`BotConfig.from_env()` сначала читает `BOT_TOKEN` из окружения, а при его отсутствии — из локального `<project>/.env`; SQLite по умолчанию размещается в `<project>/data/runtime.sqlite3`. Число in-process job workers и предел автоматических переходов задаются аргументами `worker_count` и `max_auto_transitions`. Если передан custom `BotTransport`, token не обязателен.

## Explicit handler binding

Runtime не сканирует package и не использует decorators. Каждый handler объявляется в `resources/handlers.json`:

```json
{
  "schema_version": 3,
  "handlers": [
    {
      "id": "checkout.submit",
      "module": "my_bot.handlers.checkout.submit",
      "symbol": "handle",
      "kind": "button",
      "outcomes": ["invalid"]
    }
  ]
}
```

Module обязан находиться внутри package из `bot.json`. Runtime кеширует успешно разрешённую async-функцию; hot reload во время процесса не реализован.

## Public handler SDK

```python
from tg_bot_core import ButtonContext, HandlerResult


async def handle(ctx: ButtonContext) -> HandlerResult:
    order = await ctx.services["orders"].submit(user_id=ctx.user.id)
    if order is None:
        return HandlerResult.outcome("invalid")

    ctx.state.set("order_id", order.id)
    return HandlerResult.success(values={"total": order.total})
```

Interactive contexts содержат `user`, `chat`, typed `event`, immutable payload mapping, управляемый `state`, services mapping и logger:

| Handler kind | Context | Точка вызова |
| --- | --- | --- |
| `button` | `ButtonContext` | `handler.invoke` у кнопки или named state event |
| `message` | `MessageContext` | active state `on_message` или global message fallback |
| `command` | `CommandContext` | зарегистрированная команда или command fallback |
| `lifecycle` | `LifecycleContext` | flow hooks и state `on_enter` |
| `task` | `TaskContext` | schedule или `task.enqueue` |

`TaskContext` намеренно содержит только `job_id`, `payload`, `services` и `logger`; у background job нет Telegram actor/session state.

`HandlerResult.success()` означает стандартный outcome `success`. Дополнительные outcome names нужно объявить в binding и сопоставить actions во всех местах вызова. Values из `ctx.state` и `HandlerResult.values` сохраняются в session; при одинаковом ключе значение из result имеет приоритет. Все values должны быть JSON-serializable.

Handler не получает `BotApp`, store, transport или API переходов. Flow/view/task semantics задаёт project schema.

## Services

Services передаются явно через `ServiceProvider` и становятся доступны по ключу в `ctx.services`:

```python
from tg_bot_core import BotApp, BotConfig, ServiceProvider


async def create_orders(container):
    return OrdersClient()


app = BotApp(
    config=BotConfig.from_env(project_root=root),
    services=[ServiceProvider("orders", create_orders)],
)
```

Provider может вернуть обычный объект, awaitable или async context manager. Для cleanup можно передать explicit disposer; без него container использует `aclose()` или `close()`, если метод существует. Services создаются по порядку и закрываются в обратном порядке.

## Validation и запуск

Из установленного project:

```bash
python -m tg_bot_core validate .
python -m my_bot --validate
BOT_TOKEN="<telegram-token>" python -m my_bot
```

Оба validate-варианта starter проверяют resources, cross-references и AST/signatures handler files. Startup повторяет validation и дополнительно импортирует bindings до запуска PTB polling.

## Runtime semantics

- `/start` выполняет manifest policy `reset` или `resume`.
- Остальные commands, callbacks и messages имеют документированный раздельный dispatch.
- `on_enter` выполняется только при фактическом входе в state; простой re-render его не вызывает.
- `finished`, `cancelled` и `failed` — разные session statuses с разными lifecycle hooks.
- Session update использует optimistic revision; при conflict есть одна повторная попытка после reload session.
- Callback data содержит только `v3:a:<button-id>` и ограничивается 64 bytes.
- Structured view может дать несколько Telegram messages; keyboard прикрепляется только к последнему.
- Durable jobs используют claim, lease renewal, bounded exponential retries и run history.

Подробности: [runtime-dispatch.md](../../docs/architecture/runtime-dispatch.md).

## Ограничения текущей версии

- PTB adapter работает через polling и принимает только text messages, commands и callbacks.
- Из schedule triggers реализован только `interval`; `cron` и `once` пока отклоняются validator.
- Legacy inline/template Jinja рендерится с `StrictUndefined`, без autoescape; structured content передаёт PTB готовые entities без неявного parse mode.
- Custom code исполняется в процессе бота без sandbox и hot reload.
- Update помечается processed до dispatch, а session save и `task.enqueue` не объединены одной транзакцией; детали рисков перечислены в runtime documentation.
- Для production рекомендуется один process на project SQLite database; несколько worker coroutines внутри process поддерживаются.

## Тесты

Из корня репозитория:

```powershell
$env:PYTHONPATH = (Resolve-Path '.\packages\tg-bot-core\src').Path
.\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests
```
