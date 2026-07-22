import { useId, useState } from "react";

import type {
  ActionOptions,
  FlowLifecycle,
  FlowSpec,
  HandlerInvocation,
  HandlerCreateOptions,
  StateSpec,
} from "../../domain/project";
import { HandlerControls } from "../handlers/HandlerControls";
import { OutcomeEditor, type ActionScope, type HandlerActions } from "../action-editor/ActionEditor";
import { ResourceDropTarget } from "../resource-dnd";
import { Select } from "../../shared/ui/Select";

const LIFECYCLE_HOOKS: Array<keyof FlowLifecycle> = ["on_start", "on_complete", "on_cancel", "on_error"];

export function FlowEditor({
  value,
  sourcePath,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
}: {
  value: FlowSpec;
  sourcePath: string;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: FlowSpec): void;
}) {
  const [newState, setNewState] = useState("");
  const stateIds = Object.keys(value.states);
  const flowOptions = { ...options, states: stateIds };
  return (
    <section className="editor editor--wide" aria-label="Flow editor">
      <div className="form-grid">
        <label>Flow ID<input disabled={!isNew} value={value.id} onChange={(event) => onChange({ ...value, id: event.target.value })} /></label>
        <label>
          Initial state
          <Select ariaLabel="Initial state" value={value.initial_state} options={stateIds.map((stateId) => ({ value: stateId, label: stateId }))} onChange={(initial_state) => onChange({ ...value, initial_state })} />
        </label>
        <fieldset>
          <legend>Flow lifecycle</legend>
          {LIFECYCLE_HOOKS.map((hook) => (
            <InvocationSlot
              key={hook}
              title={hook}
              invocation={value.lifecycle[hook]}
              scope={{ expectedKind: "lifecycle", currentFlow: hook === "on_start" ? value.id : undefined }}
              options={flowOptions}
              handlerActions={handlerActions}
              createOptions={isNew ? undefined : {
                attachment: { type: "flow_lifecycle", flow_id: value.id, hook },
                target_revision: revision,
              }}
              onChange={(invocation) => onChange({ ...value, lifecycle: { ...value.lifecycle, [hook]: invocation } })}
            />
          ))}
        </fieldset>
        <fieldset className="state-list">
          <legend>States</legend>
          {Object.entries(value.states).map(([stateId, state]) => (
            <StateEditor
              key={stateId}
              flowId={value.id}
              stateId={stateId}
              state={state}
              options={flowOptions}
              handlerActions={handlerActions}
              removable={stateIds.length > 1}
              targetRevision={isNew ? undefined : revision}
              onChange={(next) => onChange({ ...value, states: { ...value.states, [stateId]: next } })}
              onRemove={() => {
                const states = { ...value.states };
                delete states[stateId];
                const remaining = Object.keys(states);
                onChange({ ...value, states, initial_state: value.initial_state === stateId ? remaining[0] ?? "" : value.initial_state });
              }}
            />
          ))}
          <div className="inline-fields">
            <input aria-label="New state ID" value={newState} onChange={(event) => setNewState(event.target.value)} placeholder="payment" />
            <button type="button" className="button--quiet" onClick={() => {
              const id = newState.trim();
              if (!id || value.states[id]) return;
              onChange({ ...value, states: { ...value.states, [id]: { view: options.views[0] ?? "", events: {} } } });
              setNewState("");
            }}>Add state</button>
          </div>
        </fieldset>
      </div>
    </section>
  );
}

