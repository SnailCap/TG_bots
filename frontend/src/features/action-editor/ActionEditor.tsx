import { useEffect, useState } from "react";

import {
  actionFor,
  type ActionOptions,
  type ActionSpec,
  type HandlerKind,
  type HandlerCreateOptions,
  type HandlerUsage,
  type JsonObject,
  type OutcomeRoutes,
  type Selection,
} from "../../domain/project";
import { HandlerControls } from "../handlers/HandlerControls";
import { ResourceDropTarget, type ResourceDropTargetSpec } from "../resource-dnd";
import { FormControlGroup, FormField } from "../../shared/ui/Form";
import { Select } from "../../shared/ui/Select";
import { SuggestionInput } from "../../shared/ui/SuggestionInput";

const ACTION_LABELS: Array<{ value: ActionSpec["type"]; label: string }> = [
  { value: "noop", label: "No action" },
  { value: "view.render", label: "Go to view" },
  { value: "flow.start", label: "Start flow" },
  { value: "flow.cancel", label: "Cancel flow" },
  { value: "flow.event", label: "Emit flow event" },
  { value: "flow.goto", label: "Go to state" },
  { value: "flow.finish", label: "Finish flow" },
  { value: "task.enqueue", label: "Enqueue task" },
  { value: "handler.invoke", label: "Custom handler" },
];

export const VIEW_BUTTON_ACTION_TYPES: ActionSpec["type"][] = [
  "view.render",
  "flow.start",
  "task.enqueue",
  "handler.invoke",
];

export interface ActionScope {
  expectedKind: Exclude<HandlerKind, "task">;
  currentFlow?: string;
  placement?: "view_button";
}

export function allowedActions(scope: ActionScope): ActionSpec["type"][] {
  if (scope.placement === "view_button") return VIEW_BUTTON_ACTION_TYPES;
  return ACTION_LABELS
    .map((item) => item.value)
    .filter((type) => type !== "flow.event" || scope.expectedKind === "button")
    .filter((type) => type !== "flow.goto" || Boolean(scope.currentFlow));
}

export interface HandlerActions {
  create(id: string, kind: HandlerKind, options?: HandlerCreateOptions): Promise<void>;
  repair(id: string): Promise<void>;
  open(id: string): Promise<void>;
  usages(id: string): Promise<HandlerUsage[]>;
}

function suggestedHandlerName(options: HandlerCreateOptions | undefined, kind: HandlerKind): string {
  const attachment = options?.attachment;
  if (!attachment) return "";
  switch (attachment.type) {
    case "view_button": return normalizeHandlerName(attachment.button_id);
    case "flow_event": return normalizeHandlerName(`${attachment.flow_id}.${attachment.state_id}.${attachment.event_id}`);
    case "state_on_message": return normalizeHandlerName(`${attachment.flow_id}.${attachment.state_id}.message`);
    case "state_on_enter": return normalizeHandlerName(`${attachment.flow_id}.${attachment.state_id}.enter`);
    case "flow_lifecycle": return normalizeHandlerName(`${attachment.flow_id}.${attachment.hook}`);
    case "command": return normalizeHandlerName(`command.${attachment.command}`);
    case "global_message_fallback": return "fallback.message";
    case "global_command_fallback": return "fallback.command";
    case "schedule": return normalizeHandlerName(`schedule.${attachment.schedule_id}`);
  }
}

function normalizeHandlerName(value: string): string {
  return value
    .split(".")
    .filter(Boolean)
    .map((part) => {
      const normalized = part.replace(/[^A-Za-z0-9_]/g, "_");
      return /^[A-Za-z]/.test(normalized) ? normalized : `handler_${normalized}`;
    })
    .join(".");
}

