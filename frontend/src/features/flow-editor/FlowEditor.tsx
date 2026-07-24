import { useState } from "react";

import type { ActionOptions, FlowSpec } from "../../domain/project";
import type { HandlerActions } from "../action-editor/ActionEditor";
import { FormField, FormGrid } from "../../shared/ui/Form";

export function FlowEditor({
  value,
  onChange,
  displayName,
  nameIsDefault = false,
  onRename,
}: {
  value: FlowSpec;
  sourcePath: string;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: FlowSpec): void;
  displayName?: string;
  nameIsDefault?: boolean;
  onRename?(name: string): void;
}) {
  const [nameDraft, setNameDraft] = useState("");
  const effectiveName = displayName ?? value.id;

  return (
    <section className="editor" aria-label="Flow editor">
      <FormGrid width="standard">
        <FormField label="Name">
          {(controlProps) => <input
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
          />}
        </FormField>
      </FormGrid>
    </section>
  );
}
