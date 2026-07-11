import type { ProjectDetails, ProjectSummary, ProjectTreeKind, ProjectTreeNode } from "../../entities/project/model/types";
import type { RuntimeLogEvent, RuntimePhase, RuntimeStatus, ValidationIssue } from "../../entities/runtime/model/types";
import type {
  ActionDefinition,
  ActionUsage,
  BotSettings,
  ScriptFile,
  ScriptSearchMatch,
  ScriptSummary,
  TokenValidationResult,
} from "./types";

type UnknownRecord = Record<string, unknown>;

export function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === "object" ? (value as UnknownRecord) : {};
}

export function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : fallback;
}

export function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

export function listPayload(value: unknown, keys = ["items", "results", "data"]): unknown[] {
  if (Array.isArray(value)) return value;
  const source = asRecord(value);
  for (const key of keys) if (Array.isArray(source[key])) return source[key] as unknown[];
  return [];
}

function normalizeScriptPath(value: unknown): string {
  const path = asString(value).replace(/\\/g, "/");
  return path && !path.startsWith("scripts/") ? `scripts/${path}` : path;
}

export function normalizeProject(value: unknown): ProjectDetails {
  const outer = asRecord(value);
  const source = asRecord(outer.project ?? outer.data ?? value);
  const configuration = asRecord(source.configuration ?? source.config);
  return {
    id: asString(source.id ?? source.project_id),
    name: asString(source.name, "Untitled Bot"),
    path: asString(source.path ?? source.directory ?? source.project_path),
    updatedAt: asString(source.updatedAt ?? source.updated_at) || undefined,
    startFlowId: asString(source.startFlowId ?? source.start_flow_id ?? configuration.start_flow_id) || null,
    description: asString(source.description) || undefined,
  };
}

export function normalizeProjects(value: unknown): ProjectSummary[] {
  return listPayload(value, ["projects", "items", "results", "data"]).map(normalizeProject);
}

function normalizeTreeKind(value: unknown, path: string): ProjectTreeKind {
  const kind = asString(value).toLowerCase();
  if (["project", "directory", "flow", "script", "asset", "settings"].includes(kind)) {
    return kind as ProjectTreeKind;
  }
  if (path.endsWith(".flow.json")) return "flow";
  if (path.endsWith(".py")) return "script";
  if (/settings|bot\.json/i.test(path)) return "settings";
  return "asset";
}

export function normalizeTreeNode(value: unknown, index = 0): ProjectTreeNode {
  const source = asRecord(value);
  const path = asString(source.path ?? source.resource_path ?? source.id);
  const children = listPayload(source.children).map((child, childIndex) => normalizeTreeNode(child, childIndex));
  return {
    id: asString(source.id, path || `tree-${index}`),
    name: asString(source.name, path.split(/[\\/]/).pop() || "item"),
    path,
    kind: normalizeTreeKind(source.kind ?? source.type, path),
    children,
    hasError: asBoolean(source.hasError ?? source.has_error),
    errorCount: Number(source.errorCount ?? source.error_count) || undefined,
  };
}

export function normalizeTree(value: unknown): ProjectTreeNode[] {
  if (Array.isArray(value)) return value.map(normalizeTreeNode);
  const source = asRecord(value);
  const tree = source.tree ?? source.data ?? value;
  if (Array.isArray(tree)) return tree.map(normalizeTreeNode);
  const root = normalizeTreeNode(tree);
  return root.kind === "project" ? root.children : [root];
}

export function normalizeScript(value: unknown): ScriptFile {
  const outer = asRecord(value);
  const source = asRecord(outer.script ?? outer.data ?? value);
  const path = normalizeScriptPath(source.path ?? source.script_path);
  return {
    path,
    name: asString(source.name, path.split(/[\\/]/).pop() || "script.py"),
    content: asString(source.content ?? source.source),
    revision: typeof source.revision === "string" || typeof source.revision === "number" ? source.revision : undefined,
  };
}

export function normalizeScriptSummaries(value: unknown): ScriptSummary[] {
  return listPayload(value, ["scripts", "items", "results", "data"]).map((item) => {
    const source = asRecord(item);
    const path = normalizeScriptPath(source.path ?? source.script_path);
    return {
      path,
      name: asString(source.name, path.split(/[\\/]/).pop() || "script.py"),
      hasErrors: asBoolean(source.hasErrors ?? source.has_errors),
    };
  });
}

