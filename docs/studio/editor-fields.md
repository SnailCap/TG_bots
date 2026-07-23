# Studio editor field standard

Studio resource editors use the View Editor as the reference interaction pattern. A resource editor edits one selected resource at a time; collections belong in the explorer, not inside a single form.

## Field anatomy

- Use a visible, sentence-case label ending with `:` (`Name:`, `Access:`, `Action:`).
- Wrap ordinary properties in `editor-field`. On desktop, align the label and control in a compact two-column row with a 56 px label column and a 10 px gap.
- Keep short identity controls bounded instead of stretching them across the editor.
- Put structured controls such as `ActionEditor` in their own labeled row. The outer resource field owns the label; nested controls should not repeat it.
- Inputs use the shared graphite surface, 2 px radius, visible hover border and blue focus ring defined in `styles.css`.
- Use controlled React fields (`value` + `onChange`). Preserve unknown or currently hidden schema properties when changing one field.

## Resource lifecycle

- The explorer lists individual resources and owns create, select, rename and delete entry points.
- Creating a resource persists a valid minimal value, selects it and opens its editor.
- Save uses the latest revision and keeps the editor open. Rename updates the explorer identity and tab key.
- Destructive actions use an explicit text label and remain separate from the primary Save action.
- Empty collections show their section and creation affordance rather than a blank aggregate editor.

## Validation and accessibility

- Labels remain visible; placeholders are examples, never replacements for labels.
- Validate authoritative schema rules on save and show the recovery path. Disable Save only when a required identity field is empty.
- Preserve keyboard navigation, visible focus, semantic `label` elements and descriptive `aria-label` values.
- Below 761 px, rows collapse to a single column without horizontal scrolling.

## Command application

`commands` is an explorer section backed by the aggregate `resources/commands.json` file. Each entry in `commands[]` is presented as an individual resource. Its editor exposes:

- `Name:` as a Telegram command name with a fixed `/` prefix;
- `Action:` as the shared declarative action editor.

Fallbacks remain a fixed `fallbacks` item because they are aggregate command-routing settings, not commands.
