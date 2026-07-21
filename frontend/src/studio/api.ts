import type {
  CommandsDetail,
  CommandsSpec,
  CreateHandlerRequest,
  Diagnostic,
  FlowDetail,
  FlowSpec,
  HandlerDetail,
  HandlerInspection,
  HandlerScaffoldResult,
  HandlerSummary,
  HandlerUsage,
  OpenCodeTarget,
  Preview,
  ScheduleDetail,
  ScheduleSpec,
  TemplateDetail,
  ViewDetail,
  ViewSpec,
  Workspace,
} from "../domain/project";

interface HandlerWire {
  id: string;
  kind: HandlerSummary["kind"];
  module: string;
  symbol: string;
  outcomes?: string[];
  description?: string;
  source_path?: string;
  revision: string;
  inspection: HandlerInspection;
  usage_count?: number;
  usages?: HandlerUsage[];
  diagnostics?: Diagnostic[];
  file_created?: boolean;
  open_target?: OpenCodeWire;
}

interface OpenCodeWire {
  project_root: string;
  file_path: string;
  source_path?: string;
  line?: number;
  column?: number;
}

interface WorkspaceWire extends Omit<Workspace, "handlers"> {
  handlers: HandlerWire[];
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
}

interface ErrorEnvelope {
  detail?: { code?: string; message?: string } | Array<{ msg?: string }> | string;
  code?: string;
  message?: string;
}

export class StudioApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "StudioApiError";
  }
}

export interface StudioApiClient {
  open(rootPath: string): Promise<Workspace>;
  create(parentPath: string, name: string, packageName?: string): Promise<Workspace>;
  describe(projectId: string): Promise<Workspace>;
  getView(projectId: string, id: string): Promise<ViewDetail>;
  createView(projectId: string, id: string, payload: ViewSpec): Promise<ViewDetail>;
  saveView(projectId: string, id: string, payload: ViewSpec, revision: string): Promise<ViewDetail>;
  renameView(projectId: string, id: string, name: string, revision: string): Promise<ViewDetail>;
  deleteView(projectId: string, id: string, revision: string): Promise<void>;
  getTemplate(projectId: string, path: string): Promise<TemplateDetail>;
  saveTemplate(projectId: string, path: string, content: string, revision?: string): Promise<TemplateDetail>;
  deleteTemplate(projectId: string, path: string, revision: string): Promise<void>;
  getFlow(projectId: string, id: string): Promise<FlowDetail>;
  createFlow(projectId: string, id: string, payload: FlowSpec): Promise<FlowDetail>;
  saveFlow(projectId: string, id: string, payload: FlowSpec, revision: string): Promise<FlowDetail>;
  deleteFlow(projectId: string, id: string, revision: string): Promise<void>;
  getCommands(projectId: string): Promise<CommandsDetail>;
  saveCommands(projectId: string, payload: CommandsSpec, revision: string): Promise<CommandsDetail>;
  getSchedule(projectId: string, id: string): Promise<ScheduleDetail>;
  createSchedule(projectId: string, id: string, payload: ScheduleSpec): Promise<ScheduleDetail>;
  saveSchedule(projectId: string, id: string, payload: ScheduleSpec, revision: string): Promise<ScheduleDetail>;
  deleteSchedule(projectId: string, id: string, revision: string): Promise<void>;
  getHandler(projectId: string, id: string): Promise<HandlerDetail>;
  createHandler(projectId: string, input: CreateHandlerRequest): Promise<HandlerScaffoldResult>;
  repairHandlerSource(projectId: string, id: string, registryRevision: string): Promise<HandlerScaffoldResult>;
  deleteHandler(projectId: string, id: string, revision: string): Promise<void>;
  handlerSource(projectId: string, id: string): Promise<OpenCodeTarget>;
  handlerUsages(projectId: string, id: string): Promise<HandlerUsage[]>;
  preview(projectId: string, payload: ViewSpec): Promise<Preview>;
  validate(projectId: string): Promise<Diagnostic[]>;
}

