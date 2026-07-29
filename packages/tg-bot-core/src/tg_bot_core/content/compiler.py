from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError

from .legacy import compile_legacy_template
from .models import (
    BlockquoteBlock,
    BotContentDocument,
    CodeBlock,
    CompiledTelegramMessage,
    ContentDiagnostic,
    ContentMark,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    HardBreakNode,
    LegacyTemplateBlock,
    ParagraphBlock,
    TelegramCompileOptions,
    TelegramCompileResult,
    TelegramMessageEntity,
    TextNode,
    VariableNode,
)
from .normalization import normalize_content_document
from .utf16 import utf16_length, utf16_offsets
from .validation import validate_content_document


_ENTITY_TYPES = {
    "bold": "bold",
    "italic": "italic",
    "underline": "underline",
    "strikethrough": "strikethrough",
    "spoiler": "spoiler",
    "code": "code",
    "link": "text_link",
}
@dataclass(slots=True)
class _CompiledBuffer:
    parts: list[str]
    entities: list[TelegramMessageEntity]
    atomic_ranges: list[tuple[int, int]]
    block_boundaries: set[int]
    offset: int = 0

    @classmethod
    def create(cls) -> "_CompiledBuffer":
        return cls([], [], [], set())

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def append(self, value: str) -> tuple[int, int]:
        start = self.offset
        self.parts.append(value)
        self.offset += utf16_length(value)
        return start, self.offset


def compile_content_document(
    document: BotContentDocument,
    variables: Mapping[str, Any],
    options: TelegramCompileOptions | None = None,
) -> TelegramCompileResult:
    options = options or TelegramCompileOptions()
    diagnostics = validate_content_document(document)
    if diagnostics:
        return TelegramCompileResult((), errors=diagnostics)
    if (
        isinstance(options.max_message_length, bool)
        or not isinstance(options.max_message_length, int)
        or options.max_message_length <= 0
    ):
        return TelegramCompileResult(
            (),
            errors=(
                ContentDiagnostic(
                    "error",
                    "invalid_message_limit",
                    "Telegram message limit must be positive.",
                ),
            ),
        )

    normalized = normalize_content_document(document)
    buffer = _CompiledBuffer.create()
    warnings: list[ContentDiagnostic] = []
    errors: list[ContentDiagnostic] = []
    environment = Environment(undefined=StrictUndefined, autoescape=False)
    environment.globals.clear()

    for block_index, block in enumerate(normalized.content):
        block_start = buffer.offset
        if isinstance(block, (ParagraphBlock, BlockquoteBlock, ExpandableBlockquoteBlock)):
            for node_index, node in enumerate(block.content):
                path = f"content[{block_index}].content[{node_index}]"
                if isinstance(node, TextNode):
                    start, end = buffer.append(node.text)
                    _append_mark_entities(buffer.entities, node.marks, start, end)
                elif isinstance(node, VariableNode):
                    try:
                        rendered = _resolve_variable(node, variables, environment)
                    except TemplateError as error:
                        errors.append(
                            ContentDiagnostic(
                                "error",
                                "variable_resolution",
                                f"Could not resolve variable '{node.variable_reference.path}': {error}",
                                path,
                            )
                        )
                        continue
                    start, end = buffer.append(rendered)
                    if end > start:
                        buffer.atomic_ranges.append((start, end))
                        _append_mark_entities(buffer.entities, node.marks, start, end)
                elif isinstance(node, CustomEmojiNode):
                    start, end = buffer.append(node.fallback_emoji)
                    if end > start:
                        buffer.atomic_ranges.append((start, end))
                        buffer.entities.append(
                            TelegramMessageEntity(
                                "custom_emoji",
                                start,
                                end - start,
                                custom_emoji_id=node.custom_emoji_id,
                            )
                        )
                elif isinstance(node, HardBreakNode):
                    buffer.append("\n")

            block_end = buffer.offset
            entity_type = (
                "blockquote"
                if isinstance(block, BlockquoteBlock)
                else "expandable_blockquote"
                if isinstance(block, ExpandableBlockquoteBlock)
                else None
            )
            if entity_type and block_end > block_start:
                buffer.entities.append(
                    TelegramMessageEntity(entity_type, block_start, block_end - block_start)
                )
        elif isinstance(block, CodeBlock):
            start, end = buffer.append(block.text)
            if end > start:
                buffer.atomic_ranges.append((start, end))
                buffer.entities.append(
                    TelegramMessageEntity(
                        "pre", start, end - start, language=block.language
                    )
                )
        elif isinstance(block, LegacyTemplateBlock):
            fragment = compile_legacy_template(block.source, variables)
            warnings.extend(fragment.warnings)
            errors.extend(fragment.errors)
            start, end = buffer.append(fragment.text)
            if end > start:
                # Complex Jinja has no stable source-to-output boundaries. Keeping
                # the whole fragment atomic prevents splitting a resolved value.
                buffer.atomic_ranges.append((start, end))
            for entity in fragment.entities:
                buffer.entities.append(_shift_entity(entity, start))

        if block_index < len(normalized.content) - 1:
            buffer.append("\n")
            buffer.block_boundaries.add(buffer.offset)

    if errors:
        return TelegramCompileResult((), tuple(warnings), tuple(errors))
    text = buffer.text
    if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
        return TelegramCompileResult(
            (),
            tuple(warnings),
            (
                ContentDiagnostic(
                    "error",
                    "invalid_resolved_unicode",
                    "Resolved content contains an unpaired UTF-16 surrogate.",
                ),
            ),
        )
    if not text.strip():
        return TelegramCompileResult(
            (),
            tuple(warnings),
            (
                ContentDiagnostic(
                    "error",
                    "compiled_message_empty",
                    "Content document rendered an empty Telegram message.",
                ),
            ),
        )

    entities = _merge_entities(buffer.entities)
    overlap_error = _entity_overlap_error(entities)
    if overlap_error is not None:
        return TelegramCompileResult((), tuple(warnings), (overlap_error,))
    if utf16_length(text) <= options.max_message_length:
        return TelegramCompileResult(
            (CompiledTelegramMessage(text, entities),), tuple(warnings), ()
        )
    if not options.split_long_messages:
        return TelegramCompileResult(
            (),
            tuple(warnings),
            (
                ContentDiagnostic(
                    "error",
                    "message_too_long",
                    f"Rendered message exceeds {options.max_message_length} UTF-16 units.",
                ),
            ),
        )

    messages, split_error = _split_message(
        text,
        entities,
        [*buffer.atomic_ranges, *_unicode_atomic_ranges(text)],
        buffer.block_boundaries,
        options.max_message_length,
    )
    if split_error is not None:
        return TelegramCompileResult((), tuple(warnings), (split_error,))
    warnings.append(
        ContentDiagnostic(
            "warning",
            "message_split",
            f"Rendered content was split into {len(messages)} Telegram messages.",
        )
    )
    return TelegramCompileResult(tuple(messages), tuple(warnings), ())


