# Python action SDK

Project scripts are ordinary UTF-8 `.py` files under `scripts/`. They import the
stable `bot_engine` facade supplied with the backend; users do not construct a
Telegram client, open SQLite or move the graph themselves.

## Minimal action

```python
from bot_engine import action, ActionContext, ActionResult


@action("create_request")
async def create_request(context: ActionContext) -> ActionResult:
    description = context.variables["request.description"]
    request_id = await context.services.requests.create(
        user_id=context.user.id,
        description=description,
    )
    return ActionResult.success(
        next_transition="created",
        variables={"request.id": request_id},
    )
```

An action name starts with a letter or underscore and may contain letters,
digits, `_`, `.`, or `-`. It is unique within one project. A function accepts
exactly one context argument and must be declared with `async def`; synchronous
functions are rejected during discovery.

## `ActionContext`

The context exposes:

- `project_id` and `session_id`;
- `user` (`id`, username and names);
- `chat` (`id`, currently private);
- `bot` identity returned by `getMe`;
- a mutable copy of session `variables`;
- rendered Action-node input `parameters`;
- a project/action `logger`;
- `telegram`, the injected messaging port;
- `storage`, project-scoped key/value storage;
- `services`, an optional application-specific service bundle;
- `metadata` for invocation context.

`get_variable(name, default)` and `set_variable(name, value)` are convenience
methods. Mutations and the variables returned by `ActionResult` are merged into
the session only after successful invocation.

The SDK deliberately exposes ports rather than PTB or `sqlite3` objects. A future
worker or remote runtime can supply equivalent proxies.

## Results

```python
return ActionResult.success(
    variables={"invoice.id": invoice_id},
    next_transition="paid",
)

return ActionResult.branch("manual_review", variables={"risk": 0.82})

return ActionResult.error("Provider rejected the request")
```

- `success` selects a matching outcome when supplied, otherwise the single
  success/action/automatic edge.
- `branch` requires a transition selector.
- `error` contains a user-safe error value and normally selects the error edge.

Returning any other object is a validation/runtime error. An unhandled exception
is caught, written to runtime history, published to Console with a stack trace
and routed through the configured error branch when possible.

## Discovery and validation

The script service parses source before a bot starts. It reports syntax errors,
decorator locations, duplicate names and invalid signatures with file/line
references. Import validation runs behind an exception boundary. Critical
syntax/import/binding failures block Run but do not prevent the script from being
opened and repaired.

The action registry is scoped by project and invalidated when script file
metadata changes. Studio displays the source path, declaration line and all
Action nodes that reference the name.

## Timeouts and trust model

Actions have a configurable timeout (with a bounded runtime default). Exceptions
and cooperative async timeouts are isolated from other bot runtimes. Python code
that never yields cannot be safely stopped inside the same process; project
scripts are therefore trusted local code in version one. The invocation port is
the intended seam for a future per-bot worker process.

Do not put Telegram tokens or other credentials in scripts. Store provider
credentials through an injected secret/service adapter.

## Project storage

`context.storage` points at the current project's SQLite repository; its
low-level KV methods take `context.project_id` explicitly. Values must be JSON-
compatible; Decimal and date/time values use the backend's lossless tagged JSON
codec. Session variables should be used for conversation state, while storage
is appropriate for small action-owned durable values.
