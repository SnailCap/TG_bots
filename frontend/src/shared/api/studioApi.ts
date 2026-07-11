import type { FlowDocument } from "../../entities/flow/model/types";
import { normalizeFlow, serializeFlow } from "../../entities/flow/model/flowTransport";
import type { ProjectCreateInput, ProjectDetails, ProjectSummary, ProjectTreeKind, ProjectTreeNode } from "../../entities/project/model/types";
import type { RuntimeLogEvent, RuntimeStatus, ValidationIssue } from "../../entities/runtime/model/types";
import { ApiClient, apiClient } from "./client";
import {
  normalizeActions,
  normalizeIssues,
  normalizeLog,
  normalizeLogs,
  normalizeProject,
  normalizeProjects,
  normalizeRuntimeStatus,
  normalizeScript,
  normalizeSearchMatches,
  normalizeSettings,
  normalizeTokenResult,
  normalizeTree,
  normalizeUsages,
} from "./normalize";
import type {
  ActionDefinition,
  ActionUsage,
  BotSettings,
  RuntimeEventEnvelope,
  ScriptFile,
  ScriptSearchMatch,
  TokenValidationResult,
} from "./types";

const projectPath = (projectId: string) => `/projects/${encodeURIComponent(projectId)}`;
const resourcePath = (value: string) => encodeURIComponent(value);

export class StudioApi {
  constructor(readonly client: ApiClient = apiClient) {}

  async listProjects(): Promise<ProjectSummary[]> {
    return normalizeProjects(
      await this.client.requestFirst([
        { method: "GET", url: "/projects" },
        { method: "GET", url: "/projects/recent" },
      ]),
    );
  }

  async createProject(input: ProjectCreateInput): Promise<ProjectDetails> {
    return normalizeProject(await this.client.request({ method: "POST", url: "/projects", data: input }));
  }

  async openProject(path: string): Promise<ProjectDetails> {
    return normalizeProject(await this.client.request({ method: "POST", url: "/projects/open", data: { path } }));
  }

  async getProject(projectId: string): Promise<ProjectDetails> {
    return normalizeProject(await this.client.request({ method: "GET", url: projectPath(projectId) }));
  }

  async updateProject(projectId: string, patch: Partial<ProjectDetails>): Promise<ProjectDetails> {
    return normalizeProject(await this.client.request({ method: "PATCH", url: projectPath(projectId), data: patch }));
  }

  async getTree(projectId: string): Promise<ProjectTreeNode[]> {
    return normalizeTree(await this.client.request({ method: "GET", url: `${projectPath(projectId)}/tree` }));
  }

  async createTreeItem(projectId: string, kind: ProjectTreeKind, path: string): Promise<void> {
    await this.client.request({ method: "POST", url: `${projectPath(projectId)}/tree`, data: { kind, path } });
  }

  async renameTreeItem(projectId: string, path: string, newPath: string): Promise<void> {
    await this.client.request({ method: "PATCH", url: `${projectPath(projectId)}/tree`, data: { path, new_path: newPath } });
  }

  async deleteTreeItem(projectId: string, path: string): Promise<void> {
    await this.client.request({ method: "DELETE", url: `${projectPath(projectId)}/tree`, data: { path } });
  }

  async getFlow(projectId: string, flowId: string): Promise<FlowDocument> {
    const payload = await this.client.requestFirst([
      { method: "GET", url: `${projectPath(projectId)}/flows/${resourcePath(flowId)}` },
      { method: "GET", url: `/flows/${resourcePath(flowId)}`, params: { project_id: projectId } },
    ]);
    return normalizeFlow(payload);
  }

  async createFlow(projectId: string, name: string): Promise<FlowDocument> {
    return normalizeFlow(
      await this.client.request({ method: "POST", url: `${projectPath(projectId)}/flows`, data: { name } }),
    );
  }

