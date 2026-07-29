from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from typing import Any, Mapping

from jinja2 import Environment, TemplateError

from .models import (
    BlockquoteBlock,
    BotContentDocument,
    CodeBlock,
    ContentDiagnostic,
    ContentMetadata,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    HardBreakNode,
    LegacyTemplateBlock,
    ParagraphBlock,
    TelegramMessageEntity,
    TextNode,
    VariableNode,
    VariableReference,
)
from .utf16 import utf16_length, utf16_slice
from .validation import is_safe_link, is_valid_custom_emoji_fallback


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


def import_legacy_template(
    document_id: str,
    source: str,
    *,
    created_at: str = "1970-01-01T00:00:00Z",
    updated_at: str | None = None,
) -> BotContentDocument:
    return legacy_template_to_document(
        document_id, source, created_at=created_at, updated_at=updated_at
    )


def serialize_legacy_template(document: BotContentDocument) -> str:
    """Generate the schema-v3 plain-Jinja fallback for older core versions.

    Rich marks are intentionally omitted: old runtimes send plain text and would
    otherwise expose HTML tags to users. A legacyTemplate document returns its
    original source exactly.
    """

    if (
        len(document.content) == 1
        and isinstance(document.content[0], LegacyTemplateBlock)
    ):
        return document.content[0].source

    rendered_blocks: list[str] = []
    for block in document.content:
        if isinstance(block, (ParagraphBlock, BlockquoteBlock, ExpandableBlockquoteBlock)):
            values: list[str] = []
            for node in block.content:
                if isinstance(node, TextNode):
                    values.append(_escape_jinja_literal(node.text))
                elif isinstance(node, VariableNode):
                    source = node.variable_reference.source
                    values.append(
                        source
                        if source is not None
                        and _simple_output_expression(
                            source, node.variable_reference.path
                        )
                        else f"{{{{ {node.variable_reference.path} }}}}"
                    )
                elif isinstance(node, CustomEmojiNode):
                    values.append(_escape_jinja_literal(node.fallback_emoji))
                elif isinstance(node, HardBreakNode):
                    values.append("\n")
            rendered_blocks.append("".join(values))
        elif isinstance(block, CodeBlock):
            rendered_blocks.append(_escape_jinja_literal(block.text))
        else:
            rendered_blocks.append(block.source)
    return "\n".join(rendered_blocks)


def compile_legacy_template(
    source: str, variables: Mapping[str, Any]
) -> LegacyCompileFragment:
    try:
        rendered, plain_rendered = _render_legacy_once(source, variables)
    except TemplateError as error:
        return _legacy_render_error(error)

    if _jinja_inside_html_tag(source):
        return LegacyCompileFragment(
            plain_rendered,
            (),
            warnings=(
                ContentDiagnostic(
                    "warning",
                    "legacy_dynamic_html_simplified",
                    "Legacy Jinja inside an HTML tag was kept as plain text for safety.",
                ),
            ),
        )

    parser = _TelegramHtmlParser()
    try:
        parser.feed(rendered)
        parser.close()
    except (ValueError, TypeError) as error:
        return LegacyCompileFragment(
            plain_rendered,
            (),
            warnings=(
                ContentDiagnostic(
                    "warning",
                    "legacy_html_simplified",
                    f"Legacy HTML could not be interpreted and was kept as plain text: {error}",
                ),
            ),
        )
    if not parser.balanced:
        return LegacyCompileFragment(
            plain_rendered,
            (),
            warnings=(
                *parser.warnings,
                ContentDiagnostic(
                    "warning",
                    "malformed_legacy_html",
                    "Malformed legacy HTML was kept as plain text.",
                ),
            ),
        )
    return LegacyCompileFragment(
        parser.text,
        tuple(parser.entities),
        tuple(parser.warnings),
    )


def _render_legacy_once(
    source: str, variables: Mapping[str, Any]
) -> tuple[str, str]:
    """Render once while retaining both escaped and exact expression output."""

    prefix = "\ue000BOTSTUDIO_EXPR_"
    while prefix in source:
        prefix += "_"
    suffix = "\ue001"
    values: list[str] = []

    def preserve(value: Any) -> str:
        rendered_value = str(value)
        index = len(values)
        values.append(rendered_value)
        return f"{prefix}{index}{suffix}"

    environment = Environment(
        undefined=_strict_undefined(),
        autoescape=False,
        finalize=preserve,
    )
    tokenized = str(environment.from_string(source).render(**variables))
    token_pattern = re.compile(
        f"{re.escape(prefix)}([0-9]+){re.escape(suffix)}"
    )
    return (
        token_pattern.sub(
            lambda match: escape(values[int(match.group(1))], quote=True),
            tokenized,
        ),
        token_pattern.sub(lambda match: values[int(match.group(1))], tokenized),
    )


def _legacy_render_error(error: TemplateError) -> LegacyCompileFragment:
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


def _simple_output_expression(source: str, path: str) -> bool:
    match = _SIMPLE_EXPRESSION.fullmatch(source)
    return match is not None and match.group(1) == path


def _escape_jinja_literal(value: str) -> str:
    replacements = {"{{": "{{ '{{' }}", "{%": "{{ '{%' }}", "{#": "{{ '{#' }}"}
    return re.sub(r"{{|{%|{#", lambda match: replacements[match.group(0)], value)


def _jinja_inside_html_tag(source: str) -> bool:
    inside_tag = False
    quote: str | None = None
    index = 0
    while index < len(source):
        character = source[index]
        if not inside_tag:
            if character == "<":
                inside_tag = True
        elif source.startswith(("{{", "{%", "{#"), index):
            return True
        elif quote is not None:
            if character == quote:
                quote = None
        elif character in {'"', "'"}:
            quote = character
        elif character == ">":
            inside_tag = False
        index += 1
    return False


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
        self._malformed_nesting = False

    @property
    def text(self) -> str:
        return "".join(self._parts)

    @property
    def balanced(self) -> bool:
        return not self._stack and not self._malformed_nesting

    def handle_data(self, data: str) -> None:
        self._append(data)

    def handle_comment(self, data: str) -> None:
        self._append(f"<!--{data}-->")
        self._unsupported_markup("HTML comments")

    def handle_decl(self, decl: str) -> None:
        self._append(f"<!{decl}>")
        self._unsupported_markup("HTML declarations")

    def handle_pi(self, data: str) -> None:
        self._append(f"<?{data}>")
        self._unsupported_markup("HTML processing instructions")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self._append("\n")
            return
        self._append(self.get_starttag_text() or f"<{tag}/>")
        self.warnings.append(
            ContentDiagnostic(
                "warning",
                "unsupported_legacy_html",
                f"Self-closing legacy tag <{tag}/> was kept as text.",
            )
        )

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
        if index != len(self._stack) - 1:
            self._malformed_nesting = True
        opened = self._stack.pop(index)
        if opened.unknown:
            self._append(f"</{tag}>")
            return
        length = self._offset - opened.start
        if opened.entity_type and length > 0:
            if opened.entity_type == "custom_emoji":
                fallback = utf16_slice(self.text, opened.start, length)
                if not is_valid_custom_emoji_fallback(fallback):
                    self.warnings.append(
                        ContentDiagnostic(
                            "warning",
                            "invalid_custom_emoji_fallback",
                            "A legacy custom emoji with an invalid fallback was reduced to text.",
                        )
                    )
                    return
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

    def _unsupported_markup(self, kind: str) -> None:
        self.warnings.append(
            ContentDiagnostic(
                "warning",
                "unsupported_legacy_html",
                f"Unsupported {kind} were kept as text.",
            )
        )
