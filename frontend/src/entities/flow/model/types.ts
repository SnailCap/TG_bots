import type { Edge, Node } from "@xyflow/react";

export const NODE_KINDS = [
  "start",
  "send_message",
  "ask_input",
  "choice",
  "action",
  "condition",
  "end",
] as const;

export type FlowNodeKind = (typeof NODE_KINDS)[number];
export type TransitionKind = "automatic" | "input" | "button" | "condition" | "success" | "error";

export interface ChoiceOption {
  id: string;
  label: string;
  value: string;
}

export interface StudioNodeData extends Record<string, unknown> {
  kind: FlowNodeKind;
  title: string;
  text?: string;
  variableName?: string;
  valueType?: "string" | "integer" | "number" | "boolean";
  required?: boolean;
  validationRegex?: string;
  minValue?: number;
  maxValue?: number;
  errorMessage?: string;
  maxAttempts?: number;
  actionName?: string;
  actionTimeoutSeconds?: number;
  actionInputParameters?: Record<string, unknown>;
  actionOutputMapping?: Record<string, string>;
  conditionVariable?: string;
  conditionOperator?:
    | "eq"
    | "ne"
    | "gt"
    | "gte"
    | "lt"
    | "lte"
    | "contains"
    | "in"
    | "exists"
    | "truthy";
  conditionValue?: unknown;
  mediaKind?: "photo" | "document";
  mediaPath?: string;
  keyboard?: "none" | "inline" | "reply";
  choices?: ChoiceOption[];
}

export interface StudioEdgeData extends Record<string, unknown> {
  transitionKind: TransitionKind;
  label?: string;
  outcome?: string;
}

export type StudioNode = Node<StudioNodeData, "studioNode">;
export type StudioEdge = Edge<StudioEdgeData>;

export interface FlowDocument {
  id: string;
  name: string;
  startNodeId?: string | null;
  nodes: StudioNode[];
  edges: StudioEdge[];
  revision?: string | number;
  metadata?: Record<string, unknown>;
}

export type GraphSelection =
  | { kind: "node"; flowId: string; node: StudioNode }
  | { kind: "edge"; flowId: string; edge: StudioEdge }
  | null;

export interface NodePatch {
  revision: number;
  flowId: string;
  nodeId: string;
  patch: Partial<StudioNodeData>;
}

export interface GraphNavigationTarget {
  revision: number;
  flowId: string;
  nodeId: string;
}
