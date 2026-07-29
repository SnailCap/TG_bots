from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tg_bot_core import Actor, BotApp, BotConfig, CallbackEvent, CommandEvent
from tg_bot_core.adapters.ptb import PtbTransport
from tg_bot_core.content import (
    BotContentDocument,
    BlockquoteBlock,
    CodeBlock,
    ContentDocumentError,
    ContentMark,
    ContentMetadata,
    CustomEmojiNode,
    ExpandableBlockquoteBlock,
    HardBreakNode,
    ParagraphBlock,
    TelegramCompileOptions,
    TelegramMessageEntity,
    TextNode,
    VariableNode,
    VariableReference,
    compile_content_document,
    compile_result_to_dict,
    content_document_to_dict,
    import_legacy_template,
    import_telegram_message,
    normalize_content_document,
    parse_content_document,
    migrate_content_document,
    serialize_legacy_template,
    utf16_length,
    utf16_slice,
    validate_content_document,
)
from tg_bot_core.project import ProjectLoader, validate_project
from tg_bot_core.transport import OutboundMessage

from conftest import FakeTransport, make_project, write_json


FIXTURES = Path(__file__).parent / "fixtures" / "content"
STAMP = "2026-07-29T00:00:00Z"


def metadata(source: str = "botstudio") -> ContentMetadata:
    return ContentMetadata(STAMP, STAMP, "test", source)


def test_content_document_parser_round_trips_and_normalizes_without_mutation() -> None:
    raw = {
        "schemaVersion": 1,
        "id": "message",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "A", "marks": [{"type": "bold"}]},
                    {"type": "text", "text": "B", "marks": [{"type": "bold"}]},
                ],
            }
        ],
        "metadata": {
            "createdAt": STAMP,
            "updatedAt": STAMP,
            "editorVersion": "test",
        },
    }
    document = parse_content_document(raw)
    normalized = normalize_content_document(document)

    assert content_document_to_dict(document) == raw
    assert normalized is not document
    assert normalized.content[0].content == (TextNode("AB", (ContentMark("bold"),)),)  # type: ignore[union-attr]
    assert raw["content"][0]["content"][0]["text"] == "A"


def test_parser_rejects_unknown_content_schema_without_mutating_input() -> None:
    raw = {
        "schemaVersion": 2,
        "id": "future",
        "content": [],
        "metadata": {"createdAt": STAMP, "updatedAt": STAMP, "editorVersion": "2"},
    }
    before = json.loads(json.dumps(raw))

    with pytest.raises(ContentDocumentError, match="newer than supported"):
        parse_content_document(raw)
    assert raw == before


def test_parser_rejects_unknown_v1_fields_instead_of_dropping_them() -> None:
    raw = {
        "schemaVersion": 1,
        "id": "unknown-field",
        "content": [{"type": "paragraph", "content": [], "future": True}],
        "metadata": {"createdAt": STAMP, "updatedAt": STAMP, "editorVersion": "1"},
    }

    with pytest.raises(ContentDocumentError, match="unsupported field"):
        parse_content_document(raw)


def test_v1_migration_is_pure_and_idempotent() -> None:
    raw = {
        "schemaVersion": 1,
        "id": "v1",
        "content": [{"type": "paragraph", "content": []}],
        "metadata": {"createdAt": STAMP, "updatedAt": STAMP, "editorVersion": "1"},
    }

    first = migrate_content_document(raw)
    second = migrate_content_document(first)
    first["id"] = "changed"

    assert raw["id"] == "v1"
    assert second["id"] == "v1"


@pytest.mark.parametrize(
    ("value", "length"),
    [
        ("ASCII", 5),
        ("кириллица", 9),
        ("👍", 2),
        ("👍🏽", 4),
        ("👩‍💻", 5),
        ("🇪🇪", 4),
        ("✈️", 2),
    ],
)
def test_utf16_length_matches_telegram_offsets(value: str, length: int) -> None:
    assert utf16_length(value) == length
    assert utf16_slice(f"x{value}y", 1, length) == value


