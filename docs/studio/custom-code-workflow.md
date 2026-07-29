# Custom code в Studio

Studio реализует Unity-подобную модель: пользователь выбирает декларативную точку входа, создаёт handler, получает готовый typed Python stub и дальше редактирует только его бизнес-логику во внешней IDE. Runtime infrastructure и переходы остаются под контролем core/resources.

## Реализованные точки входа

| Сценарий в Studio/schema | Handler kind | Context | Когда вызывается |
| --- | --- | --- | --- |
| Button action `handler.invoke` | `button` | `ButtonContext` | Нажатие конкретной inline-кнопки |
| Button `flow.event` → state named event | `button` | `ButtonContext` | Нажатие кнопки, пока активен state с таким event |
| Registered command action `handler.invoke` | `command` | `CommandContext` | Ввод конкретной `/command` |
| Global command fallback | `command` | `CommandContext` | Неизвестная команда, кроме встроенной `/start` |
| State `on_message` | `message` | `MessageContext` | Обычный текст в конкретном active state |
| Global message fallback | `message` | `MessageContext` | Обычный текст, когда active state не имеет `on_message` |
| State `on_enter` | `lifecycle` | `LifecycleContext` | Фактический вход в state |
| Flow `on_start` | `lifecycle` | `LifecycleContext` | Новый запуск flow, не resume/re-render |
| Flow `on_complete` | `lifecycle` | `LifecycleContext` | `flow.finish` |
| Flow `on_cancel` | `lifecycle` | `LifecycleContext` | `flow.cancel` |
| Flow `on_error` | `lifecycle` | `LifecycleContext` | Ошибка custom handler, outcome/transition guard или рендера view в active flow |
| Resource schedule | `task` | `TaskContext` | Наступил interval schedule |
| Built-in `task.enqueue` | `task` | `TaskContext` | Action поставила one-off durable job |

Это фактический набор v3. Сейчас нет generic custom hooks «при старте/остановке процесса», «до/после любого update», «после отправки сообщения» или handlers для media/location/member updates. Не путайте `flow.on_start` с запуском process: hook относится к одной user/chat flow session. Инициализацию/cleanup внешних клиентов нужно делать через `ServiceProvider`, а не lifecycle handler.

## Создание handler из точки входа

1. Создайте или откройте view, flow, commands либо schedule.
2. Выберите `Custom handler` или соответствующий hook/event slot.
3. Задайте stable handler ID. Для scaffold используйте dot-separated segments, начинающиеся с ASCII letter, например `checkout.submit_order`.
4. Настройте outcome routes в Studio. Stored route `success` обязателен; при attach без явно заданной route scaffolder добавляет `success → noop`. Дополнительные names должны иметь route и попадут в binding `outcomes`.
5. Нажмите **Create handler**. Backend проверит kind и registry revision, построит path внутри project package и создаст binding/package initializers/file.
6. Если resource уже сохранён и editor не dirty, backend по target revision атомарно запишет также reference. Если в editor есть draft, Studio намеренно создаст binding/file без backend attachment: typed reference останется в draft и попадёт в resource при обычном **Save**.
7. Внутри той же transaction backend запускает full project validation с AST inspection. После успеха frontend обновит validation и попросит Electron открыть source file во внешней IDE.

Для существующей binding используется **Open code**. **Find usages** показывает references из views, flows/hooks/states/events, commands/fallbacks, schedules и вложенных outcome actions.

Отдельный пункт **New handler** создаёт пока не привязанную binding/file; status будет Ready с признаком Unused. Её можно позднее выбрать в compatible slot.

## Что именно записывается

Для ID `checkout.submit_order` и package `my_bot` Studio использует:

```text
src/my_bot/handlers/checkout/submit_order.py
```

и binding:

```json
{
  "id": "checkout.submit_order",
  "module": "my_bot.handlers.checkout.submit_order",
  "symbol": "handle",
  "kind": "button",
  "outcomes": ["invalid_order"]
}
```

Generated source зависит от kind:

```python
from tg_bot_core import ButtonContext, HandlerResult


async def handle(ctx: ButtonContext) -> HandlerResult:
    """Handle `checkout.submit_order`."""
    return HandlerResult.success()
```

Для остальных kinds импортируется `MessageContext`, `CommandContext`, `LifecycleContext` или `TaskContext`.

## Гарантия сохранности пользовательского кода

File создаётся exclusive operation. Если такой path уже существует, Studio не меняет ни одной строки и может переиспользовать его только когда full validation/AST inspection подтверждают совместимую функцию. Невалидный существующий source приводит к rollback новой binding/reference. Registry/reference writes выполняются под workspace lock с revision checks; при exception backend восстанавливает изменённые resources и удаляет только файлы/`__init__.py`, которые успел создать сам.

После временной записи scaffolder повторно загружает project и запускает full graph validation вместе с AST inspection. При любой error diagnostic он откатывает registry/reference и удаляет только созданный им source; поэтому существующие несвязанные ошибки project тоже нужно исправить до scaffolding. Validation panel и отдельный endpoint показывают те же authoritative diagnostics после операции.

