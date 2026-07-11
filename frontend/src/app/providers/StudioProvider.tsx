import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type {
  GraphNavigationTarget,
  GraphSelection,
  NodePatch,
  StudioNodeData,
} from "../../entities/flow/model/types";
import type {
  ProjectCreateInput,
  ProjectTreeKind,
  ProjectTreeNode,
  WorkspaceTab,
} from "../../entities/project/model/types";
import type { ValidationIssue } from "../../entities/runtime/model/types";
import { useProjectWorkspace } from "../../features/project/model/useProjectWorkspace";
import { useRuntimeConnection } from "../../features/runtime/ui/useRuntimeConnection";
import type { ActionUsage } from "../../shared/api/types";

type ProjectWorkspace = ReturnType<typeof useProjectWorkspace>;
type RuntimeConnection = ReturnType<typeof useRuntimeConnection>;

interface StudioContextValue extends ProjectWorkspace, RuntimeConnection {
  appError: string | null;
  clearAppError(): void;
  graphSelection: GraphSelection;
  selectGraphElement(selection: GraphSelection): void;
  nodePatch: NodePatch | null;
  patchSelectedNode(patch: Partial<StudioNodeData>): void;
  graphNavigation: GraphNavigationTarget | null;
  scriptNavigation: { revision: number; path: string; line?: number } | null;
  navigateToScript(path: string, line?: number): void;
  openTreeNode(node: ProjectTreeNode): void;
  navigateToUsage(usage: ActionUsage): void;
  navigateToIssue(issue: ValidationIssue): void;
  createProjectAndOpen(input: ProjectCreateInput): Promise<boolean>;
  createExplorerResource(kind: ProjectTreeKind, name: string): Promise<void>;
}

const StudioContext = createContext<StudioContextValue | null>(null);

export function StudioProvider({ children }: PropsWithChildren) {
  const [appError, setAppError] = useState<string | null>(null);
  const [graphSelection, setGraphSelection] = useState<GraphSelection>(null);
  const [nodePatch, setNodePatch] = useState<NodePatch | null>(null);
  const [graphNavigation, setGraphNavigation] = useState<GraphNavigationTarget | null>(null);
  const [scriptNavigation, setScriptNavigation] = useState<{ revision: number; path: string; line?: number } | null>(null);
  const showError = useCallback((message: string) => setAppError(message), []);
  const project = useProjectWorkspace(showError);
  const runtime = useRuntimeConnection(project.currentProject?.id, showError);

  const openTreeNode = useCallback(
    (node: ProjectTreeNode) => {
      let tab: WorkspaceTab | null = null;
      if (node.kind === "flow") {
        tab = { id: `flow:${node.id}`, type: "flow", title: node.name, resourceId: node.id };
      } else if (node.kind === "script") {
        tab = { id: `script:${node.path}`, type: "script", title: node.name, path: node.path };
      } else if (node.kind === "settings") {
        tab = { id: "settings", type: "settings", title: "Bot Settings" };
      } else if (node.kind === "asset") {
        tab = { id: `preview:${node.path}`, type: "preview", title: node.name, path: node.path };
      }
      if (tab) project.openTab(tab);
    },
    [project.openTab],
  );

  const navigateToUsage = useCallback(
    (usage: ActionUsage) => {
      project.openTab({
        id: `flow:${usage.flowId}`,
        type: "flow",
        title: usage.flowName ?? "Flow",
        resourceId: usage.flowId,
      });
      setGraphNavigation((target) => ({
        revision: (target?.revision ?? 0) + 1,
        flowId: usage.flowId,
        nodeId: usage.nodeId,
      }));
    },
    [project.openTab],
  );

  const navigateToScript = useCallback(
    (path: string, line?: number) => {
      project.openTab({
        id: `script:${path}`,
        type: "script",
        title: path.split(/[\\/]/).pop() ?? "Script",
        path,
      });
      setScriptNavigation((target) => ({ revision: (target?.revision ?? 0) + 1, path, line }));
    },
    [project.openTab],
  );

  const navigateToIssue = useCallback(
    (issue: ValidationIssue) => {
      const entity = issue.entity;
      if (entity?.scriptPath) {
        navigateToScript(entity.scriptPath, entity.line);
      } else if (entity?.flowId) {
        project.openTab({
          id: `flow:${entity.flowId}`,
          type: "flow",
          title: "Flow",
          resourceId: entity.flowId,
        });
        if (entity.nodeId) {
          setGraphNavigation((target) => ({
            revision: (target?.revision ?? 0) + 1,
            flowId: entity.flowId!,
            nodeId: entity.nodeId!,
          }));
        }
      }
    },
    [navigateToScript, project.openTab],
  );

  const patchSelectedNode = useCallback(
    (patch: Partial<StudioNodeData>) => {
      if (!graphSelection || graphSelection.kind !== "node") return;
      setGraphSelection({
        ...graphSelection,
        node: { ...graphSelection.node, data: { ...graphSelection.node.data, ...patch } },
      });
      setNodePatch((previous) => ({
        revision: (previous?.revision ?? 0) + 1,
        flowId: graphSelection.flowId,
        nodeId: graphSelection.node.id,
        patch,
      }));
    },
    [graphSelection],
  );

  const value = useMemo<StudioContextValue>(
    () => ({
      ...project,
      ...runtime,
      appError,
      clearAppError: () => setAppError(null),
      graphSelection,
      selectGraphElement: setGraphSelection,
      nodePatch,
      patchSelectedNode,
      graphNavigation,
      scriptNavigation,
      navigateToScript,
      openTreeNode,
      navigateToUsage,
      navigateToIssue,
      createProjectAndOpen: project.createProject,
      createExplorerResource: project.createResource,
    }),
    [
      appError,
      graphNavigation,
      graphSelection,
      navigateToScript,
      navigateToIssue,
      navigateToUsage,
      nodePatch,
      openTreeNode,
      patchSelectedNode,
      project,
      runtime,
      scriptNavigation,
    ],
  );

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>;
}

export function useStudio(): StudioContextValue {
  const context = useContext(StudioContext);
  if (!context) throw new Error("useStudio must be used inside StudioProvider");
  return context;
}
