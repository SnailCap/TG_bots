import { useLayoutEffect, useRef, useState } from "react";

import type { ActionOptions, TextSpec, ViewSpec } from "../../domain/project";
import { type HandlerActions } from "../action-editor/ActionEditor";
import { KeyboardComposer } from "../keyboard-composer/KeyboardComposer";
import { ResourceDropTarget } from "../resource-dnd";
import { FormControlGroup, FormField, FormGrid, type FormControlProps } from "../../shared/ui/Form";
import { AccessSelect, type AccessLevel } from "../../shared/ui/AccessSelect";
import { Select } from "../../shared/ui/Select";
import { SuggestionInput } from "../../shared/ui/SuggestionInput";

export function ViewEditor({
  value,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
  onOpenTemplate,
  onCreateTemplate,
  displayName,
  nameIsDefault = false,
  onRename,
}: {
  value: ViewSpec;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ViewSpec): void;
  onOpenTemplate?(path: string): void;
  onCreateTemplate?(suggestedPath: string): void;
  displayName?: string;
  nameIsDefault?: boolean;
  onRename?(name: string): void;
}) {
  const [accessMockup, setAccessMockup] = useState<AccessLevel>("everyone");
  const [nameDraft, setNameDraft] = useState("");
  const effectiveName = displayName ?? value.id;
  return (
    <section className="editor" aria-label="View editor">
      <FormGrid columns={2} className="view-settings">
        <FormField label="Name:">
          {(controlProps) => (
            <input
              {...controlProps}
              value={nameIsDefault ? nameDraft : (nameDraft || effectiveName)}
              placeholder={nameIsDefault ? effectiveName : undefined}
              onChange={(event) => {
                if (displayName === undefined) onChange({ ...value, id: event.target.value });
                else setNameDraft(event.target.value);
              }}
              onBlur={() => {
                const next = nameDraft.trim();
                if (next && next !== effectiveName) onRename?.(next);
                setNameDraft("");
              }}
            />
          )}
        </FormField>
        <FormField label="Access:">
          {(controlProps) => (
            <AccessSelect {...controlProps} ariaLabel="Page access" value={accessMockup} onChange={setAccessMockup} />
          )}
        </FormField>
        <FormField label="Content:" span="full">
          {(controlProps) => (
            <TextSourceControl controlProps={controlProps} text={value.text} templates={options.templates ?? []} onChange={(text) => onChange({ ...value, text })} onOpenTemplate={onOpenTemplate} onCreateTemplate={onCreateTemplate} />
          )}
        </FormField>
        <KeyboardComposer
          viewId={value.id}
          keyboard={value.keyboard}
          options={options}
          handlerActions={handlerActions}
          createOptions={isNew ? undefined : {
            attachment: { type: "view_button", view_id: value.id, button_id: "" },
            target_revision: revision,
          }}
          onChange={(keyboard) => onChange({ ...value, keyboard })}
        />
      </FormGrid>
    </section>
  );
}

function TextSourceControl({ controlProps, text, templates, onChange, onOpenTemplate, onCreateTemplate }: { controlProps: FormControlProps; text: TextSpec; templates: string[]; onChange(text: TextSpec): void; onOpenTemplate?: (path: string) => void; onCreateTemplate?(suggestedPath: string): void }) {
  const isTemplate = "template" in text;
  const templateValue = isTemplate ? text.template ?? "" : "";

  return <FormControlGroup layout="split" className="text-source">
    <Select {...controlProps} clickOnly ariaLabel="Text source" value={isTemplate ? "template" : "inline"} options={[{ value: "inline", label: "Text" }, { value: "template", label: "Template" }]} onChange={(mode) => onChange(mode === "template" ? { template: "" } : { inline: "" })} />
    {isTemplate
      ? <ResourceDropTarget target={{ type: "template-reference" }} label="Drop template here" className="text-source__template" onDrop={(resource) => onChange({ template: resource.value })}>
          <SuggestionInput
            value={templateValue}
            items={templates}
            ariaLabel="Template"
            placeholder="Template name"
            browseLabel="Browse templates"
            pickerLabel="Choose template"
            pickerEyebrow="Templates"
            emptyText="No matching templates."
            createLabel="Create template"
            recentStorageKey="tg-bot-studio.recent-templates"
            onChange={(template) => onChange({ template })}
            onOpen={onOpenTemplate ? () => onOpenTemplate(templateValue.trim()) : undefined}
            onCreate={onCreateTemplate}
          />
        </ResourceDropTarget>
      : <AutoGrowTextarea value={text.inline} onChange={(inline) => onChange({ inline })} />}
  </FormControlGroup>;
}

function AutoGrowTextarea({ value, onChange }: { value: string; onChange(value: string): void }) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const currentHeight = textarea.getBoundingClientRect().height;
    const minimumHeight = Number.parseFloat(window.getComputedStyle(textarea).minHeight) || 32;
    textarea.style.height = "auto";
    const nextHeight = Math.max(minimumHeight, Math.min(textarea.scrollHeight, 180));
    textarea.style.height = `${currentHeight}px`;
    const frame = window.requestAnimationFrame(() => { textarea.style.height = `${nextHeight}px`; });
    return () => window.cancelAnimationFrame(frame);
  }, [value]);
  return <textarea ref={textareaRef} className="text-source__inline" aria-label="Inline text" value={value} rows={1} placeholder="Write the message text" onChange={(event) => onChange(event.target.value)} />;
}
