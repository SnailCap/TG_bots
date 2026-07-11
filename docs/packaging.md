# Packaging notes

The checked-in Electron Builder configuration supports an unpacked Windows
development build and an NSIS installer. It packages the React renderer,
Electron main/preload bundles and backend source as an extra resource.

## Build inputs

Install backend and frontend dependencies first; see
[development.md](development.md). From `frontend/`:

```powershell
# Renderer + Electron bundles, then an unpacked application directory
npm run build

# Windows NSIS installer
npm run package:win
```

Artifacts are written below `frontend\release\`. The application identifier is
`dev.botstudio.telegram` and the product name is `Telegram Bot Studio`.

`npm run build:web` is useful when only renderer/main/preload compilation must
be verified. `npm run build` additionally runs Electron Builder with `--dir`;
`package:win` targets NSIS.

## Packaged resources

Electron Builder includes:

```text
resources/
└── backend/
    ├── app/
    ├── bot_engine/
    └── pyproject.toml
```

Python caches and pytest caches are filtered out. User projects, Telegram
tokens, recent-project data and `.botstudio/runtime.db` are external data and
must never be embedded in the installer.

At runtime the Electron main process resolves the backend directory from
`resources\backend`, starts `python -m uvicorn app.main:app`, hides the child
console window on Windows, forwards output to its own logs, and terminates the
child during app shutdown.

## Important Python limitation

The current package **does not bundle a Python interpreter or install backend
Python dependencies**. It is therefore a developer/test package, not yet a
self-contained end-user distribution.

Runtime interpreter selection is:

1. `BOT_STUDIO_PYTHON`, when set;
2. the repository-root `.venv\Scripts\python.exe` in a source checkout;
3. `python` from `PATH`.

For an unpacked or installed build, point to a Python 3.12 environment that
already contains the backend dependencies:

```powershell
$python = "C:\path\to\bot-studio-venv\Scripts\python.exe"
& $python -m pip install "C:\path\to\checkout\backend"

$env:BOT_STUDIO_PYTHON = $python
& ".\release\win-unpacked\Telegram Bot Studio.exe"
```

The install step supplies FastAPI, Uvicorn, Pydantic, Jinja, keyring and
python-telegram-bot to that interpreter. Backend source itself is read from the
packaged resource directory.

An environment variable set only in a temporary build shell is not a product
installer strategy. Anyone launching the NSIS-installed app later must still
provide an appropriate system/managed Python environment. Document this clearly
when sharing current artifacts.

## Windows packaging prerequisites

- Node.js/npm dependencies installed with `npm ci`;
- enough disk space for Electron, Monaco and unpacked artifacts;
- a Python 3.12 test environment for the packaged smoke test;
- no process holding files in `frontend\release`;
- network access if Electron Builder must download a missing platform binary.

Code signing is not configured in the current project. Unsigned NSIS artifacts
may trigger Windows SmartScreen and are not suitable for public production
distribution.

## Smoke test

Test the unpacked build before producing an installer:

1. set `BOT_STUDIO_PYTHON` to the prepared Python executable;
2. launch `release\win-unpacked\Telegram Bot Studio.exe`;
3. confirm the backend health endpoint reaches `ok` and no second console window
   appears;
4. create a disposable project in a directory outside the package;
5. save/validate a test token, Run and Stop the bot;
6. close the app and verify the Uvicorn child process exits;
7. relaunch and confirm recent projects and SQLite session state are found;
8. inspect the packaged `resources\backend` and verify no credentials,
   `.botstudio` database or user project is present.

Repeat the same checks with the installed NSIS artifact, especially when the
installation directory contains spaces.

## Path to a standalone distribution

A production installer needs one explicit backend-runtime strategy, for
example:

- freeze the backend into a versioned executable (such as PyInstaller/Nuitka),
  then launch that executable from Electron; or
- ship a controlled embedded Python distribution plus locked wheels and an
  integrity-checked bootstrap.

Whichever strategy is selected must include the keyring integration and PTB
dependencies, define backend upgrade/migration behavior, preserve project data
outside application resources, and be covered by a clean-machine Windows test.
Until that work is complete, `BOT_STUDIO_PYTHON`/system Python is a known
packaging limitation rather than a hidden fallback.
