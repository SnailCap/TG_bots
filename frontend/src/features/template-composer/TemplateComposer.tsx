import { useEffect, useMemo, useState } from "react";
import { Maximize2, TriangleAlert } from "lucide-react";

import { VisualTemplateEditor } from "./editor";
import { parseTemplate } from "./parser";
import { defaultPreviewValues, renderTemplatePreview } from "./preview";
import { TemplatePreviewPanel } from "./preview-panel";
import { validateTemplate } from "./validation";
import { SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";

export function TemplateComposer({
  content,
  onContentChange,
  onOpenRichEditor,
  fields = SYSTEM_CONTEXT_FIELDS,
}: {
  content: string;
  onContentChange(content: string): void;
  onOpenRichEditor?(): void;
  fields?: readonly ContextFieldDefinition[];
}) {
  const [previewValues, setPreviewValues] = useState(() => defaultPreviewValues(fields));
  useEffect(() => {
    setPreviewValues((current) => ({ ...defaultPreviewValues(fields), ...current }));
  }, [fields]);
  const document = useMemo(() => parseTemplate(content, fields), [content, fields]);
  const diagnostics = useMemo(() => validateTemplate(document, fields), [document, fields]);
  const preview = useMemo(() => renderTemplatePreview(document, previewValues), [document, previewValues]);

  return (
    <fieldset className="template-composer" aria-label="Message text editor">
      <legend className="template-composer__legend">
        <span>Content</span>
        {onOpenRichEditor && <button type="button" className="template-composer__open-rich-editor" aria-label="Open rich text editor" title="Open rich text editor" onClick={onOpenRichEditor}><Maximize2 aria-hidden="true" /></button>}
      </legend>
      <div className="template-composer__workspace">
        <div className="template-composer__editor-column">
          <VisualTemplateEditor document={document} fields={fields} onChange={onContentChange} />

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

        <TemplatePreviewPanel fields={fields} preview={preview} values={previewValues} onValuesChange={setPreviewValues} />
      </div>
    </fieldset>
  );
}

function WarningIcon() {
  return <TriangleAlert aria-hidden="true" />;
}