  async saveFlow(projectId: string, flow: FlowDocument): Promise<FlowDocument> {
    return normalizeFlow(
      await this.client.requestFirst([
        { method: "PUT", url: `${projectPath(projectId)}/flows/${resourcePath(flow.id)}`, data: serializeFlow(flow) },
        { method: "PATCH", url: `${projectPath(projectId)}/flows/${resourcePath(flow.id)}`, data: serializeFlow(flow) },
      ]),
    );
  }

  async deleteFlow(projectId: string, flowId: string): Promise<void> {
    await this.client.request({ method: "DELETE", url: `${projectPath(projectId)}/flows/${resourcePath(flowId)}` });
  }

  async getScript(projectId: string, path: string): Promise<ScriptFile> {
    return normalizeScript(
      await this.client.requestFirst([
        { method: "GET", url: `${projectPath(projectId)}/scripts/content`, params: { path } },
        { method: "GET", url: `${projectPath(projectId)}/scripts/${resourcePath(path)}` },
      ]),
    );
  }

  async createScript(projectId: string, path: string): Promise<ScriptFile> {
    return normalizeScript(
      await this.client.request({
        method: "POST",
        url: `${projectPath(projectId)}/scripts`,
        data: { path, content: "from bot_engine import action, ActionContext, ActionResult\n\n" },
      }),
    );
  }

  async saveScript(projectId: string, script: ScriptFile): Promise<ScriptFile> {
    const payload = await this.client.requestFirst([
        { method: "PUT", url: `${projectPath(projectId)}/scripts`, data: { path: script.path, content: script.content } },
        { method: "PUT", url: `${projectPath(projectId)}/scripts/${resourcePath(script.path)}`, data: script },
        { method: "PATCH", url: `${projectPath(projectId)}/scripts/${resourcePath(script.path)}`, data: script },
      ]);
    return payload ? normalizeScript(payload) : script;
  }

  async validateScript(projectId: string, path: string, content: string): Promise<ValidationIssue[]> {
    return normalizeIssues(
      await this.client.requestFirst([
        { method: "POST", url: `${projectPath(projectId)}/scripts/${resourcePath(path)}/validate`, data: { content } },
        { method: "POST", url: `${projectPath(projectId)}/scripts/validate`, data: { path, content } },
      ]),
    );
  }

  async deleteScript(projectId: string, path: string): Promise<void> {
    await this.client.requestFirst([
      { method: "DELETE", url: `${projectPath(projectId)}/scripts`, params: { path } },
      { method: "DELETE", url: `${projectPath(projectId)}/scripts/${resourcePath(path)}` },
    ]);
  }

  async renameScript(projectId: string, path: string, newPath: string): Promise<void> {
    await this.client.requestFirst([
      { method: "PATCH", url: `${projectPath(projectId)}/scripts`, data: { path, new_path: newPath } },
      { method: "PATCH", url: `${projectPath(projectId)}/tree`, data: { path, new_path: newPath } },
    ]);
  }

  async searchScripts(projectId: string, query: string): Promise<ScriptSearchMatch[]> {
    return normalizeSearchMatches(
      await this.client.request({ method: "GET", url: `${projectPath(projectId)}/scripts/search`, params: { q: query } }),
    );
  }

  async listActions(projectId: string): Promise<ActionDefinition[]> {
    return normalizeActions(
      await this.client.requestFirst([
        { method: "GET", url: `${projectPath(projectId)}/scripts/actions` },
        { method: "GET", url: `${projectPath(projectId)}/actions` },
      ]),
    );
  }

  async actionUsages(projectId: string, actionName: string): Promise<ActionUsage[]> {
    return normalizeUsages(
      await this.client.requestFirst([
        { method: "GET", url: `${projectPath(projectId)}/scripts/actions/${resourcePath(actionName)}/usages` },
        { method: "GET", url: `${projectPath(projectId)}/actions/${resourcePath(actionName)}/usages` },
      ]),
    );
  }

  async getSettings(projectId: string): Promise<BotSettings> {
    return normalizeSettings(await this.client.request({ method: "GET", url: `${projectPath(projectId)}/settings` }));
  }

