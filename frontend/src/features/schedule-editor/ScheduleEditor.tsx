import { useId, useState } from "react";

import type { ActionOptions, HandlerUsage, ScheduleSpec } from "../../domain/project";
import { JsonObjectEditor, type HandlerActions } from "../action-editor/ActionEditor";
import { HandlerControls } from "../handlers/HandlerControls";
import { ResourceDropTarget } from "../resource-dnd";
import { FormField, FormGrid, FormSectionDivider } from "../../shared/ui/Form";
import { Select } from "../../shared/ui/Select";

export function ScheduleEditor({
  value,
  sourcePath,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
  displayName,
  nameIsDefault = false,
  onRename,
}: {
  value: ScheduleSpec;
  sourcePath: string;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ScheduleSpec): void;
  displayName?: string;
  nameIsDefault?: boolean;
  onRename?(name: string): void;
}) {
  const listId = useId().replace(/:/g, "");
  const [nameDraft, setNameDraft] = useState("");
  const taskHandlers = options.handlers.filter((handler) => handler.kind === "task");
  const effectiveName = displayName ?? value.id;
  return (
    <section className="editor" aria-label="Schedule editor">
      <FormGrid columns={2}>
        <FormField label="Name" layout="stacked">
          {(controlProps) => <input {...controlProps} value={nameIsDefault ? nameDraft : (nameDraft || effectiveName)} placeholder={nameIsDefault ? effectiveName : undefined} onChange={(event) => {
            if (displayName === undefined) onChange({ ...value, id: event.target.value });
            else setNameDraft(event.target.value);
          }} onBlur={() => {
            const next = nameDraft.trim();
            if (next && next !== effectiveName) onRename?.(next);
            setNameDraft("");
          }} />}
        </FormField>
        <FormField label="Trigger" layout="stacked" disabled>
          {(controlProps) => <Select {...controlProps} ariaLabel="Trigger" value={value.trigger.type} options={[{ value: "interval", label: "Interval" }]} onChange={() => undefined} />}
        </FormField>
        <FormSectionDivider />
        <FormField label="Interval, seconds" layout="stacked">
          {(controlProps) => <input {...controlProps} type="number" min="0.001" step="any" value={value.trigger.seconds} onChange={(event) => onChange({ ...value, trigger: { type: "interval", seconds: Number(event.target.value) } })} />}
        </FormField>
        <FormField label="Task handler" layout="stacked">
          {(controlProps) => <>
            <ResourceDropTarget target={{ type: "handler-reference", handlerKind: "task" }} label="Drop task handler here" onDrop={(resource) => onChange({ ...value, handler: resource.value })}>
              <input {...controlProps} list={`${listId}-tasks`} value={value.handler} onChange={(event) => onChange({ ...value, handler: event.target.value })} />
            </ResourceDropTarget>
            <datalist id={`${listId}-tasks`}>{taskHandlers.map((handler) => <option key={handler.id} value={handler.id} />)}</datalist>
          </>}
        </FormField>
        <HandlerControls handlerId={value.handler} kind="task" handlers={options.handlers} onCreate={handlerActions.create} onRepair={handlerActions.repair} onOpen={handlerActions.open} onFindUsages={handlerActions.usages} createOptions={isNew ? undefined : { attachment: { type: "schedule", schedule_id: value.id }, target_revision: revision }} />
        <FormSectionDivider />
        <JsonObjectEditor label="Payload" value={value.payload} onChange={(payload) => onChange({ ...value, payload })} />
      </FormGrid>
    </section>
  );
}

export type { HandlerActions, HandlerUsage };