def compile_result_to_dict(result: TelegramCompileResult) -> dict[str, Any]:
    def diagnostic(value: ContentDiagnostic) -> dict[str, Any]:
        return {
            "severity": value.severity,
            "code": value.code,
            "message": value.message,
            **({"path": value.path} if value.path is not None else {}),
        }

    return {
        "messages": [
            {
                "text": message.text,
                "entities": [
                    {
                        "type": entity.type,
                        "offset": entity.offset,
                        "length": entity.length,
                        **({"url": entity.url} if entity.url is not None else {}),
                        **(
                            {"language": entity.language}
                            if entity.language is not None
                            else {}
                        ),
                        **(
                            {"custom_emoji_id": entity.custom_emoji_id}
                            if entity.custom_emoji_id is not None
                            else {}
                        ),
                    }
                    for entity in message.entities
                ],
            }
            for message in result.messages
        ],
        "warnings": [diagnostic(value) for value in result.warnings],
        "errors": [diagnostic(value) for value in result.errors],
    }


def _resolve_variable(
    node: VariableNode,
    variables: Mapping[str, Any],
    environment: Environment,
) -> str:
    reference = node.variable_reference
    # ``source`` exists only for lossless legacy serialization. Executing it
    # here would turn a persisted content document into an arbitrary Jinja
    # evaluator. The validated dotted path is the existing variable identity
    # and is the only input used for runtime resolution.
    return environment.from_string(f"{{{{ {reference.path} }}}}").render(**variables)


