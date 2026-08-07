from __future__ import annotations

import json
import keyword
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Generic, Mapping, TypeVar

from .project import ProjectDefinition, VARIABLE_UNSET, VariableDefinition, VariableOwner

T = TypeVar("T")


class VariableError(RuntimeError):
    """Base error for managed resource-variable access and resolution."""


class UnknownVariableError(VariableError):
    pass


class VariableAccessError(VariableError):
    pass


class VariableTypeError(VariableError, TypeError):
    pass


class MissingVariableError(VariableError):
    pass


@dataclass(frozen=True, slots=True)
class VariableRef(Generic[T]):
    id: str
    path: str


@dataclass(frozen=True, slots=True)
class ResourceVariableContext:
    bot_id: str
    flow_id: str | None = None
    state_id: str | None = None
    view_id: str | None = None
    handler_id: str | None = None
    instance_id: str | None = None


def _core_variable(
    variable_id: str,
    path: str,
    value_type: str,
    description: str,
    example: Any,
) -> VariableDefinition:
    return VariableDefinition(
        id=variable_id,
        owner=VariableOwner("bot", "*"),
        path=path,
        type=value_type,
        source="core",
        writable=False,
        example_value=example,
        persistence="user",
        exposed_to_templates=True,
        description=description,
    )


CORE_VARIABLE_DEFINITIONS: tuple[VariableDefinition, ...] = (
    _core_variable("core.user.first_name", "user.first_name", "string", "Telegram first name", "Anna"),
    _core_variable("core.user.last_name", "user.last_name", "string", "Telegram last name", "Petrova"),
    _core_variable("core.user.username", "user.username", "string", "Telegram username", "anna"),
    _core_variable("core.user.telegram_id", "user.telegram_id", "number", "Telegram user ID", 123456789),
    _core_variable("core.user.language_code", "user.language_code", "string", "Telegram language code", "en"),
)


class VariableCatalog:
    """Unified, immutable catalog for core and project-defined variables."""

    def __init__(self, project: ProjectDefinition) -> None:
        # Core identities and paths are reserved even when an invalid project is
        # inspected before the validator has had a chance to reject it.
        definitions = [*project.variable_definitions.values(), *CORE_VARIABLE_DEFINITIONS]
        self._by_id = MappingProxyType({item.id: item for item in definitions})
        by_path: dict[str, VariableDefinition] = {}
        for definition in definitions:
            by_path[definition.path] = definition
            for alias in definition.legacy_paths:
                by_path.setdefault(alias, definition)
        self._by_path = MappingProxyType(by_path)

    def get(self, reference: VariableRef[Any] | str) -> VariableDefinition:
        if isinstance(reference, VariableRef):
            definition = self._by_id.get(reference.id)
            if definition is not None:
                return definition
            reference = reference.path
        definition = self._by_id.get(reference) or self._by_path.get(reference)
        if definition is None:
            raise UnknownVariableError(f"Unknown variable '{reference}'.")
        return definition

    def available(self, context: ResourceVariableContext) -> tuple[VariableDefinition, ...]:
        return tuple(
            sorted(
                (item for item in self._by_id.values() if self.is_available(item, context)),
                key=lambda item: (item.source != "core", item.path, item.id),
            )
        )

    def all(self) -> tuple[VariableDefinition, ...]:
        return tuple(
            sorted(
                self._by_id.values(),
                key=lambda item: (item.source != "core", item.path, item.id),
            )
        )

    @staticmethod
    def is_available(
        definition: VariableDefinition, context: ResourceVariableContext
    ) -> bool:
        if definition.source == "core":
            return True
        owner = definition.owner
        if owner.type == "bot":
            return owner.id == context.bot_id
        if owner.type == "flow":
            return owner.id == context.flow_id
        if owner.type == "state":
            return bool(
                context.flow_id
                and context.state_id
                and owner.id == f"{context.flow_id}.{context.state_id}"
            )
        if owner.type == "view":
            return owner.id == context.view_id
        if owner.type == "handler":
            return owner.id == context.handler_id
        return False


class VariableValues:
    """Controlled view over managed values available to one resource execution."""

    __slots__ = ("_catalog", "_context", "_values", "_system_values")

    def __init__(
        self,
        catalog: VariableCatalog,
        context: ResourceVariableContext,
        values: Mapping[str, Any] | None = None,
        system_values: Mapping[str, Any] | None = None,
    ) -> None:
        self._catalog = catalog
        self._context = context
        self._values = deepcopy(dict(values or {}))
        self._system_values = dict(system_values or {})

    def get(self, reference: VariableRef[T] | str, default: T | None = None) -> T | None:
        definition = self._definition(reference)
        found, value = self._read(definition)
        if found:
            return deepcopy(value)
        if definition.default_value is not VARIABLE_UNSET:
            return deepcopy(definition.default_value)
        if definition.required and default is None:
            raise MissingVariableError(
                f"Required variable '{definition.path}' has no value in {self._context.bot_id}."
            )
        return deepcopy(default)

    def has(self, reference: VariableRef[Any] | str) -> bool:
        definition = self._definition(reference)
        found, _value = self._read(definition)
        return found or definition.default_value is not VARIABLE_UNSET

    def set(self, reference: VariableRef[T] | str, value: T) -> None:
        definition = self._definition(reference)
        if not definition.writable or definition.source != "custom":
            raise VariableAccessError(f"Variable '{definition.path}' is read-only.")
        _validate_variable_value(definition, value)
        self._values[self._storage_key(definition)] = deepcopy(value)

    def unset(self, reference: VariableRef[Any] | str) -> None:
        definition = self._definition(reference)
        if not definition.writable or definition.source != "custom":
            raise VariableAccessError(f"Variable '{definition.path}' is read-only.")
        self._values.pop(self._storage_key(definition), None)

    def list(self) -> tuple[VariableDefinition, ...]:
        return self._catalog.available(self._context)

    def _definition(self, reference: VariableRef[Any] | str) -> VariableDefinition:
        definition = self._catalog.get(reference)
        if not self._catalog.is_available(definition, self._context):
            raise VariableAccessError(
                f"Variable '{definition.path}' is not available to the current resource."
            )
        return definition

    def _read(self, definition: VariableDefinition) -> tuple[bool, Any]:
        if definition.source == "core":
            if definition.path in self._system_values:
                value = self._system_values[definition.path]
                return True, value
            return False, None
        key = self._storage_key(definition)
        return key in self._values, self._values.get(key)

    def _storage_key(self, definition: VariableDefinition) -> str:
        instance = (
            self._context.instance_id or "default"
            if definition.persistence == "resource"
            else definition.persistence
        )
        return ":".join(
            (
                definition.persistence,
                definition.owner.type,
                definition.owner.id,
                instance,
                definition.id,
            )
        )

    def _snapshot(self) -> dict[str, Any]:
        return deepcopy(self._values)


