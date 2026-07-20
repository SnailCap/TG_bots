# Migration: v2 → v3

Schema v3 — намеренный архитектурный разрыв, а не backward-compatible update. Реальных production projects на v2 в момент рефакторинга не было, поэтому основной runtime не содержит compatibility layer, deprecated aliases или автоматический migrator.

## Что удалено

| v2 concept | v3 replacement |
| --- | --- |
| Python `FlowDefinition` / `FlowState` | `resources/flows/*.json` с states, views, hooks, events и outcome routes |
| Прямые Python function references в flow | Stable handler ID + explicit module/symbol binding в `resources/handlers.json` |
| Handler, возвращающий public `Transition` | `HandlerResult(outcome_name, values)`; route хранится в resources |
| `FlowContext.app` и доступ к internals | Typed `ButtonContext`, `MessageContext`, `CommandContext`, `LifecycleContext`, `TaskContext` |
| `BotModule` как registry flows/tasks/schedules | `BotApp(config=..., services=[...])`; graph/schedules в resources |
| Manual task handler/schedule registration | Общий handler registry kind `task` + `resources/schedules/*.json` |
| Декларации commands вне полного graph | `resources/commands.json`, включая message/command fallbacks |
| Long/semantic callback payload | Core-owned `v3:a:<stable-button-id>` |
| v2 resource parsing/validation | Только `schema_version: 3` через `tg_bot_core.project` |

`Transition` не является public escape hatch v3. Custom handler не выбирает state/view/finish/enqueue; такой выбор виден Studio и validator как action.

Старый tracked package `tg_bot_core/v2` и его public exports удалены; root `tg_bot_core` экспортирует только v3 runtime/SDK.

## Что сохранено по смыслу

- SQLite persisted flow sessions;
- processed update deduplication;
- optimistic revision conflicts;
- durable jobs, leases, renewal, retries и run history;
- transport abstraction и PTB adapter;
- Jinja views/templates;
- explicit, side-effect-free registration principle;
- services как Python infrastructure dependencies.

Реализация и on-disk contract при этом изменились, поэтому «сохранено по смыслу» не означает binary/data compatibility.

## Автоматической миграции нет

`ProjectLoader` требует schema version 3 во всех JSON. V2 project не откроется автоматически ни core, ни Studio v3. В repository нет поддерживаемого one-shot converter.

Не меняйте только число `schema_version`: v3 требует `package`, start flow, `handlers.json`, `commands.json`, directories flows/schedules/templates и целостные cross-references.

## Рекомендуемый ручной путь

1. Создайте чистый v3 starter через Studio. Это даёт корректный entrypoint, package layout, dependency pin, tests и Dockerfile.
2. Перенесите templates и заново опишите views:

   - ровно `inline` или `template`;
   - stable глобальные button IDs;
   - единый v3 action object для каждой кнопки.

3. Перенесите flow graph из Python в `resources/flows/*.json`:

   - initial state и default view каждого state;
   - `on_enter`, `on_message`, named events;
   - `on_start`, `on_complete`, `on_cancel`, `on_error`;
   - explicit action для `success` и каждого named outcome.

4. Разделите custom logic по модели один handler → один module → `async def handle(ctx)`.
5. Добавьте каждый handler в `resources/handlers.json` с правильным kind/context. Studio **Create handler** может сделать binding/source/attachment; существующее тело source она не перезапишет.
6. Замените возврат `Transition`:

   ```python
   # v2 intent: перейти в payment
   return HandlerResult.outcome("payment_required", values={"order_id": order.id})
   ```

   А `payment_required → {"type": "flow.goto", "target": "payment"}` сохраните в flow resource.

7. Перенесите commands и fallbacks в `resources/commands.json`. `/start` не объявляйте: он управляется `bot.json.start`.
8. Перенесите schedules в отдельные files. Сейчас поддержан только positive `interval`; v2 cron-like custom logic нельзя записать как готовый `cron` trigger.
9. Оставьте shared clients/repositories в project `services/` и зарегистрируйте только `ServiceProvider` в entrypoint.
10. Проверьте новый project до запуска:

    ```bash
    python -m tg_bot_core validate .
    python -m <package> --validate
    pytest
    ```

11. Проведите acceptance scenario: `/start`, callback/message/command, каждый outcome, lifecycle error/cancel/finish, background task, остановка/restart и восстановление session.

## Пример преобразования

В v2 routing мог находиться внутри Python:

```python
async def submit(ctx):
    if not await can_submit(ctx):
        return Transition.render("invalid")
    return Transition.goto("payment")
```

V3 handler сообщает только business result:

```python
from tg_bot_core import ButtonContext, HandlerResult


async def handle(ctx: ButtonContext) -> HandlerResult:
    if not await ctx.services["orders"].can_submit(ctx.user.id):
        return HandlerResult.outcome("invalid")
    return HandlerResult.success()
```

Binding:

```json
{
  "id": "checkout.submit",
  "module": "my_bot.handlers.checkout.submit",
  "symbol": "handle",
  "kind": "button",
  "outcomes": ["invalid"]
}
```

Flow event:

```json
{
  "handler": "checkout.submit",
  "outcomes": {
    "success": {"type": "flow.goto", "target": "payment"},
    "invalid": {"type": "view.render", "target": "invalid"}
  }
}
```

## Runtime database

Старую v2 SQLite database не следует подключать к v3 «как есть». Даже при совпадающих table names application IDs, statuses, callback semantics, variables и schedules могли иметь другой смысл; официальной data migration нет.

Для ранних/non-production projects начните с пустого `data/runtime.sqlite3`. Если данные важны:

1. остановите v2 process и сохраните полный backup;
2. создайте отдельную v3 database;
3. напишите одноразовый проверяемый converter только для нужных records;
4. не изменяйте backup и не запускайте две версии на одной database;
5. проверьте migrated sessions/jobs на test copy.

## Почему нет compatibility layer

Двойная архитектура вернула бы исходную проблему: Studio видит один graph, а Python registry может скрыто исполнять другой. Отказ от v2 гарантирует, что runtime и Studio используют одну schema, handler source не владеет переходами, а автономный project остаётся читаемым и валидируемым без import discovery.

`pipubot/` в основном repository остаётся отдельным legacy fixture и не считается v2 project, который автоматически нужно переводить на Studio schema v3.
