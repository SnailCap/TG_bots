from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Mapping

from jinja2 import Environment, TemplateError

from .models import (
    BotContentDocument,
    ContentDiagnostic,
    ContentMetadata,
    LegacyTemplateBlock,
    ParagraphBlock,
    TelegramMessageEntity,
    TextNode,
    VariableNode,
    VariableReference,
)
from .utf16 import utf16_length
from .validation import is_safe_link


_SIMPLE_EXPRESSION = re.compile(
    r"{{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*}}"
)
_ANY_JINJA = re.compile(r"({[{%#].*?[}%#]})", re.DOTALL)
_HTML_LIKE = re.compile(r"</?[A-Za-z][^>]*>")


@dataclass(frozen=True, slots=True)
class LegacyCompileFragment:
    text: str
    entities: tuple[TelegramMessageEntity, ...]
    warnings: tuple[ContentDiagnostic, ...] = ()
    errors: tuple[ContentDiagnostic, ...] = ()


def legacy_template_to_document(
    document_id: str,
    source: str,
    *,
    created_at: str = "1970-01-01T00:00:00Z",
    updated_at: str | None = None,
) -> BotContentDocument:
    """Adapt a legacy Jinja template without ever discarding its source.

    Plain text with simple dotted expressions becomes editable structural nodes.
    HTML, statements, filters, comments and other expressions stay byte-for-byte
    in a legacyTemplate block until a richer migration can prove it is lossless.
    """

    metadata = ContentMetadata(
        created_at=created_at,
        updated_at=updated_at or created_at,
        editor_version="legacy-adapter",
        source="legacy-content",
    )
    if _HTML_LIKE.search(source) or _has_unsupported_jinja(source):
        return BotContentDocument(1, document_id, (LegacyTemplateBlock(source),), metadata)

    blocks: list[ParagraphBlock] = []
    for line in source.split("\n"):
        nodes: list[TextNode | VariableNode] = []
        cursor = 0
        for match in _SIMPLE_EXPRESSION.finditer(line):
            if match.start() > cursor:
                nodes.append(TextNode(line[cursor : match.start()]))
            nodes.append(
                VariableNode(
                    VariableReference(path=match.group(1), source=match.group(0))
                )
            )
            cursor = match.end()
        if cursor < len(line):
            nodes.append(TextNode(line[cursor:]))
        blocks.append(ParagraphBlock(tuple(nodes)))
    return BotContentDocument(1, document_id, tuple(blocks), metadata)


def compile_legacy_template(
    source: str, variables: Mapping[str, Any]
) -> LegacyCompileFragment:
    environment = Environment(undefined=_strict_undefined(), autoescape=True)
    # Variable values must never opt themselves into HTML interpretation.
    environment.filters.pop("safe", None)
    try:
        rendered = str(environment.from_string(source).render(**variables))
    except TemplateError as error:
        return LegacyCompileFragment(
            "",
            (),
            errors=(
                ContentDiagnostic(
                    "error",
                    "legacy_template_render",
                    f"Failed to render legacy template: {error}",
                ),
            ),
        )
    parser = _TelegramHtmlParser()
    try:
        parser.feed(rendered)
        parser.close()
    except (ValueError, TypeError) as error:
        return LegacyCompileFragment(
            rendered,
            (),
            warnings=(
                ContentDiagnostic(
                    "warning",
                    "legacy_html_simplified",
                    f"Legacy HTML could not be interpreted and was kept as plain text: {error}",
                ),
            ),
        )
    return LegacyCompileFragment(
        parser.text,
        tuple(parser.entities),
        tuple(parser.warnings),
    )


def _strict_undefined():
    # Kept behind a function so legacy.py does not expose Jinja as part of the
    # public content API.
    from jinja2 import StrictUndefined

    return StrictUndefined


def _has_unsupported_jinja(source: str) -> bool:
    for match in _ANY_JINJA.finditer(source):
        token = match.group(0)
        if _SIMPLE_EXPRESSION.fullmatch(token) is None:
            return True
    # An unmatched opening delimiter is also unsafe to structurally reinterpret.
    without_simple = _SIMPLE_EXPRESSION.sub("", source)
    return any(delimiter in without_simple for delimiter in ("{{", "{%", "{#"))


