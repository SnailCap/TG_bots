import { useId } from "react";

import type { ActionOptions, HandlerUsage, ScheduleSpec } from "../../domain/project";
import { JsonObjectEditor, type HandlerActions } from "../action-editor/ActionEditor";
import { HandlerControls } from "../handlers/HandlerControls";
import { ResourceDropTarget } from "../resource-dnd";
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
      <div className="form-grid">
        <label>Schedule ID<input disabled={!isNew} value={value.id} onChange={(event) => onChange({ ...value, id: event.target.value })} /></label>
        <label>Trigger<Select ariaLabel="Trigger" value={value.trigger.type} disabled options={[{ value: "interval", label: "Interval" }]} onChange={() => undefined} /></label>
        <label>Interval, seconds<input type="number" min="0.001" step="any" value={value.trigger.seconds} onChange={(event) => onChange({ ...value, trigger: { type: "interval", seconds: Number(event.target.value) } })} /></label>
        <label>
          Task handler
          <ResourceDropTarget target={{ type: "handler-reference", handlerKind: "task" }} label="Drop task handler here" onDrop={(resource) => onChange({ ...value, handler: resource.value })}>
            <input list={`${listId}-tasks`} value={value.handler} onChange={(event) => onChange({ ...value, handler: event.target.value })} />
          </ResourceDropTarget>
          <datalist id={`${listId}-tasks`}>{taskHandlers.map((handler) => <option key={handler.id} value={handler.id} />)}</datalist>
        </label>
        <HandlerControls handlerId={value.handler} kind="task" handlers={options.handlers} onCreate={handlerActions.create} onRepair={handlerActions.repair} onOpen={handlerActions.open} onFindUsages={handlerActions.usages} createOptions={isNew ? undefined : { attachment: { type: "schedule", schedule_id: value.id }, target_revision: revision }} />
        <JsonObjectEditor label="Payload" value={value.payload} onChange={(payload) => onChange({ ...value, payload })} />
      </div>
    </section>
  );
}

export type { HandlerActions, HandlerUsage };
