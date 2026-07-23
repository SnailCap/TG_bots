# Template Composer

Template Composer adds a visual editing mode for Telegram HTML templates without changing the project format. The editor shows supported context references as atomic tokens and Telegram formatting as a visual projection, while Studio continues to save a normal UTF-8 Jinja `.txt` file through the existing template API.

## Source of truth

Visual and Source modes are two projections of one Jinja string. The visual document model is transient frontend state and is never written into the bot project. This keeps templates readable outside Studio, useful in Git diffs, and compatible with the autonomous runtime.

The conversion boundary is explicit:

```text
Jinja string -> parseTemplate -> TemplateDocument -> serializeTemplate -> Jinja string
```

Known expressions retain their original source spelling when parsed. Newly inserted tokens use the canonical form `{{ user.first_name }}`. Unknown and unsupported fragments retain their exact source.

Telegram formatting is part of the transient `TemplateDocument`; it is not a second persisted document format. Visual edits serialize to canonical Bot API HTML, and switching from Source back to Visual normalizes official aliases such as `<strong>`, `<em>`, `<ins>`, `<del>`, and `<span class="tg-spoiler">`.

## Context catalog

The fixed MVP catalog lives in `frontend/src/features/template-composer/context-catalog.ts`. Every entry contains a stable ID, Jinja path, visible label and group, value type, optionality, description, and preview example.

The first catalog exposes only:

- `user.telegram_id`
- `user.username`
- `user.first_name`
- `user.last_name`
- `user.language_code`

To add a future scope, add field definitions to a catalog passed to parser, search, and validation. Do not hard-code field metadata in the React editor or add a second persisted template model.

## Supported expressions

Visual mode recognizes simple two-part references such as `{{ user.first_name }}`. Whitespace inside braces is accepted. Typing `$` opens a searchable field list; choosing a field replaces the query with an atomic token. Backspace or Delete removes the complete token.

An unknown simple reference such as `{{ order.total }}` becomes an unresolved warning token. A complex expression, Jinja statement, or comment becomes a raw fragment. Both forms preserve the original Jinja and produce an inline diagnostic. Source mode remains available for direct editing.

## Preview

The frontend preview is deliberately isolated in `preview.ts`. It substitutes only supported simple context tokens with editable example values. It is not a Jinja implementation and does not evaluate filters, statements, loops, or conditions. Unsupported source is shown unchanged.

## Telegram HTML formatting

Visual mode supports the regular-message HTML entities accepted by Telegram Bot API:

- bold, italic, underline, strikethrough, and spoiler;
- web links and `tg://user` mentions;
- inline code and preformatted code blocks with an optional language;
- regular and expandable block quotes;
- custom emoji with a required fallback emoji;
- dynamic date/time entities with Telegram's `r|w?[dD]?[tT]?` format.

Selecting text opens a compact formatting toolbar. Common inline styles are shown directly; block and special entities are available in More. The editor uses Telegram Desktop keyboard shortcuts while focus and selection remain inside Visual mode.

`telegram-formatting.ts` is the shared action catalog for toolbar actions, HTML aliases, and keyboard shortcuts. `paste-sanitizer.ts` removes external styles, classes, unsafe links, and unsupported markup while retaining formatting that can be represented by Telegram HTML.

Before Visual edits are published, the serializer:

- emits only the canonical Telegram tags;
- escapes plain `<`, `>`, and `&`;
- removes duplicate inline wrappers;
- prevents formatting inside `<code>` and `<pre>`;
- prevents nested block quotes and nested exclusive entities;
- preserves Jinja tokens and unsupported Jinja fragments without evaluating them.

## Limits

- Only the fixed system user fields are available.
- Only simple `scope.field` output expressions are visualized.
- There is no flow context schema or custom field editor.
- Filters, fallbacks, conditions, and loops are not evaluated visually.
- There is no Python generation, handler change, or rename refactoring.
- `tg-bot-core` and project schema are unchanged.
