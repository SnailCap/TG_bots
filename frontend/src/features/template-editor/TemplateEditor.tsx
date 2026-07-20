export function TemplateEditor({
  path,
  content,
  isNew,
  onPathChange,
  onContentChange,
}: {
  path: string;
  content: string;
  isNew: boolean;
  onPathChange(path: string): void;
  onContentChange(content: string): void;
}) {
  return (
    <section className="editor" aria-label="Template editor">
      <header className="editor__header"><div><p className="eyebrow">Jinja template</p><h2>{isNew ? "New template" : path}</h2></div></header>
      <div className="form-grid">
        <label>Relative .txt path<input disabled={!isNew} value={path} onChange={(event) => onPathChange(event.target.value)} /></label>
        <label className="editor__raw">Template<textarea value={content} onChange={(event) => onContentChange(event.target.value)} /></label>
      </div>
    </section>
  );
}