def _append_mark_entities(
    output: list[TelegramMessageEntity],
    marks: tuple[ContentMark, ...],
    start: int,
    end: int,
) -> None:
    if end <= start:
        return
    for mark in marks:
        output.append(
            TelegramMessageEntity(
                _ENTITY_TYPES[mark.type],
                start,
                end - start,
                url=mark.href if mark.type == "link" else None,
            )
        )


def _shift_entity(entity: TelegramMessageEntity, amount: int) -> TelegramMessageEntity:
    return TelegramMessageEntity(
        entity.type,
        entity.offset + amount,
        entity.length,
        url=entity.url,
        language=entity.language,
        custom_emoji_id=entity.custom_emoji_id,
    )


def _merge_entities(
    entities: list[TelegramMessageEntity],
) -> tuple[TelegramMessageEntity, ...]:
    ordered = sorted(
        (entity for entity in entities if entity.length > 0),
        key=lambda entity: (
            entity.offset,
            -entity.length,
            entity.type,
            entity.url or "",
            entity.language or "",
            entity.custom_emoji_id or "",
        ),
    )
    merged: list[TelegramMessageEntity] = []
    for entity in ordered:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.type == entity.type
            and previous.url == entity.url
            and previous.language == entity.language
            and previous.custom_emoji_id == entity.custom_emoji_id
            and previous.offset + previous.length == entity.offset
        ):
            merged[-1] = TelegramMessageEntity(
                previous.type,
                previous.offset,
                previous.length + entity.length,
                url=previous.url,
                language=previous.language,
                custom_emoji_id=previous.custom_emoji_id,
            )
        else:
            merged.append(entity)
    return tuple(merged)


def _entity_overlap_error(
    entities: tuple[TelegramMessageEntity, ...]
) -> ContentDiagnostic | None:
    for index, left in enumerate(entities):
        left_end = left.offset + left.length
        for right in entities[index + 1 :]:
            right_end = right.offset + right.length
            if right.offset >= left_end or left.offset >= right_end:
                continue
            if left.offset < right.offset < left_end < right_end:
                return ContentDiagnostic(
                    "error",
                    "impossible_entity_overlap",
                    f"Telegram entities '{left.type}' and '{right.type}' partially overlap.",
                )
            pair = {left.type, right.type}
            if pair & {"code", "pre"} and len(pair) > 1:
                return ContentDiagnostic(
                    "error",
                    "impossible_entity_overlap",
                    "Inline code and pre entities cannot overlap other formatting.",
                )
            if left.type == right.type == "text_link":
                return ContentDiagnostic(
                    "error",
                    "impossible_entity_overlap",
                    "Telegram text links cannot be nested.",
                )
            if "custom_emoji" in pair and pair & {"code", "pre", "text_link"}:
                return ContentDiagnostic(
                    "error",
                    "impossible_entity_overlap",
                    "Custom emoji cannot overlap code, pre, or text links.",
                )
            if pair <= {"blockquote", "expandable_blockquote"}:
                return ContentDiagnostic(
                    "error",
                    "impossible_entity_overlap",
                    "Telegram block quotes cannot be nested.",
                )
    return None


