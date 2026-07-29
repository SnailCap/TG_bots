"""Structured BotStudio content and Telegram output adapter."""

from .compiler import compile_content_document, compile_result_to_dict
from .legacy import (
    import_legacy_template,
    legacy_template_to_document,
    serialize_legacy_template,
)
from .migrations import ContentMigrationError, migrate_content_document
from .models import (
    CONTENT_SCHEMA_VERSION,
    MARK_TYPES,
    BlockquoteBlock,
    BotContentDocument,
    CodeBlock,
    CompiledTelegramMessage,
    ContentDiagnostic,
    ContentMark,
    ContentMetadata,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    HardBreakNode,
    LegacyTemplateBlock,
    ParagraphBlock,
    TelegramCompileOptions,
    TelegramCompileResult,
    TelegramImportResult,
    TelegramMessageEntity,
    TextNode,
    VariableNode,
    VariableReference,
)
from .normalization import normalize_content_document
from .parser import ContentDocumentError, content_document_to_dict, parse_content_document
from .telegram_import import import_telegram_message
from .utf16 import index_from_utf16_offset, utf16_length, utf16_offsets, utf16_slice
from .validation import (
    is_safe_link,
    is_valid_custom_emoji_fallback,
    validate_content_document,
)

__all__ = [
    "CONTENT_SCHEMA_VERSION",
    "MARK_TYPES",
    "BlockquoteBlock",
    "BotContentDocument",
    "CodeBlock",
    "CompiledTelegramMessage",
    "ContentDiagnostic",
    "ContentDocumentError",
    "ContentMark",
    "ContentMetadata",
    "ContentMigrationError",
    "CustomEmojiNode",
    "ExpandableBlockquoteBlock",
    "HardBreakNode",
    "LegacyTemplateBlock",
    "ParagraphBlock",
    "TelegramCompileOptions",
    "TelegramCompileResult",
    "TelegramImportResult",
    "TelegramMessageEntity",
    "TextNode",
    "VariableNode",
    "VariableReference",
    "compile_content_document",
    "compile_result_to_dict",
    "content_document_to_dict",
    "import_legacy_template",
    "import_telegram_message",
    "index_from_utf16_offset",
    "is_safe_link",
    "is_valid_custom_emoji_fallback",
    "legacy_template_to_document",
    "migrate_content_document",
    "normalize_content_document",
    "parse_content_document",
    "serialize_legacy_template",
    "utf16_length",
    "utf16_offsets",
    "utf16_slice",
    "validate_content_document",
]