export function normalizeSearchMatches(value: unknown): ScriptSearchMatch[] {
  return listPayload(value, ["matches", "items", "results", "data"]).map((item) => {
    const source = asRecord(item);
    return {
      path: normalizeScriptPath(source.path ?? source.script_path),
      line: Number(source.line ?? source.line_number) || 1,
      column: Number(source.column) || undefined,
      preview: asString(source.preview ?? source.text ?? source.match),
    };
  });
}

export function normalizeActions(value: unknown): ActionDefinition[] {
  const envelope = asRecord(value);
  const actionErrors = new Map<string, string>();
  const pathErrors = new Map<string, string>();
  for (const item of listPayload(envelope, ["issues"])) {
    const issue = asRecord(item);
    const message = asString(issue.message, "Action validation failed");
    const entityType = asString(issue.entity_type).toLowerCase();
    const entityId = asString(issue.entity_id);
    const path = normalizeScriptPath(issue.path);
    if (entityType === "action" && entityId) actionErrors.set(entityId, message);
    else if (path) pathErrors.set(path, message);
  }
  return listPayload(value, ["actions", "items", "results", "data"]).map((item) => {
    const source = asRecord(item);
    const name = asString(source.name ?? source.action_name);
    const scriptPath = normalizeScriptPath(source.scriptPath ?? source.script_path ?? source.file_path ?? source.file);
    const validationError = actionErrors.get(name) ?? pathErrors.get(scriptPath);
    return {
      name,
      module: asString(source.module) || undefined,
      scriptPath,
      line: Number(source.line ?? source.line_number) || undefined,
      signature:
        asString(source.signature) ||
        (Array.isArray(source.parameters)
          ? `${asString(source.name ?? source.action_name)}(${source.parameters
              .map((parameter) => asString(asRecord(parameter).name))
              .filter(Boolean)
              .join(", ")})`
          : undefined),
      valid: source.valid !== false && !source.error && !validationError,
      error: asString(source.error) || validationError || undefined,
    };
  });
}

export function normalizeUsages(value: unknown): ActionUsage[] {
  return listPayload(value, ["usages", "items", "results", "data"]).map((item) => {
    const source = asRecord(item);
    return {
      actionName: asString(source.actionName ?? source.action_name),
      flowId: asString(source.flowId ?? source.flow_id),
      flowName: asString(source.flowName ?? source.flow_name) || undefined,
      nodeId: asString(source.nodeId ?? source.node_id),
      nodeTitle: asString(source.nodeTitle ?? source.node_title ?? source.node_name) || undefined,
    };
  });
}

export function normalizeSettings(value: unknown): BotSettings {
  const outer = asRecord(value);
  const base = asRecord(outer.settings ?? outer.data ?? value);
  const source = asRecord(base.configuration ?? base.config ?? base);
  const botSource = asRecord(source.bot ?? source.bot_identity ?? source.identity);
  return {
    startFlowId: asString(source.startFlowId ?? source.start_flow_id) || null,
    startBehavior: (asString(source.startBehavior ?? source.start_behavior).replace("reset_flow", "reset") || "reset") as BotSettings["startBehavior"],
    tokenConfigured: asBoolean(source.tokenConfigured ?? source.token_configured ?? source.has_token ?? source.secret_configured),
    tokenReference: asString(source.tokenReference ?? source.token_reference ?? source.secret_ref) || null,
    bot: Object.keys(botSource).length
      ? {
          id: asString(botSource.id ?? botSource.bot_id),
          username: asString(botSource.username) || undefined,
          displayName: asString(botSource.displayName ?? botSource.display_name ?? botSource.first_name) || undefined,
        }
      : null,
  };
}

export function normalizeTokenResult(value: unknown): TokenValidationResult {
  const source = asRecord(value);
  const settings = normalizeSettings({ settings: source });
  return {
    valid: asBoolean(source.valid ?? source.is_valid, Boolean(settings.bot)),
    bot: settings.bot,
    error: asString(source.error ?? source.message) || undefined,
  };
}