export function ActionEditor({
  action,
  onChange,
  options,
  scope,
  handlerActions,
  compact = false,
  bare = false,
  hideActionLabel = false,
  fieldLayout = "stacked",
  compoundPrimary = false,
  onOpenResource,
  createOptions,
}: {
  action: ActionSpec;
  onChange(action: ActionSpec): void;
  options: ActionOptions;
  scope: ActionScope;
  handlerActions: HandlerActions;
  compact?: boolean;
  bare?: boolean;
  hideActionLabel?: boolean;
  fieldLayout?: "row" | "stacked";
  compoundPrimary?: boolean;
  onOpenResource?(selection: Selection): void;
  createOptions?: HandlerCreateOptions;
}) {
  const compatibleHandlers = options.handlers.filter((handler) => handler.kind === scope.expectedKind);
  const defaultHandlerName = suggestedHandlerName(createOptions, scope.expectedKind);
  useEffect(() => {
    if (action.type === "handler.invoke" && !action.handler) {
      onChange({ ...action, handler: defaultHandlerName });
    }
  }, [action, defaultHandlerName, onChange]);
  const allowed = allowedActions(scope);
  const currentActionAllowed = allowed.includes(action.type);
  const targetOptions = action.type === "view.render"
    ? options.views
    : action.type === "flow.start"
      ? options.flows
      : action.type === "flow.goto"
        ? options.states
        : action.type === "task.enqueue"
          ? options.handlers.filter((handler) => handler.kind === "task").map((handler) => handler.id)
          : [];
  const resourceTarget: ResourceDropTargetSpec | null = action.type === "view.render"
    ? { type: "view-reference" }
    : action.type === "flow.start"
      ? { type: "flow-reference" }
      : null;
  const compoundTarget = compoundPrimary
    ? compoundActionTarget(action, options, compatibleHandlers.map((handler) => handler.id), scope, onChange, onOpenResource)
    : null;

  return (
    <div className={["action-editor", compact ? "action-editor--compact" : "", bare ? "action-editor--bare" : ""].filter(Boolean).join(" ")}>
      {compoundPrimary && !hideActionLabel
        ? <FormField label={<span className="action-editor__label">Action</span>} layout={fieldLayout}>
            {(controlProps) => (
              <FormControlGroup layout="split" className="text-source action-source">
                <Select {...controlProps} searchable ariaLabel="Action" value={currentActionAllowed ? action.type : ""} placeholder="Choose a valid action" options={ACTION_LABELS.filter((item) => allowed.includes(item.value))} onChange={(value) => onChange(actionFor(value as ActionSpec["type"]))} />
                {compoundTarget}
              </FormControlGroup>
            )}
          </FormField>
        : hideActionLabel
        ? <Select searchable ariaLabel="Action" value={currentActionAllowed ? action.type : ""} placeholder="Choose a valid action" options={ACTION_LABELS.filter((item) => allowed.includes(item.value))} onChange={(value) => onChange(actionFor(value as ActionSpec["type"]))} />
        : <FormField label={<span className="action-editor__label">Action</span>} layout={fieldLayout}>
            {(controlProps) => <Select {...controlProps} searchable ariaLabel="Action" value={currentActionAllowed ? action.type : ""} placeholder="Choose a valid action" options={ACTION_LABELS.filter((item) => allowed.includes(item.value))} onChange={(value) => onChange(actionFor(value as ActionSpec["type"]))} />}
          </FormField>}

      {!compoundPrimary && (action.type === "view.render" || action.type === "flow.start" || action.type === "flow.goto" || action.type === "flow.event") && (
        <FormField label={<span className="action-editor__label">{action.type === "view.render" ? "View" : action.type === "flow.start" ? "Flow" : action.type === "flow.goto" ? "State" : "Event"}</span>} layout={fieldLayout}>
          {(controlProps) => resourceTarget
            ? <ResourceDropTarget target={resourceTarget} label={`Drop ${resourceTarget.type === "view-reference" ? "view" : "flow"} here`} onDrop={(resource) => onChange({ ...action, target: resource.value })}>
                <Select {...controlProps} searchable ariaLabel={action.type === "view.render" ? "View" : "Flow"} value={action.target} placeholder={`Choose a ${action.type === "view.render" ? "view" : "flow"}`} options={targetOptions.map((value) => ({ value, label: value }))} onChange={(target) => onChange({ ...action, target })} />
              </ResourceDropTarget>
            : action.type === "flow.event"
              ? <input {...controlProps} value={action.target} onChange={(event) => onChange({ ...action, target: event.target.value })} />
              : <Select {...controlProps} searchable ariaLabel="State" value={action.target} placeholder="Choose a state" options={targetOptions.map((value) => ({ value, label: value }))} onChange={(target) => onChange({ ...action, target })} />}
        </FormField>
      )}

      {!compoundPrimary && (action.type === "flow.cancel" || action.type === "flow.finish") && (
        <FormField label={<span className="action-editor__label">Final view (optional)</span>} layout={fieldLayout}>
          {(controlProps) => (
            <ResourceDropTarget target={{ type: "view-reference" }} label="Drop view here" onDrop={(resource) => onChange({ ...action, view: resource.value })}>
              <Select {...controlProps} searchable ariaLabel="Final view (optional)" value={action.view ?? ""} placeholder="Choose a view" options={options.views.map((value) => ({ value, label: value }))} onChange={(view) => onChange({ ...action, view: view || undefined })} />
            </ResourceDropTarget>
          )}
        </FormField>
      )}

      {action.type === "handler.invoke" && (
        <>
          {!compoundPrimary && <FormField label={<span className="action-editor__label">Handler name</span>} layout={fieldLayout} hint="Studio uses this stable name for the binding and Python file.">
            {(controlProps) => (
              <ResourceDropTarget target={{ type: "handler-reference", handlerKind: scope.expectedKind }} label={`Drop ${scope.expectedKind} handler here`} onDrop={(resource) => onChange({ ...action, handler: resource.value })}>
                <input {...controlProps} value={action.handler} onChange={(event) => onChange({ ...action, handler: event.target.value })} />
              </ResourceDropTarget>
            )}
          </FormField>}
          <HandlerControls
            handlerId={action.handler}
            kind={scope.expectedKind}
            handlers={options.handlers}
            onCreate={handlerActions.create}
            onRepair={handlerActions.repair}
            onOpen={handlerActions.open}
            onFindUsages={handlerActions.usages}
            createOptions={{ ...createOptions, routes: action.outcomes }}
          />
          <JsonObjectEditor label="Handler payload" layout={fieldLayout} value={action.payload ?? {}} onChange={(payload) => onChange({ ...action, payload })} />
          <OutcomeEditor
            outcomes={action.outcomes}
            onChange={(outcomes) => onChange({ ...action, outcomes })}
            options={options}
            scope={scope}
            handlerActions={handlerActions}
            suggested={["success", ...(compatibleHandlers.find((item) => item.id === action.handler)?.outcomes ?? [])]}
          />
        </>
      )}

      {action.type === "task.enqueue" && (
        <>
          {!compoundPrimary && <FormField label={<span className="action-editor__label">Task handler</span>} layout={fieldLayout}>
            {(controlProps) => (
              <ResourceDropTarget target={{ type: "handler-reference", handlerKind: "task" }} label="Drop task handler here" onDrop={(resource) => onChange({ ...action, target: resource.value })}>
                <Select {...controlProps} searchable ariaLabel="Task handler" value={action.target} placeholder="Choose a task handler" options={targetOptions.map((value) => ({ value, label: value }))} onChange={(target) => onChange({ ...action, target })} />
              </ResourceDropTarget>
            )}
          </FormField>}
          <FormField label={<span className="action-editor__label">Delay, seconds</span>} layout={fieldLayout}>
            {(controlProps) => <input {...controlProps} type="number" min="0" value={action.delay_seconds ?? 0} onChange={(event) => onChange({ ...action, delay_seconds: Number(event.target.value) })} />}
          </FormField>
          <FormField label={<span className="action-editor__label">View after enqueue (optional)</span>} layout={fieldLayout}>
            {(controlProps) => (
              <ResourceDropTarget target={{ type: "view-reference" }} label="Drop view here" onDrop={(resource) => onChange({ ...action, view: resource.value })}>
                <Select {...controlProps} searchable ariaLabel="View after enqueue (optional)" value={action.view ?? ""} placeholder="Choose a view" options={options.views.map((value) => ({ value, label: value }))} onChange={(view) => onChange({ ...action, view: view || undefined })} />
              </ResourceDropTarget>
            )}
          </FormField>
          <JsonObjectEditor label="Task payload" layout={fieldLayout} value={action.payload ?? {}} onChange={(payload) => onChange({ ...action, payload })} />
        </>
      )}
    </div>
  );
}

