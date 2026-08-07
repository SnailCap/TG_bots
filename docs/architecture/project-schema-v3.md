# Project schema v3

Этот документ описывает фактически загружаемый contract `tg_bot_core.project.ProjectLoader`. Все JSON resources имеют `schema_version: 3`; v2 resources runtime не принимает.

## Структура

```text
<project>/
├─ resources/
│  ├─ bot.json                 # обязателен
│  ├─ handlers.json            # обязателен
│  ├─ commands.json            # обязателен
│  ├─ variables.json           # optional для старых v3 projects; starter создаёт файл
│  ├─ views/                   # обязателен, JSON рекурсивно
│  ├─ content/                 # optional, structured content JSON рекурсивно
│  ├─ flows/                   # обязателен, JSON рекурсивно
│  ├─ schedules/               # обязателен, может быть пустым
│  └─ templates/               # обязателен, *.txt рекурсивно
└─ src/<package>/              # custom Python package
```

Loader принимает путь как к project root, так и непосредственно к каталогу с именем `resources`. Entity ID берётся из JSON, а не из имени файла. Повтор ID среди files одного типа является parse error.

## Manifest: `resources/bot.json`

```json
{
  "schema_version": 3,
  "id": "shop_bot",
  "package": "shop_bot",
  "entry_view": "home",
  "start": {
    "flow": "checkout",
    "policy": "reset"
  }
}
```

| Поле | Смысл |
| --- | --- |
| `id` | Stable bot/project ID, также ключ sessions/deduplication |
| `package` | Importable Python package под `src/`; handler modules обязаны находиться внутри него |
| `entry_view` | Default view без active/current view; также default после finish/cancel и успешно обработанного flow error |
| `start.flow` | Flow, запускаемый встроенной командой `/start` |
| `start.policy` | `reset` либо `resume`; default — `reset` |

### Studio presentation names

Studio may add an optional `display_names` object to `bot.json`. It maps a Studio resource kind (`views`, `flows`, `schedules`, `handlers`, or `commands`) and its stable technical ID to a human-facing name. This metadata is additive in schema v3: old projects omit it, and runtime dispatch never reads it.

```json
"display_names": {
  "views": {"welcome_screen": "Welcome screen"}
}
```

Studio creates IDs from a supplied display name using lowercase ASCII `snake_case`; spaces become `_` and Cyrillic is transliterated. The ID remains stable after a later display-name edit, so references, callback IDs, and resource file paths do not change.

При `resume` активная session только re-rendered; если active flow нет, он запускается как обычно. `/start` зарезервирован и не может повторно объявляться в commands.

## Переменные ресурсов: `resources/variables.json`

Каталог хранит декларативные определения, но не пользовательские значения. Старый v3 project без файла загружается как каталог без custom variables; новый starter создаёт пустой файл. Системные `user.*` definitions добавляет core, поэтому проект не может переопределить или удалить их.

```json
{
  "schema_version": 3,
  "variables": [
    {
      "id": "var_order_total",
      "owner": {"type": "flow", "id": "checkout"},
      "path": "order.total",
      "type": "number",
      "source": "custom",
      "required": true,
      "writable": true,
      "exampleValue": 120,
      "persistence": "resource",
      "exposedToTemplates": true,
      "legacyPaths": []
    }
  ]
}
```

`id` — стабильная runtime identity; `path` — Jinja/Python presentation path. Studio при переименовании сохраняет прежний путь в `legacyPaths`, поэтому structured reference с `fieldId` и старые `{{ order.total }}` продолжают разрешаться. ID и все current/legacy paths уникальны; path состоит из dotted Python identifiers и не может быть одновременно scalar и родителем другого path.

Поддерживаемые типы: `string`, `number`, `boolean`, `date`, `datetime`, `object`, `array`. `defaultValue` и `exampleValue` проверяются по типу и должны быть JSON-serializable. `computed` зарезервирован, но в первой версии validator его отклоняет. Owner types соответствуют существующей v3-модели: `bot`, `flow`, `state` (ID вида `flow.state`), `view`, `handler`. Flow variable доступна его states/views и handlers во время этого flow; state/view/handler variable не выходит за своего владельца; core variables доступны везде.

`persistence: "resource"` привязывает value к конкретному flow execution (`resource_instance_id`). Политики `session` и `user` сохраняют value между повторными flow starts в текущей user/chat session. Все values лежат отдельно от definitions и от свободного `ctx.state`, в runtime SQLite; definitions остаются единственным source of truth в `resources/variables.json`.

