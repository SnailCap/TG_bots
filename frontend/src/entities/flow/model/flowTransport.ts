import type { FlowDocument, FlowNodeKind, StudioEdge, StudioNode, StudioNodeData } from "./types";

type UnknownRecord = Record<string, unknown>;

const aliases: Record<string, FlowNodeKind> = {
  start: "start",
  send: "send_message",
  sendmessage: "send_message",
  send_message: "send_message",
  ask: "ask_input",
  askinput: "ask_input",
  ask_input: "ask_input",
  choice: "choice",
  action: "action",
  condition: "condition",
  end: "end",
};

function record(value: unknown): UnknownRecord {
  return value && typeof value === "object" ? (value as UnknownRecord) : {};
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function nodeKind(value: unknown): FlowNodeKind {
  const key = text(value, "send_message").replace(/[\s-]/g, "_").toLowerCase();
  return aliases[key.replace(/_/g, "")] ?? aliases[key] ?? "send_message";
}

function titleFor(kind: FlowNodeKind): string {
  return {
    start: "Start",
    send_message: "Send Message",
    ask_input: "Ask Input",
    choice: "Choice",
    action: "Action",
    condition: "Condition",
    end: "End",
  }[kind];
}

function optionalNumber(value: unknown): number | undefined {
  if (value === "" || value === null || value === undefined) return undefined;
  const result = Number(value);
  return Number.isFinite(result) ? result : undefined;
}

function mediaKind(value: unknown, path: string): StudioNodeData["mediaKind"] {
  const explicit = text(value).toLowerCase();
  if (explicit === "photo" || explicit === "image") return "photo";
  if (explicit === "document" || explicit === "file") return "document";
  return /\.(?:avif|bmp|gif|jpe?g|png|webp)$/i.test(path) ? "photo" : "document";
}

function dataFromConfig(kind: FlowNodeKind, payload: UnknownRecord, source: UnknownRecord): StudioNodeData {
  const media = record(payload.media);
  const mediaPath = text(
    payload.mediaPath ??
      payload.media_path ??
      media.path ??
      media.source ??
      media.url ??
      payload.photo ??
      payload.image ??
      payload.document ??
      payload.file,
  );
  const explicitMediaKind =
    payload.mediaKind ??
    payload.media_kind ??
    media.type ??
    media.kind ??
    (payload.photo !== undefined || payload.image !== undefined ? "photo" : undefined) ??
    (payload.document !== undefined || payload.file !== undefined ? "document" : undefined);
  const choices = Array.isArray(payload.choices)
    ? payload.choices.map((item, index) => {
        const choice = record(item);
        return {
          id: text(choice.id, `option-${index + 1}`),
          label: text(choice.label, `Option ${index + 1}`),
          value: text(choice.value, text(choice.label)),
        };
      })
    : undefined;
  return {
    kind,
    title: text(payload.title ?? source.name ?? source.title, titleFor(kind)),
    text: text(payload.text ?? source.text),
    variableName: text(payload.variableName ?? payload.variable_name) || undefined,
    valueType: (text(payload.valueType ?? payload.input_type) || undefined) as StudioNodeData["valueType"],
    required: typeof payload.required === "boolean" ? payload.required : undefined,
    validationRegex: text(payload.validationRegex ?? payload.validation_regex ?? payload.regex) || undefined,
    minValue: optionalNumber(payload.minValue ?? payload.min_value ?? payload.min ?? payload.minimum),
    maxValue: optionalNumber(payload.maxValue ?? payload.max_value ?? payload.max ?? payload.maximum),
    errorMessage: text(payload.errorMessage ?? payload.error_message) || undefined,
    maxAttempts: optionalNumber(payload.maxAttempts ?? payload.max_attempts),
    actionName: text(payload.actionName ?? payload.action_name) || undefined,
    actionTimeoutSeconds: optionalNumber(payload.actionTimeoutSeconds ?? payload.timeout_seconds),
    actionInputParameters: record(payload.actionInputParameters ?? payload.input_parameters),
    actionOutputMapping: record(payload.actionOutputMapping ?? payload.output_mapping) as Record<string, string>,
    conditionVariable: text(payload.conditionVariable ?? payload.variable) || undefined,
    conditionOperator: (text(payload.conditionOperator ?? payload.operator) || undefined) as StudioNodeData["conditionOperator"],
    conditionValue: payload.conditionValue ?? payload.value,
    mediaKind: mediaPath ? mediaKind(explicitMediaKind, mediaPath) : undefined,
    mediaPath: mediaPath || undefined,
    keyboard: (text(payload.keyboard ?? payload.keyboard_type) || undefined) as StudioNodeData["keyboard"],
    choices,
  };
}

function configFromData(data: StudioNodeData): UnknownRecord {
  switch (data.kind) {
    case "send_message":
      return {
        text: data.text ?? "",
        media: data.mediaPath
          ? {
              type: data.mediaKind ?? mediaKind(undefined, data.mediaPath),
              path: data.mediaPath,
              source_type: "asset",
            }
          : undefined,
        keyboard_type: data.keyboard && data.keyboard !== "none" ? data.keyboard : undefined,
      };
    case "ask_input":
      return {
        text: data.text ?? "",
        variable_name: data.variableName ?? "",
        input_type: data.valueType ?? "string",
        required: data.required ?? true,
        regex: data.validationRegex || undefined,
        min_value: data.minValue,
        max_value: data.maxValue,
        error_message: data.errorMessage || undefined,
        max_attempts: data.maxAttempts ?? 3,
      };
    case "choice":
      return {
        text: data.text ?? "",
        keyboard_type: data.keyboard ?? "inline",
        choices: (data.choices ?? []).map((choice) => ({
          id: choice.id,
          label: choice.label,
          value: choice.value,
        })),
      };
    case "action":
      return {
        action_name: data.actionName ?? "",
        timeout_seconds: data.actionTimeoutSeconds ?? 30,
        input_parameters: data.actionInputParameters ?? {},
        output_mapping: data.actionOutputMapping ?? {},
      };
    case "condition":
      return {
        variable: data.conditionVariable ?? "",
        operator: data.conditionOperator ?? "truthy",
        value: data.conditionValue,
      };
    case "start":
    case "end":
      return {};
  }
}

function normalizeNode(value: unknown, index: number): StudioNode {
  const source = record(value);
  const payload = record(source.data ?? source.config ?? source.properties);
  const kind = nodeKind(payload.kind ?? source.kind ?? source.node_type ?? source.type);
  const position = record(source.position ?? source.layout);
  const data = dataFromConfig(kind, payload, source);
  return {
    id: text(source.id ?? source.node_id, `node-${index + 1}`),
    type: "studioNode",
    position: {
      x: Number(position.x ?? source.x ?? index * 180) || 0,
      y: Number(position.y ?? source.y ?? 80) || 0,
    },
    data,
  };
}

function normalizeEdge(value: unknown, index: number): StudioEdge {
  const source = record(value);
  const payload = record(source.data ?? source.config);
  return {
    id: text(source.id ?? source.transition_id, `edge-${index + 1}`),
    source: text(source.source ?? source.source_node_id ?? source.from),
    target: text(source.target ?? source.target_node_id ?? source.to),
    sourceHandle: text(source.sourceHandle ?? source.source_handle ?? payload.source_handle) || undefined,
    targetHandle: text(source.targetHandle ?? source.target_handle ?? payload.target_handle) || undefined,
    label: text(source.label ?? payload.label) || undefined,
    data: {
      ...payload,
      transitionKind: (text(
        payload.transitionKind ?? source.transition_kind ?? source.kind,
        "automatic",
      ) || "automatic") as "automatic" | "input" | "button" | "condition" | "success" | "error",
      outcome: text(source.outcome ?? payload.outcome) || undefined,
    },
  };
}

export function normalizeFlow(payload: unknown): FlowDocument {
  const outer = record(payload);
  const source = record(outer.flow ?? outer.data ?? payload);
  const nodes = Array.isArray(source.nodes) ? source.nodes.map(normalizeNode) : [];
  const rawEdges = source.edges ?? source.transitions;
  const edges = Array.isArray(rawEdges) ? rawEdges.map(normalizeEdge) : [];
  return {
    id: text(source.id ?? source.flow_id, "flow"),
    name: text(source.name ?? source.title, "Untitled Flow"),
    startNodeId: text(source.start_node_id ?? source.startNodeId) || null,
    nodes,
    edges,
    revision: typeof source.revision === "string" || typeof source.revision === "number" ? source.revision : undefined,
    metadata: record(source.metadata),
  };
}

export function serializeFlow(flow: FlowDocument): UnknownRecord {
  const startNodeId = flow.startNodeId ?? flow.nodes.find((node) => node.data.kind === "start")?.id ?? null;
  return {
    schema_version: 1,
    id: flow.id,
    name: flow.name,
    start_node_id: startNodeId,
    revision: flow.revision,
    nodes: flow.nodes.map((node) => ({
      id: node.id,
      type: node.data.kind,
      name: node.data.title,
      position: { x: node.position.x, y: node.position.y },
      config: configFromData(node.data),
    })),
    transitions: flow.edges.map((edge) => ({
      id: edge.id,
      source_node_id: edge.source,
      target_node_id: edge.target,
      kind: edge.data?.transitionKind ?? "automatic",
      label: typeof edge.label === "string" ? edge.label : edge.data?.label,
      outcome: edge.data?.outcome ?? edge.sourceHandle,
      config: {
        ...edge.data,
        source_handle: edge.sourceHandle,
        target_handle: edge.targetHandle,
      },
    })),
    metadata: flow.metadata ?? {},
  };
}

export function createEmptyFlow(id: string, name: string): FlowDocument {
  return {
    id,
    name,
    startNodeId: "start-1",
    nodes: [
      {
        id: "start-1",
        type: "studioNode",
        position: { x: 80, y: 120 },
        data: { kind: "start", title: "Start" },
      },
    ],
    edges: [],
    metadata: {},
  };
}
