import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type ActionOptions,
  type Selection,
  type Workspace,
} from "../../domain/project";
import { createTelegramPreviewModel } from "../../features/telegram-preview/preview-model";
import { type StudioApiClient, StudioApiError } from "../../studio/api";
import type { CreatableResource } from "../../widgets/project-explorer/ProjectExplorer";
import {
  canSave,
  deletedResourceSnapshot,
  draftForEditor,
  previewEditor,
  selectionForDeletedResource,
  selectionForEditor,
  selectionKeyEquals,
  selectionTabKey,
  isEditorInvalid,
  openViewTextTab,
  studioStatus,
  viewTextTabKey,
  type DeletedResource,
  type EditorState,
  type EditorTab,
} from "./editor-model";
import { StudioPageView } from "./StudioPageView";
import {
  createResource,
  deleteEditor,
  deletePersistedResource as deletePersistedResourceViaApi,
  deleteSelection,
  loadEditor,
  renameResource as renameResourceViaApi,
  restoreDeletedResource as restoreDeletedResourceViaApi,
  saveEditor,
} from "./studio-resource-api";
import { useLocalProjectRun } from "./useLocalProjectRun";
import { useProjectSettings } from "./useProjectSettings";
import { useStudioHandlers } from "./useStudioHandlers";
import { useStudioLayout } from "./useStudioLayout";
import { useStudioUndo } from "./useStudioUndo";
import { StudioRouter } from "./StudioRouter";

