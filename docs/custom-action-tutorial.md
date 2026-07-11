# Tutorial: add a custom Python action

This tutorial extends the first bot with an async action that creates a request
identifier. The flow still owns conversation and branching; Python owns the
small computation that does not belong in a visual node.

## 1. Create the script

In Project Explorer select **+ Script**, enter `request_actions.py`, and open the
file in the Monaco editor. Replace its contents with:

```python
from bot_engine import ActionContext, ActionResult, action


@action("create_request")
async def create_request(context: ActionContext) -> ActionResult:
    description = str(context.get_variable("request.description", "")).strip()
    if not description:
        return ActionResult.error("Request description is missing")

    prefix = str(context.parameters.get("prefix", "REQ"))
    request_id = f"{prefix}-{context.user.id}-{context.session_id[-6:]}"
    context.logger.info("Created request %s", request_id)

    return ActionResult.success(
        variables={
            "request.id": request_id,
            "request.status": "created",
        }
    )
```

Save with **Ctrl+S**. Action functions must be declared with `async def`, accept
exactly one `ActionContext`, and return `ActionResult`. Studio discovers the
`@action` decorator and lists `create_request` without executing the function.

Project scripts import the stable `bot_engine` facade. Do not create another
Telegram client, open `.botstudio/runtime.db` directly, or put credentials in
the script.

## 2. Bind the Action node

Open the `Main` flow from [first-bot-tutorial.md](first-bot-tutorial.md). Insert
an **Action** node between `Ask description` and `Confirmation`.

In Inspector:

1. choose `create_request` under **Registered action**;
2. leave the timeout at `30` seconds;
3. set **Input parameters (JSON)** to:

   ```json
   { "prefix": "REQ" }
   ```

4. set **Output mapping (JSON)** to:

   ```json
   {
     "request.id": "request.id",
     "request.status": "request.status"
   }
   ```

Connect the Action `success` handle to Confirmation. Add a separate Send
Message node such as `Sorry, the request could not be created.` and connect the
Action `error` handle to it, then to End.

Change Confirmation to:

```jinja2
Created request {{ request.id }}: {{ request.description }}
```

Save and Validate. The validation result links an invalid binding back to both
the Action node and the script declaration.

Action input values may contain templates and are rendered from current session
variables before invocation. They are available as `context.parameters`.
Output mapping uses `result variable -> session variable`; explicitly mapping
outputs makes the flow contract visible in Inspector.

## 3. Run the action

Run the bot, send `/start`, follow the New request branch and enter a
description. The action returns two variables, the mapping commits them to the
session, and Confirmation renders the new ID.

Console shows `action.completed` on success. An uncaught exception, timeout or
`ActionResult.error(...)` is reported with project/session/action context and
uses the error transition. It does not terminate another bot runtime.

## Branching explicitly

An action may select a named Action transition:

```python
if context.get_variable("request.priority") == "high":
    return ActionResult.branch(
        "manual_review",
        variables={"request.route": "operator"},
    )

return ActionResult.success(
    next_transition="automatic",
    variables={"request.route": "queue"},
)
```

The selected value must match exactly one outgoing transition outcome. If no
explicit selector is returned, configure exactly one compatible success edge.

## Context and durable storage

`ActionContext` provides project/session IDs, Telegram user/chat/bot identity,
session variables, rendered parameters, a logger, the Telegram port, durable
project storage and optional injected services. Prefer `ActionResult.variables`
for values the next flow node needs.

Small action-owned data can use the injected storage adapter. Its current
low-level methods take the project namespace explicitly:

```python
key = "requests.created"
count = int(context.storage.get_kv(context.project_id, key, 0)) + 1
context.storage.set_kv(context.project_id, key, count)
```

These values live in the project's SQLite database. External databases or APIs
should be wrapped behind `context.services` in a controlled backend
composition, rather than constructed globally when the script is imported.

## Async and timeout rules

- Use `async def`; synchronous actions are rejected during discovery.
- Await network or other cooperative async operations.
- Keep CPU-heavy work out of the shared backend process.
- Treat the Action node timeout as a failure boundary, not as a security
  sandbox.
- Return a user-safe error message and inspect the full traceback in Console.

See [script-sdk.md](script-sdk.md) for the complete result and trust model.
