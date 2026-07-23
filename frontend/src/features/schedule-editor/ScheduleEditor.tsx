import { useId } from "react";

import type { ActionOptions, HandlerUsage, ScheduleSpec } from "../../domain/project";
import { JsonObjectEditor, type HandlerActions } from "../action-editor/ActionEditor";
import { HandlerControls } from "../handlers/HandlerControls";
import { ResourceDropTarget } from "../resource-dnd";
import { FormField, FormGrid } from "../../shared/ui/Form";
import { Select } from "../../shared/ui/Select";

export function ScheduleEditor({
  value,
  sourcePath,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
}: {
  value: ScheduleSpec;
  sourcePath: string;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ScheduleSpec): void;
}) {
  const listId = useId().replace(/:/g, "");
  const taskHandlers = options.handlers.filter((handler) => handler.kind === "task");
  return (
    <section className="editor" aria-label="Schedule editor">
      <FormGrid columns={2}>
        <FormField label="Schedule ID" layout="stacked" disabled={!isNew}>
          {(controlProps) => <input {...controlProps} value={value.id} onChange={(event) => onChange({ ...value, id: event.target.value })} />}
        </FormField>
        <FormField label="Trigger" layout="stacked" disabled>
          {(controlProps) => <Select {...controlProps} ariaLabel="Trigger" value={value.trigger.type} options={[{ value: "interval", label: "Interval" }]} onChange={() => undefined} />}
        </FormField>
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
        <JsonObjectEditor label="Payload" value={value.payload} onChange={(payload) => onChange({ ...value, payload })} />
      </FormGrid>
    </section>
  );
}

export type { HandlerActions, HandlerUsage };