function compoundActionTarget(
  action: ActionSpec,
  options: ActionOptions,
  compatibleHandlerIds: string[],
  scope: ActionScope,
  onChange: (action: ActionSpec) => void,
  onOpenResource?: (selection: Selection) => void,
) {
  const renderTarget = ({
    value,
    items,
    ariaLabel,
    placeholder,
    resourceName,
    dropTarget,
    openSelection,
    disabled = false,
    showBrowse = true,
    change,
  }: {
    value: string;
    items: string[];
    ariaLabel: string;
    placeholder: string;
    resourceName: string;
    dropTarget?: ResourceDropTargetSpec;
    openSelection?: Selection;
    disabled?: boolean;
    showBrowse?: boolean;
    change(value: string): void;
  }) => {
    const input = (
      <SuggestionInput
        value={value}
        items={items}
        ariaLabel={ariaLabel}
        placeholder={placeholder}
        browseLabel={`Browse ${resourceName}`}
        pickerLabel={`Choose ${resourceName}`}
        pickerEyebrow={resourceName}
        emptyText={`No matching ${resourceName}.`}
        disabled={disabled}
        showBrowse={showBrowse}
        onChange={change}
        onOpen={openSelection && onOpenResource ? () => onOpenResource(openSelection) : undefined}
      />
    );
    return dropTarget
      ? <ResourceDropTarget target={dropTarget} label={`Drop ${resourceName} here`} className="action-source__target" onDrop={(resource) => change(resource.value)}>{input}</ResourceDropTarget>
      : input;
  };

  switch (action.type) {
    case "view.render":
      return renderTarget({ value: action.target, items: options.views, ariaLabel: "Action target", placeholder: "Choose or enter a view", resourceName: "views", dropTarget: { type: "view-reference" }, openSelection: { kind: "view", id: action.target }, change: (target) => onChange({ ...action, target }) });
    case "flow.start":
      return renderTarget({ value: action.target, items: options.flows, ariaLabel: "Action target", placeholder: "Choose or enter a flow", resourceName: "flows", dropTarget: { type: "flow-reference" }, openSelection: { kind: "flow", id: action.target }, change: (target) => onChange({ ...action, target }) });
    case "flow.goto":
      return renderTarget({ value: action.target, items: options.states, ariaLabel: "Action target", placeholder: "Choose or enter a state", resourceName: "states", openSelection: scope.currentFlow ? { kind: "flow", id: scope.currentFlow } : undefined, change: (target) => onChange({ ...action, target }) });
    case "flow.event":
      return renderTarget({ value: action.target, items: [], ariaLabel: "Action target", placeholder: "Enter an event", resourceName: "events", showBrowse: false, change: (target) => onChange({ ...action, target }) });
    case "flow.cancel":
    case "flow.finish":
      return renderTarget({ value: action.view ?? "", items: options.views, ariaLabel: "Action target", placeholder: "Optional final view", resourceName: "views", dropTarget: { type: "view-reference" }, openSelection: action.view ? { kind: "view", id: action.view } : undefined, change: (view) => onChange({ ...action, view: view || undefined }) });
    case "handler.invoke":
      return renderTarget({ value: action.handler, items: compatibleHandlerIds, ariaLabel: "Action target", placeholder: "Choose or enter a handler", resourceName: "handlers", dropTarget: { type: "handler-reference", handlerKind: scope.expectedKind }, openSelection: { kind: "handler", id: action.handler }, change: (handler) => onChange({ ...action, handler }) });
    case "task.enqueue": {
      const taskHandlers = options.handlers.filter((handler) => handler.kind === "task").map((handler) => handler.id);
      return renderTarget({ value: action.target, items: taskHandlers, ariaLabel: "Action target", placeholder: "Choose or enter a task handler", resourceName: "task handlers", dropTarget: { type: "handler-reference", handlerKind: "task" }, openSelection: { kind: "handler", id: action.target }, change: (target) => onChange({ ...action, target }) });
    }
    default:
      return renderTarget({ value: "", items: [], ariaLabel: "Action target", placeholder: "No target", resourceName: "targets", disabled: true, showBrowse: false, change: () => undefined });
  }
}

