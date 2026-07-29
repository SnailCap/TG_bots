from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


CONTENT_SCHEMA_VERSION = 1

MARK_TYPES = frozenset(
    {
        "bold",
        "italic",
        "underline",
        "strikethrough",
        "spoiler",
        "code",
        "link",
    }
)


@dataclass(frozen=True, slots=True)
class ContentMetadata:
    created_at: str
    updated_at: str
    editor_version: str
    source: str | None = None


@dataclass(frozen=True, slots=True)
class ContentMark:
    type: str
    href: str | None = None


@dataclass(frozen=True, slots=True)
class VariableReference:
    path: str
    field_id: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class TextNode:
    text: str
    marks: tuple[ContentMark, ...] = ()
    type: str = field(default="text", init=False)


@dataclass(frozen=True, slots=True)
class VariableNode:
    variable_reference: VariableReference
    marks: tuple[ContentMark, ...] = ()
    type: str = field(default="variable", init=False)


@dataclass(frozen=True, slots=True)
class CustomEmojiNode:
    custom_emoji_id: str
    fallback_emoji: str
    type: str = field(default="customEmoji", init=False)


@dataclass(frozen=True, slots=True)
class HardBreakNode:
    type: str = field(default="hardBreak", init=False)


ContentInlineNode = TextNode | VariableNode | CustomEmojiNode | HardBreakNode


@dataclass(frozen=True, slots=True)
class ParagraphBlock:
    content: tuple[ContentInlineNode, ...] = ()
    type: str = field(default="paragraph", init=False)


@dataclass(frozen=True, slots=True)
class BlockquoteBlock:
    content: tuple[ContentInlineNode, ...] = ()
    type: str = field(default="blockquote", init=False)


@dataclass(frozen=True, slots=True)
class ExpandableBlockquoteBlock:
    content: tuple[ContentInlineNode, ...] = ()
    type: str = field(default="expandableBlockquote", init=False)


@dataclass(frozen=True, slots=True)
class CodeBlock:
    text: str
    language: str | None = None
    type: str = field(default="codeBlock", init=False)


@dataclass(frozen=True, slots=True)
class LegacyTemplateBlock:
    """Lossless escape hatch for content that cannot be represented structurally yet."""

    source: str
    type: str = field(default="legacyTemplate", init=False)


ContentBlock = (
    ParagraphBlock
    | BlockquoteBlock
    | ExpandableBlockquoteBlock
    | CodeBlock
    | LegacyTemplateBlock
)


@dataclass(frozen=True, slots=True)
class BotContentDocument:
    schema_version: int
    id: str
    content: tuple[ContentBlock, ...]
    metadata: ContentMetadata


@dataclass(frozen=True, slots=True)
class ContentDiagnostic:
    severity: str
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramMessageEntity:
    type: str
    offset: int
    length: int
    url: str | None = None
    language: str | None = None
    custom_emoji_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompiledTelegramMessage:
    text: str
    entities: tuple[TelegramMessageEntity, ...] = ()


@dataclass(frozen=True, slots=True)
class TelegramCompileOptions:
    max_message_length: int = 4096
    split_long_messages: bool = True


@dataclass(frozen=True, slots=True)
class TelegramCompileResult:
    messages: tuple[CompiledTelegramMessage, ...]
    warnings: tuple[ContentDiagnostic, ...] = ()
    errors: tuple[ContentDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class TelegramImportResult:
    document: BotContentDocument
    warnings: tuple[ContentDiagnostic, ...] = ()


JsonMapping = Mapping[str, Any]