export class StudioApi implements StudioApiClient {
  constructor(private readonly baseUrl: string) {}

  open(rootPath: string): Promise<Workspace> {
    return this.workspace("/projects/open", { method: "POST", body: { root_path: rootPath } });
  }

  create(parentPath: string, name: string, packageName?: string): Promise<Workspace> {
    return this.workspace("/projects", {
      method: "POST",
      body: { parent_path: parentPath, name, package_name: packageName || undefined },
    });
  }

  describe(projectId: string): Promise<Workspace> {
    return this.workspace(`/projects/${projectId}`);
  }

  getView(projectId: string, id: string): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}`);
  }

  createView(projectId: string, id: string, payload: ViewSpec): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views`, { method: "POST", body: { id, payload } });
  }

  saveView(projectId: string, id: string, payload: ViewSpec, revision: string): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: { payload, revision },
    });
  }

  renameView(projectId: string, id: string, name: string, revision: string): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}/rename`, { method: "POST", body: { id: name, revision } });
  }

  deleteView(projectId: string, id: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  getTemplate(projectId: string, path: string): Promise<TemplateDetail> {
    return this.request(`/projects/${projectId}/templates/${this.resourcePath(path)}`);
  }

  saveTemplate(projectId: string, path: string, content: string, revision?: string): Promise<TemplateDetail> {
    return this.request(`/projects/${projectId}/templates/${this.resourcePath(path)}`, {
      method: "PUT",
      body: { content, revision },
    });
  }

  deleteTemplate(projectId: string, path: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/templates/${this.resourcePath(path)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  getFlow(projectId: string, id: string): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows/${encodeURIComponent(id)}`);
  }

  createFlow(projectId: string, id: string, payload: FlowSpec): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows`, { method: "POST", body: { id, payload } });
  }

  saveFlow(projectId: string, id: string, payload: FlowSpec, revision: string): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: { payload, revision },
    });
  }

  deleteFlow(projectId: string, id: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/flows/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  getCommands(projectId: string): Promise<CommandsDetail> {
    return this.request(`/projects/${projectId}/commands`);
  }

  saveCommands(projectId: string, payload: CommandsSpec, revision: string): Promise<CommandsDetail> {
    return this.request(`/projects/${projectId}/commands`, { method: "PUT", body: { payload, revision } });
  }

  getSchedule(projectId: string, id: string): Promise<ScheduleDetail> {
    return this.request(`/projects/${projectId}/schedules/${encodeURIComponent(id)}`);
  }

  createSchedule(projectId: string, id: string, payload: ScheduleSpec): Promise<ScheduleDetail> {
    return this.request(`/projects/${projectId}/schedules`, { method: "POST", body: { id, payload } });
  }

  saveSchedule(projectId: string, id: string, payload: ScheduleSpec, revision: string): Promise<ScheduleDetail> {
    return this.request(`/projects/${projectId}/schedules/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: { payload, revision },
    });
  }

  deleteSchedule(projectId: string, id: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/schedules/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  async getHandler(projectId: string, id: string): Promise<HandlerDetail> {
    return normalizeHandler(await this.request<HandlerWire>(`/projects/${projectId}/handlers/${encodeURIComponent(id)}`));
  }

  async createHandler(projectId: string, input: CreateHandlerRequest): Promise<HandlerScaffoldResult> {
    const result = await this.request<HandlerWire>(`/projects/${projectId}/handlers`, {
      method: "POST",
      body: input,
    });
    const source = result.open_target ? normalizeOpenTarget(result.open_target) : await this.handlerSource(projectId, result.id);
    return { handler: normalizeHandler(result), created: Boolean(result.file_created), source };
  }

  async repairHandlerSource(projectId: string, id: string, registryRevision: string): Promise<HandlerScaffoldResult> {
    const result = await this.request<HandlerWire>(`/projects/${projectId}/handlers/${encodeURIComponent(id)}/repair`, {
      method: "POST",
      body: { registry_revision: registryRevision },
    });
    const source = result.open_target ? normalizeOpenTarget(result.open_target) : await this.handlerSource(projectId, result.id);
    return { handler: normalizeHandler(result), created: Boolean(result.file_created), source };
  }

  deleteHandler(projectId: string, id: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/handlers/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  async handlerSource(projectId: string, id: string): Promise<OpenCodeTarget> {
    const value = await this.request<OpenCodeTarget | OpenCodeWire>(`/projects/${projectId}/handlers/${encodeURIComponent(id)}/open`, { method: "POST" });
    if ("projectRoot" in value) return value;
    return normalizeOpenTarget(value);
  }

  async handlerUsages(projectId: string, id: string): Promise<HandlerUsage[]> {
    const value = await this.request<HandlerUsage[] | { usages: HandlerUsage[] }>(`/projects/${projectId}/handlers/${encodeURIComponent(id)}/usages`);
    return Array.isArray(value) ? value : value.usages;
  }

  preview(projectId: string, payload: ViewSpec): Promise<Preview> {
    return this.request(`/projects/${projectId}/preview`, { method: "POST", body: { payload } });
  }

  async validate(projectId: string): Promise<Diagnostic[]> {
    const value = await this.request<Diagnostic[] | { issues?: Diagnostic[]; diagnostics?: Diagnostic[] }>(`/projects/${projectId}/validation`);
    if (Array.isArray(value)) return value;
    return value.diagnostics ?? value.issues ?? [];
  }

  private async workspace(path: string, options?: RequestOptions): Promise<Workspace> {
    const value = await this.request<WorkspaceWire>(path, options);
    return {
      ...value,
      schema_version: 3,
      views: value.views ?? [],
      templates: value.templates ?? [],
      flows: value.flows ?? [],
      handlers: (value.handlers ?? []).map(normalizeHandler),
      schedules: value.schedules ?? [],
    };
  }

  private resourcePath(value: string): string {
    return value.split("/").map(encodeURIComponent).join("/");
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}/api/v1${path}`, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (response.status === 204) return undefined as T;

    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const envelope = isErrorEnvelope(data) ? data : undefined;
      const detail = envelope?.detail;
      const detailObject = detail && !Array.isArray(detail) && typeof detail === "object" ? detail : undefined;
      const code = detailObject?.code ?? envelope?.code ?? `http_${response.status}`;
      const validationMessage = Array.isArray(detail)
        ? detail.map((item) => item.msg).filter(Boolean).join("; ")
        : undefined;
      const message = detailObject?.message
        ?? envelope?.message
        ?? (typeof detail === "string" ? detail : validationMessage)
        ?? `Request failed with ${response.status}`;
      throw new StudioApiError(response.status, code, message, data);
    }
    return data as T;
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return Boolean(value && typeof value === "object");
}

function normalizeHandler(value: HandlerWire): HandlerDetail {
  const rawStatus = value.inspection?.status ?? "missing_file";
  const status = rawStatus === "unused" ? "ready" : rawStatus;
  return {
    id: value.id,
    kind: value.kind,
    module: value.module,
    symbol: value.symbol,
    outcomes: value.outcomes ?? [],
    description: value.description,
    source_path: value.source_path ?? "handlers.json",
    source_file: value.inspection?.source?.path,
    revision: value.revision,
    inspection: value.inspection,
    status,
    usage_count: value.usage_count ?? value.usages?.length ?? (value.inspection?.used ? 1 : 0),
    usages: value.usages,
    diagnostics: value.diagnostics,
  };
}

function normalizeOpenTarget(value: OpenCodeWire): OpenCodeTarget {
  return {
    projectRoot: value.project_root,
    filePath: value.file_path,
    line: value.line,
    column: value.column,
  };
}
