# Template Composer MVP

Template Composer adds a visual editing mode for plain text templates without changing the project format. The editor shows supported context references as atomic tokens, while Studio continues to save a normal UTF-8 Jinja `.txt` file through the existing template API.

## Source of truth

Visual and Source modes are two projections of one Jinja string. The visual document model is transient frontend state and is never written into the bot project. This keeps templates readable outside Studio, useful in Git diffs, and compatible with the autonomous runtime.

The conversion boundary is explicit:

```text
Jinja string -> parseTemplate -> TemplateDocument -> serializeTemplate -> Jinja string
```

Known expressions retain their original source spelling when parsed. Newly inserted tokens use the canonical form `{{ user.first_name }}`. Unknown and unsupported fragments retain their exact source.

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

## MVP limits

- Only the fixed system user fields are available.
- Only simple `scope.field` output expressions are visualized.
- There is no flow context schema or custom field editor.
- Filters, fallbacks, conditions, and loops are not evaluated visually.
- There is no Python generation, handler change, or rename refactoring.
- `tg-bot-core` and project schema are unchanged.

