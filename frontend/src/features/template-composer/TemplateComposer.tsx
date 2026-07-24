import { useMemo, useState } from "react";

import { VisualTemplateEditor } from "./editor";
import { parseTemplate } from "./parser";
import { defaultPreviewValues, renderTemplatePreview } from "./preview";
import { TemplatePreviewPanel } from "./preview-panel";
import { validateTemplate } from "./validation";

export function TemplateComposer({
  content,
  onContentChange,
}: {
  content: string;
  onContentChange(content: string): void;
}) {
  const [previewValues, setPreviewValues] = useState(defaultPreviewValues);
  const document = useMemo(() => parseTemplate(content), [content]);
  const diagnostics = useMemo(() => validateTemplate(document), [document]);
  const preview = useMemo(() => renderTemplatePreview(document, previewValues), [document, previewValues]);

  return (
    <fieldset className="template-composer" aria-label="Message text editor">
      <legend>Content</legend>
      <div className="template-composer__workspace">
        <div className="template-composer__editor-column">
          <VisualTemplateEditor document={document} onChange={onContentChange} />

          {diagnostics.length > 0 && (
            <div className="template-diagnostics" role="status" aria-label="Message diagnostics">
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
    </fieldset>
  );
}

function WarningIcon() {
  return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.1 14 13H2L8 2.1Z" /><path d="M8 5.6v3.6M8 11.4v.1" /></svg>;
}
