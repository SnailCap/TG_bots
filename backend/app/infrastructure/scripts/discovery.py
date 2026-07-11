from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from app.domain.enums import ValidationSeverity
from app.domain.scripting import ActionParameter, ScriptAction
from app.domain.validation import ValidationIssue
from app.project_imports import isolated_project_imports
from app.sdk import ActionRegistry, get_action_name


@dataclass(frozen=True, slots=True)
class ScriptDiscoveryResult:
    actions: tuple[ScriptAction, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)


class ScriptDiscovery:
    def discover_source(self, relative_path: str, source: str) -> ScriptDiscoveryResult:
        try:
            tree = ast.parse(source, filename=relative_path)
        except SyntaxError as exc:
            return ScriptDiscoveryResult(
                actions=(),
                issues=(
                    self._issue(
                        "script.syntax_error",
                        f"{exc.msg} (line {exc.lineno}, column {exc.offset})",
                        relative_path,
                    ),
                ),
            )
        actions, issues = self._actions_from_ast(relative_path, tree)
        self._append_duplicate_issues(actions, issues)
        return ScriptDiscoveryResult(tuple(actions), tuple(issues))

    def discover(
        self,
        project_root: Path,
        *,
        validate_imports: bool = False,
    ) -> ScriptDiscoveryResult:
        scripts_root = self._scripts_root(project_root)
        actions: list[ScriptAction] = []
        issues: list[ValidationIssue] = []
        parsed_files: list[tuple[Path, ast.Module]] = []

        for path in self._script_files(scripts_root):
            relative = path.relative_to(scripts_root).as_posix()
            public_path = self._public_path(relative)
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative)
            except (OSError, UnicodeError) as exc:
                issues.append(self._issue("script.read_error", str(exc), public_path))
                continue
            except SyntaxError as exc:
                issues.append(
                    self._issue(
                        "script.syntax_error",
                        f"{exc.msg} (line {exc.lineno}, column {exc.offset})",
                        public_path,
                    )
                )
                continue
            parsed_files.append((path, tree))
            file_actions, file_issues = self._actions_from_ast(public_path, tree)
            actions.extend(file_actions)
            issues.extend(file_issues)

        self._append_duplicate_issues(actions, issues)

        if validate_imports:
            for path, _ in parsed_files:
                relative = path.relative_to(scripts_root).as_posix()
                public_path = self._public_path(relative)
                try:
                    module = self._import_module(scripts_root, path, keep=False)
                    self._validate_imported_functions(module, public_path, issues)
                except Exception as exc:
                    issues.append(
                        self._issue(
                            "script.import_error",
                            f"{type(exc).__name__}: {exc}",
                            public_path,
                        )
                    )

        return ScriptDiscoveryResult(
            actions=tuple(sorted(actions, key=lambda item: (item.name, item.file_path))),
            issues=tuple(issues),
        )

    def load_registry(
        self,
        project_root: Path,
    ) -> tuple[ActionRegistry, ScriptDiscoveryResult]:
        result = self.discover(project_root, validate_imports=False)
        registry = ActionRegistry()
        issues = list(result.issues)
        scripts_root = self._scripts_root(project_root)
        if not result.is_valid:
            return registry, result

        for path in self._script_files(scripts_root):
            relative = path.relative_to(scripts_root).as_posix()
            public_path = self._public_path(relative)
            try:
                module = self._import_module(scripts_root, path, keep=True)
                for function in self._registered_functions(module):
                    registry.register(
                        function,
                        module=module.__name__,
                        file_path=public_path,
                        line=inspect.getsourcelines(function)[1],
                    )
            except Exception as exc:
                issues.append(
                    self._issue(
                        "script.import_error",
                        f"{type(exc).__name__}: {exc}",
                        public_path,
                    )
                )

        return registry, ScriptDiscoveryResult(result.actions, tuple(issues))

    def _actions_from_ast(
        self,
        relative_path: str,
        tree: ast.Module,
    ) -> tuple[list[ScriptAction], list[ValidationIssue]]:
        actions: list[ScriptAction] = []
        issues: list[ValidationIssue] = []
        module = relative_path.removesuffix(".py").replace("/", ".")
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = self._decorated_action_name(node)
            if name is None:
                continue
            parameters = tuple(
                ActionParameter(
                    name=argument.arg,
                    annotation=ast.unparse(argument.annotation)
                    if argument.annotation is not None
                    else None,
                    required=index < len(node.args.args) - len(node.args.defaults),
                )
                for index, argument in enumerate(node.args.args)
            )
            action = ScriptAction(
                name=name,
                module=module,
                file_path=relative_path,
                line=node.lineno,
                is_async=isinstance(node, ast.AsyncFunctionDef),
                parameters=parameters,
                docstring=ast.get_docstring(node),
            )
            actions.append(action)
            if not action.is_async:
                issues.append(
                    self._issue(
                        "action.must_be_async",
                        f"Action {name!r} must be declared with async def",
                        relative_path,
                        entity_id=name,
                    )
                )
            positional_count = len(node.args.posonlyargs) + len(node.args.args)
            if (
                positional_count != 1
                or node.args.vararg is not None
                or node.args.kwarg is not None
                or node.args.kwonlyargs
            ):
                issues.append(
                    self._issue(
                        "action.invalid_signature",
                        f"Action {name!r} must accept exactly one ActionContext argument",
                        relative_path,
                        entity_id=name,
                    )
                )
        return actions, issues

    @staticmethod
    def _decorated_action_name(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str | None:
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            function = decorator.func
            is_action = isinstance(function, ast.Name) and function.id == "action"
            is_action = is_action or (
                isinstance(function, ast.Attribute) and function.attr == "action"
            )
            if not is_action:
                continue
            value = decorator.args[0] if decorator.args else None
            if value is None:
                for keyword in decorator.keywords:
                    if keyword.arg == "name":
                        value = keyword.value
                        break
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
        return None

    @staticmethod
    def _append_duplicate_issues(
        actions: list[ScriptAction],
        issues: list[ValidationIssue],
    ) -> None:
        seen: dict[str, ScriptAction] = {}
        for action in actions:
            previous = seen.get(action.name)
            if previous is not None:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="action.duplicate",
                        message=(
                            f"Action {action.name!r} is registered in both "
                            f"{previous.file_path} and {action.file_path}"
                        ),
                        entity_type="action",
                        entity_id=action.name,
                        path=action.file_path,
                    )
                )
            else:
                seen[action.name] = action

    def _import_module(
        self,
        scripts_root: Path,
        path: Path,
        *,
        keep: bool,
    ) -> ModuleType:
        relative = path.relative_to(scripts_root).as_posix()
        project_hash = hashlib.sha256(str(scripts_root).encode("utf-8")).hexdigest()[:12]
        safe_module = re.sub(r"[^A-Za-z0-9_]", "_", relative.removesuffix(".py"))
        module_name = f"_botstudio_{project_hash}_{safe_module}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {relative}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            with isolated_project_imports(scripts_root):
                spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        if not keep:
            sys.modules.pop(module_name, None)
        return module

    def _validate_imported_functions(
        self,
        module: ModuleType,
        relative_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        for function in self._registered_functions(module):
            name = get_action_name(function) or function.__name__
            signature = inspect.signature(function)
            if not inspect.iscoroutinefunction(function) or len(signature.parameters) != 1:
                issues.append(
                    self._issue(
                        "action.invalid_runtime_signature",
                        f"Imported action {name!r} must be async and accept one argument",
                        relative_path,
                        entity_id=name,
                    )
                )

    @staticmethod
    def _registered_functions(module: ModuleType):
        for value in vars(module).values():
            if inspect.isfunction(value) and value.__module__ == module.__name__:
                if get_action_name(value) is not None:
                    yield value

    @staticmethod
    def _script_files(scripts_root: Path) -> tuple[Path, ...]:
        if not scripts_root.is_dir():
            return ()
        return tuple(
            sorted(
                path
                for path in scripts_root.rglob("*.py")
                if path.is_file() and not path.is_symlink()
            )
        )

    @staticmethod
    def _scripts_root(project_root: Path) -> Path:
        return (project_root.expanduser().resolve(strict=False) / "scripts").resolve(
            strict=False
        )

    @staticmethod
    def _public_path(relative_path: str) -> str:
        normalized = relative_path.replace("\\", "/").removeprefix("scripts/")
        return f"scripts/{normalized}"

    @staticmethod
    def _issue(
        code: str,
        message: str,
        path: str,
        *,
        entity_id: str | None = None,
    ) -> ValidationIssue:
        return ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code=code,
            message=message,
            entity_type="action" if entity_id else "script",
            entity_id=entity_id,
            path=path,
        )
