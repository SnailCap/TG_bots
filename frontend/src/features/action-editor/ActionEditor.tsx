import { useEffect, useId, useState } from "react";

import {
  actionFor,
  type ActionOptions,
  type ActionSpec,
  type HandlerKind,
  type HandlerCreateOptions,
  type HandlerUsage,
  type JsonObject,
  type OutcomeRoutes,
} from "../../domain/project";
import { HandlerControls } from "../handlers/HandlerControls";
import { Select } from "../../shared/ui/Select";

const ACTION_LABELS: Array<{ value: ActionSpec["type"]; label: string }> = [
  { value: "noop", label: "No action" },
  { value: "view.render", label: "Render view" },
  { value: "flow.start", label: "Start flow" },
  { value: "flow.cancel", label: "Cancel flow" },
  { value: "flow.event", label: "Emit flow event" },
  { value: "flow.goto", label: "Go to state" },
  { value: "flow.finish", label: "Finish flow" },
  { value: "handler.invoke", label: "Custom handler" },
  { value: "task.enqueue", label: "Enqueue task" },
];

export interface ActionScope {
  expectedKind: Exclude<HandlerKind, "task">;
  currentFlow?: string;
}

export function allowedActions(scope: ActionScope): ActionSpec["type"][] {
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
  createOptions,
}: {
  action: ActionSpec;
  onChange(action: ActionSpec): void;
  options: ActionOptions;
  scope: ActionScope;
  handlerActions: HandlerActions;
  compact?: boolean;
  createOptions?: HandlerCreateOptions;
}) {
  const listId = useId().replace(/:/g, "");
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

  return (
    <div className={compact ? "action-editor action-editor--compact" : "action-editor"}>
      <label>
        Action
        <Select ariaLabel="Action" value={currentActionAllowed ? action.type : ""} placeholder="Choose a valid action" options={ACTION_LABELS.filter((item) => allowed.includes(item.value))} onChange={(value) => onChange(actionFor(value as ActionSpec["type"]))} />
        {!currentActionAllowed && <small className="error">{action.type} is not valid in this slot.</small>}
      </label>

      {(action.type === "view.render" || action.type === "flow.start" || action.type === "flow.goto" || action.type === "flow.event") && (
        <label>
          {action.type === "view.render" ? "View" : action.type === "flow.start" ? "Flow" : action.type === "flow.goto" ? "State" : "Event"}
          <input
            list={targetOptions.length ? `${listId}-targets` : undefined}
            value={action.target}
            onChange={(event) => onChange({ ...action, target: event.target.value })}
          />
          {targetOptions.length > 0 && <datalist id={`${listId}-targets`}>{targetOptions.map((item) => <option key={item} value={item} />)}</datalist>}
        </label>
      )}

      {(action.type === "flow.cancel" || action.type === "flow.finish") && (
        <label>
          Final view (optional)
          <input list={`${listId}-views`} value={action.view ?? ""} onChange={(event) => onChange({ ...action, view: event.target.value || undefined })} />
          <datalist id={`${listId}-views`}>{options.views.map((item) => <option key={item} value={item} />)}</datalist>
        </label>
      )}

      {action.type === "handler.invoke" && (
        <>
          <label>
            Handler name
            <input list={`${listId}-handlers`} value={action.handler} onChange={(event) => onChange({ ...action, handler: event.target.value })} />
            <datalist id={`${listId}-handlers`}>{compatibleHandlers.map((handler) => <option key={handler.id} value={handler.id} />)}</datalist>
          </label>
          <small className="muted">Studio uses this stable name for the binding and Python file.</small>
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
          <JsonObjectEditor label="Handler payload" value={action.payload ?? {}} onChange={(payload) => onChange({ ...action, payload })} />
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
          <label>
            Task handler
            <input list={`${listId}-tasks`} value={action.target} onChange={(event) => onChange({ ...action, target: event.target.value })} />
            <datalist id={`${listId}-tasks`}>{targetOptions.map((item) => <option key={item} value={item} />)}</datalist>
          </label>
          <label>
            Delay, seconds
            <input type="number" min="0" value={action.delay_seconds ?? 0} onChange={(event) => onChange({ ...action, delay_seconds: Number(event.target.value) })} />
          </label>
          <label>
            View after enqueue (optional)
            <input list={`${listId}-views`} value={action.view ?? ""} onChange={(event) => onChange({ ...action, view: event.target.value || undefined })} />
            <datalist id={`${listId}-views`}>{options.views.map((item) => <option key={item} value={item} />)}</datalist>
          </label>
          <JsonObjectEditor label="Task payload" value={action.payload ?? {}} onChange={(payload) => onChange({ ...action, payload })} />
        </>
      )}
    </div>
  );
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

export function JsonObjectEditor({ label, value, onChange }: { label: string; value: JsonObject; onChange(value: JsonObject): void }) {
  const [raw, setRaw] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState("");
  useEffect(() => setRaw(JSON.stringify(value, null, 2)), [value]);
  return (
    <label>
      {label}
      <textarea
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
      {error && <small className="error">{error}</small>}
    </label>
  );
}
