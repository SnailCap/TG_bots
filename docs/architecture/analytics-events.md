# Analytics events

## Назначение

Runtime заранее сохраняет базовые факты о взаимодействиях, views, flows, states и
handlers, чтобы исторические данные существовали до появления аналитического
интерфейса. Экран статистики, выборки, агрегации и графики не являются частью
runtime: их можно построить позднее поверх автономной SQLite-базы проекта.

Analytics event отличается от application log:

- event имеет стабильное имя и структурированные индексируемые поля;
- event представляет бизнес-факт, а не диагностическое сообщение;
- event не содержит stack trace, полного текста сообщения или session values;
- application log может меняться для удобства диагностики, контракт event — нет.

Таблица append-only. Runtime только добавляет строки и не исправляет историю
задним числом. Retention policy и удаление событий на этом этапе отсутствуют.

Analytics работает в режиме best-effort. Ошибка построения или записи события
попадает в стандартный logger, а основная операция продолжается. Поэтому сбой
SQLite может создать пропуск в истории, но не может сделать handler, transition
или отправку view неуспешными.

## Архитектура

Модель, каталог событий, serializer, `AnalyticsRecorder` и SQLite writer находятся
в `tg_bot_core.analytics`.

`SqliteStore.initialize()` вызывает принадлежащую analytics-модулю инициализацию
таблицы `analytics_events`. Таблица находится в той же `data/runtime.sqlite3`,
что users, sessions и jobs, но не является частью declarative project schema v3.

`BotApp` создаёт один recorder для bot ID и передаёт его `FlowEngine` и
`HandlerExecutor`. Runtime записывает события только через:

```python
await analytics.record(
    AnalyticsEventType.BUTTON_CLICKED,
    actor=event.actor,
    resource_id=event.action_id,
    flow_id=session.flow_id,
    state_id=session.state_id,
    view_id=session.view_id,
)
```

Прямые INSERT из dispatcher, engine, handlers или transport запрещены. Это
сохраняет единые validation, privacy и failure-isolation правила. Custom handler
не получает recorder, `SqliteStore` или raw connection через SDK.

### Storage contract

`analytics_events` содержит:

```text
id, bot_id, user_id?, chat_id?, session_id?, event_type,
resource_type?, resource_id?, flow_id?, state_id?, view_id?,
handler_id?, outcome?, status?, occurred_at, metadata_json
```

- `id` — UUID-строка;
- `occurred_at` — UTC Unix timestamp;
- `session_id` сейчас всегда `NULL`, поскольку отдельного стабильного session ID нет;
- `metadata_json` всегда JSON object не более 8 KiB;
- resource IDs сохраняются как строковый snapshot текущей project schema.

Индексы покрывают:

- `(bot_id, occurred_at)`;
- `(bot_id, user_id, occurred_at)`;
- `(bot_id, event_type, occurred_at)`;
- `(bot_id, resource_type, resource_id, occurred_at)`.

### Metadata и конфиденциальность

Serializer принимает только `null`, boolean, string, integer, конечный float,
list и objects со строковыми ключами. Каталог каждого event дополнительно
разрешает конкретный набор metadata keys.

Запрещено сохранять:

- bot tokens и credentials;
- полный текст сообщений или command arguments;
- session state и form values;
- exception messages и stack traces;
- произвольные данные custom handler.

Metadata дополняет событие, но не заменяет отдельные индексируемые поля.

## Каталог базовых событий

Во всех примерах `bot_id`, UUID и `occurred_at` добавляет recorder.