def test_lone_surrogates_are_countable_but_rejected_from_outbound_content() -> None:
    surrogate = "\ud800"
    static = BotContentDocument(
        1,
        "invalid-static-unicode",
        (ParagraphBlock((TextNode(surrogate),)),),
        metadata(),
    )
    dynamic = BotContentDocument(
        1,
        "invalid-resolved-unicode",
        (ParagraphBlock((VariableNode(VariableReference("value")),)),),
        metadata(),
    )

    assert utf16_length(surrogate) == 1
    assert compile_content_document(static, {}).errors[0].code == "invalid_unicode"
    assert (
        compile_content_document(dynamic, {"value": surrogate}).errors[0].code
        == "invalid_resolved_unicode"
    )


@pytest.mark.parametrize(
    "fixture_path",
    sorted(FIXTURES.glob("*.json")),
    ids=lambda path: path.stem,
)
def test_content_compiler_golden_fixtures(fixture_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    raw_options = fixture.get("options", {})
    options = TelegramCompileOptions(
        max_message_length=raw_options.get("maxMessageLength", 4096),
        split_long_messages=raw_options.get("splitLongMessages", True),
    )

    result = compile_content_document(
        parse_content_document(fixture["document"]),
        fixture.get("variables", {}),
        options,
    )

    assert compile_result_to_dict(result) == fixture["expected"]


def test_all_supported_marks_and_expandable_quote_map_to_telegram_entities() -> None:
    marks = (
        ContentMark("bold"),
        ContentMark("italic"),
        ContentMark("underline"),
        ContentMark("strikethrough"),
        ContentMark("spoiler"),
        ContentMark("code"),
        ContentMark("link", "https://example.com/path"),
    )
    document = BotContentDocument(
        1,
        "marks",
        (
            ParagraphBlock(
                tuple(
                    TextNode(chr(ord("a") + index), (mark,))
                    for index, mark in enumerate(marks)
                )
            ),
            # Keep the block content unmarked so the quote entity itself is easy
            # to distinguish from inline formatting.
            ExpandableBlockquoteBlock((TextNode("quote"),)),
        ),
        metadata(),
    )

    result = compile_content_document(document, {})

    assert result.errors == ()
    assert [entity.type for entity in result.messages[0].entities] == [
        "bold",
        "italic",
        "underline",
        "strikethrough",
        "spoiler",
        "code",
        "text_link",
        "expandable_blockquote",
    ]
    assert result.messages[0].entities[6].url == "https://example.com/path"


def test_variable_values_are_plain_text_and_marks_use_resolved_utf16_length() -> None:
    document = BotContentDocument(
        1,
        "plain-variable",
        (
            ParagraphBlock(
                (
                    VariableNode(
                        VariableReference("value"),
                        (ContentMark("italic"),),
                    ),
                )
            ),
        ),
        metadata(),
    )

    result = compile_content_document(document, {"value": "<b>👍</b>"})

    assert result.messages[0].text == "<b>👍</b>"
    assert result.messages[0].entities == (
        TelegramMessageEntity("italic", 0, 9),
    )


def test_variable_source_cannot_execute_arbitrary_jinja() -> None:
    document = BotContentDocument(
        1,
        "safe-variable-source",
        (
            ParagraphBlock(
                (
                    VariableNode(
                        VariableReference("value", source="{{ value | upper }}")
                    ),
                )
            ),
        ),
        metadata(),
    )

    result = compile_content_document(document, {"value": "plain"})

    assert result.messages == ()
    assert result.errors[0].code == "invalid_variable_source"
    assert serialize_legacy_template(document) == "{{ value }}"


def test_unresolved_and_multiline_emoji_variables_have_deterministic_diagnostics_and_offsets() -> None:
    document = BotContentDocument(
        1,
        "variables",
        (
            ParagraphBlock(
                (
                    TextNode("before "),
                    VariableNode(
                        VariableReference("value"),
                        (ContentMark("underline"),),
                    ),
                    TextNode(" after"),
                )
            ),
        ),
        metadata(),
    )

    resolved = compile_content_document(document, {"value": "one\n👍"})
    unresolved = compile_content_document(document, {})

    assert resolved.messages[0].entities == (
        TelegramMessageEntity("underline", 7, 6),
    )
    assert unresolved.messages == ()
    assert unresolved.errors[0].code == "variable_resolution"


def test_jinja_builtin_names_do_not_resolve_as_content_variables() -> None:
    document = BotContentDocument(
        1,
        "builtin-name",
        (ParagraphBlock((VariableNode(VariableReference("range")),)),),
        metadata(),
    )

    missing = compile_content_document(document, {})
    explicit = compile_content_document(document, {"range": "provided"})

    assert missing.errors[0].code == "variable_resolution"
    assert explicit.messages[0].text == "provided"


def test_long_messages_split_at_blocks_and_clip_formatting_entities() -> None:
    document = BotContentDocument(
        1,
        "split",
        (
            ParagraphBlock((TextNode("A" * 8, (ContentMark("bold"),)),)),
            ParagraphBlock((TextNode("B" * 8, (ContentMark("bold"),)),)),
        ),
        metadata(),
    )

    result = compile_content_document(
        document, {}, TelegramCompileOptions(max_message_length=10)
    )

    assert [message.text for message in result.messages] == ["A" * 8 + "\n", "B" * 8]
    assert result.messages[0].entities == (TelegramMessageEntity("bold", 0, 8),)
    assert result.messages[1].entities == (TelegramMessageEntity("bold", 0, 8),)
    assert [warning.code for warning in result.warnings] == ["message_split"]


def test_split_rejects_a_resolved_variable_larger_than_one_message() -> None:
    document = BotContentDocument(
        1,
        "atomic",
        (ParagraphBlock((VariableNode(VariableReference("value")),)),),
        metadata(),
    )

    result = compile_content_document(
        document,
        {"value": "x" * 11},
        TelegramCompileOptions(max_message_length=10),
    )

    assert result.messages == ()
    assert result.errors[0].code == "message_split_impossible"


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_compile_rejects_invalid_message_limits(limit: object) -> None:
    document = BotContentDocument(
        1,
        "invalid-limit",
        (ParagraphBlock((TextNode("text"),)),),
        metadata(),
    )

    result = compile_content_document(
        document,
        {},
        TelegramCompileOptions(max_message_length=limit),  # type: ignore[arg-type]
    )

    assert result.messages == ()
    assert result.errors[0].code == "invalid_message_limit"


def test_split_can_stop_immediately_before_an_atomic_variable() -> None:
    document = BotContentDocument(
        1,
        "atomic-boundary",
        (
            ParagraphBlock(
                (
                    TextNode("abc"),
                    VariableNode(VariableReference("value")),
                )
            ),
        ),
        metadata(),
    )

    result = compile_content_document(
        document,
        {"value": "1234567890"},
        TelegramCompileOptions(max_message_length=10),
    )

    assert result.errors == ()
    assert [message.text for message in result.messages] == ["abc", "1234567890"]


@pytest.mark.parametrize("value", ["👩‍💻", "👍🏽", "🇪🇪", "✈️", "1️⃣"])
def test_forced_split_never_breaks_unicode_emoji_sequences(value: str) -> None:
    document = BotContentDocument(
        1,
        "unicode-atomic",
        (ParagraphBlock((TextNode(value),)),),
        metadata(),
    )

    result = compile_content_document(
        document,
        {},
        TelegramCompileOptions(max_message_length=max(1, utf16_length(value) - 1)),
    )

    assert result.messages == ()
    assert result.errors[0].code == "message_split_impossible"


def test_legacy_adapter_preserves_complex_source_and_escapes_variable_html() -> None:
    source = "<b>{{ user.name }}</b>{% if flag %}!{% endif %}"
    document = import_legacy_template("legacy", source)

    assert serialize_legacy_template(document) == source
    result = compile_content_document(
        document, {"user": {"name": "<i>Ada</i>"}, "flag": True}
    )

    assert result.errors == ()
    assert result.messages[0].text == "<i>Ada</i>!"
    assert result.messages[0].entities == (TelegramMessageEntity("bold", 0, 10),)


def test_legacy_safe_filter_cannot_turn_a_variable_value_into_html() -> None:
    document = import_legacy_template("legacy", "<b>{{ value | safe }}</b>")

    result = compile_content_document(document, {"value": "<i>Ada</i>"})

    assert result.messages[0].text == "<i>Ada</i>"
    assert result.messages[0].entities == (TelegramMessageEntity("bold", 0, 10),)


def test_simple_legacy_variables_become_atomic_nodes_and_keep_source() -> None:
    source = "Hello {{ user.first_name }}"
    document = import_legacy_template("legacy", source)

    assert serialize_legacy_template(document) == source
    assert isinstance(document.content[0], ParagraphBlock)
    assert isinstance(document.content[0].content[1], VariableNode)


def test_legacy_projection_escapes_literal_jinja_delimiters() -> None:
    document = BotContentDocument(
        1,
        "literal-jinja",
        (ParagraphBlock((TextNode("Literal {{ value }} and {% statement %}"),)),),
        metadata(),
    )
    source = serialize_legacy_template(document)

    imported = import_legacy_template("literal-jinja", source)
    result = compile_content_document(imported, {})

    assert result.messages[0].text == "Literal {{ value }} and {% statement %}"


@pytest.mark.parametrize("tag", ["widget", "i", "a href=\"https://example.com\""])
def test_self_closing_legacy_html_is_preserved_once(tag: str) -> None:
    document = import_legacy_template("self-closing-html", f"before<{tag}/>after")

    result = compile_content_document(document, {})

    assert result.messages[0].text == f"before<{tag}/>after"
    assert result.messages[0].entities == ()
    assert result.warnings[0].code == "unsupported_legacy_html"


def test_unsupported_legacy_html_comments_are_not_discarded() -> None:
    source = "<b>x</b><!--keep-->"
    result = compile_content_document(import_legacy_template("comment", source), {})

    assert result.messages[0].text == "x<!--keep-->"
    assert result.messages[0].entities == (TelegramMessageEntity("bold", 0, 1),)
    assert result.warnings[0].code == "unsupported_legacy_html"


@pytest.mark.parametrize("source", ["<b>x", "<b><i>x</b>"])
def test_malformed_legacy_html_is_kept_as_plain_text(source: str) -> None:
    result = compile_content_document(import_legacy_template("malformed", source), {})

    assert result.messages[0].text == source
    assert result.messages[0].entities == ()
    assert result.warnings[-1].code == "malformed_legacy_html"


def test_malformed_legacy_fallback_preserves_entities_and_raw_variables() -> None:
    source = "<b>&amp; {{ value }}"
    result = compile_content_document(
        import_legacy_template("malformed-entities", source),
        {"value": "<i>raw</i>"},
    )

    assert result.messages[0].text == "<b>&amp; <i>raw</i>"
    assert result.messages[0].entities == ()
    assert result.warnings[-1].code == "malformed_legacy_html"


@pytest.mark.parametrize(
    "source, variables, expected",
    [
        (
            "<span {{ attrs }}>x</span>",
            {"attrs": "class=tg-spoiler"},
            "<span class=tg-spoiler>x</span>",
        ),
        (
            '<span class="{{ css_class }}">x</span>',
            {"css_class": "tg-spoiler"},
            '<span class="tg-spoiler">x</span>',
        ),
    ],
)
def test_legacy_jinja_cannot_inject_html_attributes(
    source: str, variables: dict[str, str], expected: str
) -> None:
    result = compile_content_document(
        import_legacy_template("dynamic-attribute", source),
        variables,
    )

    assert result.messages[0].text == expected
    assert result.messages[0].entities == ()
    assert result.warnings[0].code == "legacy_dynamic_html_simplified"


def test_invalid_legacy_custom_emoji_fallback_is_reduced_to_text() -> None:
    source = '<tg-emoji emoji-id="123">hello</tg-emoji>'
    result = compile_content_document(import_legacy_template("bad-emoji", source), {})

    assert result.messages[0].text == "hello"
    assert result.messages[0].entities == ()
    assert result.warnings[0].code == "invalid_custom_emoji_fallback"


def test_telegram_entity_import_round_trips_supported_inline_entities() -> None:
    imported = import_telegram_message(
        "Hi 👍",
        (
            TelegramMessageEntity("bold", 0, 2),
            TelegramMessageEntity("custom_emoji", 3, 2, custom_emoji_id="123"),
        ),
        document_id="telegram",
    )
    result = compile_content_document(imported.document, {})

    assert result.messages[0].text == "Hi 👍"
    assert result.messages[0].entities == (
        TelegramMessageEntity("bold", 0, 2),
        TelegramMessageEntity("custom_emoji", 3, 2, custom_emoji_id="123"),
    )


def test_telegram_import_preserves_one_multiline_pre_entity() -> None:
    imported = import_telegram_message(
        "one\n\ntwo",
        (TelegramMessageEntity("pre", 0, 8, language="python"),),
        document_id="telegram-pre",
    )
    result = compile_content_document(imported.document, {})

    assert imported.document.content == (CodeBlock("one\n\ntwo", "python"),)
    assert result.messages[0].text == "one\n\ntwo"
    assert result.messages[0].entities == (
        TelegramMessageEntity("pre", 0, 8, language="python"),
    )


def test_telegram_import_uses_hard_breaks_inside_multiline_quotes() -> None:
    imported = import_telegram_message(
        "one\ntwo",
        (TelegramMessageEntity("blockquote", 0, 7),),
        document_id="telegram-quote",
    )
    result = compile_content_document(imported.document, {})

    assert imported.document.content == (
        BlockquoteBlock((TextNode("one"), HardBreakNode(), TextNode("two"))),
    )
    assert result.messages[0].text == "one\ntwo"
    assert result.messages[0].entities == (
        TelegramMessageEntity("blockquote", 0, 7),
    )


def test_telegram_import_preserves_a_final_newline_inside_pre() -> None:
    imported = import_telegram_message(
        "one\ntwo\n",
        (TelegramMessageEntity("pre", 0, 8),),
        document_id="telegram-pre-newline",
    )
    result = compile_content_document(imported.document, {})

    assert imported.warnings == ()
    assert imported.document.content == (CodeBlock("one\ntwo\n"),)
    assert result.messages[0].text == "one\ntwo\n"
    assert result.messages[0].entities == (TelegramMessageEntity("pre", 0, 8),)


def test_telegram_import_warns_when_a_trailing_block_newline_is_normalized() -> None:
    imported = import_telegram_message(
        "one\nnext",
        (TelegramMessageEntity("pre", 0, 4),),
        document_id="telegram-pre-boundary",
    )
    result = compile_content_document(imported.document, {})

    assert result.messages[0].text == "one\nnext"
    assert result.messages[0].entities == (TelegramMessageEntity("pre", 0, 3),)
    assert imported.warnings[0].code == "block_entity_boundary_normalized"


def test_telegram_import_reduces_invalid_entities_to_plain_text_with_warnings() -> None:
    imported = import_telegram_message(
        "Hi 👍",
        (
            TelegramMessageEntity("bold", 0, 0),
            TelegramMessageEntity("custom_emoji", 3, 2),
        ),
        document_id="telegram-invalid",
    )
    result = compile_content_document(imported.document, {})

    assert result.messages[0].text == "Hi 👍"
    assert result.messages[0].entities == ()
    assert {warning.code for warning in imported.warnings} == {
        "invalid_imported_entity",
        "invalid_custom_emoji_id",
    }


def test_telegram_import_reduces_invalid_custom_emoji_span_to_text() -> None:
    imported = import_telegram_message(
        "hello",
        (TelegramMessageEntity("custom_emoji", 0, 5, custom_emoji_id="123"),),
        document_id="telegram-invalid-fallback",
    )
    result = compile_content_document(imported.document, {})

    assert imported.warnings[0].code == "invalid_custom_emoji_fallback"
    assert result.errors == ()
    assert result.messages[0].text == "hello"
    assert result.messages[0].entities == ()


def test_loader_indexes_content_documents_and_validates_references(tmp_path: Path) -> None:
    make_project(
        tmp_path,
        views=[
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Fallback", "document": "views/home.json"},
                "keyboard": [],
            }
        ],
    )
    document = BotContentDocument(
        1,
        "home",
        (ParagraphBlock((TextNode("Structured"),)),),
        metadata(),
    )
    write_json(
        tmp_path / "resources" / "content" / "views" / "home.json",
        content_document_to_dict(document),
    )

    project = ProjectLoader().load(tmp_path)

    assert project.views["home"].text.inline == "Fallback"
    assert project.views["home"].text.document == "views/home.json"
    assert project.content_documents["views/home.json"].id == "home"
    assert not [item for item in validate_project(project) if item.level == "error"]


