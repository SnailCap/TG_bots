# Telegram Bot Studio

Telegram Bot Studio is a local low-code IDE and persistent runtime for building
one Telegram bot per portable project. The new implementation lives alongside
the preserved `core/` reference:

- `backend/` — FastAPI, project storage, SQLite runtime, PTB long polling and
  the Python action SDK;
- `frontend/` — Electron, React, React Flow, Monaco, Inspector and Console;
- `docs/` — architecture, tutorials, development, testing and packaging notes.

`pipubot/` is an unrelated legacy project and is intentionally unchanged.

## Quick start (Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"

Set-Location .\frontend
npm ci
npm run dev
```

Create or choose an empty directory for each bot project. Telegram tokens are
validated with Telegram and stored in the operating-system keyring; project
JSON contains only a secret reference.

Start with [the first-bot tutorial](docs/first-bot-tutorial.md). See
[development setup](docs/development.md), [testing](docs/testing.md),
[architecture](docs/architecture.md) and [packaging notes](docs/packaging.md)
for the complete handoff.
