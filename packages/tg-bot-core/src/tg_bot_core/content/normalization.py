from __future__ import annotations

from dataclasses import replace

from .models import (
    BlockquoteBlock,
    BotContentDocument,
    ContentBlock,
    ContentInlineNode,
    ContentMark,
    ExpandableBlockquoteBlock,
    MARK_TYPES,
    ParagraphBlock,
    TextNode,
    VariableNode,
)


_MARK_ORDER = {
    "bold": 0,
    "italic": 1,
    "underline": 2,
    "strikethrough": 3,
    "spoiler": 4,
    "code": 5,
    "link": 6,
}


def normalize_content_document(document: BotContentDocument) -> BotContentDocument:
    blocks = tuple(_normalize_block(block) for block in document.content)
    if not blocks:
        blocks = (ParagraphBlock(),)
    return replace(document, content=blocks)


def _normalize_block(block: ContentBlock) -> ContentBlock:
    if isinstance(block, (ParagraphBlock, BlockquoteBlock, ExpandableBlockquoteBlock)):
        content: list[ContentInlineNode] = []
        for node in block.content:
            normalized = _normalize_inline(node)
            if isinstance(normalized, TextNode) and not normalized.text:
                continue
            previous = content[-1] if content else None
            if (
                isinstance(previous, TextNode)
                and isinstance(normalized, TextNode)
                and previous.marks == normalized.marks
            ):
                content[-1] = TextNode(previous.text + normalized.text, previous.marks)
            else:
                content.append(normalized)
        return replace(block, content=tuple(content))
    return block


def _normalize_inline(node: ContentInlineNode) -> ContentInlineNode:
    if isinstance(node, (TextNode, VariableNode)):
        return replace(node, marks=_normalize_marks(node.marks))
    return node


def _normalize_marks(marks: tuple[ContentMark, ...]) -> tuple[ContentMark, ...]:
    unique: dict[tuple[str, str | None], ContentMark] = {}
    for mark in marks:
        if mark.type in MARK_TYPES:
            unique[(mark.type, mark.href)] = mark
    normalized = list(unique.values())
    if any(mark.type == "code" for mark in normalized):
        normalized = [mark for mark in normalized if mark.type == "code"]
    return tuple(
        sorted(normalized, key=lambda mark: (_MARK_ORDER.get(mark.type, 99), mark.href or ""))
    )
