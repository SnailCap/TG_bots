from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .models import (
    BlockquoteBlock,
    BotContentDocument,
    CodeBlock,
    ContentDiagnostic,
    ContentMark,
    ContentMetadata,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    HardBreakNode,
    ParagraphBlock,
    TelegramImportResult,
    TelegramMessageEntity,
    TextNode,
)
from .normalization import normalize_content_document
from .utf16 import utf16_offsets
from .validation import is_safe_link, is_valid_custom_emoji_fallback


_INLINE_MARKS = {
    "bold": "bold",
    "italic": "italic",
    "underline": "underline",
    "strikethrough": "strikethrough",
    "spoiler": "spoiler",
    "code": "code",
    "text_link": "link",
}
_BLOCK_TYPES = frozenset({"blockquote", "expandable_blockquote", "pre"})
_KNOWN_TYPES = frozenset({*_INLINE_MARKS, *_BLOCK_TYPES, "custom_emoji"})


@dataclass(frozen=True, slots=True)
class _ImportedEntity:
    value: TelegramMessageEntity
    start: int
    end: int


def import_telegram_message(
    text: str,
    entities: Sequence[TelegramMessageEntity | Mapping[str, Any]],
    *,
    document_id: str,
    created_at: str = "1970-01-01T00:00:00Z",
    updated_at: str | None = None,
) -> TelegramImportResult:
    warnings: list[ContentDiagnostic] = []
    imported: list[_ImportedEntity] = []
    offsets = utf16_offsets(text)
    offset_to_index = {offset: index for index, offset in enumerate(offsets)}
    for index, raw in enumerate(entities):
        try:
            entity = _coerce_entity(raw)
            start = _index_for_offset(offset_to_index, entity.offset)
            end = _index_for_offset(offset_to_index, entity.offset + entity.length)
        except (KeyError, TypeError, ValueError) as error:
            warnings.append(
                ContentDiagnostic(
                    "warning",
                    "invalid_imported_entity",
                    f"Telegram entity {index} was ignored: {error}",
                    f"entities[{index}]",
                )
            )
            continue
        if entity.type not in _KNOWN_TYPES:
            warnings.append(
                ContentDiagnostic(
                    "warning",
                    "unknown_imported_entity",
                    f"Telegram entity type '{entity.type}' was converted to plain text.",
                    f"entities[{index}]",
                )
            )
            continue
        if entity.type == "text_link" and (
            entity.url is None or not is_safe_link(entity.url)
        ):
            warnings.append(
                ContentDiagnostic(
                    "warning",
                    "unsafe_link_removed",
                    "An imported unsafe link was converted to plain text.",
                    f"entities[{index}]",
                )
            )
            continue
        if entity.type == "custom_emoji" and (
            entity.custom_emoji_id is None
            or not entity.custom_emoji_id.isdigit()
        ):
            warnings.append(
                ContentDiagnostic(
                    "warning",
                    "invalid_custom_emoji_id",
                    "A Telegram custom emoji without a valid numeric id was converted to plain text.",
                    f"entities[{index}]",
                )
            )
            continue
        if entity.type == "custom_emoji" and not is_valid_custom_emoji_fallback(
            text[start:end]
        ):
            warnings.append(
                ContentDiagnostic(
                    "warning",
                    "invalid_custom_emoji_fallback",
                    "A Telegram custom emoji with an invalid fallback span was converted to plain text.",
                    f"entities[{index}]",
                )
            )
            continue
        if (
            entity.type in _BLOCK_TYPES
            and end > start
            and text[end - 1] == "\n"
            and end < len(text)
            and text[end] != "\n"
        ):
            warnings.append(
                ContentDiagnostic(
                    "warning",
                    "block_entity_boundary_normalized",
                    "A block entity's trailing newline was normalized to the document block boundary.",
                    f"entities[{index}]",
                )
            )
        imported.append(_ImportedEntity(entity, start, end))

    line_records: list[tuple[int, int, _ImportedEntity | None]] = []
    cursor = 0
    lines = text.split("\n")
    for line_index, line in enumerate(lines):
        start = cursor
        end = start + len(line)
        start_offset, end_offset = offsets[start], offsets[end]
        block_entity = next(
            (
                item
                for item in imported
                if item.value.type in _BLOCK_TYPES
                and item.value.offset <= start_offset
                and item.value.offset + item.value.length >= end_offset
                and (
                    end_offset > start_offset
                    or item.value.offset <= start_offset
                    < item.value.offset + item.value.length
                    or (
                        start > 0
                        and text[start - 1] == "\n"
                        and item.value.offset + item.value.length == start_offset
                    )
                )
            ),
            None,
        )
        line_records.append((start, end, block_entity))
        cursor = end + (1 if line_index < len(lines) - 1 else 0)

    blocks = []
    line_index = 0
    while line_index < len(line_records):
        start, end, block_entity = line_records[line_index]
        if block_entity is not None:
            last_index = line_index
            while (
                last_index + 1 < len(line_records)
                and line_records[last_index + 1][2] is block_entity
            ):
                last_index += 1
            end = line_records[last_index][1]
            value = block_entity.value
            if value.type == "pre":
                blocks.append(CodeBlock(text[start:end], value.language))
            else:
                content = _inline_nodes(text, start, end, imported)
                if value.type == "blockquote":
                    blocks.append(BlockquoteBlock(content))
                else:
                    blocks.append(ExpandableBlockquoteBlock(content))
            line_index = last_index + 1
        else:
            content = _inline_nodes(text, start, end, imported)
            blocks.append(ParagraphBlock(content))
            line_index += 1

    document = normalize_content_document(
        BotContentDocument(
            1,
            document_id,
            tuple(blocks),
            ContentMetadata(
                created_at,
                updated_at or created_at,
                "telegram-import",
                "telegram-import",
            ),
        )
    )
    return TelegramImportResult(document, tuple(warnings))


