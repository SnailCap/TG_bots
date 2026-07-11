# Bot runtime

The runtime executes saved flow documents directly. It does not generate Python
code from the graph. One backend process can own several independent bot
runtimes, while each Studio project still represents exactly one Telegram bot.

## Lifecycle

`RuntimeManager` is the control-plane boundary. For every project it creates at
most one active `RuntimeService`, and exposes `run`, `stop` and `status`
operations. A service owns the project's Telegram adapter, graph executor,
action loader and event sink.

The observable states are:

```text
stopped -> starting -> running -> stopping -> stopped
                    \-> error <-/
```

Run validates the project before starting long polling. Critical flow, token,
script or action-binding issues move that runtime to `error` and do not affect
another project. Starting an already running runtime and stopping an already
stopped runtime are idempotent. Backend shutdown asks all managed runtimes to
stop, which closes PTB polling cleanly.

The desktop UI uses the project runtime endpoints for Run, Stop, status,
validation and history. Execution/project events are delivered through SSE at
`/api/v1/events?project_id=<id>`; status is also polled over HTTP and history
remains available from the project's SQLite database after a reconnect.

## Telegram transport

The production adapter uses `python-telegram-bot` long polling and accepts
messages, `/start` commands and callback queries. Version one intentionally
processes private chats only. Groups, channels, inline mode and webhooks are out
of scope.

`GraphExecutor` depends on a small `TelegramPort`, not PTB classes. Tests inject
a fake adapter, and a future worker or remote transport can implement the same
port without changing flow semantics.

## Session identity and persistence

There is one active session for a `(project_id, telegram_user_id,
telegram_chat_id)` tuple. A session stores:

- the current flow and node;
- `active`, `waiting_input`, `completed`, `failed` or `reset` status;
- variables and the pending input expectation;
- the flow schema version and runtime metadata;
- creation and update timestamps.

Sessions, runtime history and action key/value data live in
`.botstudio/runtime.db`. Schema migrations run when the repository opens. State
is committed at node boundaries and before waiting for user input, so stopping
the runtime or restarting the backend does not discard an unfinished dialog.

A per-session async lock serializes updates from the same user/chat. Telegram
update IDs are recorded so a repeated update is ignored. Independent sessions
and independent projects may progress concurrently.

### `/start` behavior

The project's `start_behavior` setting controls an existing session:

- `reset` marks the previous active session as reset and starts a new one at the
  configured start flow;
- `resume` continues the saved active session.

An ordinary message with no active session receives the configured inactive
session message (by default, `Send /start to begin.`).

## Node execution

| Node | Runtime behavior |
| --- | --- |
| `start` | Selects the single automatic outgoing transition. |
| `send_message` | Renders and sends text or supported media, optionally with an inline/reply keyboard. It then advances or waits for a button transition. |
| `ask_input` | Sends a prompt, validates the reply, stores it under the configured variable name and follows the input/success edge. |
| `choice` | Sends inline or reply buttons, waits, validates the selected value and follows the matching button edge. |
| `condition` | Evaluates an allow-listed operator and follows the `true` or `false` condition edge. |
| `action` | Invokes a registered project action with a timeout, merges mapped outputs and follows success/action/error branching. |
| `end` | Optionally sends a final message and marks the session completed. |

Automatic traversal is capped (64 steps by default). This guard turns a broken
automatic cycle into a structured runtime error instead of monopolizing the
backend loop.

## Input and conditions

Ask Input supports `string`, `integer`, `number` and `boolean` values. It can
enforce required input, a regular expression, min/max value or length,
`max_attempts`, and a custom `error_message`. Exhausted attempts follow an error
edge when one exists; otherwise the session becomes failed.

Condition nodes never evaluate Python source. Supported operators include
equality and ordering, `contains`/`in`, string prefix/suffix checks,
existence and truthiness checks. Dotted variable names such as
`request.customer.age` are resolved from either literal dotted keys or nested
mappings. Complex calculations belong in an Action node.

## Variables and templates

Messages, captions, button labels, media references and action parameters use a
sandboxed Jinja environment with strict undefined values:

```jinja2
Request {{ request.id }} was created for {{ user.name }}.
```

Dotted session keys are exposed as nested template values. A missing variable is
an error rather than silently becoming an empty string. Templates are authored
by the local project and are rendered without Python `eval`.

## Transitions

The executor selects outgoing transitions by kind and, for branches, by
`outcome`, label or configured value. Selection must be unambiguous. A missing
edge or two equally matching edges is a validation/runtime error.

Choice callback data is namespaced as `svc:flow:<selector>` and checked against
Telegram's 64-byte callback limit. Action results may select an explicit
outcome; otherwise the single compatible success/action/automatic edge is used.
Action failures follow the error edge when available.

## Errors and observability

Runtime events include project, session and, where applicable, flow/node/action
references. They are both published to the Studio Console and appended to
SQLite history. Script exceptions include a traceback. A failed action or
malformed update is isolated at the project/update boundary and does not stop
other bots.

Project scripts are trusted local code. Import guards, typed errors and async
timeouts improve failure isolation but are not a security sandbox. In
particular, CPU-bound code that never yields cannot be forcibly stopped safely
inside the shared backend process; process-per-bot workers are the intended
future isolation boundary.