@dataclass(slots=True)
class _OpenTag:
    tag: str
    start: int
    entity_type: str | None
    url: str | None = None
    language: str | None = None
    custom_emoji_id: str | None = None
    unknown: bool = False


class _TelegramHtmlParser(HTMLParser):
    _SIMPLE_TAGS = {
        "b": "bold",
        "strong": "bold",
        "i": "italic",
        "em": "italic",
        "u": "underline",
        "ins": "underline",
        "s": "strikethrough",
        "strike": "strikethrough",
        "del": "strikethrough",
        "tg-spoiler": "spoiler",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._offset = 0
        self._stack: list[_OpenTag] = []
        self.entities: list[TelegramMessageEntity] = []
        self.warnings: list[ContentDiagnostic] = []

    @property
    def text(self) -> str:
        return "".join(self._parts)

    def handle_data(self, data: str) -> None:
        self._append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self._append("\n")
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value for name, value in attrs}
        if tag == "br":
            self._append("\n")
            return
        entity_type = self._SIMPLE_TAGS.get(tag)
        if entity_type:
            self._stack.append(_OpenTag(tag, self._offset, entity_type))
            return
        if tag == "span" and "tg-spoiler" in (attributes.get("class") or "").split():
            self._stack.append(_OpenTag(tag, self._offset, "spoiler"))
            return
        if tag == "a":
            href = attributes.get("href") or ""
            if is_safe_link(href):
                self._stack.append(_OpenTag(tag, self._offset, "text_link", url=href))
            else:
                self._stack.append(_OpenTag(tag, self._offset, None))
                self.warnings.append(
                    ContentDiagnostic(
                        "warning", "unsafe_link_removed", "An unsafe legacy link was reduced to text."
                    )
                )
            return
        if tag == "blockquote":
            expandable = "expandable" in attributes
            self._stack.append(
                _OpenTag(
                    tag,
                    self._offset,
                    "expandable_blockquote" if expandable else "blockquote",
                )
            )
            return
        if tag == "pre":
            self._stack.append(_OpenTag(tag, self._offset, "pre"))
            return
        if tag == "code":
            active_pre = next(
                (item for item in reversed(self._stack) if item.entity_type == "pre"), None
            )
            if active_pre is not None:
                class_name = attributes.get("class") or ""
                if class_name.startswith("language-"):
                    active_pre.language = class_name.removeprefix("language-") or None
                self._stack.append(_OpenTag(tag, self._offset, None))
            else:
                self._stack.append(_OpenTag(tag, self._offset, "code"))
            return
        if tag == "tg-emoji":
            emoji_id = attributes.get("emoji-id") or ""
            if emoji_id.isdigit():
                self._stack.append(
                    _OpenTag(tag, self._offset, "custom_emoji", custom_emoji_id=emoji_id)
                )
            else:
                self._stack.append(_OpenTag(tag, self._offset, None))
                self.warnings.append(
                    ContentDiagnostic(
                        "warning",
                        "invalid_custom_emoji_id",
                        "A legacy custom emoji with an invalid id was reduced to its fallback.",
                    )
                )
            return

        raw = self.get_starttag_text() or f"<{tag}>"
        self._append(raw)
        self._stack.append(_OpenTag(tag, self._offset, None, unknown=True))
        self.warnings.append(
            ContentDiagnostic(
                "warning",
                "unsupported_legacy_html",
                f"Unsupported legacy HTML tag <{tag}> was kept as text.",
            )
        )

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        index = next(
            (index for index in range(len(self._stack) - 1, -1, -1) if self._stack[index].tag == tag),
            None,
        )
        if index is None:
            self._append(f"</{tag}>")
            self.warnings.append(
                ContentDiagnostic(
                    "warning",
                    "unmatched_legacy_html",
                    f"Unmatched legacy closing tag </{tag}> was kept as text.",
                )
            )
            return
        opened = self._stack.pop(index)
        if opened.unknown:
            self._append(f"</{tag}>")
            return
        length = self._offset - opened.start
        if opened.entity_type and length > 0:
            self.entities.append(
                TelegramMessageEntity(
                    opened.entity_type,
                    opened.start,
                    length,
                    url=opened.url,
                    language=opened.language,
                    custom_emoji_id=opened.custom_emoji_id,
                )
            )

    def _append(self, value: str) -> None:
        self._parts.append(value)
        self._offset += utf16_length(value)
