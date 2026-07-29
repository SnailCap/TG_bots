import { Eye } from "lucide-react";

import { SYSTEM_CONTEXT_FIELDS } from "./context-catalog";
import type { PreviewValues } from "./preview";

export function TemplatePreviewPanel({
  preview,
  values,
  onValuesChange,
}: {
  preview: string;
  values: PreviewValues;
  onValuesChange(values: PreviewValues): void;
}) {
  return (
    <aside className="template-preview" aria-label="Message preview">
      <header>
        <div>
          <span className="template-panel-kicker">Preview</span>
          <h3>Test message</h3>
        </div>
        <PreviewIcon />
      </header>
      <div className="template-preview__divider" />
      <div className="template-preview__message" data-empty={preview ? "false" : "true"}>{preview || "Your rendered message will appear here."}</div>
      <details className="template-preview__values">
        <summary>Test user values</summary>
        <div className="template-preview__fields">
          {SYSTEM_CONTEXT_FIELDS.map((field) => (
            <label key={field.id}>
              <span>{field.label}</span>
              <input
                aria-label={`Preview ${field.label}`}
                type={field.valueType === "integer" ? "number" : "text"}
                value={values[field.path]}
                onChange={(event) => onValuesChange({
                  ...values,
                  [field.path]: field.valueType === "integer" ? Number(event.target.value) : event.target.value,
                })}
              />
            </label>
          ))}
        </div>
      </details>
    </aside>
  );
}

function PreviewIcon() {
  return <Eye className="template-preview__icon" aria-hidden="true" />;
}
