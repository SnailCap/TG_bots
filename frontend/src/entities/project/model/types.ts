export type ProjectTreeKind =
  | "project"
  | "directory"
  | "flow"
  | "script"
  | "asset"
  | "settings";

export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  updatedAt?: string;
}

export interface ProjectDetails extends ProjectSummary {
  startFlowId?: string | null;
  description?: string;
}

export interface ProjectTreeNode {
  id: string;
  name: string;
  path: string;
  kind: ProjectTreeKind;
  children: ProjectTreeNode[];
  hasError?: boolean;
  errorCount?: number;
}

export interface ProjectCreateInput {
  name: string;
  directory: string;
}

export interface WorkspaceTab {
  id: string;
  type: "flow" | "script" | "settings" | "preview";
  title: string;
  resourceId?: string;
  path?: string;
  dirty?: boolean;
}
