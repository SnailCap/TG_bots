# Backend architecture

The backend is a Python 3.12 FastAPI control plane. It owns all project,
validation, secret, runtime and Telegram behavior; Electron/React is a client of
its versioned HTTP and SSE API.

## Package layout

```text
backend/
├── app/
│   ├── api/                 FastAPI composition, schemas and routers
│   ├── application/         project/flow/settings/script use cases
│   ├── domain/              models, enums and ports
│   ├── infrastructure/      filesystem, SQLite, keyring, PTB and event adapters
│   ├── runtime/             graph execution and lifecycle
│   └── sdk/                 stable action-facing types
├── bot_engine/              facade imported by project scripts
├── tests/
└── pyproject.toml
```

Dependencies point inward. Domain modules do not import FastAPI, SQLite,
python-telegram-bot or frontend types. Application services coordinate domain
ports. Infrastructure implements those ports, while API routers translate
transport schemas to application calls.

## Domain

The domain contains immutable or explicitly mutable dataclasses for projects,
flows, nodes, transitions, sessions, runtime status/results, script actions and
validation issues. `StrEnum` values form the persisted vocabulary for node,
transition, session and runtime states.

Protocols under `app/domain/ports` define project storage, secrets, sessions,
runtime key/value/history storage, token validation and event publication. This
keeps the graph executor testable with in-memory or fake adapters.

## Application services

Each service implements bounded use cases:

- `ProjectApplicationService` creates, opens, renames and tracks recent projects;
- `FlowApplicationService` performs flow CRUD through the project repository;
- `SettingsApplicationService` updates entry behavior and validates/stores the
  Telegram token;
- `ScriptApplicationService` owns source CRUD, AST discovery, import validation,
  action listings and usage search;
- `AssetApplicationService` performs path-safe asset operations;
- `ValidationApplicationService` combines project, flow, script and binding
  validation for the editor; runtime startup performs its own equivalent
  preflight at the execution boundary.

Services publish structured events but do not know about HTTP responses or React
state.

## API and composition

`AppContainer` is the composition root. The default container wires the
filesystem repository, recent-project index, OS keyring, Telegram token
validator, SQLite runtime repositories, in-memory event bus and
`RuntimeManager`. Tests can replace any of these with deterministic fakes.

`create_app(container)` makes dependency injection explicit and lets API tests
run without the real keyring or Telegram network. Routers live below `/api/v1`:

| Area | Representative endpoints |
| --- | --- |
| health | `GET /health` |
| projects | create/open/list/recent/get/rename and project tree CRUD |
| flows | list/create/get/save/delete |
| settings/token | project settings, secure token set/delete/validate |
| scripts | source CRUD, validation, actions, usages and search |
| assets | content and file operations below `assets/` |
| validation | project validation report |
| runtime | run, stop, status and persisted logs |
| events | global or project-filtered SSE stream |

Pydantic request/response schemas are deliberately separate from domain
dataclasses. Errors are converted into a stable JSON error response by central
handlers. CORS accepts the Electron file origin and loopback development
origins; the API is still intended as a local control plane in version one.

FastAPI lifespan cleanup stops every active runtime. This is important in the
desktop process model because closing Electron also terminates the child backend
and should release Telegram polling before process exit.

## Project filesystem

`FilesystemProjectRepository` stores portable UTF-8 `bot.json`, flow JSON,
Python scripts and assets. Writes use a sibling temporary file followed by an
atomic replace. All user-controlled relative paths are resolved below the
appropriate project root; absolute paths, drive prefixes and traversal are
rejected.

The recent-project index belongs to Studio application data, not a project. A
recent entry can be reopened lazily after a backend restart. Unknown schema
versions and malformed files surface as typed errors and are not rewritten.

## Secrets

Project JSON contains only `secret_ref`. `KeyringSecretStore` reads and writes
the actual Telegram token through the operating-system credential store. There
is no plaintext fallback. Token validation calls Telegram `getMe`, then stores
only non-secret bot identity in `bot.json`.

Tests use `MemorySecretStore`; this is an injected test adapter, not a production
fallback. Consequently a machine without a functioning keyring backend cannot
configure a production token until its OS credential service is available.

## SQLite runtime storage

Every project gets `.botstudio/runtime.db`. Ordered migrations create:

- `sessions`, including variables and pending input state;
- `runtime_history`, used by logs and Console recovery;
- `kv_storage`, available to project actions;
- `schema_migrations`, recording applied versions.

The SQLite adapter enables foreign keys and a busy timeout, serializes writes,
and uses a tagged JSON codec for values such as `Decimal` and dates. Database
state is project-local but deliberately excluded from the portable definition.

## Runtime boundary

`RuntimeManager` owns project runtime handles. `StandardRuntimeFactory` composes
one service from repository, Telegram and event ports. `GraphExecutor` contains
flow semantics; `PtbLongPollingAdapter` only converts Telegram updates and
outbound messages. See [runtime.md](runtime.md) for node and session behavior.

This split is the migration seam for remote execution: a future manager may
hold worker/RPC handles while application services, flow documents and frontend
contracts remain unchanged.

## Script boundary

Script discovery parses source before import and reports file/line issues.
Runtime loading is project-scoped and registers decorated actions. Actions are
async, execute behind a timeout/exception boundary and return typed results.
They receive SDK ports instead of PTB or SQLite implementation objects.

Project scripts are trusted code in the backend process, not a hostile-code
sandbox. Package installation, arbitrary dependency management and production
multi-tenant isolation are intentionally outside the first version.

## Extension rules

When adding a capability:

1. add or extend a domain model/port without transport dependencies;
2. implement the use case in an application or runtime service;
3. add an infrastructure adapter behind the port;
4. expose a transport schema/router only at the outer layer;
5. cover domain behavior with fakes and adapter behavior with integration tests.

Do not import Electron contracts into Python domain code, expose a raw database
connection to scripts, or move flow execution decisions into an API router.
