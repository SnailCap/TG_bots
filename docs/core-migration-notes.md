# Migration notes for the legacy `core`

## Status and boundary

The existing `core` package remains an unchanged reference implementation. The
new Studio backend is deliberately placed next to it and does not import
`pipubot`. This avoids breaking the 73 legacy `pipubot` import sites found during
the repository audit and allows useful concepts to be migrated behind tests.

The Studio is not a second skin over the old page configuration. Its source of
truth is a versioned, portable flow graph, while runtime state is project-scoped
and persisted in SQLite.

## Ideas retained

- Ports around messaging, state and sessions. The old `Messenger`,
  `StateStore`, and `SessionProvider` protocols demonstrated the right
  dependency direction. Studio defines transport-neutral ports in its domain
  and supplies filesystem, SQLite, keyring and Telegram adapters.
- A compact interaction context. `UserInput` grouped actor, chat, message,
  callback, state and reply capabilities. Studio's incoming update and action
  contexts follow the same principle without depending on PTB types.
- A state facade over raw persistence. `InteractionState` normalized the shape
  of `user_data`; Studio moves that responsibility to a typed, versioned Session
  aggregate and a repository.
- Typed effects/results. The old process coordinator used explicit effects such
  as render, next, finish and cancel. Studio nodes and Python actions return
  typed runtime results rather than mutating a state machine indirectly.
- Explicit callback namespaces. The `svc:`/`st:` callback standard prevented
  collisions. Studio reserves a `svc:flow:` namespace for graph transitions and
  validates Telegram's callback length limit.
- Strict templates. The Jinja renderer used strict undefined-variable handling.
  Studio keeps strict rendering so broken bindings become visible errors instead
  of silently producing incorrect messages.
- Registries and discovery. UI decorators and convention discovery offered a
  good developer experience. Studio adapts this to a project-scoped `@action`
  registry, combining AST inspection with guarded loading so projects and
  reloads cannot share a global registry accidentally.
- Composable lifecycle. `AppPlugin`, `BotRuntimeBuilder`, and `AppHost` separated
  assembly and startup. Studio retains explicit runtime composition and reverse
  shutdown, but exposes programmable `run`/`stop` operations to the desktop API.
- Strict configuration loading. Duplicate keys, invalid JSON and source-path
  context were surfaced clearly. Studio adds atomic writes, schema versions and
  entity references to that approach.
- Repository and transaction boundaries. These are retained conceptually even
  though the first Studio repository uses local SQLite rather than the legacy
  PostgreSQL-oriented models.

## Ideas adapted or replaced

| Legacy mechanism | Studio decision | Reason |
| --- | --- | --- |
| Pages, steps and processes assembled from several JSON groups | One versioned directed flow graph | Visual editing, branching and portable diffs require a single canonical graph. |
| PTB `context.user_data` as the state store | SQLite Session repository | No PTB persistence is configured in `core`; the state would not reliably survive a backend restart. |
| Process-wide UI registry populated by import side effects | Registry per project load | Multiple open projects, script edits and reloads must not leak registrations. |
| PostgreSQL `JSONB` models and dialect-specific inserts | SQLite schema owned by each bot project | The desktop product is local and portable; mechanical reuse would not be cross-dialect. |
| Signal-driven blocking `AppHost` | API-controlled runtime service with graceful `start`/`stop` | Electron must control several bots on Windows, where signal-handler support is limited. |
| Global low-level Telegram bot singleton | Injected Telegram port per runtime | A process can host more than one project and tests require a fake adapter. |
| Arbitrary callbacks handled by pages/steps | Transition IDs in a validated `svc:flow:` protocol | The graph owns sequencing and callback routing. |
| Import-all convention discovery | AST discovery followed by guarded import on execution/validation | It provides source locations and signature errors while reducing accidental side effects during browsing. |

## Not migrated in the first version

- Background and recurring-task workers.
- Notification deduplication and the legacy notification log.
- General page navigation/history outside a flow.
- Object-input wizard helpers and bulk text codecs.
- Legacy JSON import for pages, steps, buttons and notifications.
- PostgreSQL repositories and application-specific identity roles.
- The optional ASGI plugin embedded in a bot runtime; Studio owns one separate
  FastAPI control plane instead.

These features can be migrated only when a Studio use case needs them. They
must enter through project-scoped ports and tests rather than by importing the
legacy global runtime.

## Conditions for archiving `core`

`core` can be archived only after all consumers have either migrated or are
explicitly frozen. In particular:

1. `pipubot` no longer imports `core`, or is pinned to a maintained compatibility
   package.
2. Equivalent messaging, input, templating, callback, notification and
   background use cases have acceptance tests in their new homes.
3. Public contracts and persisted data have an explicit migration path.
4. A deprecation window has been documented.

Until then, removing, renaming or silently changing `core` is out of scope.

## Repository audit note

The audit found a tracked legacy Google OAuth client-secret file under
`pipubot`. No credential values are repeated here. Because `pipubot` is outside
this migration, the Studio change does not edit that file. The credential owner
should revoke and rotate it, then handle history cleanup as a separate security
task.
