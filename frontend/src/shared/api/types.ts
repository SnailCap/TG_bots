import type { FlowDocument } from "../../entities/flow/model/types";
import type { ProjectDetails, ProjectSummary, ProjectTreeNode } from "../../entities/project/model/types";
import type { BotIdentity, RuntimeLogEvent, RuntimeStatus, ValidationIssue } from "../../entities/runtime/model/types";

export interface ListEnvelope<T> {
  items?: T[];
  results?: T[];
  data?: T[];
}

export type ProjectListResponse = ProjectSummary[] | ListEnvelope<ProjectSummary>;
export type ProjectResponse = ProjectDetails | { project: ProjectDetails } | { data: ProjectDetails };
export type TreeResponse = ProjectTreeNode[] | { tree: ProjectTreeNode[] | ProjectTreeNode } | ProjectTreeNode;
export type FlowResponse = FlowDocument | { flow: FlowDocument } | { data: FlowDocument };

export interface ScriptFile {
  path: string;
  name: string;
  content: string;
  revision?: string | number;
}

export interface ScriptSummary {
  path: string;
  name: string;
  hasErrors?: boolean;
}

export interface ScriptSearchMatch {
  path: string;
  line: number;
  column?: number;
  preview: string;
}

export interface ActionDefinition {
  name: string;
  module?: string;
  scriptPath: string;
  line?: number;
  signature?: string;
  valid: boolean;
  error?: string;
}

export interface ActionUsage {
  actionName: string;
  flowId: string;
  flowName?: string;
  nodeId: string;
  nodeTitle?: string;
}

export interface BotSettings {
  startFlowId?: string | null;
  startBehavior?: "reset" | "resume";
  tokenConfigured: boolean;
  tokenReference?: string | null;
  bot?: BotIdentity | null;
}

export interface TokenValidationResult {
  valid: boolean;
  bot?: BotIdentity | null;
  error?: string;
}

export interface RuntimeEventEnvelope {
  type?: "log" | "status" | "validation";
  log?: RuntimeLogEvent;
  status?: RuntimeStatus;
  issues?: ValidationIssue[];
}
