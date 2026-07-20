from __future__ import annotations

import ast
import keyword
import re
from dataclasses import dataclass
from pathlib import Path

from .models import Diagnostic, HandlerBinding


_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_CONTEXTS = {
    "button": "ButtonContext",
    "message": "MessageContext",
    "command": "CommandContext",
    "lifecycle": "LifecycleContext",
    "task": "TaskContext",
}


@dataclass(frozen=True, slots=True)
class HandlerSourceInspection:
    status: str
    source_path: str | None
    message: str | None = None
    diagnostic_code: str | None = None
    line: int | None = None
    column: int | None = None

    def diagnostic(self, binding: HandlerBinding) -> Diagnostic | None:
        if self.diagnostic_code is None or self.message is None:
            return None
        return Diagnostic(
            "error",
            self.diagnostic_code,
            self.message,
            source_path=self.source_path or binding.source_path,
            entity_id=binding.id,
        )


def inspect_handler_source(
    project_root: Path,
    package: str,
    binding: HandlerBinding,
) -> HandlerSourceInspection:
    """Inspect one explicit binding without importing project code."""

    if (
        not _MODULE.fullmatch(binding.module)
        or any(keyword.iskeyword(part) for part in binding.module.split("."))
        or not binding.module.startswith(f"{package}.")
    ):
        return HandlerSourceInspection(
            "invalid_module",
            None,
            f"Handler '{binding.id}' module must be inside package '{package}'.",
            "invalid_handler_module",
        )

    relative = Path("src").joinpath(*binding.module.split(".")).with_suffix(".py")
    source_root = (project_root / "src").resolve()
    source = (project_root / relative).resolve(strict=False)
    source_path = relative.as_posix()
    if not source.is_relative_to(source_root):
        return HandlerSourceInspection(
            "invalid_module",
            source_path,
            f"Handler '{binding.id}' escapes the project source root.",
            "invalid_handler_module",
        )
    if not source.is_file():
        return HandlerSourceInspection(
            "missing_file",
            source_path,
            f"Handler '{binding.id}' module file is missing.",
            "handler_file_missing",
        )
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except (OSError, SyntaxError) as error:
        return HandlerSourceInspection(
            "invalid_module",
            source_path,
            f"Cannot parse handler '{binding.id}': {error}",
            "handler_module_invalid",
        )
    symbol = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == binding.symbol
        ),
        None,
    )
    if symbol is None:
        return HandlerSourceInspection(
            "missing_symbol",
            source_path,
            f"Handler '{binding.id}' symbol '{binding.symbol}' is missing.",
            "handler_symbol_missing",
        )
    line, column = symbol.lineno, symbol.col_offset + 1
    signature_error = _signature_error(symbol, binding.kind)
    if signature_error:
        return HandlerSourceInspection(
            "invalid_signature",
            source_path,
            f"Handler '{binding.id}' {signature_error}",
            "handler_signature_invalid",
            line,
            column,
        )
    return HandlerSourceInspection("ready", source_path, line=line, column=column)


def _signature_error(
    symbol: ast.FunctionDef | ast.AsyncFunctionDef,
    kind: str,
) -> str | None:
    if not isinstance(symbol, ast.AsyncFunctionDef):
        return "must be async."
    positional = [*symbol.args.posonlyargs, *symbol.args.args]
    if (
        len(positional) != 1
        or symbol.args.vararg
        or symbol.args.kwarg
        or symbol.args.kwonlyargs
    ):
        return "must accept exactly one context argument."
    annotation = _annotation_name(positional[0].annotation)
    expected = _CONTEXTS.get(kind)
    if expected and annotation != expected:
        return f"expects {expected}, got {annotation or 'no context annotation'}."
    return_annotation = _annotation_name(symbol.returns)
    if return_annotation != "HandlerResult":
        return f"must return HandlerResult, got {return_annotation or 'no return annotation'}."
    return None


def _annotation_name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.rsplit(".", 1)[-1]
    return None
