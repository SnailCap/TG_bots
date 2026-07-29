import { Eye } from "lucide-react";

export function PreviewToolRail({ open, onToggle }: { open: boolean; onToggle(): void }) {
  return (
    <aside className="studio-side-rail preview-tool-rail" aria-label="Studio tools">
      <button
        type="button"
        className={open ? "studio-side-rail__button studio-side-rail__button--active preview-tool-rail__button" : "studio-side-rail__button preview-tool-rail__button"}
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
  return <Eye aria-hidden="true" />;
}
