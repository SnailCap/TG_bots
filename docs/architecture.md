# Telegram Bot Studio architecture

## Product boundary

A Studio project represents exactly one Telegram bot. Project definitions are
portable files; runtime state belongs to that project and lives in its local
SQLite database. The desktop application can open and switch between projects,
and the backend can host more than one running project.

The React renderer is a thin client. It edits documents through the HTTP API and
observes runtime events through Server-Sent Events (SSE). It never opens the
runtime database, imports project scripts, talks to Telegram, or executes a
flow.

```text
Electron main process
  ├─ owns the window and native directory dialogs
  └─ starts/stops the Python control-plane process

React renderer
  ├─ Project Explorer, tabs, graph, Inspector and preview
  ├─ script editor and action/usages navigation
  └─ HTTP commands + SSE observations

Python backend
  ├─ API/application services
  ├─ project filesystem, keyring and SQLite adapters
  ├─ project-scoped script discovery
  └─ RuntimeManager
       └─ BotRuntime(project)
            ├─ graph executor
            ├─ session repository
            └─ Telegram port (PTB long polling or fake test adapter)
```

## Dependency direction

The backend uses four boundaries:

1. **Domain** — dataclasses, enums, invariants, results and repository/adapter
   protocols. It has no dependency on FastAPI, PTB, SQLite, Electron or React.
2. **Application** — project, flow, settings, script and validation use cases.
   It coordinates ports and owns no transport details.
3. **Runtime** — graph execution and bot lifecycle. It consumes the same domain
   models and ports as tests and infrastructure.
4. **Infrastructure/API** — filesystem, atomic JSON, SQLite, OS keyring, PTB,
   script loading, event fan-out and HTTP/SSE adapters.

Transport schemas are intentionally separate from domain models. This permits a
future remote backend without moving business rules into the frontend.

## Important decisions

### The graph is the source of truth

Flows are executed directly from versioned JSON. Studio never generates Python
code, so there is no second representation to synchronize. Node positions are
editor metadata in the same portable flow document.

### Commands and observations are separate

HTTP endpoints perform bounded operations and return their result. Runtime and
project log entries, including action stack traces, are also published as
structured events. Status and validation reports remain explicit HTTP reads.
SSE was selected for live logs because communication is server-to-client only,
reconnect is native to browsers and commands already have HTTP endpoints.

### State is committed at node boundaries

The graph executor persists the session before it waits for input and after each
state-changing node. A per-session asynchronous lock serializes updates for the
same project/user/chat identity. A guard caps automatic node traversal so a
damaged cycle cannot monopolize the backend.

### `/start` has an explicit project policy

The first version has one active session per `(project, Telegram user, chat)`.
With the default `reset` policy, `/start` resets flow position, input wait state,
attempts and variables before starting the configured flow. The alternative
`resume` policy continues an unfinished persisted session.

### Scripts are trusted local project code

Studio performs AST syntax/signature discovery and guards imports, exceptions
and async execution timeouts. It does not claim to sandbox hostile Python in the
backend process. The action boundary is designed so execution can move to a
worker process later; package installation through the UI is intentionally out
of scope.

### Secrets are references

`bot.json` stores a stable secret reference only. The default desktop adapter
uses the operating-system keyring. Tests inject an in-memory provider. There is
no automatic plaintext fallback.

### Files are written atomically

Project documents are written to a sibling temporary file, flushed, and then
replaced. Paths are resolved below their project roots before CRUD operations;
script and asset APIs reject traversal.

## Failure isolation

- A script exception becomes an action-error result and a structured event with
  project/flow/node/script context; it does not terminate another bot runtime.
- A Telegram connection failure moves only that project's runtime to `error`.
- Backend shutdown asks every runtime to stop in reverse lifecycle order.
- Corrupt flow/project files and unavailable secrets are typed application
  errors and visible in Console.
- Validation blocks Run on critical issues but does not prevent opening and
  repairing a project.

## Future worker/remote boundary

`RuntimeManager` is the control-plane abstraction. Its inputs are project IDs and
its outputs are status/events; the graph executor talks only to ports. Replacing
an in-process runtime handle with a worker/RPC handle therefore does not change
flow semantics, the project format or frontend endpoints.