def _index_for_offset(offsets: Mapping[int, int], offset: int) -> int:
    try:
        return offsets[offset]
    except KeyError as error:
        raise ValueError(
            "UTF-16 offset does not fall on a Unicode boundary."
        ) from error


def _inline_nodes(
    text: str,
    start: int,
    end: int,
    entities: list[_ImportedEntity],
):
    boundaries = {start, end}
    relevant = []
    for item in entities:
        if item.value.type in _BLOCK_TYPES or item.end <= start or item.start >= end:
            continue
        boundaries.add(max(start, item.start))
        boundaries.add(min(end, item.end))
        relevant.append(item)
    ordered = sorted(boundaries)
    nodes = []
    for left, right in zip(ordered, ordered[1:]):
        if right <= left:
            continue
        segment = text[left:right]
        custom = next(
            (
                item
                for item in relevant
                if item.value.type == "custom_emoji"
                and item.start == left
                and item.end == right
                and item.value.custom_emoji_id
            ),
            None,
        )
        if custom is not None:
            nodes.append(CustomEmojiNode(custom.value.custom_emoji_id or "", segment))
            continue
        marks: list[ContentMark] = []
        for item in relevant:
            if item.start <= left and item.end >= right and item.value.type in _INLINE_MARKS:
                kind = _INLINE_MARKS[item.value.type]
                marks.append(
                    ContentMark(kind, item.value.url if kind == "link" else None)
                )
        _append_text_segment(nodes, segment, tuple(marks))
    return tuple(nodes)


def _append_text_segment(
    output: list,
    value: str,
    marks: tuple[ContentMark, ...],
) -> None:
    parts = value.split("\n")
    for index, part in enumerate(parts):
        if part:
            output.append(TextNode(part, marks))
        if index < len(parts) - 1:
            output.append(HardBreakNode())


def _coerce_entity(
    value: TelegramMessageEntity | Mapping[str, Any],
) -> TelegramMessageEntity:
    if isinstance(value, TelegramMessageEntity):
        _validate_entity_shape(value.type, value.offset, value.length)
        for name, optional in (
            ("url", value.url),
            ("language", value.language),
            ("custom_emoji_id", value.custom_emoji_id),
        ):
            if optional is not None and not isinstance(optional, str):
                raise TypeError(f"{name} must be a string when present")
        return value
    entity_type = value["type"]
    offset = value["offset"]
    length = value["length"]
    _validate_entity_shape(entity_type, offset, length)
    return TelegramMessageEntity(
        entity_type,
        offset,
        length,
        url=value.get("url") if isinstance(value.get("url"), str) else None,
        language=(
            value.get("language") if isinstance(value.get("language"), str) else None
        ),
        custom_emoji_id=(
            value.get("custom_emoji_id")
            if isinstance(value.get("custom_emoji_id"), str)
            else value.get("customEmojiId")
            if isinstance(value.get("customEmojiId"), str)
            else None
        ),
    )


def _validate_entity_shape(entity_type: Any, offset: Any, length: Any) -> None:
    if not isinstance(entity_type, str):
        raise TypeError("type must be a string")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise TypeError("offset must be a non-negative integer")
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
        raise TypeError("length must be a positive integer")
