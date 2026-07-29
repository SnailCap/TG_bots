from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .migrations import ContentMigrationError, migrate_content_document
from .models import (
    BlockquoteBlock,
    BotContentDocument,
    CodeBlock,
    ContentBlock,
    ContentInlineNode,
    ContentMark,
    ContentMetadata,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    HardBreakNode,
    LegacyTemplateBlock,
    ParagraphBlock,
    TextNode,
    VariableNode,
    VariableReference,
)


class ContentDocumentError(ValueError):
    pass


def parse_content_document(value: str | bytes | Mapping[str, Any]) -> BotContentDocument:
    if isinstance(value, (str, bytes)):
        try:
            raw = json.loads(value)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ContentDocumentError(f"Invalid content document JSON: {error}") from error
    else:
        raw = value
    if not isinstance(raw, Mapping):
        raise ContentDocumentError("Content document must be a JSON object.")
    try:
        data = migrate_content_document(raw)
    except ContentMigrationError as error:
        raise ContentDocumentError(str(error)) from error

    _reject_unknown(data, {"schemaVersion", "id", "content", "metadata"}, "document")
    metadata = _mapping(data.get("metadata"), "metadata")
    _reject_unknown(
        metadata,
        {"createdAt", "updatedAt", "editorVersion", "source"},
        "metadata",
    )
    blocks = _sequence(data.get("content"), "content")
    return BotContentDocument(
        schema_version=_integer(data.get("schemaVersion"), "schemaVersion"),
        id=_string(data.get("id"), "id"),
        content=tuple(_block(item, f"content[{index}]") for index, item in enumerate(blocks)),
        metadata=ContentMetadata(
            created_at=_string(metadata.get("createdAt"), "metadata.createdAt"),
            updated_at=_string(metadata.get("updatedAt"), "metadata.updatedAt"),
            editor_version=_string(metadata.get("editorVersion"), "metadata.editorVersion"),
            source=_optional_string(metadata.get("source"), "metadata.source"),
        ),
    )


def content_document_to_dict(document: BotContentDocument) -> dict[str, Any]:
    metadata = {
        "createdAt": document.metadata.created_at,
        "updatedAt": document.metadata.updated_at,
        "editorVersion": document.metadata.editor_version,
    }
    if document.metadata.source is not None:
        metadata["source"] = document.metadata.source
    return {
        "schemaVersion": document.schema_version,
        "id": document.id,
        "content": [_block_to_dict(block) for block in document.content],
        "metadata": metadata,
    }


def _block(value: Any, path: str) -> ContentBlock:
    data = _mapping(value, path)
    block_type = _string(data.get("type"), f"{path}.type")
    if block_type in {"paragraph", "blockquote", "expandableBlockquote"}:
        _reject_unknown(data, {"type", "content"}, path)
        raw_content = _sequence(data.get("content", []), f"{path}.content")
        content = tuple(
            _inline(item, f"{path}.content[{index}]")
            for index, item in enumerate(raw_content)
        )
        if block_type == "paragraph":
            return ParagraphBlock(content)
        if block_type == "blockquote":
            return BlockquoteBlock(content)
        return ExpandableBlockquoteBlock(content)
    if block_type == "codeBlock":
        _reject_unknown(data, {"type", "language", "text"}, path)
        return CodeBlock(
            text=_string(data.get("text"), f"{path}.text", allow_empty=True),
            language=_optional_string(data.get("language"), f"{path}.language"),
        )
    if block_type == "legacyTemplate":
        _reject_unknown(data, {"type", "source"}, path)
        return LegacyTemplateBlock(
            source=_string(data.get("source"), f"{path}.source", allow_empty=True)
        )
    raise ContentDocumentError(f"{path}.type has unsupported value '{block_type}'.")