Studio backend предоставляет revision-aware чтение/запись каталога и поиск usages. Удаление используемой custom variable блокируется. После успешной записи обновляется derived `src/<package>/_botstudio_variables.py`; этот модуль даёт autocomplete, но не является источником истины и не перезаписывается, если файл не имеет generated marker.

## Views и templates

`resources/views/home.json`:

```json
{
  "schema_version": 3,
  "id": "home",
  "text": {
    "template": "views/home.txt",
    "document": "views/home.json"
  },
  "keyboard": [
    [
      {
        "id": "checkout.confirm",
        "text": "Подтвердить",
        "action": {
          "type": "flow.event",
          "target": "confirm"
        }
      },
      {
        "id": "home.help",
        "text": "Помощь",
        "action": {
          "type": "view.render",
          "target": "help"
        }
      }
    ]
  ]
}
```

`text` должен содержать ровно одно из двух source-полей:

- `{"inline": "Hello {{ user.first_name }}"}`;
- `{"template": "views/home.txt"}` — POSIX-style relative path внутри `resources/templates/`.

Дополнительно `text` может содержать `"document": "views/home.json"` — POSIX-style relative `.json` path внутри `resources/content/`. Это additive extension schema v3: `schema_version` view остаётся равным `3`, а сам content document имеет независимое camelCase поле `schemaVersion`. Loader не требует каталог `resources/content/` у legacy projects, но validator требует существующий document для каждой указанной ссылки и отклоняет absolute paths, `..` и обратные слеши.

Templates читаются только из `*.txt`. Validation проверяет каждый template один раз, включая неиспользуемые, и выдаёт diagnostics с его собственным `templates/<path>`. Без `document` runtime использует прежний `StrictUndefined`, передаёт session values и объект `user`, а PTB отправляет результат как обычный текст без неявного HTML/Markdown parse mode. Пустой результат и текст длиннее 4096 символов отклоняются до вызова Telegram API.

При наличии `document` новый runtime предпочитает structured content и компилирует его в один или несколько Telegram messages с entities. `template` остаётся derived plain-Jinja projection для совместимости и старых core versions; rich marks не кодируются в нём как HTML. Canonical Studio paths:

```text
resources/content/views/<view-id>.json
resources/templates/views/<view-id>.txt
```

Content document schema v1 поддерживает paragraphs, quotes, expandable quotes, code blocks, lossless legacy blocks, typed variables, custom emoji, hard breaks и Telegram marks. Loader индексирует все `resources/content/**/*.json`; validation проверяет в том числе неиспользуемые documents, duplicate document IDs и Jinja syntax внутри `legacyTemplate`, привязывая diagnostics к `content/<path>`. Точный JSON contract, compiler, migrations и правила расширения описаны в [Rich Text Content Editor](../studio/content-editor.md).

Studio не показывает templates как отдельный ресурс. Обычный редактор работает с текстом выбранного view, а backend при сохранении пишет его в owned path `resources/templates/views/<view-id>.txt` и обновляет `text.template`. Открытые legacy `inline` или non-canonical template references читаются как обычно и канонизируются только при следующем сохранении через Studio. Rich editor revision-aware сохраняет document, derived template и view reference одной операцией. Это additive UI/storage policy Studio, а не новый project format.

`keyboard` — массив rows, каждая row — массив buttons. `button.text` проходит через тот же `StrictUndefined` Jinja context, что и view text, поэтому в подписи можно использовать доступные переменные ресурсов. Button `id` является глобальным action ID всего проекта. Core кодирует callback как `v3:a:<button-id>`; UTF-8 payload обязан помещаться в 64 bytes. Текст, handler ID или target в callback не включаются. При dispatch ID дополнительно должен принадлежать текущему сохранённому view session, поэтому кнопка из старого экрана не выполняет action другого экрана.

## Actions

Action object имеет единственный нормализованный формат. Loader отклоняет неизвестные поля для известных action types.

| `type` | Поля | Runtime semantics |
| --- | --- | --- |
| `noop` | только `type` | Сохранить и показать current/default view |
| `view.render` | `target`, optional `delivery` | Сохранить явный `view_id` и показать view, не меняя flow/state |
| `flow.start` | `target`, optional `delivery` | Сбросить variables, запустить flow и его `on_start`/initial state |
| `flow.cancel` | optional `view` | Вызвать `on_cancel`, очистить active flow/state, status `cancelled`, показать `view` или entry view |
| `flow.event` | `target` | Передать named event текущему state; разрешён только из button context, а target должен быть объявлен хотя бы в одном `state.events` проекта |
| `flow.goto` | `target` | Войти в state текущего flow и выполнить его `on_enter` |
| `flow.finish` | optional `view` | Вызвать `on_complete`, очистить flow/state, status `finished`, показать `view` или entry view |
| `handler.invoke` | `handler`, `outcomes`, optional `payload` | Вызвать handler текущего event kind и применить outcome route |
| `task.enqueue` | `target`, optional `payload`, `delay_seconds`, `view` | Сохранить session, поставить task handler в durable queue, показать `view` или current view |

