# Testing

The test strategy keeps Telegram and the operating-system keyring out of the
default automated suite. Domain/runtime tests use temporary projects, SQLite,
an in-memory secret store and a fake Telegram adapter.

## Backend tests

After installing `backend[dev]` as described in [development.md](development.md):

```powershell
Set-Location <repository-root>
.\.venv\Scripts\python.exe -m pytest .\backend\tests -q
```

The complete backend suite is also standard-library `unittest` compatible:

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
.\.venv\Scripts\python.exe -m unittest discover `
  -s .\backend\tests `
  -t .\backend `
  -v
```

Coverage is organized around behavior rather than framework internals:

- strict template rendering, input coercion and condition operators;
- deterministic transition selection and missing/ambiguous edges;
- node execution, variables and action result/error handling;
- SQLite session persistence and resume with a new repository/executor;
- a vertical Start -> Ask -> Choice -> Action -> template -> End scenario;
- project create/open and atomic flow/script persistence;
- API composition with injected secret, Telegram and runtime fakes.

Do not use a real Telegram token in automated tests. `FakeTelegramPort`
captures outbound messages and injects updates deterministically without
network access.

## Frontend tests

```powershell
Set-Location <repository-root>\frontend
npm test
```

Vitest runs in jsdom with Testing Library. The focused suite covers flow
serialization, Inspector edits, workspace/tab state, API error normalization
and runtime reducer state. Add tests at the transport/editor boundary whenever
a persisted config field changes; a node that looks correct but serializes the
wrong key is a runtime bug.

Run static and production-renderer checks separately:

```powershell
npx tsc --noEmit
npm run build:web
```

`build:web` verifies the renderer and Electron entry bundling without creating
an installer. A Monaco chunk-size warning is expected and is not a type or build
failure.

## Full local verification

Before handing off a change, run:

```powershell
Set-Location <repository-root>
.\.venv\Scripts\python.exe -m compileall -q .\backend\app .\backend\bot_engine
.\.venv\Scripts\python.exe -m pytest .\backend\tests -q

Set-Location .\frontend
npm test
npx tsc --noEmit
npm run build:web
```

`compileall` is a fast syntax/import-path sanity check, not a replacement for
tests. Installer verification is documented separately in
[packaging.md](packaging.md).

## Manual acceptance scenario

Use one disposable project and a real test bot only for the final acceptance
pass:

1. create/open a project and securely save/validate its token;
2. build a branching flow with Start, Send Message, Ask Input, Choice, Action,
   Condition and End nodes;
3. verify variables in strict templates and both success/error action branches;
4. Run, complete one dialog in Telegram, then inspect Console/history;
5. stop while waiting for input, restart the backend, Run again and continue;
6. switch to a second project and verify its runtime/status is isolated;
7. Stop and confirm polling terminates cleanly.

Never commit the disposable token, runtime database or generated build output.

## Test-writing rules

- Use temporary directories for projects and application data.
- Inject `MemorySecretStore`; assert that API/project JSON never echoes the
  token.
- Use a temporary on-disk SQLite database for migration and restart tests.
- Give every fake update a stable increasing update ID.
- Assert persisted state and emitted events, not private implementation fields.
- Test action exceptions and timeouts without allowing them to stop another
  runtime.
- Keep Electron UI tests focused; business rules belong in backend tests.

When fixing a transport mismatch, add one backend/domain assertion and one
frontend serialization/normalization assertion when both sides participate in
the contract.