def test_missing_content_document_is_a_stable_project_diagnostic(tmp_path: Path) -> None:
    make_project(
        tmp_path,
        views=[
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Fallback", "document": "views/missing.json"},
                "keyboard": [],
            }
        ],
    )

    diagnostics = validate_project(ProjectLoader().load(tmp_path))

    assert any(item.code == "content_document_missing" for item in diagnostics)


def test_attached_statically_empty_content_document_is_a_project_error(
    tmp_path: Path,
) -> None:
    make_project(
        tmp_path,
        views=[
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Fallback", "document": "views/home.json"},
                "keyboard": [],
            }
        ],
    )
    document = BotContentDocument(
        1,
        "home",
        (ParagraphBlock((TextNode(" \n "),)),),
        metadata(),
    )
    write_json(
        tmp_path / "resources" / "content" / "views" / "home.json",
        content_document_to_dict(document),
    )

    diagnostics = validate_project(ProjectLoader().load(tmp_path))

    assert any(item.code == "content_document_empty" for item in diagnostics)


@pytest.mark.asyncio
async def test_runtime_prefers_content_entities_and_splits_edit_only_on_first_message(
    tmp_path: Path,
) -> None:
    make_project(
        tmp_path,
        views=[
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Home"},
                "keyboard": [
                    [
                        {
                            "id": "open_rich",
                            "text": "Open",
                            "action": {"type": "view.render", "target": "rich"},
                        }
                    ]
                ],
            },
            {
                "schema_version": 3,
                "id": "rich",
                "text": {"inline": "Fallback", "document": "views/rich.json"},
                "keyboard": [
                    [
                        {
                            "id": "stay",
                            "text": "Stay",
                            "action": {"type": "noop"},
                        }
                    ]
                ],
            },
        ],
    )
    document = BotContentDocument(
        1,
        "rich",
        (
            ParagraphBlock((TextNode("A" * 3000, (ContentMark("bold"),)),)),
            ParagraphBlock((TextNode("B" * 2000), CustomEmojiNode("123", "👍"))),
        ),
        metadata(),
    )
    write_json(
        tmp_path / "resources" / "content" / "views" / "rich.json",
        content_document_to_dict(document),
    )
    transport = FakeTransport()
    app = BotApp(
        config=BotConfig(tmp_path, None, tmp_path / "runtime.sqlite3"),
        services=[],
        transport=transport,
    )
    actor = Actor(1, 2, first_name="Ada")

    await app.start()
    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(CallbackEvent(actor, 2, "open_rich", message_id=77))

    rich_messages = transport.messages[-2:]
    assert [message.edit_message_id for message in rich_messages] == [77, None]
    assert rich_messages[0].text == "A" * 3000 + "\n"
    assert rich_messages[0].entities == (TelegramMessageEntity("bold", 0, 3000),)
    assert rich_messages[0].keyboard == ()
    assert rich_messages[1].text == "B" * 2000 + "👍"
    assert rich_messages[1].entities[-1] == TelegramMessageEntity(
        "custom_emoji", 2000, 2, custom_emoji_id="123"
    )
    assert rich_messages[1].keyboard[0][0].callback_data == "v3:a:stay"
    await app.stop()