Примеры:

```json
{"type": "flow.start", "target": "checkout"}
```

```json
{
  "type": "handler.invoke",
  "handler": "checkout.submit",
  "payload": {"source": "confirm_button"},
  "outcomes": {
    "success": {"type": "flow.finish", "view": "checkout_done"},
    "invalid": {"type": "view.render", "target": "checkout_confirm"}
  }
}
```

```json
{
  "type": "task.enqueue",
  "target": "notifications.send_receipt",
  "payload": {"priority": "normal"},
  "delay_seconds": 5,
  "view": "queued"
}
```

Defaults: `payload={}`, `outcomes={}`, `delay_seconds=0`. Validator требует существующие targets/kinds и для каждого `handler.invoke` — explicit route `success` плюс routes всех outcomes, объявленных binding. `flow.goto` проверяется относительно flow, внутри которого action размещён; поэтому он не является глобальной навигацией.

Для `view.render` и `flow.start` поле `delivery` принимает `edit` или `send` и по умолчанию равно `edit`. При callback-переходе `edit` заменяет текущее сообщение бота, сохраняя чат чистым. Если событие не содержит редактируемого сообщения бота (например, обычная команда), runtime отправляет новое сообщение. `delivery: "send"` всегда создаёт новое сообщение.

## Flows, states и hooks

`resources/flows/checkout.json`:

```json
{
  "schema_version": 3,
  "id": "checkout",
  "initial_state": "details",
  "lifecycle": {
    "on_start": {
      "handler": "checkout.prepare",
      "outcomes": {
        "success": {"type": "noop"}
      }
    },
    "on_complete": {
      "handler": "checkout.completed",
      "outcomes": {
        "success": {"type": "noop"}
      }
    },
    "on_cancel": {
      "handler": "checkout.cancelled",
      "outcomes": {
        "success": {"type": "noop"}
      }
    },
    "on_error": {
      "handler": "checkout.failed",
      "outcomes": {
        "success": {"type": "noop"}
      }
    }
  },
  "states": {
    "details": {
      "view": "checkout_details",
      "on_enter": {
        "handler": "checkout.enter_details",
        "outcomes": {
          "success": {"type": "noop"}
        }
      },
      "on_message": {
        "handler": "checkout.save_details",
        "outcomes": {
          "success": {"type": "flow.goto", "target": "confirmation"},
          "invalid": {"type": "view.render", "target": "checkout_details"}
        }
      },
      "events": {}
    },
    "confirmation": {
      "view": "checkout_confirm",
      "events": {
        "confirm": {
          "handler": "checkout.submit",
          "outcomes": {
            "success": {"type": "flow.finish", "view": "checkout_done"},
            "payment_required": {"type": "flow.goto", "target": "payment"}
          }
        }
      }
    },
    "payment": {
      "view": "checkout_payment",
      "events": {}
    }
  }
}
```

Invocation object в hook/state event содержит `handler` и `outcomes`; в отличие от action `handler.invoke`, у него нет configurable `payload`. `on_error` runtime передаёт `payload={"error": "..."}`, остальные direct invocations получают пустой payload.

Kinds фиксированы контекстом:

- lifecycle hooks и state `on_enter` → `lifecycle`;
- state `on_message` → `message`;
- named state event → `button`.

`on_enter` исполняется только при старте/переходе в state. `noop`, stale callback и простой render текущего view повторно его не вызывают. `on_complete`, `on_cancel` и `on_error` имеют разные причины и statuses. Automatic action chain ограничен `BotConfig.max_auto_transitions` (default 32).

## Handler registry

`resources/handlers.json`:

```json
{
  "schema_version": 3,
  "handlers": [
    {
      "id": "checkout.submit",
      "module": "shop_bot.handlers.checkout.submit",
      "symbol": "handle",
      "kind": "button",
      "outcomes": ["payment_required", "invalid"],
      "description": "Submit a validated order"
    }
  ]
}
```

Допустимые kinds: `button`, `message`, `command`, `lifecycle`, `task`. `success` всегда существует неявно и не должен входить в `outcomes`; task handler вообще не может объявлять routed outcomes. `description` optional.

