from . import assets, events, flows, health, projects, runtime, scripts, settings, tokens, validation

ALL_ROUTERS = (
    health.router,
    projects.router,
    flows.router,
    settings.router,
    tokens.router,
    scripts.router,
    assets.router,
    validation.router,
    validation.alias_router,
    runtime.router,
    events.router,
)

__all__ = ["ALL_ROUTERS"]