function runtimePhase(value: unknown): RuntimePhase {
  const phase = asString(value, "unknown").toLowerCase();
  return ["stopped", "starting", "running", "stopping", "error"].includes(phase)
    ? (phase as RuntimePhase)
    : "unknown";
}

export function normalizeRuntimeStatus(value: unknown): RuntimeStatus {
  const outer = asRecord(value);
  const source = asRecord(outer.status ?? outer.runtime ?? outer.data ?? value);
  const bot = normalizeSettings({ bot: source.bot ?? source.bot_identity }).bot;
  return {
    phase: runtimePhase(source.phase ?? source.status ?? source.state),
    telegramConnected: asBoolean(source.telegramConnected ?? source.telegram_connected ?? source.connected),
    lastError: asString(source.lastError ?? source.last_error) || null,
    bot,
    startedAt: asString(source.startedAt ?? source.started_at) || null,
  };
}

export function normalizeLog(value: unknown, index = 0): RuntimeLogEvent {
  const source = asRecord(value);
  const entity = asRecord(source.entity ?? source.context);
  const entityType = asString(source.entity_type ?? entity.kind).toLowerCase();
  const entityId = asString(source.entity_id ?? entity.id);
  const rawLevel = asString(source.level, "info").toLowerCase();
  const level = ["debug", "info", "warning", "error"].includes(rawLevel)
    ? (rawLevel as RuntimeLogEvent["level"])
    : "info";
  return {
    id: asString(source.id, `${Date.now()}-${index}`),
    timestamp: asString(source.timestamp ?? source.created_at, new Date().toISOString()),
    level,
    message: asString(source.message ?? source.text, JSON.stringify(value)),
    source: asString(source.source ?? source.logger ?? source.event_type ?? source.category) || undefined,
    entity: Object.keys(entity).length || entityType || entityId
      ? {
          flowId: asString(entity.flowId ?? entity.flow_id) || (entityType === "flow" ? entityId : undefined),
          nodeId: asString(entity.nodeId ?? entity.node_id) || (entityType === "node" ? entityId : undefined),
          scriptPath: normalizeScriptPath(entity.scriptPath ?? entity.script_path) || undefined,
          line: Number(entity.line) || undefined,
        }
      : undefined,
  };
}

export function normalizeLogs(value: unknown): RuntimeLogEvent[] {
  return listPayload(value, ["logs", "items", "events", "data"]).map(normalizeLog);
}

export function normalizeIssues(value: unknown): ValidationIssue[] {
  return listPayload(value, ["issues", "items", "results", "data"]).map((item) => {
    const source = asRecord(item);
    const entity = asRecord(source.entity ?? source.entity_reference);
    const entityType = asString(entity.kind ?? source.entity_type).toLowerCase();
    const entityId = asString(entity.id ?? source.entity_id);
    const entityPath = asString(entity.scriptPath ?? entity.script_path ?? source.path);
    const flowPathMatch = entityPath.replace(/\\/g, "/").match(/(?:^|\/)flows\/([^/]+)\.flow\.json$/);
    const pathFlowId = flowPathMatch?.[1];
    const severity = asString(source.severity, "error").toLowerCase();
    return {
      code: asString(source.code, "VALIDATION_ERROR"),
      severity: (["info", "warning", "error"].includes(severity) ? severity : "error") as ValidationIssue["severity"],
      message: asString(source.message, "Validation failed"),
      hint: asString(source.hint ?? source.fix_hint) || undefined,
      entity: Object.keys(entity).length || source.entity_type || source.entity_id || source.path
        ? {
            kind: entityType || undefined,
            id: entityId || undefined,
            flowId: asString(entity.flowId ?? entity.flow_id) || (entityType === "flow" ? entityId : undefined) || pathFlowId,
            nodeId: asString(entity.nodeId ?? entity.node_id) || (entityType === "node" ? entityId : undefined),
            scriptPath:
              entityPath && (entityType.includes("script") || entityType.includes("action") || entityPath.endsWith(".py"))
                ? normalizeScriptPath(entityPath)
                : undefined,
            line: Number(entity.line ?? source.line) || undefined,
          }
        : undefined,
    };
  });
}