Binding — единственный механизм разрешения кода. Module обязан быть dotted Python path внутри manifest package. При `inspect_code=True` проверяются file, parse, top-level symbol, `async def`, ровно один context argument, соответствующая context annotation и return annotation `HandlerResult`. Startup затем реально импортирует каждый module и кеширует callable.

Core допускает generic stable handler IDs, но Studio scaffolder намеренно использует более узкий безопасный формат: dot-separated segments, каждый начинается с ASCII letter и продолжается letters/digits/`_`; Python keywords запрещены. Это позволяет детерминированно построить `src/<package>/handlers/<segments>.py`.

## Commands и fallbacks

`resources/commands.json`:

```json
{
  "schema_version": 3,
  "commands": [
    {
      "name": "help",
      "description": "Show help",
      "action": {"type": "view.render", "target": "help"}
    },
    {
      "name": "checkout",
      "action": {"type": "flow.start", "target": "checkout"}
    },
    {
      "name": "profile",
      "action": {
        "type": "handler.invoke",
        "handler": "profile.open",
        "outcomes": {
          "success": {"type": "view.render", "target": "profile"}
        }
      }
    }
  ],
  "message_fallback": {
    "type": "handler.invoke",
    "handler": "fallback.message",
    "outcomes": {
      "success": {"type": "noop"}
    }
  },
  "command_fallback": {
    "type": "view.render",
    "target": "home"
  }
}
```

Один начальный `/` при parsing удаляется. После этого command name должен соответствовать `[a-z][a-z0-9_]{0,31}`; сравнение runtime case-insensitive. Имена уникальны, `/start` зарезервирован. `message_fallback` вызывается только когда active state не имеет `on_message`; command fallback — для неизвестной команды.

## Schedules

Каждый schedule хранится отдельным JSON, например `resources/schedules/daily_digest.json`:

```json
{
  "schema_version": 3,
  "id": "daily_digest",
  "handler": "notifications.daily_digest",
  "trigger": {
    "type": "interval",
    "seconds": 86400
  },
  "payload": {
    "channel": "daily"
  }
}
```

Форма `trigger` рассчитана на расширение, но текущие validator и runtime поддерживают только `interval` с положительным numeric `seconds`. `cron` и `once` пока дают `unsupported_schedule_trigger`. Handler обязан иметь kind `task`; payload default — `{}`.

При startup schedules синхронизируются с SQLite. Удалённые из resources schedules деактивируются. Просроченный interval materializes в одну job, а `next_run_at` перескакивает через пропущенные intervals без массового catch-up.

## IDs и references

Generic entity ID соответствует `^[A-Za-z][A-Za-z0-9_.-]{0,127}$`. Это правило применяется к bot, view, button/action, flow, state, event, handler и schedule IDs. Дополнительно:

- `package` и handler `module` — dotted Python identifiers без keywords;
- handler module начинается с `<manifest.package>.`;
- button IDs глобально уникальны во всех views;
- state target у `flow.goto` локален текущему flow;
- непустой target `flow.event` должен совпадать хотя бы с одним key в `state.events` проекта, иначе validator возвращает `unknown_event_reference`;
- template path должен существовать в индексированных `*.txt`;
- optional content document path должен быть безопасным relative `.json` path и существовать среди индексированных `resources/content/**/*.json`;
- command names имеют отдельное более узкое правило;
- declared handler outcome соответствует generic ID, но не равен `success`.

Cross-resource references проверяются общим validator, который используют runtime, CLI и Studio backend.

## Diagnostics

После успешного parsing `validate_project()` возвращает список records:

```json
{
  "level": "error",
  "code": "handler_kind_mismatch",
  "message": "Handler 'checkout.submit' has kind 'message', expected 'button'.",
  "source_path": "flows/checkout.json",
  "entity_id": "checkout.confirmation",
  "field_path": "events.confirm.handler"
}
```

Поля `source_path`, `entity_id` и `field_path` присутствуют, когда location известна. Коды стабильны для UI/CLI; среди них `missing_entry_view`, `missing_start_flow`, `unknown_view_reference`, `unknown_flow_reference`, `unknown_state_reference`, `unknown_event_reference`, `duplicate_action_id`, `outcome_route_missing`, `handler_*`, `command_collision`, `callback_encoding_invalid`, `template_missing`, `content_document_missing`, `content_document_path_invalid`, `duplicate_content_document_id`, content validation codes, `jinja_syntax`, `unreachable_state`, `unsupported_schedule_trigger`.

Синтаксические/структурные ошибки до построения `ProjectDefinition` являются `ProjectLoadError`; core CLI печатает их с code `project_load`.

Проверка без Studio:

```bash
python -m tg_bot_core validate /path/to/project
```
