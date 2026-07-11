# Development setup

These instructions target Windows PowerShell, which is also the first supported
desktop development platform.

## Prerequisites

- Python 3.12 (64-bit) with `venv` and `pip`;
- Node.js 22 LTS and npm;
- Git, if working from version control;
- Windows Credential Manager available to Python keyring;
- network access to Telegram only when validating a real token or running a bot.

The new implementation lives in `backend/` and `frontend/`. The existing
`core/` remains a migration reference and `pipubot/` is outside this project's
change scope.

## Install dependencies

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"

Set-Location .\frontend
npm ci
Set-Location ..
```

Using a root `.venv` is convenient because the Electron main process discovers
`..\.venv\Scripts\python.exe` relative to `backend/`. If Python lives elsewhere,
set `BOT_STUDIO_PYTHON` explicitly.

## Run the desktop application

```powershell
Set-Location .\frontend
npm run dev
```

Vite serves the React renderer on `127.0.0.1:5173`, builds the Electron
main/preload entries, and Electron starts FastAPI on `127.0.0.1:8000`. Backend
stdout/stderr is forwarded to the Electron terminal. Closing the desktop app
stops its child backend.

To force a particular interpreter:

```powershell
$env:BOT_STUDIO_PYTHON = (Resolve-Path ..\.venv\Scripts\python.exe).Path
npm run dev
```

## Run backend and UI separately

Manual backend startup is useful for API work:

```powershell
Set-Location <repository-root>
.\.venv\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir .\backend `
  --host 127.0.0.1 `
  --port 8000 `
  --reload
```

Open `http://127.0.0.1:8000/api/docs` for the generated API documentation and
`http://127.0.0.1:8000/api/v1/health` for the health check.

In another PowerShell window, prevent Electron from spawning a duplicate
backend:

```powershell
Set-Location <repository-root>\frontend
$env:BOT_STUDIO_SKIP_BACKEND = "1"
npm run dev
```

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `BOT_STUDIO_PYTHON` | Absolute Python executable used by Electron | root `.venv`, then `python` on `PATH` |
| `BOT_STUDIO_BACKEND_DIR` | Backend source/resource directory | repository `backend/` or packaged resource |
| `BOT_STUDIO_BACKEND_APP` | Uvicorn ASGI import | `app.main:app` |
| `BOT_STUDIO_BACKEND_HOST` | Local API bind host | `127.0.0.1` |
| `BOT_STUDIO_BACKEND_PORT` | Local API port | `8000` |
| `BOT_STUDIO_SKIP_BACKEND` | Set to `1` when the backend is managed separately | unset |
| `BOTSTUDIO_DATA_DIR` | Recent-project index and Studio-local application data | `%LOCALAPPDATA%\TelegramBotStudio` |

Environment variables must be set before starting Electron. The renderer learns
the backend base URL only through the restricted preload bridge.

## Local data

- Portable project definitions are stored in the user-selected project folder.
- Session/history/action state is `<project>\.botstudio\runtime.db`.
- The recent-project index defaults to
  `%LOCALAPPDATA%\TelegramBotStudio\recent-projects.json`.
- Telegram tokens are stored in the operating-system keyring, not the
  repository or project JSON.

For deterministic manual tests, use a fresh empty project directory. Stop its
runtime before copying or deleting `.botstudio/runtime.db`.

## Development workflow

1. Change backend domain/application behavior before adding transport-specific
   code.
2. Keep frontend API normalization in `src/shared/api` and graph translation in
   `flowTransport.ts`.
3. Save project files through backend APIs; do not teach Electron/React to write
   them directly.
4. Add or update focused tests, then run the commands in [testing.md](testing.md).
5. Use Validate and a fake/manual bot flow before packaging.

## Common Windows issues

### `python` or `uvicorn` is not found

Use the full `.venv\Scripts\python.exe` path or set `BOT_STUDIO_PYTHON`. The
interpreter must contain all dependencies from `backend/pyproject.toml`.

### Keyring is unavailable

The production backend intentionally has no plaintext secret fallback. Ensure
the desktop session can access Windows Credential Manager and that `keyring` is
installed in the selected interpreter. Unit tests should inject
`MemorySecretStore` instead.

### Port 8000 or 5173 is already in use

Stop the old process, or change `BOT_STUDIO_BACKEND_PORT` for the API. Vite uses
a strict port 5173 in the checked-in configuration so a second development
renderer fails clearly.

### PowerShell execution policy blocks npm shims

Use `npm.cmd`/`npx.cmd` from PowerShell or adjust the user-level execution policy
according to your organization's rules. No project setting requires disabling
Windows security globally.
