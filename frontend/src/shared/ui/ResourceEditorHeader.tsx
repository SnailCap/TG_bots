export function ResourceEditorHeader({
  category,
  title,
  saveAction,
}: {
  category: string;
  title: string;
  saveAction?: { disabled: boolean; saving: boolean; onSave(): void };
}) {
  return <header className="editor__header resource-editor-header">
    <div>
      <p className="eyebrow">{category}</p>
      <h2>{title}</h2>
    </div>
    {saveAction && <div className="editor__header-actions">
      <button type="button" className={saveAction.saving ? "button--saving" : undefined} aria-busy={saveAction.saving} disabled={saveAction.disabled} onClick={saveAction.onSave}>Save</button>
    </div>}
  </header>;
}