export function StudioPage({ api, apiBaseUrl, initialWorkspace, recentProjects = [], onOpenProject = () => undefined, onNewProject = () => undefined }: { api: StudioApiClient; apiBaseUrl: string; initialWorkspace: Workspace; recentProjects?: readonly string[]; onOpenProject?(path: string): void; onNewProject?(): void }) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [editor, setEditor] = useState<EditorState>(null);
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activeTabKey, setActiveTabKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const tabsRef = useRef(tabs);
  const activeTabKeyRef = useRef(activeTabKey);
  const saveShortcutRef = useRef<() => void>(() => undefined);
  tabsRef.current = tabs;
  activeTabKeyRef.current = activeTabKey;
  const nextNewTabId = useRef(1);
  const firstContentKey = useRef<string | null>(null);
  if (!firstContentKey.current && activeTabKey) firstContentKey.current = activeTabKey;

  const report = useCallback((caught: unknown) => {
    const message = caught instanceof Error ? caught.message : "Unexpected error";
    setError(message);
    setConflict(caught instanceof StudioApiError && caught.code === "revision_conflict");
  }, []);
  const clearError = useCallback(() => {
    setError("");
    setConflict(false);
  }, []);
  const { undoAvailable, pushUndo, performUndo } = useStudioUndo({ busy, setBusy, clearError, report });

  const {
    explorerWidth,
    terminalHeight,
    workspaceRef,
    maximumExplorerWidth,
    maximumTerminalHeight,
    resizeExplorer,
    commitExplorerSize,
    resizeTerminal,
    commitTerminalSize,
  } = useStudioLayout(previewOpen);
  const {
    settingsOpen,
    setSettingsOpen,
    projectSettings,
    settingsLoading,
    settingsSaving,
    openProjectSettings,
    saveProjectSettings,
    clearProjectSettings,
  } = useProjectSettings(api, workspace.project_id);
  const {
    startingLocalRun,
    stoppingLocalRun,
    localRunPid,
    terminalEntries,
    localRunActive,
    canRunLocalProject,
    runProject,
    stopProject,
  } = useLocalProjectRun({
    workspace,
    dirty,
    busy,
    saving,
    setTerminalOpen,
    setNotice,
    setError,
    report,
  });

  const refreshWorkspace = useCallback(async () => {
    const next = await api.describe(workspace.project_id);
    setWorkspace(next);
    return next;
  }, [api, workspace.project_id]);

  const loadSelection = useCallback(async (next: Selection, tabKey?: string) => {
    const nextEditor = await loadEditor(api, workspace.project_id, next);
    setEditor(nextEditor);
    if (tabKey) setTabs((current) => current.some((tab) => tab.key === tabKey)
      ? current.map((tab) => tab.key === tabKey ? { ...tab, editor: nextEditor, dirty: false } : tab)
      : [...current, { key: tabKey, editor: nextEditor, dirty: false }]);
    setDirty(false);
    setNotice("");
    setError("");
    setConflict(false);
  }, [api, workspace.project_id]);

  const select = useCallback((next: Selection) => {
    const tabKey = selectionTabKey(next);
    const existing = tabs.find((tab) => tab.key === tabKey);
    if (existing) {
      setActiveTabKey(tabKey);
      setEditor(existing.editor);
      setSelection(selectionForEditor(existing.editor));
      setDirty(existing.dirty);
      setNotice("");
      setError("");
      setConflict(false);
      return;
    }
    if (editor && activeTabKey) setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
    setActiveTabKey(tabKey);
    setSelection(next);
    setBusy(true);
    void loadSelection(next, tabKey).catch(report).finally(() => setBusy(false));
  }, [activeTabKey, dirty, editor, loadSelection, report, tabs]);

  const openViewTextEditor = useCallback((viewId: string, displayName: string) => {
    const next = openViewTextTab(tabs, activeTabKey, editor, dirty, viewId, displayName);
    setActiveTabKey(next.tabKey);
    setSelection({ kind: "view", id: viewId });
    setTabs(next.tabs);
    setEditor(next.editor);
    setDirty(next.dirty);
    setNotice("");
    setError("");
    setConflict(false);
  }, [activeTabKey, dirty, editor, tabs]);

  const restoreDeletedResource = useCallback(async (snapshot: DeletedResource) => {
    await restoreDeletedResourceViaApi(api, workspace.project_id, snapshot);
  }, [api, workspace.project_id]);

  const pushDeleteUndo = useCallback((snapshot: DeletedResource) => {
    pushUndo({
      undo: async () => {
        await restoreDeletedResource(snapshot);
        await refreshWorkspace();
        select(selectionForDeletedResource(snapshot));
      },
    });
  }, [pushUndo, refreshWorkspace, restoreDeletedResource, select]);

  const closeTabsFor = useCallback((target: Selection) => {
    const remaining = tabsRef.current.filter((tab) => !selectionKeyEquals(selectionForEditor(tab.editor), target));
    setTabs(remaining);
    const activeTab = tabsRef.current.find((tab) => tab.key === activeTabKeyRef.current);
    if (activeTab && selectionKeyEquals(selectionForEditor(activeTab.editor), target)) {
      const fallback = remaining[remaining.length - 1] ?? null;
      setActiveTabKey(fallback?.key ?? null);
      setEditor(fallback?.editor ?? null);
      setSelection(null);
      setDirty(fallback?.dirty ?? false);
    }
  }, []);

  const deletePersistedResource = useCallback(async (target: Selection) => {
    await deletePersistedResourceViaApi(api, workspace.project_id, target);
  }, [api, workspace.project_id]);

  useEffect(() => {
    if (!editor || !activeTabKey) return;
    setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
  }, [activeTabKey, dirty, editor]);

  const { createAndOpenHandler, openHandler, repairHandler, findUsages, handlerActions } = useStudioHandlers({
    api,
    workspace,
    dirty,
    selection,
    setBusy,
    setEditor,
    setNotice,
    clearError,
    report,
    refreshWorkspace,
    loadSelection,
  });

  const options: ActionOptions = useMemo(() => ({
    views: workspace.views.map((item) => item.id),
    flows: workspace.flows.map((item) => item.id),
    states: editor?.kind === "flow" ? Object.keys(editor.detail.payload.states) : [],
    handlers: workspace.handlers,
  }), [editor, workspace]);

  const explorerDraft = useMemo(() => draftForEditor(editor), [editor]);
  const previewModel = useMemo(() => createTelegramPreviewModel(workspace, previewEditor(editor)), [editor, workspace]);

  const addResource = async (kind: CreatableResource) => {
    if (editor && activeTabKey) setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
    if (kind === "handler") {
      const nextEditor: Exclude<EditorState, null> = { kind: "new-handler" };
      const tabKey = `new:${kind}:${nextNewTabId.current++}`;
      setSelection(null);
      setActiveTabKey(tabKey);
      setTabs((current) => [...current, { key: tabKey, editor: nextEditor, dirty: false }]);
      setEditor(nextEditor);
      setDirty(false);
      setNotice("");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const { editor: nextEditor, selection: nextSelection } = await createResource(api, workspace, kind);
      const tabKey = selectionTabKey(nextSelection);
      setSelection(nextSelection);
      setActiveTabKey(tabKey);
      setTabs((current) => [...current, { key: tabKey, editor: nextEditor, dirty: false }]);
      setEditor(nextEditor);
      setDirty(false);
      setError("");
      setConflict(false);
      pushUndo({
        undo: async () => {
          await deletePersistedResource(nextSelection);
          closeTabsFor(nextSelection);
          await refreshWorkspace();
        },
      });
      await refreshWorkspace();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  };

  const closeTab = useCallback((tabKey: string, force = false) => {
    const tab = tabs.find((item) => item.key === tabKey);
    if (!tab) return;
    const needsConfirmation = tabKey === activeTabKey ? dirty : tab.dirty;
    if (!force && needsConfirmation && !window.confirm("Discard unsaved changes?")) return;
    const tabIndex = tabs.findIndex((item) => item.key === tabKey);
    const nextTabs = tabs.filter((item) => item.key !== tabKey);
    setTabs(nextTabs);
    if (tabKey !== activeTabKey) return;
    const nextTab = nextTabs[Math.max(0, tabIndex - 1)] ?? null;
    if (!nextTab) {
      setActiveTabKey(null);
      setEditor(null);
      setDirty(false);
      return;
    }
    setActiveTabKey(nextTab.key);
    setEditor(nextTab.editor);
    setDirty(nextTab.dirty);
  }, [activeTabKey, dirty, tabs]);

  const activateTab = useCallback((tabKey: string) => {
    const tab = tabs.find((item) => item.key === tabKey);
    if (!tab) return;
    if (tabKey === activeTabKey) return;
    if (editor && activeTabKey) setTabs((current) => current.map((item) => item.key === activeTabKey ? { ...item, editor, dirty } : item));
    setActiveTabKey(tabKey);
    setEditor(tab.editor);
    setDirty(tab.dirty);
    setNotice("");
    setError("");
    setConflict(false);
  }, [activeTabKey, dirty, editor, tabs]);

  useEffect(() => {
    const closeWithShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && matchesPhysicalKey(event, "KeyS", "s")) {
        event.preventDefault();
        saveShortcutRef.current();
        return;
      }
      if (event.ctrlKey && (event.key === "`" || event.code === "Backquote")) {
        event.preventDefault();
        setTerminalOpen((open) => !open);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && matchesPhysicalKey(event, "KeyW", "w") && activeTabKey) {
        event.preventDefault();
        closeTab(activeTabKey);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && matchesPhysicalKey(event, "KeyZ", "z")) {
        const target = event.target as HTMLElement | null;
        if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable) return;
        event.preventDefault();
        void performUndo();
      }
    };
    window.addEventListener("keydown", closeWithShortcut);
    return () => window.removeEventListener("keydown", closeWithShortcut);
  }, [activeTabKey, closeTab, performUndo]);

  const save = async () => {
    if (!editor) return;
    setBusy(true);
    setSaving(true);
    try {
      const { editor: nextEditor, selection: nextSelection } = await saveEditor(api, workspace.project_id, editor, selection);
      const nextWorkspace = await api.describe(workspace.project_id);
      setWorkspace(nextWorkspace);
      setEditor(nextEditor);
      setSelection(nextSelection);
      if (activeTabKey) {
        const nextTabKey = nextSelection ? selectionTabKey(nextSelection) : activeTabKey;
        setActiveTabKey(nextTabKey);
        setTabs((current) => current.map((tab) => tab.key === activeTabKey
          ? { ...tab, key: nextTabKey, editor: nextEditor, dirty: false }
          : tab));
      }
      setDirty(false);
      setNotice("");
      setError("");
      setConflict(false);
    } catch (caught) {
      report(caught);
    } finally {
      setSaving(false);
      setBusy(false);
    }
  };

  const saveAll = async () => {
    const pending = tabsRef.current.filter((tab) => tab.dirty);
    if (!pending.length) return;
    const invalid = pending.filter((tab) => isEditorInvalid(tab.editor));
    if (invalid.length) {
      throw new Error(`Fix invalid editor data before using Git: ${invalid.map((tab) => tab.key).join(", ")}`);
    }
    const commandDrafts = pending.filter((tab) => tab.editor.kind === "command" || tab.editor.kind === "commands");
    if (commandDrafts.length > 1) {
      throw new Error("Save the open command editors individually before using Git.");
    }
    setBusy(true);
    setSaving(true);
    try {
      const saved = new Map<string, Awaited<ReturnType<typeof saveEditor>>>();
      for (const tab of pending) {
        saved.set(tab.key, await saveEditor(api, workspace.project_id, tab.editor, selectionForEditor(tab.editor)));
      }
      setTabs((current) => current.map((tab) => {
        const result = saved.get(tab.key);
        return result ? { ...tab, editor: result.editor, dirty: false } : tab;
      }));
      if (activeTabKey) {
        const result = saved.get(activeTabKey);
        if (result) {
          setEditor(result.editor);
          setSelection(result.selection);
          setDirty(false);
        }
      }
      setWorkspace(await api.describe(workspace.project_id));
      setNotice("");
      setError("");
      setConflict(false);
    } catch (caught) {
      report(caught);
      throw caught;
    } finally {
      setSaving(false);
      setBusy(false);
    }
  };

  saveShortcutRef.current = () => {
    if (editor && !busy && canSave(editor)) void save();
  };

  const remove = async () => {
    if (!editor) return;
    const snapshot = deletedResourceSnapshot(editor);
    if (!snapshot) return;
    setBusy(true);
    try {
      await deleteEditor(api, workspace.project_id, editor);
      if (snapshot.kind === "command") setSelection({ kind: "command", name: snapshot.command.name });
      if (activeTabKey) closeTab(activeTabKey, true);
      pushDeleteUndo(snapshot);
      setNotice("");
      await refreshWorkspace();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  };

  const removeFromExplorer = (next: Selection) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setBusy(true);
    void (async () => {
      const snapshot = await deleteSelection(api, workspace.project_id, next);
      if (!snapshot) return;
      if (activeTabKey && selectionKeyEquals(selection, next)) closeTab(activeTabKey, true);
      setTabs((current) => current.filter((tab) => !selectionKeyEquals(selectionForEditor(tab.editor), next)));
      pushDeleteUndo(snapshot);
      await refreshWorkspace();
    })().catch(report).finally(() => setBusy(false));
  };

  const renameResource = useCallback(async (next: Exclude<Selection, { kind: "commands" }>, name: string): Promise<{ selection: Exclude<Selection, { kind: "commands" }>; editor: Exclude<EditorState, null> }> => {
    return renameResourceViaApi(api, workspace.project_id, workspace.manifest.revision, next, name);
  }, [api, workspace.manifest.revision, workspace.project_id]);

  const applyRenameToTabs = useCallback((from: Selection, to: Selection, toEditor: Exclude<EditorState, null>) => {
    const previousTabKey = selectionTabKey(from);
    const nextTabKey = selectionTabKey(to);
    const renamedViewTextEditor = toEditor.kind === "view"
      ? { kind: "view-text" as const, viewId: toEditor.detail.id, displayName: toEditor.detail.name ?? toEditor.detail.id }
      : null;
    setTabs((current) => current.map((tab) => {
      if (!selectionKeyEquals(selectionForEditor(tab.editor), from)) return tab;
      if (tab.editor.kind === "view-text" && renamedViewTextEditor) {
        return {
          ...tab,
          key: viewTextTabKey(renamedViewTextEditor.viewId),
          editor: renamedViewTextEditor,
          dirty: false,
        };
      }
      return { ...tab, key: nextTabKey, editor: toEditor, dirty: false };
    }));
    const activeTab = tabsRef.current.find((tab) => tab.key === activeTabKeyRef.current);
    if (activeTab?.editor.kind === "view-text" && selectionKeyEquals(selectionForEditor(activeTab.editor), from) && renamedViewTextEditor) {
      setActiveTabKey(viewTextTabKey(renamedViewTextEditor.viewId));
      setEditor(renamedViewTextEditor);
      setDirty(false);
    }
    if (activeTabKeyRef.current === previousTabKey) {
      setActiveTabKey(nextTabKey);
      setEditor(toEditor);
      setDirty(false);
    }
    setSelection(to);
  }, []);

  const renameFromExplorer = useCallback(async (next: Exclude<Selection, { kind: "commands" }>, name: string) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setBusy(true);
    try {
      const { selection: nextSelection, editor: nextEditor } = await renameResource(next, name);
      applyRenameToTabs(next, nextSelection, nextEditor);
      await refreshWorkspace();
      const previousName = next.kind === "command" ? next.name : next.id;
      pushUndo({
        undo: async () => {
          const restored = await renameResource(nextSelection, previousName);
          applyRenameToTabs(nextSelection, restored.selection, restored.editor);
          await refreshWorkspace();
        },
      });
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, applyRenameToTabs, dirty, pushUndo, refreshWorkspace, renameResource, report, workspace.project_id]);

  const reloadCurrent = () => {
    if (!selection) return;
    setNotice("");
    setBusy(true);
    void loadSelection(selection).catch(report).finally(() => setBusy(false));
  };

  const switchProject = (path: string) => {
    if (dirty && !window.confirm("Discard unsaved changes and switch project?")) return;
    onOpenProject(path);
  };

  const createProject = () => {
    if (dirty && !window.confirm("Discard unsaved changes and create a new project?")) return;
    onNewProject();
  };
  const status = studioStatus({ error: Boolean(error), saving, busy, dirty, hasEditor: Boolean(editor) });

  return <StudioRouter><StudioPageView
    api={api}
    apiBaseUrl={apiBaseUrl}
    workspace={workspace}
    recentProjects={recentProjects}
    selection={selection}
    editor={editor}
    setEditor={setEditor}
    setDirty={setDirty}
    tabs={tabs}
    activeTabKey={activeTabKey}
    error={error}
    notice={notice}
    conflict={conflict}
    busy={busy}
    saving={saving}
    dirty={dirty}
    undoAvailable={undoAvailable}
    previewOpen={previewOpen}
    setPreviewOpen={setPreviewOpen}
    terminalOpen={terminalOpen}
    setTerminalOpen={setTerminalOpen}
    settingsOpen={settingsOpen}
    setSettingsOpen={setSettingsOpen}
    projectSettings={projectSettings}
    settingsLoading={settingsLoading}
    settingsSaving={settingsSaving}
    openProjectSettings={openProjectSettings}
    saveProjectSettings={saveProjectSettings}
    clearProjectSettings={clearProjectSettings}
    explorerWidth={explorerWidth}
    terminalHeight={terminalHeight}
    workspaceRef={workspaceRef}
    maximumExplorerWidth={maximumExplorerWidth}
    maximumTerminalHeight={maximumTerminalHeight}
    resizeExplorer={resizeExplorer}
    commitExplorerSize={commitExplorerSize}
    resizeTerminal={resizeTerminal}
    commitTerminalSize={commitTerminalSize}
    startingLocalRun={startingLocalRun}
    stoppingLocalRun={stoppingLocalRun}
    localRunPid={localRunPid}
    terminalEntries={terminalEntries}
    localRunActive={localRunActive}
    canRunLocalProject={canRunLocalProject}
    runProject={runProject}
    stopProject={stopProject}
    status={status}
    firstContentKey={firstContentKey.current}
    explorerDraft={explorerDraft}
    previewModel={previewModel}
    options={options}
    handlerActions={handlerActions}
    switchProject={switchProject}
    createProject={createProject}
    save={save}
    saveAll={saveAll}
    closeTab={closeTab}
    activateTab={activateTab}
    performUndo={performUndo}
    reloadCurrent={reloadCurrent}
    dismissError={() => { setError(""); setConflict(false); }}
    dismissNotice={() => setNotice("")}
    select={select}
    openViewTextEditor={openViewTextEditor}
    addResource={addResource}
    renameFromExplorer={renameFromExplorer}
    removeFromExplorer={removeFromExplorer}
    remove={remove}
    repairHandler={repairHandler}
    openHandler={openHandler}
    findUsages={findUsages}
    createAndOpenHandler={createAndOpenHandler}
  /></StudioRouter>;
}

function matchesPhysicalKey(event: KeyboardEvent, code: string, fallbackKey: string): boolean {
  return event.code === code || (!event.code && event.key.toLowerCase() === fallbackKey);
}

export { emptyCommandsDetail } from "./editor-model";
