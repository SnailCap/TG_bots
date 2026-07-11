# Studio project format

## Directory layout

Each directory is one independently portable Telegram bot project.

```text
my-bot/
├── bot.json
├── flows/
│   └── <flow-id>.flow.json
├── scripts/
│   └── actions.py
├── assets/
└── .botstudio/
    ├── .gitignore
    └── runtime.db
```

`bot.json`, `flows`, `scripts` and assets are intended for Git. `.botstudio` is
local runtime state; Studio creates `.botstudio/.gitignore` so its database is
excluded by default. JSON is UTF-8, human-readable and written atomically by
the backend.

All relative paths accepted by the API are normalized below their designated
project directory. A path containing an absolute root, drive prefix or `..` is
rejected. Script files must end in `.py`.

## Versioning

Every project and flow document contains `"schema_version": 1`. The loader
rejects an unknown version with a structured error rather than guessing. Future
format migrations must write a backup and migrate explicitly.

## `bot.json`

```json
{
  "schema_version": 1,
  "project": {
    "id": "c53989a7-6090-4ae4-8526-3c8b2a516715",
    "name": "Support bot",
    "created_at": "2026-07-11T12:00:00Z",
    "updated_at": "2026-07-11T12:00:00Z"
  },
  "bot": {
    "secret_ref": "botstudio:c53989a7-6090-4ae4-8526-3c8b2a516715:telegram-token",
    "start_flow_id": "main",
    "start_behavior": "reset",
    "identity": {
      "bot_id": 123456789,
      "username": "support_example_bot",
      "display_name": "Support Example"
    },
    "metadata": {}
  }
}
```

The Telegram token is never serialized. `secret_ref` is the key used by the
configured secret provider. `identity` is non-secret data returned by Telegram
`getMe` after validation.

## Flow document

```json
{
  "schema_version": 1,
  "id": "main",
  "name": "Main flow",
  "start_node_id": "start",
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "name": "Start",
      "position": { "x": 80, "y": 120 },
      "config": {}
    },
    {
      "id": "hello",
      "type": "send_message",
      "name": "Greeting",
      "position": { "x": 320, "y": 120 },
      "config": {
        "text": "Hello, {{ user.name }}!"
      }
    }
  ],
  "transitions": [
    {
      "id": "start-to-hello",
      "source_node_id": "start",
      "target_node_id": "hello",
      "kind": "automatic",
      "label": null,
      "outcome": null,
      "config": {}
    }
  ],
  "metadata": {}
}
```

Node IDs and transition IDs are unique within a flow. Positions are presentation
metadata; runtime uses IDs and transitions only.

### Node types and configuration

| Type | Important configuration |
| --- | --- |
| `start` | no required fields |
| `send_message` | `text`; optional `parse_mode`, `media`, `keyboard` |
| `ask_input` | `prompt`/`text`, `variable`, `input_type`, `required`, `regex`, min/max, `error_message`, `max_attempts` |
| `choice` | `text`, keyboard mode, `choices`, and matching outgoing button transitions |
| `action` | `action_name` (`action` is also accepted), optional templated `input_parameters`, `timeout_seconds`, `output_mapping` |
| `condition` | allow-listed `operator`, left/variable and right/value operands |
| `end` | optional final `text` |

The condition language never evaluates Python source. Complex conditions belong
in a registered action.

### Transition types

`automatic`, `input`, `button`, `condition`, `action`, `success` and `error` are
valid kinds. `outcome`, `label` and `config.value` can select a branch. A branch
must resolve to exactly one outgoing transition; missing and ambiguous matches
are runtime/validation errors.

Button callbacks use a compact, validated `svc:flow:` value containing the
transition selector. Human-readable reply keyboard labels can select the same
transition.

## Runtime database

`.botstudio/runtime.db` is created on first runtime access. It contains schema
migration records, sessions, runtime history and project action key/value data.
It is not part of the portable definition and should not be copied while a bot
is running. To preserve conversations when moving a project, stop the bot and
copy the `.botstudio` directory deliberately.

## Atomic updates and recovery

Studio writes a complete sibling temporary file, flushes it, and replaces the
target. A failed write leaves the previous valid document intact. The backend
validates decoded documents before returning them to runtime; opening a corrupt
project reports the exact source file and does not rewrite it automatically.
