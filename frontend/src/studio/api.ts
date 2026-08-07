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
  ViewDetail,
  ViewSpec,
  VariableCatalogDetail,
  VariableCatalogSpec,
  VariableResourceContext,
  Workspace,
} from "../domain/project";
import type { BotContentDocument, ContentDiagnostic, TelegramCompileResult } from "../domain/content";

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
  signal?: AbortSignal;
}

interface ErrorEnvelope {
  detail?: { code?: string; message?: string } | Array<{ msg?: string }> | string;
  code?: string;
  message?: string;
}

export interface ProjectSettings {
  telegram_bot_token_configured: boolean;
  revision: string | null;
}

export interface ProjectSettingsUpdate {
  telegram_bot_token?: string;
  clear_telegram_bot_token?: boolean;
  revision: string | null;
}

export type CustomEmojiSource = "telegram-message" | "sticker-set" | "manual-id" | "recent" | "favorite";
export type CustomEmojiResolveStatus = "resolved" | "fallback-only" | "unavailable";
export type CustomEmojiCapability = "unknown" | "available" | "unavailable" | "test-required";

export interface ResolvedCustomEmoji {
  id: string;
  fallbackEmoji: string;
  status: CustomEmojiResolveStatus;
  source: CustomEmojiSource;
  lastUsedAt: string;
  lastCheckedAt: string;
  cached: boolean;
  reason?: string;
  previewKey?: string;
  preview?: {
    key: string;
    format: "webp" | "tgs" | "webm";
    mimeType: string;
    loadedAt: string;
  };
}

export interface CustomEmojiCapabilityResult {
  capability: CustomEmojiCapability;
  reason?: string;
}

export interface SendPreviewMessageInput {
  document: BotContentDocument;
  variables?: Record<string, unknown>;
  chatId: number | string;
  splitLongMessages?: boolean;
}

export interface SendPreviewMessageResult {
  sent: true;
  sentCount: number;
  totalCount: number;
  messageIds: Array<number | null>;
  warnings: ContentDiagnostic[];
}

export type UserRole = "user" | "trusted" | "moderator" | "administrator";
export type UserStatus = "active" | "blocked";

export interface ManagedUser {
  telegramId: string;
  username: string | null;
  firstName: string | null;
  lastName: string | null;
  languageCode: string | null;
  role: UserRole;
  status: UserStatus;
  note: string;
  avatarVersion: string | null;
}

export interface ManagedUserUpdate {
  role: UserRole;
  blocked: boolean;
  note: string;
}

export type GitSyncState = "synced" | "changes" | "conflict";
export type GitChangeStatus = "modified" | "added" | "deleted" | "renamed" | "untracked";

export interface GitCommit {
  hash: string;
  short_hash: string;
  author: string;
  authored_at: string;
  message: string;
  branch?: string;
  published?: boolean;
  url?: string;
}

export interface GitStatus {
  connected: boolean;
  git_installed: boolean;
  account?: string;
  repository?: string;
  remote_name?: string;
  branch?: string;
  development_branch?: string;
  production_branch?: string;
  local_changes?: number;
  remote_changes?: number;
  ahead?: number;
  behind?: number;
  sync_state?: GitSyncState;
  last_commit?: GitCommit | null;
  last_publication?: { version: string | null; commit: string | null; at: string | null } | null;
}

export interface GitChange {
  path: string;
  old_path: string | null;
  status: GitChangeStatus;
  staged: boolean;
  summary: string;
  binary: boolean;
  diff: string | null;
}

export interface GitChanges {
  changes: GitChange[];
  suggested_message: string;
}

export interface GitConnectInput {
  repository: string;
  remote_name?: string;
  development_branch: string;
  production_branch: string;
  token?: string;
}

export interface GitCreateRepositoryInput extends Omit<GitConnectInput, "repository"> {
  repository: string;
  visibility: "private" | "public";
}

export interface GitPublishInput {
  version: "patch" | "minor" | "major" | "none" | "custom";
  custom_version?: string;
  token?: string;
}

