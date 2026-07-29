from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from .models import (
    CONTENT_SCHEMA_VERSION,
    BlockquoteBlock,
    BotContentDocument,
    ContentDiagnostic,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    MARK_TYPES,
    ParagraphBlock,
    TextNode,
    VariableNode,
)
from .utf16 import utf16_length


_VARIABLE_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_ALLOWED_LINK_SCHEMES = frozenset({"http", "https", "tg", "mailto"})


def is_safe_link(value: str) -> bool:
    if not value or any(character in value for character in "\r\n\x00"):
        return False
    parsed = urlparse(value)
    return parsed.scheme.lower() in _ALLOWED_LINK_SCHEMES


def validate_content_document(document: BotContentDocument) -> tuple[ContentDiagnostic, ...]:
    diagnostics: list[ContentDiagnostic] = []

    def issue(code: str, message: str, path: str) -> None:
        diagnostics.append(ContentDiagnostic("error", code, message, path))

    if document.schema_version != CONTENT_SCHEMA_VERSION:
        issue(
            "unsupported_content_schema",
            f"Content schemaVersion must be {CONTENT_SCHEMA_VERSION}.",
            "schemaVersion",
        )
    if not document.id.strip():
        issue("content_id_empty", "Content document id cannot be empty.", "id")
    if not document.content:
        issue("content_empty", "Content document needs at least one paragraph.", "content")

    for block_index, block in enumerate(document.content):
        block_path = f"content[{block_index}]"
        if isinstance(block, (ParagraphBlock, BlockquoteBlock, ExpandableBlockquoteBlock)):
            for node_index, node in enumerate(block.content):
                path = f"{block_path}.content[{node_index}]"
                if isinstance(node, (TextNode, VariableNode)):
                    seen: set[str] = set()
                    for mark_index, mark in enumerate(node.marks):
                        mark_path = f"{path}.marks[{mark_index}]"
                        if mark.type not in MARK_TYPES:
                            issue("unsupported_mark", f"Unsupported mark '{mark.type}'.", mark_path)
                        if mark.type in seen:
                            issue("duplicate_mark", f"Mark '{mark.type}' is duplicated.", mark_path)
                        seen.add(mark.type)
                        if mark.type == "link":
                            if mark.href is None or not is_safe_link(mark.href):
                                issue("unsafe_link", "Link uses an unsupported or unsafe URL.", mark_path)
                        elif mark.href is not None:
                            issue("unexpected_mark_href", "Only link marks may have href.", mark_path)
                    if "code" in seen and len(seen) > 1:
                        issue("code_mark_overlap", "Inline code cannot overlap other marks.", path)
                if isinstance(node, VariableNode):
                    reference = node.variable_reference
                    if not _VARIABLE_PATH.fullmatch(reference.path):
                        issue(
                            "invalid_variable_path",
                            "Variable path must be a dotted Jinja identifier.",
                            f"{path}.variableReference.path",
                        )
                    if reference.source is not None and not reference.source.strip():
                        issue(
                            "invalid_variable_source",
                            "Variable source cannot be blank.",
                            f"{path}.variableReference.source",
                        )
                if isinstance(node, CustomEmojiNode):
                    if not node.custom_emoji_id.isdigit():
                        issue(
                            "invalid_custom_emoji_id",
                            "Custom emoji id must contain digits only.",
                            f"{path}.customEmojiId",
                        )
                    if not _valid_fallback(node.fallback_emoji):
                        issue(
                            "invalid_custom_emoji_fallback",
                            "Custom emoji fallback must be a short visible Unicode value.",
                            f"{path}.fallbackEmoji",
                        )
    return tuple(diagnostics)


def _valid_fallback(value: str) -> bool:
    if not value or utf16_length(value) > 32:
        return False
    return all(not unicodedata.category(character).startswith("C") for character in value)