@pytest.mark.asyncio
async def test_runtime_content_context_exposes_documented_user_fields(
    tmp_path: Path,
) -> None:
    make_project(
        tmp_path,
        views=[
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Fallback", "document": "views/home.json"},
                "keyboard": [],
            }
        ],
    )
    document = BotContentDocument(
        1,
        "home",
        (
            ParagraphBlock(
                (
                    VariableNode(VariableReference("user.telegram_id")),
                    TextNode("|"),
                    VariableNode(VariableReference("user.language_code")),
                    TextNode("|"),
                    VariableNode(VariableReference("user.id")),
                )
            ),
        ),
        metadata(),
    )
    write_json(
        tmp_path / "resources" / "content" / "views" / "home.json",
        content_document_to_dict(document),
    )
    transport = FakeTransport()
    app = BotApp(
        config=BotConfig(tmp_path, None, tmp_path / "runtime.sqlite3"),
        services=[],
        transport=transport,
    )

    await app.start()
    await transport.emit(
        CommandEvent(
            Actor(42, 7, first_name="Ada", language_code="et"),
            1,
            "start",
        )
    )

    assert transport.messages[-1].text == "42|et|42"
    await app.stop()


def test_ptb_adapter_maps_core_entities_without_parse_mode() -> None:
    mapped = PtbTransport._message_entity(
        TelegramMessageEntity(
            "custom_emoji", 3, 2, custom_emoji_id="5368324170671202286"
        )
    )

    assert (mapped.type, mapped.offset, mapped.length) == ("custom_emoji", 3, 2)
    assert mapped.custom_emoji_id == "5368324170671202286"