interface ManagedUserWire {
  telegram_id: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  language_code: string | null;
  role: UserRole;
  status: UserStatus;
  note: string;
  avatar_version: string | null;
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
  getProjectSettings(projectId: string): Promise<ProjectSettings>;
  saveProjectSettings(projectId: string, payload: ProjectSettingsUpdate): Promise<ProjectSettings>;
  resolveCustomEmojis(projectId: string, ids: string[], fallbackById?: Record<string, string>, source?: CustomEmojiSource): Promise<{ items: ResolvedCustomEmoji[] }>;
  customEmojiPreviewUrl(projectId: string, id: string): string;
  testCustomEmojiCapability(projectId: string, id: string, chatId: number | string, fallbackEmoji?: string): Promise<CustomEmojiCapabilityResult>;
  listUsers(projectId: string): Promise<ManagedUser[]>;
  updateUser(projectId: string, telegramId: string, payload: ManagedUserUpdate): Promise<ManagedUser>;
  getView(projectId: string, id: string): Promise<ViewDetail>;
  createView(projectId: string, id: string, payload: ViewSpec, textContent?: string, contentDocument?: BotContentDocument): Promise<ViewDetail>;
  createNamedView?(projectId: string, name?: string, textContent?: string, contentDocument?: BotContentDocument): Promise<ViewDetail>;
  saveView(projectId: string, id: string, payload: ViewSpec, revision: string, textContent: string, textRevision: string | null): Promise<ViewDetail>;
  saveViewContent(projectId: string, id: string, payload: ViewSpec, revision: string, document: BotContentDocument, documentRevision: string | null, textRevision: string | null): Promise<ViewDetail>;
  renameView(projectId: string, id: string, name: string, revision: string): Promise<ViewDetail>;
  deleteView(projectId: string, id: string, revision: string): Promise<void>;
  getFlow(projectId: string, id: string): Promise<FlowDetail>;
  createFlow(projectId: string, id: string, payload: FlowSpec): Promise<FlowDetail>;
  createNamedFlow?(projectId: string, name?: string): Promise<FlowDetail>;
  saveFlow(projectId: string, id: string, payload: FlowSpec, revision: string): Promise<FlowDetail>;
  renameFlow(projectId: string, id: string, name: string, revision: string): Promise<FlowDetail>;
  deleteFlow(projectId: string, id: string, revision: string): Promise<void>;
  getCommands(projectId: string): Promise<CommandsDetail>;
  saveCommands(projectId: string, payload: CommandsSpec, revision: string): Promise<CommandsDetail>;
  getVariables?(projectId: string, context?: VariableResourceContext): Promise<VariableCatalogDetail>;
  saveVariables?(projectId: string, payload: VariableCatalogSpec, revision: string | null): Promise<VariableCatalogDetail>;
  getSchedule(projectId: string, id: string): Promise<ScheduleDetail>;
  createSchedule(projectId: string, id: string, payload: ScheduleSpec): Promise<ScheduleDetail>;
  createNamedSchedule?(projectId: string, name?: string): Promise<ScheduleDetail>;
  saveSchedule(projectId: string, id: string, payload: ScheduleSpec, revision: string): Promise<ScheduleDetail>;
  renameSchedule(projectId: string, id: string, name: string, revision: string): Promise<ScheduleDetail>;
  deleteSchedule(projectId: string, id: string, revision: string): Promise<void>;
  getHandler(projectId: string, id: string): Promise<HandlerDetail>;
  renameHandler(projectId: string, id: string, name: string, revision: string): Promise<HandlerDetail>;
  createHandler(projectId: string, input: CreateHandlerRequest): Promise<HandlerScaffoldResult>;
  repairHandlerSource(projectId: string, id: string, registryRevision: string): Promise<HandlerScaffoldResult>;
  deleteHandler(projectId: string, id: string, revision: string): Promise<void>;
  handlerSource(projectId: string, id: string): Promise<OpenCodeTarget>;
  handlerUsages(projectId: string, id: string): Promise<HandlerUsage[]>;
  preview(projectId: string, payload: ViewSpec): Promise<Preview>;
  compileContent(projectId: string, document: BotContentDocument, variables?: Record<string, unknown>, signal?: AbortSignal): Promise<TelegramCompileResult>;
  sendPreviewMessage(projectId: string, input: SendPreviewMessageInput): Promise<SendPreviewMessageResult>;
  validate(projectId: string): Promise<Diagnostic[]>;
  setDisplayName?(projectId: string, kind: "views" | "flows" | "schedules" | "handlers" | "commands", key: string, name: string, manifestRevision: string): Promise<{ name: string; name_is_default: boolean }>;
  gitStatus(projectId: string): Promise<GitStatus>;
  gitChanges(projectId: string): Promise<GitChanges>;
  gitHistory(projectId: string): Promise<GitCommit[]>;
  gitConnect(projectId: string, payload: GitConnectInput): Promise<GitStatus>;
  gitCreateRepository(projectId: string, payload: GitCreateRepositoryInput): Promise<GitStatus>;
  gitDisconnect(projectId: string): Promise<GitStatus>;
  gitFetch(projectId: string, token?: string): Promise<GitStatus>;
  gitSync(projectId: string, token?: string): Promise<GitStatus>;
  gitPush(projectId: string, message: string, token?: string): Promise<{ pushed: boolean; reason?: string; commit?: GitCommit; changed_files?: number; status: GitStatus }>;
  gitPublish(projectId: string, payload: GitPublishInput): Promise<{ published: boolean; commit: string; version: string | null; published_at: string; status: GitStatus }>;
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