  async saveSettings(projectId: string, settings: Partial<BotSettings>): Promise<BotSettings> {
    return normalizeSettings(
      await this.client.request({
        method: "PUT",
        url: `${projectPath(projectId)}/settings`,
        data: {
          start_flow_id: settings.startFlowId,
          start_behavior: settings.startBehavior,
        },
      }),
    );
  }

  async saveToken(projectId: string, token: string): Promise<TokenValidationResult> {
    const saved = await this.client.request({
      method: "PUT",
      url: `${projectPath(projectId)}/token`,
      data: { token },
    });
    return normalizeTokenResult(saved);
  }

  async validateToken(projectId: string): Promise<TokenValidationResult> {
    return normalizeTokenResult(
      await this.client.request({ method: "POST", url: `${projectPath(projectId)}/token/validate` }),
    );
  }

  async validateProject(projectId: string): Promise<ValidationIssue[]> {
    return normalizeIssues(
      await this.client.requestFirst([
        { method: "POST", url: `${projectPath(projectId)}/validate` },
        { method: "POST", url: `${projectPath(projectId)}/validation` },
      ]),
    );
  }

  async runtimeStatus(projectId: string): Promise<RuntimeStatus> {
    return normalizeRuntimeStatus(
      await this.client.requestFirst([
        { method: "GET", url: `${projectPath(projectId)}/runtime/status` },
        { method: "GET", url: `/runtime/${resourcePath(projectId)}/status` },
      ]),
    );
  }

  async run(projectId: string): Promise<RuntimeStatus> {
    return normalizeRuntimeStatus(
      await this.client.requestFirst([
        { method: "POST", url: `${projectPath(projectId)}/runtime/run` },
        { method: "POST", url: `/runtime/${resourcePath(projectId)}/run` },
      ]),
    );
  }

  async stop(projectId: string): Promise<RuntimeStatus> {
    return normalizeRuntimeStatus(
      await this.client.requestFirst([
        { method: "POST", url: `${projectPath(projectId)}/runtime/stop` },
        { method: "POST", url: `/runtime/${resourcePath(projectId)}/stop` },
      ]),
    );
  }

  async logs(projectId: string): Promise<RuntimeLogEvent[]> {
    return normalizeLogs(
      await this.client.requestFirst([
        { method: "GET", url: `${projectPath(projectId)}/runtime/logs` },
        { method: "GET", url: `/runtime/${resourcePath(projectId)}/logs` },
      ]),
    );
  }

  connectRuntimeEvents(projectId: string, onEvent: (event: RuntimeEventEnvelope) => void, onError: () => void): EventSource {
    const configuredPath = import.meta.env.VITE_RUNTIME_EVENTS_PATH as string | undefined;
    const eventsPath = configuredPath
      ? configuredPath.replace("{projectId}", encodeURIComponent(projectId))
      : `/events?project_id=${encodeURIComponent(projectId)}`;
    const source = new EventSource(this.client.absoluteUrl(eventsPath));
    const consume = (message: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(message.data) as RuntimeEventEnvelope & Record<string, unknown>;
        if (parsed.type || parsed.log || parsed.status || parsed.issues) {
          onEvent(parsed);
          return;
        }
        const category = typeof parsed.category === "string" ? parsed.category.toLowerCase() : "runtime";
        if (category.includes("status") && parsed.context && typeof parsed.context === "object") {
          onEvent({ type: "status", status: normalizeRuntimeStatus(parsed.context) });
        } else {
          onEvent({ type: "log", log: normalizeLog(parsed) });
        }
      } catch {
        onEvent({
          type: "log",
          log: {
            id: `${Date.now()}`,
            timestamp: new Date().toISOString(),
            level: "info",
            message: message.data,
          },
        });
      }
    };
    source.onmessage = consume;
    source.addEventListener("log", consume as EventListener);
    source.addEventListener("status", consume as EventListener);
    source.addEventListener("runtime", consume as EventListener);
    source.onerror = onError;
    return source;
  }
}

export const studioApi = new StudioApi();
