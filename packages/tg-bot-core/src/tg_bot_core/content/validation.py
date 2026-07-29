from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from .models import (
    CONTENT_SCHEMA_VERSION,
    BlockquoteBlock,
    BotContentDocument,
    CodeBlock,
    ContentDiagnostic,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    LegacyTemplateBlock,
    MARK_TYPES,
    ParagraphBlock,
    TextNode,
    VariableNode,
)
from .utf16 import utf16_length


_VARIABLE_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_VARIABLE_SOURCE = re.compile(
    r"^{{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*}}$"
)
_ALLOWED_LINK_SCHEMES = frozenset({"http", "https", "tg", "mailto"})
_CONTENT_SOURCES = frozenset({"botstudio", "telegram-import", "legacy-content"})


def is_safe_link(value: str) -> bool:
    if not value or any(
        character.isspace() or unicodedata.category(character).startswith("C")
        for character in value
    ):
        return False
    try:
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        if scheme not in _ALLOWED_LINK_SCHEMES:
            return False
        if scheme in {"http", "https"}:
            return bool(parsed.netloc and parsed.hostname)
        if scheme == "mailto":
            return bool(parsed.path.strip("/"))
        return bool(parsed.netloc or parsed.path.strip("/"))  # tg://... or tg:...
    except ValueError:
        return False


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
    if not document.metadata.created_at.strip() or not document.metadata.updated_at.strip():
        issue(
            "content_metadata_timestamp_empty",
            "Content metadata timestamps cannot be empty.",
            "metadata",
        )
    if not document.metadata.editor_version.strip():
        issue(
            "content_editor_version_empty",
            "Content editorVersion cannot be empty.",
            "metadata.editorVersion",
        )
    if (
        document.metadata.source is not None
        and document.metadata.source not in _CONTENT_SOURCES
    ):
        issue(
            "content_source_invalid",
            f"Unsupported content source '{document.metadata.source}'.",
            "metadata.source",
        )
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
                if isinstance(node, TextNode) and _has_lone_surrogate(node.text):
                    issue(
                        "invalid_unicode",
                        "Text cannot contain an unpaired UTF-16 surrogate.",
                        f"{path}.text",
                    )
                if isinstance(node, VariableNode):
                    reference = node.variable_reference
                    if not _VARIABLE_PATH.fullmatch(reference.path):
                        issue(
                            "invalid_variable_path",
                            "Variable path must be a dotted Jinja identifier.",
                            f"{path}.variableReference.path",
                        )
                    if reference.source is not None:
                        source_match = _VARIABLE_SOURCE.fullmatch(reference.source)
                        if (
                            source_match is None
                            or source_match.group(1) != reference.path
                        ):
                            issue(
                                "invalid_variable_source",
                                "Variable source must be a simple Jinja reference to the same path.",
                                f"{path}.variableReference.source",
                            )
                if isinstance(node, CustomEmojiNode):
                    if not node.custom_emoji_id.isdigit():
                        issue(
                            "invalid_custom_emoji_id",
                            "Custom emoji id must contain digits only.",
                            f"{path}.customEmojiId",
                        )
                    if not is_valid_custom_emoji_fallback(node.fallback_emoji):
                        issue(
                            "invalid_custom_emoji_fallback",
                            "Custom emoji fallback must be a short visible Unicode value.",
                            f"{path}.fallbackEmoji",
                        )
        elif isinstance(block, CodeBlock) and block.language is not None:
            if (
                len(block.language) > 64
                or any(character in block.language for character in "\r\n\x00")
            ):
                issue(
                    "invalid_code_language",
                    "Code block language must be a short single-line value.",
                    f"{block_path}.language",
                )
        if isinstance(block, CodeBlock) and _has_lone_surrogate(block.text):
            issue(
                "invalid_unicode",
                "Code block text cannot contain an unpaired UTF-16 surrogate.",
                f"{block_path}.text",
            )
        if isinstance(block, LegacyTemplateBlock) and _has_lone_surrogate(block.source):
            issue(
                "invalid_unicode",
                "Legacy template source cannot contain an unpaired UTF-16 surrogate.",
                f"{block_path}.source",
            )
    return tuple(diagnostics)


def is_valid_custom_emoji_fallback(value: str) -> bool:
    if not value or utf16_length(value) > 32:
        return False
    if not all(
        not unicodedata.category(character).startswith("C")
        or character == "\u200d"  # zero-width joiner in composed emoji
        or 0xE0020 <= ord(character) <= 0xE007F  # emoji tag sequences
        for character in value
    ):
        return False

    codepoints = [ord(character) for character in value]
    if all(0x1F1E6 <= codepoint <= 0x1F1FF for codepoint in codepoints):
        return len(codepoints) == 2
    if (
        len(codepoints) in {2, 3}
        and chr(codepoints[0]) in "#*0123456789"
        and codepoints[-1] == 0x20E3
    ):
        return len(codepoints) == 2 or codepoints[1] == 0xFE0F
    if (
        len(codepoints) >= 3
        and codepoints[0] == 0x1F3F4
        and codepoints[-1] == 0xE007F
    ):
        return all(0xE0020 <= codepoint <= 0xE007E for codepoint in codepoints[1:-1])

    index = _consume_emoji_component(codepoints, 0)
    if index is None:
        return False
    while index < len(codepoints):
        if codepoints[index] != 0x200D:
            return False
        index = _consume_emoji_component(codepoints, index + 1)
        if index is None:
            return False
    return True


def _consume_emoji_component(codepoints: list[int], index: int) -> int | None:
    if index >= len(codepoints):
        return None
    base = codepoints[index]
    if 0x1F3FB <= base <= 0x1F3FF or not _is_emoji_base(base):
        return None
    index += 1
    if index < len(codepoints) and codepoints[index] in {0xFE0E, 0xFE0F}:
        index += 1
    if index < len(codepoints) and 0x1F3FB <= codepoints[index] <= 0x1F3FF:
        index += 1
    return index


def _is_emoji_base(codepoint: int) -> bool:
    return (
        codepoint
        in {
            0x00A9,
            0x00AE,
            0x203C,
            0x2049,
            0x2122,
            0x2139,
            0x2328,
            0x23CF,
            0x24C2,
            0x3030,
            0x303D,
            0x3297,
            0x3299,
        }
        or 0x2194 <= codepoint <= 0x2199
        or 0x21A9 <= codepoint <= 0x21AA
        or 0x231A <= codepoint <= 0x231B
        or 0x23E9 <= codepoint <= 0x23F3
        or 0x23F8 <= codepoint <= 0x23FA
        or 0x25AA <= codepoint <= 0x25AB
        or codepoint in {0x25B6, 0x25C0}
        or 0x25FB <= codepoint <= 0x25FE
        or 0x2600 <= codepoint <= 0x27BF
        or 0x2934 <= codepoint <= 0x2935
        or 0x2B05 <= codepoint <= 0x2B07
        or 0x2B1B <= codepoint <= 0x2B1C
        or codepoint in {0x2B50, 0x2B55}
        or 0x1F000 <= codepoint <= 0x1FAFF
    )


def _has_lone_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