def _split_message(
    text: str,
    entities: tuple[TelegramMessageEntity, ...],
    atomic_ranges: list[tuple[int, int]],
    block_boundaries: set[int],
    limit: int,
) -> tuple[list[CompiledTelegramMessage], ContentDiagnostic | None]:
    offsets = utf16_offsets(text)
    total = offsets[-1]
    offset_to_index = {offset: index for index, offset in enumerate(offsets)}
    start_index = 0
    chunks: list[tuple[int, int]] = []

    while offsets[start_index] < total:
        start_offset = offsets[start_index]
        if total - start_offset <= limit:
            chunks.append((start_index, len(text)))
            break
        maximum_index = start_index
        while (
            maximum_index + 1 < len(offsets)
            and offsets[maximum_index + 1] - start_offset <= limit
        ):
            maximum_index += 1
        if maximum_index == start_index:
            return [], ContentDiagnostic(
                "error",
                "message_split_impossible",
                "No Unicode boundary fits within the configured Telegram message limit.",
            )

        candidates = _split_candidates(
            text,
            start_index,
            maximum_index,
            block_boundaries,
            offset_to_index,
        )
        boundary = next(
            (
                candidate
                for candidate in candidates
                if not _inside_atomic(offsets[candidate], atomic_ranges)
            ),
            None,
        )
        if boundary is None or boundary <= start_index:
            blocking = next(
                (
                    item
                    for item in atomic_ranges
                    if item[0] <= start_offset < item[1]
                    or (start_offset < item[0] and item[1] > offsets[maximum_index])
                ),
                None,
            )
            detail = (
                f" An atomic resolved value spans {blocking[1] - blocking[0]} UTF-16 units."
                if blocking
                else ""
            )
            return [], ContentDiagnostic(
                "error",
                "message_split_impossible",
                "Rendered content cannot be split without damaging an atomic value." + detail,
            )
        chunks.append((start_index, boundary))
        start_index = boundary

    messages: list[CompiledTelegramMessage] = []
    for start, end in chunks:
        chunk_text = text[start:end]
        chunk_start = offsets[start]
        chunk_end = offsets[end]
        chunk_entities: list[TelegramMessageEntity] = []
        for entity in entities:
            entity_start = entity.offset
            entity_end = entity.offset + entity.length
            overlap_start = max(entity_start, chunk_start)
            overlap_end = min(entity_end, chunk_end)
            if overlap_end <= overlap_start:
                continue
            chunk_entities.append(
                TelegramMessageEntity(
                    entity.type,
                    overlap_start - chunk_start,
                    overlap_end - overlap_start,
                    url=entity.url,
                    language=entity.language,
                    custom_emoji_id=entity.custom_emoji_id,
                )
            )
        messages.append(
            CompiledTelegramMessage(chunk_text, _merge_entities(chunk_entities))
        )
    return messages, None


def _split_candidates(
    text: str,
    start: int,
    maximum: int,
    block_boundaries: set[int],
    offset_to_index: Mapping[int, int],
) -> list[int]:
    # Each category is evaluated independently so a later whitespace does not
    # outrank an earlier semantic block boundary.
    block = sorted(
        (
            offset_to_index[offset]
            for offset in block_boundaries
            if offset in offset_to_index and start < offset_to_index[offset] <= maximum
        ),
        reverse=True,
    )
    segment = text[start:maximum]
    empty_line = [start + match.end() for match in re.finditer(r"\n\n+", segment)]
    sentence = [
        start + match.end()
        for match in re.finditer(r"[.!?…](?:[\"'»”)]*)[ \t\n]+", segment)
    ]
    whitespace = [
        start + match.end() for match in re.finditer(r"[ \t\n]+", segment)
    ]
    result: list[int] = []
    seen: set[int] = set()
    # A forced split may use any Unicode boundary, not only the absolute
    # maximum. Walking backwards lets the caller skip boundaries inside an
    # atomic variable/custom-emoji/grapheme and stop immediately before it.
    forced = range(maximum, start, -1)
    for group in (block, reversed(empty_line), reversed(sentence), reversed(whitespace), forced):
        for candidate in group:
            if candidate not in seen and candidate > start:
                seen.add(candidate)
                result.append(candidate)
    return result


def _inside_atomic(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < offset < end for start, end in ranges)


def _unicode_atomic_ranges(value: str) -> list[tuple[int, int]]:
    """Protect common extended emoji/grapheme sequences during forced splitting.

    Python's string boundaries already protect surrogate pairs. This small,
    dependency-free segmenter additionally covers combining marks, variation
    selectors, skin tones, ZWJ/tag sequences and regional-indicator flag pairs.
    """

    offsets = utf16_offsets(value)
    ranges: list[tuple[int, int]] = []
    cluster_start = 0
    regional_count = 0
    for index, character in enumerate(value):
        codepoint = ord(character)
        regional = 0x1F1E6 <= codepoint <= 0x1F1FF
        extends = (
            index > cluster_start
            and (
                unicodedata.category(character).startswith("M")
                or 0xFE00 <= codepoint <= 0xFE0F
                or 0x1F3FB <= codepoint <= 0x1F3FF
                or 0xE0020 <= codepoint <= 0xE007F
                or character == "\u200d"
                or value[index - 1] == "\u200d"
                or (regional and regional_count % 2 == 1)
            )
        )
        if not extends:
            if index - cluster_start > 1:
                ranges.append((offsets[cluster_start], offsets[index]))
            cluster_start = index
            regional_count = 0
        regional_count = regional_count + 1 if regional else 0
    if len(value) - cluster_start > 1:
        ranges.append((offsets[cluster_start], offsets[-1]))
    return ranges
