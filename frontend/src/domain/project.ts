export const SCHEMA_VERSION = 3 as const;

export type HandlerKind = "button" | "message" | "command" | "lifecycle" | "task";
export type HandlerIntegrity = "ready" | "missing_file" | "missing_symbol" | "invalid_signature" | "invalid_module";
export type HandlerInspectionStatus = HandlerIntegrity | "unused";
export type DiagnosticLevel = "error" | "warning";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export interface NoopAction {
  type: "noop";
}

export interface ViewRenderAction {
  type: "view.render";
  target: string;
  delivery?: "edit" | "send";
}

export interface FlowStartAction {
  type: "flow.start";
  target: string;
  delivery?: "edit" | "send";
}

export interface FlowCancelAction {
  type: "flow.cancel";
  view?: string;
}

export interface FlowEventAction {
  type: "flow.event";
  target: string;
}

export interface FlowGotoAction {
  type: "flow.goto";
  target: string;
}

export interface FlowFinishAction {
  type: "flow.finish";
  view?: string;
}

export interface HandlerInvokeAction {
  type: "handler.invoke";
  handler: string;
  outcomes: OutcomeRoutes;
  payload?: JsonObject;
}

export interface TaskEnqueueAction {
  type: "task.enqueue";
  target: string;
  payload?: JsonObject;
  delay_seconds?: number;
  view?: string;
}

export type ActionSpec =
  | NoopAction
  | ViewRenderAction
  | FlowStartAction
  | FlowCancelAction
  | FlowEventAction
  | FlowGotoAction
  | FlowFinishAction
  | HandlerInvokeAction
  | TaskEnqueueAction;

export interface OutcomeRoutes {
  [name: string]: ActionSpec;
}

export type TextSpec = { inline: string; template?: never } | { template: string; inline?: never };

export interface ButtonSpec {
  id: string;
  text: string;
  action: ActionSpec;
}

export interface ViewSpec {
  schema_version: typeof SCHEMA_VERSION;
  id: string;
  text: TextSpec;
  keyboard: ButtonSpec[][];
}

export interface HandlerInvocation {
  handler: string;
  outcomes: OutcomeRoutes;
}

export interface StateSpec {
  view: string;
  on_enter?: HandlerInvocation;
  on_message?: HandlerInvocation;
  events: { [eventId: string]: HandlerInvocation };
}

export interface FlowLifecycle {
  on_start?: HandlerInvocation;
  on_complete?: HandlerInvocation;
  on_cancel?: HandlerInvocation;
  on_error?: HandlerInvocation;
}

export interface FlowSpec {
  schema_version: typeof SCHEMA_VERSION;
  id: string;
  initial_state: string;
  lifecycle: FlowLifecycle;
  states: { [stateId: string]: StateSpec };
}

export interface CommandSpec {
  name: string;
  description?: string;
  action: ActionSpec;
}

export interface CommandsSpec {
  schema_version: typeof SCHEMA_VERSION;
  commands: CommandSpec[];
  message_fallback?: ActionSpec;
  command_fallback?: ActionSpec;
}

export interface ScheduleSpec {
  schema_version: typeof SCHEMA_VERSION;
  id: string;
  handler: string;
  trigger: {
    type: "interval";
    seconds: number;
  };
  payload: JsonObject;
}

export interface ResourceSummary {
  id: string;
  name?: string;
  source_path: string;
  revision: string;
}

export interface ViewSummary extends ResourceSummary {}
export interface FlowSummary extends ResourceSummary {
  states: string[];
}
export interface ScheduleSummary extends ResourceSummary {}

export interface AggregateSummary {
  source_path: string;
  revision: string;
}

export interface CommandsSummary extends AggregateSummary {
  items: Array<Pick<CommandSpec, "name" | "description"> & { display_name?: string }>;
}

export interface ManifestSpec {
  schema_version: typeof SCHEMA_VERSION;
  id: string;
  package: string;
  entry_view: string;
  start: { flow: string; policy: "reset" | "resume" };
}

export interface ManifestSummary extends AggregateSummary {
  payload: ManifestSpec;
}

export interface HandlerInspection {
  status: HandlerInspectionStatus;
  used: boolean;
  source?: { path: string; line?: number; column?: number } | null;
  message?: string;
}

export interface HandlerSummary {
  id: string;
  name?: string;
  name_is_default?: boolean;
  kind: HandlerKind;
  module: string;
  symbol: string;
  outcomes: string[];
  description?: string;
  source_path: string;
  revision: string;
  status: HandlerIntegrity;
  usage_count: number;
  inspection?: HandlerInspection;
  source_file?: string;
}