@pytest.mark.asyncio
async def test_ptb_send_passes_entities_without_parse_mode() -> None:
    transport = object.__new__(PtbTransport)
    bot = SimpleNamespace(send_message=AsyncMock())
    transport._app = SimpleNamespace(bot=bot)  # type: ignore[attr-defined]

    await transport.send(
        OutboundMessage(
            42,
            "Bold",
            entities=(TelegramMessageEntity("bold", 0, 4),),
        )
    )

    kwargs = bot.send_message.await_args.kwargs
    assert "parse_mode" not in kwargs
    assert kwargs["entities"][0].type == "bold"
    assert (kwargs["entities"][0].offset, kwargs["entities"][0].length) == (0, 4)


def test_validation_blocks_unsafe_links_and_invalid_custom_emoji() -> None:
    document = BotContentDocument(
        1,
        "unsafe",
        (
            ParagraphBlock(
                (
                    TextNode("click", (ContentMark("link", "javascript:alert(1)"),)),
                    CustomEmojiNode("not-a-number", ""),
                )
            ),
        ),
        metadata(),
    )

    codes = {item.code for item in validate_content_document(document)}

    assert {"unsafe_link", "invalid_custom_emoji_id", "invalid_custom_emoji_fallback"} <= codes


@pytest.mark.parametrize(
    "value",
    [
        "https:",
        "https:///",
        "mailto:",
        "mailto:/",
        "tg:",
        "tg:/",
        "https://bad host",
        "https://example.com/\x07",
    ],
)
def test_validation_rejects_links_without_a_valid_target(value: str) -> None:
    document = BotContentDocument(
        1,
        "bad-link-target",
        (ParagraphBlock((TextNode("bad", (ContentMark("link", value),)),)),),
        metadata(),
    )

    assert validate_content_document(document)[0].code == "unsafe_link"


@pytest.mark.parametrize("fallback", ["👍", "👩‍💻", "🇪🇪", "1️⃣", "❤️"])
def test_validation_accepts_one_unicode_emoji_fallback(fallback: str) -> None:
    document = BotContentDocument(
        1,
        "zwj-fallback",
        (ParagraphBlock((CustomEmojiNode("123", fallback),)),),
        metadata(),
    )

    assert validate_content_document(document) == ()


@pytest.mark.parametrize(
    "fallback",
    [
        "text",
        "A",
        "👍👎",
        "😀\u200d",
        "\u200d😀",
        "😀\u200d\u200d😀",
        "😀\u200d😀😀",
        "😀\U000e0067",
    ],
)
def test_validation_rejects_non_emoji_or_multiple_fallbacks(fallback: str) -> None:
    document = BotContentDocument(
        1,
        "bad-fallback",
        (ParagraphBlock((CustomEmojiNode("123", fallback),)),),
        metadata(),
    )

    assert validate_content_document(document)[0].code == "invalid_custom_emoji_fallback"