export function OutcomeEditor({
  outcomes,
  onChange,
  options,
  scope,
  handlerActions,
  suggested = ["success"],
}: {
  outcomes: OutcomeRoutes;
  onChange(outcomes: OutcomeRoutes): void;
  options: ActionOptions;
  scope: ActionScope;
  handlerActions: HandlerActions;
  suggested?: string[];
}) {
  const [newName, setNewName] = useState("");
  const names = Object.keys(outcomes);
  const add = (name: string) => {
    const normalized = name.trim();
    if (!normalized || outcomes[normalized]) return;
    onChange({ ...outcomes, [normalized]: actionFor("noop") });
    setNewName("");
  };
  return (
    <fieldset className="outcome-editor">
      <legend>Outcome routes</legend>
      {names.length === 0 && <p className="muted">No outcome routes.</p>}
      {names.map((name) => (
        <div className="outcome-route" key={name}>
          <strong>{name}</strong>
          <ActionEditor
            action={outcomes[name]}
            onChange={(route) => onChange({ ...outcomes, [name]: route })}
            options={options}
            scope={scope}
            handlerActions={handlerActions}
            compact
          />
          <button type="button" className="button--quiet" onClick={() => {
            const next = { ...outcomes };
            delete next[name];
            onChange(next);
          }}>Remove route</button>
        </div>
      ))}
      <div className="inline-fields">
        <input list="suggested-outcomes" aria-label="New outcome name" value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="success" />
        <datalist id="suggested-outcomes">{suggested.map((item) => <option key={item} value={item} />)}</datalist>
        <button type="button" className="button--quiet" onClick={() => add(newName)}>Add route</button>
      </div>
    </fieldset>
  );
}

export function JsonObjectEditor({ label, layout = "stacked", value, onChange }: { label: string; layout?: "row" | "stacked"; value: JsonObject; onChange(value: JsonObject): void }) {
  const [raw, setRaw] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState("");
  useEffect(() => setRaw(JSON.stringify(value, null, 2)), [value]);
  return (
    <FormField label={label} layout={layout} span="full" error={error || undefined}>
      {(controlProps) => (
        <textarea
          {...controlProps}
          value={raw}
          onChange={(event) => {
            setRaw(event.target.value);
            try {
              const parsed: unknown = JSON.parse(event.target.value);
              if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Payload must be a JSON object.");
              onChange(parsed as JsonObject);
              setError("");
            } catch (caught) {
              setError(caught instanceof Error ? caught.message : "Invalid JSON");
            }
          }}
        />
      )}
    </FormField>
  );
}
