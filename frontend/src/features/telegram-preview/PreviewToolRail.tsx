export function PreviewToolRail({ open, onToggle }: { open: boolean; onToggle(): void }) {
  return (
    <aside className="preview-tool-rail" aria-label="Studio tools">
      <button
        type="button"
        className={open ? "preview-tool-rail__button preview-tool-rail__button--active" : "preview-tool-rail__button"}
        aria-label="Предпросмотр"
        aria-pressed={open}
        title="Предпросмотр"
        data-tooltip="Предпросмотр"
        onClick={onToggle}
      >
        <PreviewIcon />
      </button>
    </aside>
  );
}

function PreviewIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M2.25 10s2.7-4.5 7.75-4.5 7.75 4.5 7.75 4.5-2.7 4.5-7.75 4.5S2.25 10 2.25 10Z" /><circle cx="10" cy="10" r="2.1" /></svg>;
}