def _inline(value: Any, path: str) -> ContentInlineNode:
    data = _mapping(value, path)
    node_type = _string(data.get("type"), f"{path}.type")
    if node_type == "text":
        _reject_unknown(data, {"type", "text", "marks"}, path)
        return TextNode(
            _string(data.get("text"), f"{path}.text", allow_empty=True),
            _marks(data.get("marks", []), f"{path}.marks"),
        )
    if node_type == "variable":
        _reject_unknown(data, {"type", "variableReference", "marks"}, path)
        reference = _mapping(data.get("variableReference"), f"{path}.variableReference")
        _reject_unknown(
            reference,
            {"path", "fieldId", "source"},
            f"{path}.variableReference",
        )
        return VariableNode(
            VariableReference(
                path=_string(reference.get("path"), f"{path}.variableReference.path"),
                field_id=_optional_string(
                    reference.get("fieldId"), f"{path}.variableReference.fieldId"
                ),
                source=_optional_string(
                    reference.get("source"), f"{path}.variableReference.source"
                ),
            ),
            _marks(data.get("marks", []), f"{path}.marks"),
        )
    if node_type == "customEmoji":
        _reject_unknown(data, {"type", "customEmojiId", "fallbackEmoji"}, path)
        return CustomEmojiNode(
            custom_emoji_id=_string(
                data.get("customEmojiId"), f"{path}.customEmojiId"
            ),
            fallback_emoji=_string(
                data.get("fallbackEmoji"), f"{path}.fallbackEmoji"
            ),
        )
    if node_type == "hardBreak":
        _reject_unknown(data, {"type"}, path)
        return HardBreakNode()
    raise ContentDocumentError(f"{path}.type has unsupported value '{node_type}'.")


def _marks(value: Any, path: str) -> tuple[ContentMark, ...]:
    values = _sequence(value, path)
    result: list[ContentMark] = []
    for index, raw in enumerate(values):
        mark = _mapping(raw, f"{path}[{index}]")
        _reject_unknown(mark, {"type", "href"}, f"{path}[{index}]")
        mark_type = _string(mark.get("type"), f"{path}[{index}].type")
        result.append(
            ContentMark(
                mark_type,
                _optional_string(mark.get("href"), f"{path}[{index}].href"),
            )
        )
    return tuple(result)


def _block_to_dict(block: ContentBlock) -> dict[str, Any]:
    if isinstance(block, (ParagraphBlock, BlockquoteBlock, ExpandableBlockquoteBlock)):
        return {
            "type": block.type,
            "content": [_inline_to_dict(node) for node in block.content],
        }
    if isinstance(block, CodeBlock):
        return {
            "type": block.type,
            **({"language": block.language} if block.language is not None else {}),
            "text": block.text,
        }
    return {"type": block.type, "source": block.source}


def _inline_to_dict(node: ContentInlineNode) -> dict[str, Any]:
    if isinstance(node, TextNode):
        return {
            "type": node.type,
            "text": node.text,
            **({"marks": [_mark_to_dict(mark) for mark in node.marks]} if node.marks else {}),
        }
    if isinstance(node, VariableNode):
        reference = {"path": node.variable_reference.path}
        if node.variable_reference.field_id is not None:
            reference["fieldId"] = node.variable_reference.field_id
        if node.variable_reference.source is not None:
            reference["source"] = node.variable_reference.source
        return {
            "type": node.type,
            "variableReference": reference,
            **({"marks": [_mark_to_dict(mark) for mark in node.marks]} if node.marks else {}),
        }
    if isinstance(node, CustomEmojiNode):
        return {
            "type": node.type,
            "customEmojiId": node.custom_emoji_id,
            "fallbackEmoji": node.fallback_emoji,
        }
    return {"type": node.type}


def _mark_to_dict(mark: ContentMark) -> dict[str, Any]:
    return {
        "type": mark.type,
        **({"href": mark.href} if mark.href is not None else {}),
    }


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContentDocumentError(f"{path} must be an object.")
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContentDocumentError(f"{path} must be an array.")
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContentDocumentError(f"{path} must be an integer.")
    return value


def _string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ContentDocumentError(f"{path} must be {qualifier}.")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    return None if value is None else _string(value, path)


def _reject_unknown(
    value: Mapping[str, Any], allowed: set[str], path: str
) -> None:
    unknown = sorted(str(key) for key in value if key not in allowed)
    if unknown:
        raise ContentDocumentError(
            f"{path} contains unsupported field(s): {', '.join(unknown)}."
        )