def render_variable_context(
    catalog: VariableCatalog,
    context: ResourceVariableContext,
    managed_values: Mapping[str, Any] | None,
    system_values: Mapping[str, Any],
    state_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one renderer context from the same rules used by ``ctx.vars``."""

    result = deepcopy(dict(state_values or {}))
    values = VariableValues(catalog, context, managed_values, system_values)
    for definition in catalog.available(context):
        if not definition.exposed_to_templates:
            continue
        found, value = values._read(definition)
        if not found and definition.default_value is not VARIABLE_UNSET:
            found, value = True, definition.default_value
        if not found:
            if definition.required:
                raise MissingVariableError(
                    f"Required variable '{definition.path}' has no value for resource context."
                )
            continue
        _set_path(result, definition.path, deepcopy(value))
        for alias in definition.legacy_paths:
            _set_path(result, alias, deepcopy(value))
    return result


def set_render_alias(values: dict[str, Any], source_path: str, target_path: str) -> None:
    found, value = _get_path(values, target_path)
    if found:
        _set_path(values, source_path, deepcopy(value))


def preview_variable_context(
    catalog: VariableCatalog,
    context: ResourceVariableContext,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for definition in catalog.available(context):
        if not definition.exposed_to_templates:
            continue
        value = definition.example_value
        if value is VARIABLE_UNSET:
            value = definition.default_value
        if value is not VARIABLE_UNSET:
            _set_path(result, definition.path, deepcopy(value))
    _deep_merge(result, dict(overrides or {}))
    return result


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value


def _get_path(values: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = values
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _deep_merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _validate_variable_value(definition: VariableDefinition, value: Any) -> None:
    valid = False
    if definition.type == "string":
        valid = isinstance(value, str)
    elif definition.type == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif definition.type == "boolean":
        valid = isinstance(value, bool)
    elif definition.type == "object":
        valid = isinstance(value, Mapping)
    elif definition.type == "array":
        valid = isinstance(value, (list, tuple))
    elif definition.type == "date":
        valid = isinstance(value, str) and _is_date(value)
    elif definition.type == "datetime":
        valid = isinstance(value, str) and _is_datetime(value)
    if not valid:
        raise VariableTypeError(
            f"Variable '{definition.path}' expects {definition.type}, got {type(value).__name__}."
        )
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise VariableTypeError(
            f"Variable '{definition.path}' value must be JSON-serializable."
        ) from error


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def generate_variable_module(project: ProjectDefinition) -> str:
    """Generate an autocomplete-friendly projection; resources remain authoritative."""

    catalog = VariableCatalog(project)
    tree: dict[str, Any] = {}
    for definition in catalog.available(
        ResourceVariableContext(project.manifest.id)
    ):
        _add_generated_reference(tree, definition)
    for definition in project.variable_definitions.values():
        _add_generated_reference(tree, definition)
    lines = [
        '"""Generated from resources/variables.json. Do not edit by hand."""',
        "",
        "from tg_bot_core import VariableRef",
        "",
        "",
        "class Vars:",
    ]
    _emit_generated_tree(lines, tree, indent=1)
    return "\n".join(lines).rstrip() + "\n"


def _add_generated_reference(tree: dict[str, Any], definition: VariableDefinition) -> None:
    current = tree
    for part in definition.path.split(".")[:-1]:
        current = current.setdefault(_python_name(part), {})
    current[_python_name(definition.path.split(".")[-1])] = definition


def _emit_generated_tree(lines: list[str], tree: dict[str, Any], *, indent: int) -> None:
    prefix = "    " * indent
    if not tree:
        lines.append(f"{prefix}pass")
        return
    for name, value in sorted(tree.items()):
        if isinstance(value, dict):
            lines.append(f"{prefix}class {name}:")
            _emit_generated_tree(lines, value, indent=indent + 1)
        else:
            python_type = {
                "string": "str",
                "number": "float",
                "boolean": "bool",
                "object": "dict[str, object]",
                "array": "list[object]",
                "date": "str",
                "datetime": "str",
            }.get(value.type, "object")
            lines.append(
                f'{prefix}{name} = VariableRef[{python_type}]("{value.id}", "{value.path}")'
            )


def _python_name(value: str) -> str:
    normalized = re.sub(r"\W", "_", value)
    if keyword.iskeyword(normalized):
        return f"{normalized}_"
    return normalized
