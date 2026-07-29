import { useMemo, useState } from "react";
import { Maximize2, TriangleAlert } from "lucide-react";

import { VisualTemplateEditor } from "./editor";
import { parseTemplate } from "./parser";
import { defaultPreviewValues, renderTemplatePreview } from "./preview";
import { TemplatePreviewPanel } from "./preview-panel";
import { validateTemplate } from "./validation";

export function TemplateComposer({
  content,
  onContentChange,
  onOpenRichEditor,
}: {
  content: string;
  onContentChange(content: string): void;
  onOpenRichEditor?(): void;
}) {
  const [previewValues, setPreviewValues] = useState(defaultPreviewValues);
  const document = useMemo(() => parseTemplate(content), [content]);
  const diagnostics = useMemo(() => validateTemplate(document), [document]);
  const preview = useMemo(() => renderTemplatePreview(document, previewValues), [document, previewValues]);

  return (
    <fieldset className="template-composer" aria-label="Message text editor">
      <legend className="template-composer__legend">
        <span>Content</span>
        {onOpenRichEditor && <button type="button" className="template-composer__open-rich-editor" aria-label="Open rich text editor" title="Open rich text editor" onClick={onOpenRichEditor}><Maximize2 aria-hidden="true" /></button>}
      </legend>
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
  return <TriangleAlert aria-hidden="true" />;
}
