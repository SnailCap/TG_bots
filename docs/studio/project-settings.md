# Project settings and runtime secrets

Project settings are local runtime configuration and deliberately do not extend the v3
resource schema. `resources/` remains the source of truth for the declarative application
graph; credentials stay in the autonomous bot project beside it.

## Telegram bot token

Studio stores the Telegram token as `BOT_TOKEN` in `<project>/.env`. The file is ignored by
the starter's Git and Docker ignore rules. The Studio API never returns the token: it exposes
only a `telegram_bot_token_configured` flag and a revision for optimistic writes.

Saving and clearing the token are path-safe, project-locked, revision-aware writes. Existing
keys and comments in `.env` are preserved; only the `BOT_TOKEN` assignment is changed.

At runtime `BotConfig.from_env(project_root=...)` resolves the token in this order:

1. `BOT_TOKEN` from the host process environment, for production deployment and process managers;
2. `BOT_TOKEN` from `<project>/.env`, for local Studio-managed development.

This keeps production environment injection authoritative while allowing a token saved through
Studio to run the generated bot independently with `python -m <package>`.

## Overlay dialogs

Use `frontend/src/shared/ui/OverlayDialog.tsx` for any temporary full-screen Studio surface.
It owns the backdrop, Escape handling, focus trapping, focus restoration, and backdrop click
dismissal. Feature components provide only their dialog content and a labelled `onClose` action.

The template browser and project settings are both built on this primitive. New overlays should
reuse it rather than implementing another fixed backdrop or modal keyboard handler.