  getProjectSettings(projectId: string): Promise<ProjectSettings> {
    return this.request(`/projects/${projectId}/settings`);
  }

  saveProjectSettings(projectId: string, payload: ProjectSettingsUpdate): Promise<ProjectSettings> {
    return this.request(`/projects/${projectId}/settings`, { method: "PUT", body: payload });
  }

  async listUsers(projectId: string): Promise<ManagedUser[]> {
    const users = await this.request<ManagedUserWire[]>(`/projects/${projectId}/users`);
    return users.map(normalizeManagedUser);
  }

  async updateUser(projectId: string, telegramId: string, payload: ManagedUserUpdate): Promise<ManagedUser> {
    const user = await this.request<ManagedUserWire>(`/projects/${projectId}/users/${encodeURIComponent(telegramId)}`, {
      method: "PUT",
      body: payload,
    });
    return normalizeManagedUser(user);
  }

  getView(projectId: string, id: string): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}`);
  }

  createView(projectId: string, id: string, payload: ViewSpec, textContent?: string, contentDocument?: BotContentDocument): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views`, { method: "POST", body: { id, payload, text_content: textContent, content_document: contentDocument } });
  }

  resolveCustomEmojis(projectId: string, ids: string[], fallbackById: Record<string, string> = {}, source: CustomEmojiSource = "manual-id"): Promise<{ items: ResolvedCustomEmoji[] }> {
    return this.request(`/projects/${projectId}/telegram/custom-emojis/resolve`, {
      method: "POST",
      body: { customEmojiIds: ids, fallbackById, source },
    });
  }

  customEmojiPreviewUrl(projectId: string, id: string): string {
    const root = this.baseUrl.replace(/\/$/, "");
    return `${root}/api/v1/projects/${encodeURIComponent(projectId)}/telegram/custom-emojis/${encodeURIComponent(id)}/preview`;
  }

  testCustomEmojiCapability(projectId: string, id: string, chatId: number | string, fallbackEmoji = "🙂"): Promise<CustomEmojiCapabilityResult> {
    return this.request(`/projects/${projectId}/telegram/custom-emojis/capability-test`, {
      method: "POST",
      body: { customEmojiId: id, chatId, fallbackEmoji },
    });
  }

  createNamedView(projectId: string, name?: string, textContent?: string, contentDocument?: BotContentDocument): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views`, { method: "POST", body: { name, text_content: textContent, content_document: contentDocument } });
  }

  saveView(projectId: string, id: string, payload: ViewSpec, revision: string, textContent: string, textRevision: string | null): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: { payload, revision, text_content: textContent, text_revision: textRevision },
    });
  }

  saveViewContent(projectId: string, id: string, payload: ViewSpec, revision: string, document: BotContentDocument, documentRevision: string | null, textRevision: string | null): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}/content`, {
      method: "PUT",
      body: {
        payload,
        revision,
        document,
        document_revision: documentRevision,
        text_revision: textRevision,
      },
    });
  }

  renameView(projectId: string, id: string, name: string, revision: string): Promise<ViewDetail> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}/rename`, { method: "POST", body: { id: name, revision } });
  }

  deleteView(projectId: string, id: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/views/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  getFlow(projectId: string, id: string): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows/${encodeURIComponent(id)}`);
  }

  createFlow(projectId: string, id: string, payload: FlowSpec): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows`, { method: "POST", body: { id, payload } });
  }

  createNamedFlow(projectId: string, name?: string): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows`, { method: "POST", body: { name } });
  }

  saveFlow(projectId: string, id: string, payload: FlowSpec, revision: string): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: { payload, revision },
    });
  }

  renameFlow(projectId: string, id: string, name: string, revision: string): Promise<FlowDetail> {
    return this.request(`/projects/${projectId}/flows/${encodeURIComponent(id)}/rename`, { method: "POST", body: { id: name, revision } });
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

  createNamedSchedule(projectId: string, name?: string): Promise<ScheduleDetail> {
    return this.request(`/projects/${projectId}/schedules`, { method: "POST", body: { name } });
  }

  saveSchedule(projectId: string, id: string, payload: ScheduleSpec, revision: string): Promise<ScheduleDetail> {
    return this.request(`/projects/${projectId}/schedules/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: { payload, revision },
    });
  }

  renameSchedule(projectId: string, id: string, name: string, revision: string): Promise<ScheduleDetail> {
    return this.request(`/projects/${projectId}/schedules/${encodeURIComponent(id)}/rename`, { method: "POST", body: { id: name, revision } });
  }

  deleteSchedule(projectId: string, id: string, revision: string): Promise<void> {
    return this.request(`/projects/${projectId}/schedules/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" });
  }

  async getHandler(projectId: string, id: string): Promise<HandlerDetail> {
    return normalizeHandler(await this.request<HandlerWire>(`/projects/${projectId}/handlers/${encodeURIComponent(id)}`));
  }

  async renameHandler(projectId: string, id: string, name: string, revision: string): Promise<HandlerDetail> {
    return normalizeHandler(await this.request<HandlerWire>(`/projects/${projectId}/handlers/${encodeURIComponent(id)}/rename`, { method: "POST", body: { id: name, revision } }));
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

  getVariables(projectId: string, context: VariableResourceContext = {}): Promise<VariableCatalogDetail> {
    const query = new URLSearchParams();
    if (context.resourceType) query.set("resource_type", context.resourceType);
    if (context.resourceId) query.set("resource_id", context.resourceId);
    if (context.flowId) query.set("flow_id", context.flowId);
    if (context.stateId) query.set("state_id", context.stateId);
    if (context.handlerId) query.set("handler_id", context.handlerId);
    const suffix = query.size ? `?${query.toString()}` : "";
    return this.request(`/projects/${projectId}/variables${suffix}`);
  }

  saveVariables(projectId: string, payload: VariableCatalogSpec, revision: string | null): Promise<VariableCatalogDetail> {
    return this.request(`/projects/${projectId}/variables`, {
      method: "PUT",
      body: { payload, revision },
    });
  }

  compileContent(projectId: string, document: BotContentDocument, variables: Record<string, unknown> = {}, signal?: AbortSignal): Promise<TelegramCompileResult> {
    return this.request(`/projects/${projectId}/content/compile`, {
      method: "POST",
      body: { document, variables },
      signal,
    });
  }

  sendPreviewMessage(projectId: string, input: SendPreviewMessageInput): Promise<SendPreviewMessageResult> {
    return this.request(`/projects/${projectId}/content/send-preview`, {
      method: "POST",
      body: {
        document: input.document,
        variables: input.variables ?? {},
        chatId: input.chatId,
        splitLongMessages: input.splitLongMessages ?? true,
      },
    });
  }

  async validate(projectId: string): Promise<Diagnostic[]> {
    const value = await this.request<Diagnostic[] | { issues?: Diagnostic[]; diagnostics?: Diagnostic[] }>(`/projects/${projectId}/validation`);
    if (Array.isArray(value)) return value;
    return value.diagnostics ?? value.issues ?? [];
  }

  setDisplayName(projectId: string, kind: "views" | "flows" | "schedules" | "handlers" | "commands", key: string, name: string, manifestRevision: string): Promise<{ name: string; name_is_default: boolean }> {
    return this.request(`/projects/${projectId}/display-names`, { method: "POST", body: { kind, key, name, revision: manifestRevision } });
  }

  gitStatus(projectId: string): Promise<GitStatus> {
    return this.request(`/projects/${projectId}/git/status`);
  }

  gitChanges(projectId: string): Promise<GitChanges> {
    return this.request(`/projects/${projectId}/git/changes`);
  }

  async gitHistory(projectId: string): Promise<GitCommit[]> {
    const value = await this.request<{ commits: GitCommit[] }>(`/projects/${projectId}/git/history`);
    return value.commits;
  }

  gitConnect(projectId: string, payload: GitConnectInput): Promise<GitStatus> {
    return this.request(`/projects/${projectId}/git/connect`, { method: "POST", body: payload });
  }

  gitCreateRepository(projectId: string, payload: GitCreateRepositoryInput): Promise<GitStatus> {
    return this.request(`/projects/${projectId}/git/create-repository`, { method: "POST", body: payload });
  }

  gitDisconnect(projectId: string): Promise<GitStatus> {
    return this.request(`/projects/${projectId}/git/disconnect`, { method: "POST" });
  }

  gitFetch(projectId: string, token?: string): Promise<GitStatus> {
    return this.request(`/projects/${projectId}/git/fetch`, { method: "POST", body: { token } });
  }

  gitSync(projectId: string, token?: string): Promise<GitStatus> {
    return this.request(`/projects/${projectId}/git/sync`, { method: "POST", body: { token } });
  }

  gitPush(projectId: string, message: string, token?: string): Promise<{ pushed: boolean; reason?: string; commit?: GitCommit; changed_files?: number; status: GitStatus }> {
    return this.request(`/projects/${projectId}/git/push`, { method: "POST", body: { message, token } });
  }

  gitPublish(projectId: string, payload: GitPublishInput): Promise<{ published: boolean; commit: string; version: string | null; published_at: string; status: GitStatus }> {
    return this.request(`/projects/${projectId}/git/publish`, { method: "POST", body: payload });
  }

  private async workspace(path: string, options?: RequestOptions): Promise<Workspace> {
    const value = await this.request<WorkspaceWire>(path, options);
    return {
      ...value,
      schema_version: 3,
      views: value.views ?? [],
      flows: value.flows ?? [],
      handlers: (value.handlers ?? []).map(normalizeHandler),
      schedules: value.schedules ?? [],
    };
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}/api/v1${path}`, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
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

function normalizeManagedUser(value: ManagedUserWire): ManagedUser {
  return {
    telegramId: value.telegram_id,
    username: value.username,
    firstName: value.first_name,
    lastName: value.last_name,
    languageCode: value.language_code,
    role: value.role,
    status: value.status,
    note: value.note,
    avatarVersion: value.avatar_version,
  };
}
