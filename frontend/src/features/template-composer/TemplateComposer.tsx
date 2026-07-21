import { useMemo, useState } from "react";

import { VisualTemplateEditor } from "./editor";
import { parseTemplate } from "./parser";
import { defaultPreviewValues, renderTemplatePreview } from "./preview";
import { TemplatePreviewPanel } from "./preview-panel";
import { validateTemplate } from "./validation";

type EditorMode = "visual" | "source";

export function TemplateComposer({
  content,
  path,
  onContentChange,
}: {
  content: string;
  path: string;
  onContentChange(content: string): void;
}) {
  const [mode, setMode] = useState<EditorMode>("visual");
  const [previewValues, setPreviewValues] = useState(defaultPreviewValues);
  const document = useMemo(() => parseTemplate(content), [content]);
  const diagnostics = useMemo(() => validateTemplate(document), [document]);
  const preview = useMemo(() => renderTemplatePreview(document, previewValues), [document, previewValues]);

  return (
    <section className="template-composer" aria-label={`Template composer for ${path}`}>
      <div className="template-composer__workspace">
        <div className="template-composer__editor-column">
          <header className="template-composer__toolbar">
            <div className="template-mode-switch" role="tablist" aria-label="Template editor mode">
              <button type="button" role="tab" aria-selected={mode === "visual"} className={mode === "visual" ? "template-mode-switch__button template-mode-switch__button--active" : "template-mode-switch__button"} onClick={() => setMode("visual")}>Visual</button>
              <button type="button" role="tab" aria-selected={mode === "source"} className={mode === "source" ? "template-mode-switch__button template-mode-switch__button--active" : "template-mode-switch__button"} onClick={() => setMode("source")}>Source</button>
            </div>
            <span className="template-composer__hint">Type <kbd>$</kbd> to insert a context field</span>
          </header>

          {mode === "visual" ? (
            <VisualTemplateEditor document={document} onChange={onContentChange} />
          ) : (
            <textarea
              className="template-source-editor"
              aria-label="Template source"
              spellCheck={false}
              value={content}
              onChange={(event) => onContentChange(event.target.value)}
              placeholder="Write Jinja template source…"
            />
          )}

          {diagnostics.length > 0 && (
            <div className="template-diagnostics" role="status" aria-label="Template diagnostics">
              {diagnostics.map((diagnostic, index) => (
                <div className="template-diagnostic" key={`${diagnostic.code}-${index}`}>
                  <WarningIcon /><span>{diagnostic.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <TemplatePreviewPanel preview={preview} values={previewValues} onValuesChange={setPreviewValues} />
      </div>
    </section>
  );
}

function WarningIcon() {
  return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.1 14 13H2L8 2.1Z" /><path d="M8 5.6v3.6M8 11.4v.1" /></svg>;
}

