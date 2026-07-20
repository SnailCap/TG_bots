"""Shared schema v3 project model used by both runtime and Studio."""

from .loader import ProjectLoadError, ProjectLoader
from .inspection import HandlerSourceInspection, inspect_handler_source
from .references import HandlerUsage, find_handler_usages
from .models import (
    ActionSpec,
    BotManifest,
    ButtonSpec,
    CommandSpec,
    CommandsSpec,
    Diagnostic,
    FlowLifecycle,
    FlowSpec,
    HandlerBinding,
    HandlerInvocation,
    ProjectDefinition,
    ScheduleSpec,
    StateSpec,
    ViewSpec,
)
from .validation import (
    ProjectValidationError,
    load_and_validate_project,
    validate_project,
)

__all__ = [
    "ActionSpec",
    "BotManifest",
    "ButtonSpec",
    "CommandSpec",
    "CommandsSpec",
    "Diagnostic",
    "FlowLifecycle",
    "FlowSpec",
    "HandlerBinding",
    "HandlerInvocation",
    "HandlerSourceInspection",
    "HandlerUsage",
    "ProjectDefinition",
    "ProjectLoadError",
    "ProjectLoader",
    "ProjectValidationError",
    "ScheduleSpec",
    "StateSpec",
    "ViewSpec",
    "load_and_validate_project",
    "validate_project",
    "find_handler_usages",
    "inspect_handler_source",
]