export interface Workspace {
  project_id: string;
  name: string;
  project_root: string;
  resource_root: string;
  package: string;
  schema_version: typeof SCHEMA_VERSION;
  manifest: ManifestSummary;
  views: ViewSummary[];
  flows: FlowSummary[];
  handlers: HandlerSummary[];
  handlers_revision: string;
  commands: CommandsSummary;
  schedules: ScheduleSummary[];
}

export interface ResourceDetail<T> extends ResourceSummary {
  name_is_default?: boolean;
  payload: T;
}

export interface ViewDetail extends ResourceDetail<ViewSpec> {
  text_content: string;
  text_revision: string | null;
}
export type FlowDetail = ResourceDetail<FlowSpec>;
export type ScheduleDetail = ResourceDetail<ScheduleSpec>;

export interface CommandsDetail {
  source_path: string;
  revision: string;
  payload: CommandsSpec;
}

export interface HandlerDetail extends HandlerSummary {
  diagnostics?: Diagnostic[];
  usages?: HandlerUsage[];
}

export interface Diagnostic {
  level: DiagnosticLevel;
  code: string;
  message: string;
  source_path?: string;
  entity_id?: string;
  field_path?: string;
}

export interface Preview {
  text: string;
  keyboard: Array<Array<{ id?: string; text: string; action: ActionSpec }>>;
  warnings: string[];
}

export interface HandlerUsage {
  handler_id: string;
  entity_type: string;
  entity_id: string;
  field_path: string;
  source_path?: string;
}

export type HandlerAttachment =
  | { type: "view_button"; view_id: string; button_id: string }
  | { type: "flow_lifecycle"; flow_id: string; hook: keyof FlowLifecycle }
  | { type: "state_on_message"; flow_id: string; state_id: string }
  | { type: "state_on_enter"; flow_id: string; state_id: string }
  | { type: "flow_event"; flow_id: string; state_id: string; event_id: string }
  | { type: "command"; command: string }
  | { type: "global_message_fallback" }
  | { type: "global_command_fallback" }
  | { type: "schedule"; schedule_id: string };

export interface CreateHandlerRequest {
  handler_id: string;
  kind: HandlerKind;
  registry_revision: string;
  outcomes?: string[];
  description?: string;
  attachment?: HandlerAttachment;
  target_revision?: string;
  routes?: OutcomeRoutes;
}

export type HandlerCreateOptions = Pick<CreateHandlerRequest, "attachment" | "target_revision" | "routes">;

export interface HandlerScaffoldResult {
  handler: HandlerDetail;
  created: boolean;
  source: OpenCodeTarget;
}

export interface OpenCodeTarget {
  projectRoot: string;
  filePath: string;
  line?: number;
  column?: number;
}

export type Selection =
    | { kind: "view"; id: string }
    | { kind: "flow"; id: string }
    | { kind: "handler"; id: string }
    | { kind: "command"; name: string }
    | { kind: "commands" }
    | { kind: "schedule"; id: string };

export interface ActionOptions {
  views: string[];
  flows: string[];
  states: string[];
  handlers: HandlerSummary[];
}

export function actionFor(type: ActionSpec["type"]): ActionSpec {
  switch (type) {
    case "view.render": return { type, target: "" };
    case "flow.start": return { type, target: "" };
    case "flow.cancel": return { type };
    case "flow.event": return { type, target: "" };
    case "flow.goto": return { type, target: "" };
    case "flow.finish": return { type };
    case "handler.invoke": return {
      type,
      handler: "",
      outcomes: { success: { type: "noop" } },
    };
    case "task.enqueue": return { type, target: "", payload: {}, delay_seconds: 0 };
    default: return { type: "noop" };
  }
}

export function emptyView(id = ""): ViewSpec {
  return { schema_version: SCHEMA_VERSION, id, text: { inline: "" }, keyboard: [] };
}

export function emptyFlow(id = ""): FlowSpec {
  return {
    schema_version: SCHEMA_VERSION,
    id,
    initial_state: "start",
    lifecycle: {},
    states: { start: { view: "", events: {} } },
  };
}

export function emptySchedule(id = ""): ScheduleSpec {
  return {
    schema_version: SCHEMA_VERSION,
    id,
    handler: "",
    trigger: { type: "interval", seconds: 3600 },
    payload: {},
  };
}
