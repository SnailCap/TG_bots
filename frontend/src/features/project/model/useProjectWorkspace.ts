import { useCallback, useEffect, useReducer, useState } from "react";
import type { ActionDefinition } from "../../../shared/api/types";
import { toApiError } from "../../../shared/api/client";
import { studioApi } from "../../../shared/api/studioApi";
import type {
  ProjectCreateInput,
  ProjectDetails,
  ProjectSummary,
  ProjectTreeKind,
  ProjectTreeNode,
  WorkspaceTab,
} from "../../../entities/project/model/types";
import { initialWorkspaceState, workspaceReducer } from "./workspaceReducer";

export function useProjectWorkspace(onError: (message: string) => void) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectDetails | null>(null);
  const [tree, setTree] = useState<ProjectTreeNode[]>([]);
  const [actions, setActions] = useState<ActionDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [workspace, dispatch] = useReducer(workspaceReducer, initialWorkspaceState);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      setProjects(await studioApi.listProjects());
    } catch (error) {
      onError(toApiError(error).message);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const refreshProjectResources = useCallback(
    async (projectId = currentProject?.id) => {
      if (!projectId) return;
      const [nextTree, nextActions] = await Promise.all([
        studioApi.getTree(projectId),
        studioApi.listActions(projectId).catch(() => []),
      ]);
      setTree(nextTree);
      setActions(nextActions);
    },
    [currentProject?.id],
  );

  const selectProject = useCallback(
    async (projectId: string) => {
      setLoading(true);
      try {
        const project = await studioApi.getProject(projectId);
        setCurrentProject(project);
        dispatch({ type: "reset" });
        await refreshProjectResources(project.id);
      } catch (error) {
        onError(toApiError(error).message);
      } finally {
        setLoading(false);
      }
    },
    [onError, refreshProjectResources],
  );

  const adoptProject = useCallback(
    async (project: ProjectDetails) => {
      setProjects((items) => [project, ...items.filter((item) => item.id !== project.id)]);
      setCurrentProject(project);
      dispatch({ type: "reset" });
      await refreshProjectResources(project.id);
    },
    [refreshProjectResources],
  );

  const createProject = useCallback(
    async (input: ProjectCreateInput) => {
      try {
        await adoptProject(await studioApi.createProject(input));
        return true;
      } catch (error) {
        onError(toApiError(error).message);
        return false;
      }
    },
    [adoptProject, onError],
  );

  const openProject = useCallback(
    async (path: string) => {
      try {
        await adoptProject(await studioApi.openProject(path));
      } catch (error) {
        onError(toApiError(error).message);
      }
    },
    [adoptProject, onError],
  );

  const renameCurrentProject = useCallback(
    async (name: string) => {
      if (!currentProject || !name.trim()) return;
      try {
        const updated = await studioApi.updateProject(currentProject.id, { name: name.trim() });
        setCurrentProject(updated);
        setProjects((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      } catch (error) {
        onError(toApiError(error).message);
      }
    },
    [currentProject, onError],
  );

  const openTab = useCallback((tab: WorkspaceTab) => dispatch({ type: "open", tab }), []);
  const closeTab = useCallback((tabId: string) => dispatch({ type: "close", tabId }), []);
  const activateTab = useCallback((tabId: string) => dispatch({ type: "activate", tabId }), []);
  const markTabDirty = useCallback(
    (tabId: string, dirty: boolean) => dispatch({ type: "dirty", tabId, dirty }),
    [],
  );

  const createResource = useCallback(
    async (kind: ProjectTreeKind, name: string) => {
      if (!currentProject) return;
      try {
        if (kind === "flow") {
          const flow = await studioApi.createFlow(currentProject.id, name);
          openTab({ id: `flow:${flow.id}`, type: "flow", title: flow.name, resourceId: flow.id });
        } else if (kind === "script") {
          const path = name.startsWith("scripts/") ? name : `scripts/${name.endsWith(".py") ? name : `${name}.py`}`;
          const script = await studioApi.createScript(currentProject.id, path);
          openTab({ id: `script:${script.path}`, type: "script", title: script.name, path: script.path });
        } else {
          await studioApi.createTreeItem(currentProject.id, kind, name);
        }
        await refreshProjectResources();
      } catch (error) {
        onError(toApiError(error).message);
      }
    },
    [currentProject, onError, openTab, refreshProjectResources],
  );

  const renameResource = useCallback(
    async (node: ProjectTreeNode, newPath: string) => {
      if (!currentProject) return;
      try {
        if (node.kind === "script") await studioApi.renameScript(currentProject.id, node.path, newPath);
        else await studioApi.renameTreeItem(currentProject.id, node.path, newPath);
        await refreshProjectResources();
      } catch (error) {
        onError(toApiError(error).message);
      }
    },
    [currentProject, onError, refreshProjectResources],
  );

  const deleteResource = useCallback(
    async (node: ProjectTreeNode) => {
      if (!currentProject) return;
      try {
        if (node.kind === "flow") await studioApi.deleteFlow(currentProject.id, node.id);
        else if (node.kind === "script") await studioApi.deleteScript(currentProject.id, node.path);
        else await studioApi.deleteTreeItem(currentProject.id, node.path);
        closeTab(`${node.kind}:${node.kind === "flow" ? node.id : node.path}`);
        await refreshProjectResources();
      } catch (error) {
        onError(toApiError(error).message);
      }
    },
    [closeTab, currentProject, onError, refreshProjectResources],
  );

  return {
    projects,
    currentProject,
    tree,
    actions,
    loading,
    workspace,
    loadProjects,
    selectProject,
    createProject,
    openProject,
    renameCurrentProject,
    refreshProjectResources,
    openTab,
    closeTab,
    activateTab,
    markTabDirty,
    createResource,
    renameResource,
    deleteResource,
  };
}
