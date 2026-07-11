export type RuntimePhase = "stopped" | "starting" | "running" | "stopping" | "error" | "unknown";

export interface BotIdentity {
  id: string;
  username?: string;
  displayName?: string;
}

export interface RuntimeStatus {
  phase: RuntimePhase;
  telegramConnected: boolean;
  lastError?: string | null;
  bot?: BotIdentity | null;
  startedAt?: string | null;
}

export interface RuntimeLogEvent {
  id: string;
  timestamp: string;
  level: "debug" | "info" | "warning" | "error";
  message: string;
  source?: string;
  entity?: {
    flowId?: string;
    nodeId?: string;
    scriptPath?: string;
    line?: number;
  };
}

export interface ValidationIssue {
  code: string;
  severity: "info" | "warning" | "error";
  message: string;
  hint?: string;
  entity?: {
    kind?: string;
    id?: string;
    flowId?: string;
    nodeId?: string;
    scriptPath?: string;
    line?: number;
  };
}

export interface RuntimeControlState {
  status: RuntimeStatus;
  pending: "run" | "stop" | null;
  error: string | null;
}

export type RuntimeControlAction =
  | { type: "status"; status: RuntimeStatus }
  | { type: "run_requested" }
  | { type: "stop_requested" }
  | { type: "failed"; message: string };

export function runtimeControlReducer(
  state: RuntimeControlState,
  action: RuntimeControlAction,
): RuntimeControlState {
  switch (action.type) {
    case "status":
      return { status: action.status, pending: null, error: action.status.lastError ?? null };
    case "run_requested":
      return { ...state, pending: "run", error: null, status: { ...state.status, phase: "starting" } };
    case "stop_requested":
      return { ...state, pending: "stop", error: null, status: { ...state.status, phase: "stopping" } };
    case "failed":
      return {
        ...state,
        pending: null,
        error: action.message,
        status: { ...state.status, phase: "error", lastError: action.message },
      };
  }
}