| Event | Момент записи | Обязательные поля и references | Metadata |
| --- | --- | --- | --- |
| `user_first_seen` | После первого INSERT пользователя | actor | `{}` |
| `interaction_received` | При каждом полученном `InteractionEvent`, до blocked/dedup boundary | actor | `{}` |
| `command_received` | После dedup или перед blocked exit | actor, `resource_type=command`, нормализованный command ID | `{}` |
| `message_received` | После dedup или перед blocked exit | actor | `{}` |
| `button_clicked` | После dedup или перед blocked exit, включая stale callback | actor, `resource_type=button`, action ID; optional flow/state/view snapshot | `{}` |
| `view_rendered` | После успешного `transport.send` | actor, `resource_type=view`, `resource_id=view_id`, view ID; optional flow/state | `{}` |
| `flow_started` | После первого успешного checkpoint нового flow | actor, `resource_type=flow`, flow ID, `status=active` | `{}` |
| `flow_completed` | После успешного checkpoint завершения | actor, flow reference, `status=finished` | `{}` |
| `flow_cancelled` | После успешного checkpoint отмены | actor, flow reference, `status=cancelled` | `{}` |
| `flow_failed` | После сохранения failed lifecycle | actor, flow reference, `status=failed` | `{}` |
| `state_entered` | При фактическом входе, после успешного checkpoint цепочки | actor, `resource_type=state`, flow ID, state ID | `{}` |
| `state_exited` | При фактическом выходе, после успешного checkpoint цепочки | actor, state reference scoped flow ID | `{}` |
| `handler_started` | Непосредственно перед `await handle(ctx)` | handler reference; actor и flow/state/view optional; `status=started` | `handler_kind`, optional `job_id` |
| `handler_succeeded` | После валидного `HandlerResult` | handler reference, outcome, `status=succeeded` | `handler_kind`, `duration_ms`, optional `job_id` |
| `handler_failed` | После exception или невалидного handler result | handler reference, `status=failed` | `handler_kind`, `duration_ms`, `error_type`, optional `job_id` |

Повторный render текущего state создаёт новый `view_rendered`, но не создаёт
`state_entered`. Явный `flow.goto` в тот же state является новым lifecycle entry.

При optimistic `SessionConflict` каждый реальный повтор handler получает свою
started/final пару. Flow/state events проигравшей попытки не записываются:
engine держит их локально до успешного session checkpoint.

### Примеры записей

Полученная команда:

```python
await analytics.record(
    AnalyticsEventType.COMMAND_RECEIVED,
    actor=event.actor,
    resource_id=event.command.lower().removeprefix("/"),
)
```

Фактически отправленный view:

```python
await transport.send(outbound)
await analytics.record(
    AnalyticsEventType.VIEW_RENDERED,
    actor=session.actor,
    view_id=view_id,
    flow_id=session.flow_id,
    state_id=session.state_id,
)
```

Успешный task handler:

```python
await analytics.record(
    AnalyticsEventType.HANDLER_SUCCEEDED,
    handler_id=job.handler_id,
    outcome="success",
    metadata={
        "handler_kind": "task",
        "job_id": job.id,
        "duration_ms": duration_ms,
    },
)
```

## Как добавить новое событие

1. Сформулировать один бизнес-факт и стабильный смысл события.
2. Найти единственную runtime-точку, где факт уже произошёл.
3. Добавить имя в `AnalyticsEventType`.
4. Добавить catalog spec с обязательными/допустимыми fields и metadata.
5. Проверить, что данные не содержат secrets, message text, state или forms.
6. Вызвать общий recorder в выбранной точке.
7. Добавить storage/runtime test и строку в каталог выше.

Один факт нельзя одновременно писать в transport, dispatcher и engine. Например,
`view_rendered` принадлежит точке после успешного send, а не намерению dispatcher
открыть view.

### Примеры будущих расширений

Новый resource event, например открытие каталога, должен получить собственное
стабильное имя и catalog spec с `resource_type="catalog"` и строковым snapshot ID.
Его записывают после фактического открытия, а не при выборе route.

Domain event из custom handler пока не поддерживается публичным SDK. Будущее
расширение должно предоставить ограниченный typed emitter с allowlisted
metadata; передавать handler raw SQLite, store или внутренний recorder нельзя.

Новое системное событие, например terminal failure job, добавляется в общий
каталог и записывается в `JobRuntime` после фактического перехода job в terminal
status. Нельзя выводить его косвенно из logger text.

## Правила стабильности

- Существующее имя event нельзя переименовать без миграции исторических данных.
- Смысл существующего event нельзя незаметно менять.
- Новое column-поле должно быть nullable; дополнительные неиндексируемые данные
  можно добавлять в разрешённую metadata.
- Metadata не заменяет поля, по которым потребуются фильтрация или индексы.
- Ошибка analytics не влияет на успешность основной операции.
- Строковые resource IDs сохраняются как snapshot.
- Позднее можно добавить nullable `resource_uid`, не меняя места записи событий:
  generic resource reference формируется централизованным recorder.
- Analytics UI, query API, export, aggregation, retention и remote delivery не
  входят в runtime analytics recorder.
