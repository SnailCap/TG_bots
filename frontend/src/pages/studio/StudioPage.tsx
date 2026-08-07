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
  editorTabKey,
  previewEditor,
  selectionForDeletedResource,
  selectionForEditor,
  selectionKeyEquals,
  selectionTabKey,
  isEditorInvalid,
  reconcileSavedEditor,
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
  viewTextEditorFromDetail,
} from "./studio-resource-api";
import { useLocalProjectRun } from "./useLocalProjectRun";
import { useProjectSettings } from "./useProjectSettings";
import { useOpenViewTextEditor } from "./useOpenViewTextEditor";
import { dirtyViewModeConflicts, resourceHasDirtyTab } from "./studio-tab-guards";
import { useStudioHandlers } from "./useStudioHandlers";
import { useStudioKeyboardShortcuts } from "./useStudioKeyboardShortcuts";
import { useStudioLayout } from "./useStudioLayout";
import { useStudioTabLifecycle } from "./useStudioTabLifecycle";
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
  const editorRef = useRef(editor);
  editorRef.current = editor;
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const saveInFlightRef = useRef<Promise<void> | null>(null);
  const saveRef = useRef<(rethrow?: boolean) => Promise<void>>(async () => undefined);
  const nextNewTabId = useRef(1);
  const firstContentKey = useRef<string | null>(null);
  if (!firstContentKey.current && activeTabKey) firstContentKey.current = activeTabKey;

  const {
    tabsRef,
    activeTabKeyRef,
    discardRichDraftsFor,
    closeTabsFor,
    closeTab,
  } = useStudioTabLifecycle({
    tabs,
    activeTabKey,
    dirty,
    projectRoot: workspace.project_root,
    setTabs,
    setActiveTabKey,
    setEditor,
    setSelection,
    setDirty,
  });

  const report = useCallback((caught: unknown) => {
    const message = caught instanceof Error ? caught.message : "Unexpected error";
    setError(message);
    setConflict(caught instanceof StudioApiError && caught.code === "revision_conflict");
  }, []);
  const clearError = useCallback(() => {
    setError("");
    setConflict(false);
  }, []);
  const saveCurrentBeforeTransition = useCallback(async () => {
    if (!editorRef.current || !dirtyRef.current) return;
    if (saveInFlightRef.current) {
      await saveInFlightRef.current;
      return;
    }
    await saveRef.current(true);
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
    saveBeforeRun: saveCurrentBeforeTransition,
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
    if (tabKey === activeTabKey) return;
    const wasDirty = dirty;
    const continueSelection = () => {
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
      if (!wasDirty && editor && activeTabKey) setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
      setActiveTabKey(tabKey);
      setSelection(next);
      setBusy(true);
      void loadSelection(next, tabKey).catch(report).finally(() => setBusy(false));
    };
    if (!dirty || !editor) {
      continueSelection();
      return;
    }
    void saveCurrentBeforeTransition().then(continueSelection).catch(() => undefined);
  }, [activeTabKey, dirty, editor, loadSelection, report, saveCurrentBeforeTransition, tabs]);

  const openViewTextEditor = useOpenViewTextEditor({
    api, projectId: workspace.project_id, tabs, activeTabKey, editor, dirty,
    setTabs, setActiveTabKey, setEditor, setSelection, setDirty, setBusy, setSaving,
    saveCurrentBeforeTransition,
    clearMessages: () => { setNotice(""); clearError(); }, report,
  });

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
    const wasDirty = dirty;
    try {
      await saveCurrentBeforeTransition();
    } catch {
      return;
    }
    if (!wasDirty && editor && activeTabKey) setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
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

  const activateTab = useCallback((tabKey: string) => {
    const tab = tabs.find((item) => item.key === tabKey);
    if (!tab) return;
    if (tabKey === activeTabKey) return;
    const wasDirty = dirty;
    const continueActivation = () => {
      if (!wasDirty && editor && activeTabKey) setTabs((current) => current.map((item) => item.key === activeTabKey ? { ...item, editor, dirty } : item));
      setActiveTabKey(tabKey);
      setEditor(tab.editor);
      setDirty(tab.dirty);
      setNotice("");
      setError("");
      setConflict(false);
    };
    if (!dirty || !editor) {
      continueActivation();
      return;
    }
    void saveCurrentBeforeTransition().then(continueActivation).catch(() => undefined);
  }, [activeTabKey, dirty, editor, saveCurrentBeforeTransition, tabs]);

  const save = async (rethrow = false) => {
    if (!editor) return;
    const existingSave = saveInFlightRef.current;
    if (existingSave) {
      try {
        await existingSave;
      } catch (caught) {
        if (rethrow) throw caught;
      }
      return;
    }
    const editorToSave = editor;
    const tabKeyToSave = activeTabKey;
    const operation = (async () => {
      setBusy(true);
      setSaving(true);
      try {
        const { editor: savedEditor, selection: nextSelection } = await saveEditor(api, workspace.project_id, editorToSave, selection);
        const nextWorkspace = await api.describe(workspace.project_id);
        setWorkspace(nextWorkspace);
        const nextTabKey = editorTabKey(savedEditor);
        setTabs((current) => current.map((tab) => {
          if (tab.key === tabKeyToSave) {
            const reconciled = reconcileSavedEditor(tab.editor, savedEditor);
            return { ...tab, key: nextTabKey, ...reconciled };
          }
          if (savedEditor.kind === "view-text"
            && tab.editor.kind === "view"
            && tab.editor.detail.id === savedEditor.detail.id
            && !tab.dirty) {
            return { ...tab, editor: { ...tab.editor, detail: savedEditor.detail } };
          }
          return tab;
        }));
        if (tabKeyToSave && activeTabKeyRef.current === tabKeyToSave) {
          const reconciled = reconcileSavedEditor(editorRef.current, savedEditor);
          setActiveTabKey(nextTabKey);
          setEditor(reconciled.editor);
          setSelection(nextSelection);
          setDirty(reconciled.dirty);
        }
        setNotice("");
        setError("");
        setConflict(false);
      } finally {
        setSaving(false);
        setBusy(false);
      }
    })();
    saveInFlightRef.current = operation;
    try {
      await operation;
    } catch (caught) {
      report(caught);
      if (rethrow) throw caught;
    } finally {
      if (saveInFlightRef.current === operation) saveInFlightRef.current = null;
    }
  };
  saveRef.current = save;

  const saveAll = async () => {
    const currentTabs = tabsRef.current.map((tab) => tab.key === activeTabKeyRef.current && editorRef.current
      ? { ...tab, editor: editorRef.current, dirty }
      : tab);
    const pending = currentTabs.filter((tab) => tab.dirty);
    if (!pending.length) return;
    const viewModeConflicts = dirtyViewModeConflicts(pending);
    if (viewModeConflicts.length) {
      throw new Error(`Save either the compact or rich editor first for: ${viewModeConflicts.join(", ")}.`);
    }
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
        if (!result) return tab;
        const reconciled = reconcileSavedEditor(tab.editor, result.editor);
        return { ...tab, ...reconciled };
      }));
      if (activeTabKey) {
        const result = saved.get(activeTabKey);
        if (result) {
          const reconciled = reconcileSavedEditor(editorRef.current, result.editor);
          setEditor(reconciled.editor);
          setSelection(result.selection);
          setDirty(reconciled.dirty);
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

  useStudioKeyboardShortcuts({
    activeTabKey,
    closeTab,
    performUndo,
    save: () => { if (editor && !busy && canSave(editor)) void save(); },
    setTerminalOpen,
  });

  const remove = async () => {
    if (!editor) return;
    const snapshot = deletedResourceSnapshot(editor);
    if (!snapshot) return;
    setBusy(true);
    try {
      await deleteEditor(api, workspace.project_id, editor);
      closeTabsFor(selectionForDeletedResource(snapshot));
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
    if (resourceHasDirtyTab(tabsRef.current, activeTabKeyRef.current, dirty, next)
      && !window.confirm("Delete this resource and discard unsaved changes in its open tabs?")) return;
    setBusy(true);
    void (async () => {
      const snapshot = await deleteSelection(api, workspace.project_id, next);
      if (!snapshot) return;
      closeTabsFor(next);
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
      ? viewTextEditorFromDetail(toEditor.detail)
      : null;
    setTabs((current) => current.map((tab) => {
      if (!selectionKeyEquals(selectionForEditor(tab.editor), from)) return tab;
      if (tab.editor.kind === "view-text" && renamedViewTextEditor) {
        return {
          ...tab,
          key: viewTextTabKey(renamedViewTextEditor.detail.id),
          editor: renamedViewTextEditor,
          dirty: false,
        };
      }
      return { ...tab, key: nextTabKey, editor: toEditor, dirty: false };
    }));
    const activeTab = tabsRef.current.find((tab) => tab.key === activeTabKeyRef.current);
    if (activeTab?.editor.kind === "view-text" && selectionKeyEquals(selectionForEditor(activeTab.editor), from) && renamedViewTextEditor) {
      setActiveTabKey(viewTextTabKey(renamedViewTextEditor.detail.id));
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
    if (resourceHasDirtyTab(tabsRef.current, activeTabKeyRef.current, dirty, next)
      && !window.confirm("Rename this resource and discard unsaved changes in its open tabs?")) return;
    setBusy(true);
    try {
      const { selection: nextSelection, editor: nextEditor } = await renameResource(next, name);
      discardRichDraftsFor(next);
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
  }, [api, applyRenameToTabs, dirty, discardRichDraftsFor, pushUndo, refreshWorkspace, renameResource, report, workspace.project_id]);

  const reloadCurrent = () => {
    if (!selection) return;
    setNotice("");
    setBusy(true);
    void (editor?.kind === "view-text"
      ? api.getView(workspace.project_id, editor.detail.id).then((detail) => {
        const next = viewTextEditorFromDetail(detail);
        setEditor(next);
        setDirty(false);
      })
      : loadSelection(selection)).catch(report).finally(() => setBusy(false));
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

export { emptyCommandsDetail } from "./editor-model";