Studio не вставляет функцию в общий модуль, не форматирует source и не regenerates тело при изменении binding.

## Context: доступный кодом контекст

Interactive contexts дают:

```text
ctx.user       UserInfo(id, username, first_name, last_name)
ctx.chat       ChatInfo(id)
ctx.event      typed CallbackEvent / MessageEvent / CommandEvent / LifecycleEvent
ctx.payload    action payload; у on_error также содержит error text
ctx.state      controlled StateValues
ctx.services   mapping явно зарегистрированных project services
ctx.logger     logger данного handler
```

Пример:

```python
from tg_bot_core import MessageContext, HandlerResult


async def handle(ctx: MessageContext) -> HandlerResult:
    value = ctx.event.text.strip()
    if not value:
        return HandlerResult.outcome("invalid")

    ctx.state.set("customer_name", value)
    return HandlerResult.success(values={"name_length": len(value)})
```

`ctx.state.get/set/delete/snapshot` работает с draft session values. `HandlerResult.values` объединяется с draft и выигрывает при совпадении ключа. Значения обязаны сериализоваться в JSON.

Rich Text Content Editor не расширяет public handler context и не даёт handler raw send API. Его variable picker переиспользует общий Studio context catalog, а runtime разрешает сохранённые dotted paths из того же session/user mapping. Поэтому handler передаёт данные через `ctx.state` или `HandlerResult.values`, после чего декларативный view компилирует текст и Telegram entities. `variableReference.source` нужен только для lossless legacy round-trip и не выполняется как произвольный Jinja expression. Подробности — в [Content Editor guide](content-editor.md#variables-и-jinja).

`TaskContext` отличается: у background job есть только `job_id`, `payload`, `services`, `logger`; нет user/chat/event/session state.

Context намеренно не раскрывает `BotApp`, dispatcher, raw SQLite store, transport или переходы.

## Outcomes, а не transitions

Handler сообщает результат бизнес-операции:

```python
if access_denied:
    return HandlerResult.outcome("access_denied")
return HandlerResult.success(values={"order_id": order.id})
```

А Studio сохраняет routing:

```json
{
  "handler": "checkout.submit_order",
  "outcomes": {
    "success": {"type": "flow.finish", "view": "checkout_done"},
    "access_denied": {"type": "view.render", "target": "access_denied"}
  }
}
```

Так application graph виден Studio и validator. Handler не может через public SDK выполнить `goto`, `render`, `finish` или raw send. Escape hatch для произвольных transitions в первой версии отсутствует.

Task handlers всегда возвращают `HandlerResult.success()`; task outcome routing не поддерживается.

## Services и собственные modules

Общий код размещайте в `src/<package>/services/` либо других modules package и импортируйте из handler обычным Python import. Studio не управляет произвольными dependencies или service bootstrap.

Services регистрируются вручную в маленьком project entrypoint:

```python
from pathlib import Path

from tg_bot_core import BotApp, BotConfig, ServiceProvider

from my_bot.services.orders import OrdersClient


async def create_orders(container):
    return OrdersClient()


root = Path(__file__).resolve().parents[2]
BotApp(
    config=BotConfig.from_env(project_root=root),
    services=[ServiceProvider("orders", create_orders)],
).run()
```

В handler service доступен как `ctx.services["orders"]`. Provider может иметь explicit disposer или вернуть async context manager; runtime закрывает services в обратном порядке.

## Open code

Electron canonicalizes project root и file path, требует существующий `.py` строго внутри schema v3 project, который пользователь предварительно разрешил через native directory picker, и запускает IDE без shell interpolation.

Текущий UI использует настройки process environment:

```text
BOT_STUDIO_IDE=vscode     # default; executable default: code, поддерживает line/column
BOT_STUDIO_IDE=system     # explicit opt-in к OS association
BOT_STUDIO_IDE=jetbrains  # нужен BOT_STUDIO_IDE_EXECUTABLE
BOT_STUDIO_IDE=custom     # нужен BOT_STUDIO_IDE_EXECUTABLE, получает file path одним argument
```

VS Code получает `--goto file:line:column`, JetBrains — `--line N file`. Произвольный command template frontend передать не может. В browser-only режиме `Open code` недоступен: нужен desktop Electron preload.

## Status и validation

Inspector различает:

- Ready;
- Missing file;
- Missing symbol;
- Invalid signature;
- Invalid module;
- Unused (в UI отображается как признак у Ready).

Проверяются top-level async symbol, один annotated context argument и return annotation `HandlerResult`. Полный validator дополнительно проверяет kind/reference/outcomes и показывает diagnostics с source/entity/field. Runtime startup повторяет проверку и реально импортирует все modules.

Перед commit/deploy:

```bash
python -m tg_bot_core validate .
python -m <package> --validate
pytest
```

## Deployment без Studio

Все bindings, content documents, templates и source files находятся в bot project. После commit/copy на VPS устанавливается только сам project и pinned `tg-bot-core`; `backend/`, `frontend/` и Electron не копируются. См. [VPS guide](../deployment/vps.md).