function StateEditor({
  flowId,
  stateId,
  state,
  options,
  handlerActions,
  removable,
  targetRevision,
  onChange,
  onRemove,
}: {
  flowId: string;
  stateId: string;
  state: StateSpec;
  options: ActionOptions;
  handlerActions: HandlerActions;
  removable: boolean;
  targetRevision?: string;
  onChange(state: StateSpec): void;
  onRemove(): void;
}) {
  const [newEvent, setNewEvent] = useState("");
  return (
    <article className="state-card">
      <header><div><strong>{stateId}</strong><small>{flowId}.{stateId}</small></div>{removable && <button type="button" className="button--danger" onClick={onRemove}>Remove state</button>}</header>
      <label>
        Default view
        <ResourceDropTarget target={{ type: "view-reference" }} label="Drop view here" onDrop={(resource) => onChange({ ...state, view: resource.value })}>
          <Select ariaLabel="Default view" value={state.view} options={[{ value: "", label: "Select a view" }, ...options.views.map((viewId) => ({ value: viewId, label: viewId }))]} onChange={(view) => onChange({ ...state, view })} />
        </ResourceDropTarget>
      </label>
      <InvocationSlot title="on_enter" invocation={state.on_enter} scope={{ expectedKind: "lifecycle", currentFlow: flowId }} options={options} handlerActions={handlerActions} createOptions={targetRevision ? { attachment: { type: "state_on_enter", flow_id: flowId, state_id: stateId }, target_revision: targetRevision } : undefined} onChange={(on_enter) => onChange({ ...state, on_enter })} />
      <InvocationSlot title="on_message" invocation={state.on_message} scope={{ expectedKind: "message", currentFlow: flowId }} options={options} handlerActions={handlerActions} createOptions={targetRevision ? { attachment: { type: "state_on_message", flow_id: flowId, state_id: stateId }, target_revision: targetRevision } : undefined} onChange={(on_message) => onChange({ ...state, on_message })} />
      <fieldset>
        <legend>Named events</legend>
        {Object.entries(state.events).map(([eventId, invocation]) => (
          <div className="event-card" key={eventId}>
            <InvocationEditor title={eventId} invocation={invocation} scope={{ expectedKind: "button", currentFlow: flowId }} options={options} handlerActions={handlerActions} createOptions={targetRevision ? { attachment: { type: "flow_event", flow_id: flowId, state_id: stateId, event_id: eventId }, target_revision: targetRevision } : undefined} onChange={(next) => onChange({ ...state, events: { ...state.events, [eventId]: next } })} />
            <button type="button" className="button--quiet" onClick={() => {
              const events = { ...state.events };
              delete events[eventId];
              onChange({ ...state, events });
            }}>Remove event</button>
          </div>
        ))}
        <div className="inline-fields">
          <input aria-label={`New event for ${stateId}`} value={newEvent} onChange={(event) => setNewEvent(event.target.value)} placeholder="confirm" />
          <button type="button" className="button--quiet" onClick={() => {
            const id = newEvent.trim();
            if (!id || state.events[id]) return;
              onChange({
                ...state,
                events: {
                  ...state.events,
                  [id]: { handler: "", outcomes: { success: { type: "noop" } } },
                },
              });
            setNewEvent("");
          }}>Add event</button>
        </div>
      </fieldset>
    </article>
  );
}

function InvocationSlot({
  title,
  invocation,
  scope,
  options,
  handlerActions,
  createOptions,
  onChange,
}: {
  title: string;
  invocation?: HandlerInvocation;
  scope: ActionScope;
  options: ActionOptions;
  handlerActions: HandlerActions;
  createOptions?: HandlerCreateOptions;
  onChange(invocation?: HandlerInvocation): void;
}) {
  return (
    <section className="invocation-slot">
      {!invocation
        ? <ResourceDropTarget target={{ type: "handler-reference", handlerKind: scope.expectedKind }} label={`Drop ${scope.expectedKind} handler here`} onDrop={(resource) => onChange({ handler: resource.value, outcomes: { success: { type: "noop" } } })}>
            <button
              type="button"
              className="button--quiet"
              onClick={() => onChange({ handler: "", outcomes: { success: { type: "noop" } } })}
            >Add {title} handler</button>
          </ResourceDropTarget>
        : <>
          <InvocationEditor title={title} invocation={invocation} scope={scope} options={options} handlerActions={handlerActions} createOptions={createOptions} onChange={onChange} />
          <button type="button" className="button--quiet" onClick={() => onChange(undefined)}>Detach {title}</button>
        </>}
    </section>
  );
}

function InvocationEditor({
  title,
  invocation,
  scope,
  options,
  handlerActions,
  createOptions,
  onChange,
}: {
  title: string;
  invocation: HandlerInvocation;
  scope: ActionScope;
  options: ActionOptions;
  handlerActions: HandlerActions;
  createOptions?: HandlerCreateOptions;
  onChange(invocation: HandlerInvocation): void;
}) {
  const datalist = useId().replace(/:/g, "");
  const compatible = options.handlers.filter((handler) => handler.kind === scope.expectedKind);
  const selected = compatible.find((handler) => handler.id === invocation.handler);
  return (
    <div className="invocation-editor">
      <h4>{title}</h4>
      <label>
        Handler name
        <ResourceDropTarget target={{ type: "handler-reference", handlerKind: scope.expectedKind }} label={`Drop ${scope.expectedKind} handler here`} onDrop={(resource) => onChange({ ...invocation, handler: resource.value })}>
          <input list={`${datalist}-handlers`} value={invocation.handler} onChange={(event) => onChange({ ...invocation, handler: event.target.value })} />
        </ResourceDropTarget>
        <datalist id={`${datalist}-handlers`}>{compatible.map((handler) => <option key={handler.id} value={handler.id} />)}</datalist>
      </label>
      <small className="muted">Stable name for this handler's binding and generated Python file.</small>
      <HandlerControls handlerId={invocation.handler} kind={scope.expectedKind} handlers={options.handlers} onCreate={handlerActions.create} onRepair={handlerActions.repair} onOpen={handlerActions.open} onFindUsages={handlerActions.usages} createOptions={{ ...createOptions, routes: invocation.outcomes }} />
      <OutcomeEditor
        outcomes={invocation.outcomes}
        onChange={(outcomes) => onChange({ ...invocation, outcomes })}
        options={options}
        scope={scope}
        handlerActions={handlerActions}
        suggested={["success", ...(selected?.outcomes ?? [])]}
      />
    </div>
  );
}
