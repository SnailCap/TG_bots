import { useState } from "react";

import type { ActionOptions, ViewSpec } from "../../domain/project";
import { type HandlerActions } from "../action-editor/ActionEditor";
import { KeyboardComposer } from "../keyboard-composer/KeyboardComposer";
import { TemplateComposer } from "../template-composer/TemplateComposer";
import { FormField, FormGrid, FormSectionDivider } from "../../shared/ui/Form";
import { AccessSelect, type AccessLevel } from "../../shared/ui/AccessSelect";
import type { StudioApiClient } from "../../studio/api";
import { useResourceVariableFields } from "../template-composer/use-resource-variable-fields";

export function ViewEditor({
  value,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
  onOpenTextEditor,
  textContent,
  onTextContentChange,
  displayName,
  nameIsDefault = false,
  onRename,
  api,
  projectId,
}: {
  value: ViewSpec;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ViewSpec): void;
  onOpenTextEditor?(): void;
  textContent: string;
  onTextContentChange(content: string): void;
  displayName?: string;
  nameIsDefault?: boolean;
  onRename?(name: string): void;
  api?: StudioApiClient;
  projectId?: string;
}) {
  const [accessMockup, setAccessMockup] = useState<AccessLevel>("everyone");
  const [nameDraft, setNameDraft] = useState("");
  const effectiveName = displayName ?? value.id;
  const variableFields = useResourceVariableFields(api, projectId ?? "", {
    resourceType: "view",
    resourceId: value.id,
  });
  return (
    <section className="editor editor--wide" aria-label="View editor">
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
        <FormSectionDivider />
        <div className="view-settings__content">
          <TemplateComposer fields={variableFields} content={textContent} onContentChange={onTextContentChange} onOpenRichEditor={onOpenTextEditor} />
        </div>
        <FormSectionDivider />
        <KeyboardComposer
          viewId={value.id}
          keyboard={value.keyboard}
          variableFields={variableFields}
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
