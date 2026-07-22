import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

import {
  SCHEMA_VERSION,
  emptyFlow,
  emptySchedule,
  emptyView,
  type ActionOptions,
  type CommandsDetail,
  type FlowDetail,
  type HandlerDetail,
  type HandlerCreateOptions,
  type HandlerKind,
  type HandlerUsage,
  type ScheduleDetail,
  type Selection,
  type TemplateDetail,
  type ViewDetail,
  type Workspace,
} from "../../domain/project";
import { type HandlerActions } from "../../features/action-editor/ActionEditor";
import { CommandsEditor } from "../../features/commands-editor/CommandsEditor";
import { FlowEditor } from "../../features/flow-editor/FlowEditor";
import { HandlerInspector, NewHandlerEditor } from "../../features/handler-inspector/HandlerInspector";
import { ScheduleEditor } from "../../features/schedule-editor/ScheduleEditor";
import { TemplateEditor } from "../../features/template-editor/TemplateEditor";
import { ViewEditor } from "../../features/view-editor/ViewEditor";
import { MainMenu } from "../../shared/ui/MainMenu";
import { ResourceEditorHeader } from "../../shared/ui/ResourceEditorHeader";
import { ProjectSwitcher } from "../../shared/ui/ProjectSwitcher";
import { type StudioApiClient, StudioApiError } from "../../studio/api";
import { openCode } from "../../studio/desktop";
import { ProjectExplorer, ResourceIcon, type CreatableResource, type ExplorerDraft } from "../../widgets/project-explorer/ProjectExplorer";

type EditorState =
  | { kind: "view"; detail: ViewDetail; isNew: boolean }
  | { kind: "template"; detail: TemplateDetail; isNew: boolean }
  | { kind: "flow"; detail: FlowDetail; isNew: boolean }
  | { kind: "commands"; detail: CommandsDetail }
  | { kind: "schedule"; detail: ScheduleDetail; isNew: boolean }
  | { kind: "handler"; detail: HandlerDetail }
  | { kind: "new-handler" }
  | null;

type EditorTab = { key: string; editor: Exclude<EditorState, null>; dirty: boolean };

export function StudioPage({ api, apiBaseUrl: _apiBaseUrl, initialWorkspace, recentProjects = [], onOpenProject = () => undefined, onNewProject = () => undefined }: { api: StudioApiClient; apiBaseUrl: string; initialWorkspace: Workspace; recentProjects?: readonly string[]; onOpenProject?(path: string): void; onNewProject?(): void }) {
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
  const [dirty, setDirty] = useState(false);
  const [explorerWidth, setExplorerWidth] = useState(262);
  const explorerWidthRef = useRef(explorerWidth);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const nextNewTabId = useRef(1);

  const report = useCallback((caught: unknown) => {
    const message = caught instanceof Error ? caught.message : "Unexpected error";
    setError(message);
    setConflict(caught instanceof StudioApiError && caught.code === "revision_conflict");
  }, []);

  const refreshWorkspace = useCallback(async () => {
    const next = await api.describe(workspace.project_id);
    setWorkspace(next);
    return next;
  }, [api, workspace.project_id]);

  const validateProject = useCallback(async () => {
    try {
      const diagnostics = await api.validate(workspace.project_id);
      setNotice(diagnostics.length === 0 ? "Project is valid." : `Validation found ${diagnostics.length} issue(s).`);
    } catch (caught) {
      report(caught);
    }
  }, [api, report, workspace.project_id]);

  const resizeExplorer = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const workspaceElement = workspaceRef.current;
    if (!workspaceElement) return;
    const startX = event.clientX;
    const startWidth = explorerWidthRef.current;
    const maximumWidth = Math.max(320, workspaceElement.clientWidth - 420);
    document.body.classList.add("is-resizing");

    const onMove = (moveEvent: globalThis.PointerEvent) => {
      const width = Math.min(maximumWidth, Math.max(180, startWidth + moveEvent.clientX - startX));
      explorerWidthRef.current = width;
      workspaceElement.style.setProperty("--explorer-width", `${width}px`);
    };
    const onEnd = () => {
      document.body.classList.remove("is-resizing");
      setExplorerWidth(explorerWidthRef.current);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onEnd);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
  }, []);

  const resizeExplorerByKeyboard = useCallback((event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowLeft" ? -1 : 1;
    const maximumWidth = Math.max(320, (workspaceRef.current?.clientWidth ?? 0) - 420);
    const width = Math.min(maximumWidth, Math.max(180, explorerWidthRef.current + direction * 16));
    explorerWidthRef.current = width;
    setExplorerWidth(width);
  }, []);

  const loadSelection = useCallback(async (next: Selection, tabKey?: string) => {
    let nextEditor: Exclude<EditorState, null>;
    switch (next.kind) {
      case "view": nextEditor = { kind: "view", detail: await api.getView(workspace.project_id, next.id), isNew: false }; break;
      case "template": nextEditor = { kind: "template", detail: await api.getTemplate(workspace.project_id, next.path), isNew: false }; break;
      case "flow": nextEditor = { kind: "flow", detail: await api.getFlow(workspace.project_id, next.id), isNew: false }; break;
      case "commands": nextEditor = { kind: "commands", detail: await api.getCommands(workspace.project_id) }; break;
      case "schedule": nextEditor = { kind: "schedule", detail: await api.getSchedule(workspace.project_id, next.id), isNew: false }; break;
      case "handler": nextEditor = { kind: "handler", detail: await api.getHandler(workspace.project_id, next.id) }; break;
    }
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

  useEffect(() => {
    if (!editor || !activeTabKey) return;
    setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
  }, [activeTabKey, dirty, editor]);

  const createAndOpenHandler = useCallback(async (id: string, kind: HandlerKind, outcomes: string[] = [], description?: string, createOptions?: HandlerCreateOptions) => {
    // The backend can attach atomically only to the persisted revision. If this
    // editor has a draft, scaffold the binding/file first and keep the draft in
    // memory; the ordinary Save then persists its already-typed reference.
    const attachPersistedTarget = Boolean(createOptions?.attachment) && !dirty;
    const effectiveOptions = attachPersistedTarget ? createOptions : undefined;
    setBusy(true);
    try {
      const result = await api.createHandler(workspace.project_id, {
        handler_id: id,
        kind,
        registry_revision: workspace.handlers_revision,
        outcomes,
        description,
        ...effectiveOptions,
      });
      await refreshWorkspace();
      if (attachPersistedTarget && selection) await loadSelection(selection);
      const referenceStaysInDraft = dirty && Boolean(createOptions);
      setNotice(referenceStaysInDraft
        ? "Handler created. Its reference is still only in this draft; save the resource to persist it."
        : "");
      setError("");
      setConflict(false);
      try {
        await openCode(result.source);
      } catch (caught) {
        report(caught);
      }
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, dirty, loadSelection, refreshWorkspace, report, selection, workspace.handlers_revision, workspace.project_id]);

  const openHandler = useCallback(async (id: string) => {
    try {
      await openCode(await api.handlerSource(workspace.project_id, id));
    } catch (caught) {
      report(caught);
    }
  }, [api, report, workspace.project_id]);

  const repairHandler = useCallback(async (id: string) => {
    setBusy(true);
    try {
      const result = await api.repairHandlerSource(workspace.project_id, id, workspace.handlers_revision);
      await refreshWorkspace();
      if (selection?.kind === "handler" && selection.id === id) {
        setEditor({ kind: "handler", detail: result.handler });
      }
      setError("");
      setConflict(false);
      try {
        await openCode(result.source);
      } catch (caught) {
        report(caught);
      }
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, refreshWorkspace, report, selection, workspace.handlers_revision, workspace.project_id]);

  const findUsages = useCallback(async (id: string): Promise<HandlerUsage[]> => {
    try {
      return await api.handlerUsages(workspace.project_id, id);
    } catch (caught) {
      report(caught);
      return [];
    }
  }, [api, report, workspace.project_id]);

  const handlerActions: HandlerActions = useMemo(() => ({
    create: (id, kind, createOptions) => createAndOpenHandler(
      id,
      kind,
      Object.keys(createOptions?.routes ?? {}).filter((name) => name !== "success"),
      undefined,
      createOptions,
    ),
    repair: repairHandler,
    open: openHandler,
    usages: findUsages,
  }), [createAndOpenHandler, findUsages, openHandler, repairHandler]);

  const options: ActionOptions = useMemo(() => ({
    views: workspace.views.map((item) => item.id),
    flows: workspace.flows.map((item) => item.id),
    states: editor?.kind === "flow" ? Object.keys(editor.detail.payload.states) : [],
    handlers: workspace.handlers,
    templates: workspace.templates.map((item) => item.path),
  }), [editor, workspace]);

  const explorerDraft = useMemo(() => draftForEditor(editor), [editor]);

  const addResource = (kind: CreatableResource) => {
    let nextEditor: Exclude<EditorState, null>;
    if (kind === "view") nextEditor = { kind, isNew: true, detail: { id: "", source_path: "", revision: "", payload: emptyView() } };
    else if (kind === "template") nextEditor = { kind, isNew: true, detail: { path: "new-template.txt", content: "", revision: "" } };
    else if (kind === "flow") nextEditor = { kind, isNew: true, detail: { id: "", source_path: "", revision: "", payload: emptyFlow() } };
    else if (kind === "schedule") nextEditor = { kind, isNew: true, detail: { id: "", source_path: "", revision: "", payload: emptySchedule() } };
    else nextEditor = { kind: "new-handler" };
    if (editor && activeTabKey) setTabs((current) => current.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab));
    const tabKey = `new:${kind}:${nextNewTabId.current++}`;
    setSelection(null);
    setActiveTabKey(tabKey);
    setTabs((current) => [...current, { key: tabKey, editor: nextEditor, dirty: false }]);
    setEditor(nextEditor);
    setDirty(false);
    setNotice("");
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
      setSelection(null);
      setDirty(false);
      return;
    }
    setActiveTabKey(nextTab.key);
    setEditor(nextTab.editor);
    setSelection(selectionForEditor(nextTab.editor));
    setDirty(nextTab.dirty);
  }, [activeTabKey, dirty, tabs]);

  const activateTab = useCallback((tabKey: string) => {
    const tab = tabs.find((item) => item.key === tabKey);
    if (!tab || tabKey === activeTabKey) return;
    if (editor && activeTabKey) setTabs((current) => current.map((item) => item.key === activeTabKey ? { ...item, editor, dirty } : item));
    setActiveTabKey(tabKey);
    setEditor(tab.editor);
    setSelection(selectionForEditor(tab.editor));
    setDirty(tab.dirty);
    setNotice("");
    setError("");
    setConflict(false);
  }, [activeTabKey, dirty, editor, tabs]);

  useEffect(() => {
    const closeWithShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "w" && activeTabKey) {
        event.preventDefault();
        closeTab(activeTabKey);
      }
    };
    window.addEventListener("keydown", closeWithShortcut);
    return () => window.removeEventListener("keydown", closeWithShortcut);
  }, [activeTabKey, closeTab]);

  const save = async () => {
    if (!editor) return;
    setBusy(true);
    setSaving(true);
    try {
      let nextSelection: Selection | null = selection;
      if (editor.kind === "view") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createView(workspace.project_id, id, editor.detail.payload)
          : editor.detail.id !== id
            ? await api.renameView(workspace.project_id, editor.detail.id, id, editor.detail.revision)
            : await api.saveView(workspace.project_id, id, editor.detail.payload, editor.detail.revision);
        setEditor({ kind: "view", detail: saved, isNew: false });
        nextSelection = { kind: "view", id: saved.id };
      } else if (editor.kind === "template") {
        const saved = await api.saveTemplate(workspace.project_id, editor.detail.path, editor.detail.content, editor.isNew ? undefined : editor.detail.revision);
        setEditor({ kind: "template", detail: saved, isNew: false });
        nextSelection = { kind: "template", path: saved.path };
      } else if (editor.kind === "flow") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createFlow(workspace.project_id, id, editor.detail.payload)
          : await api.saveFlow(workspace.project_id, id, editor.detail.payload, editor.detail.revision);
        setEditor({ kind: "flow", detail: saved, isNew: false });
        nextSelection = { kind: "flow", id: saved.id };
      } else if (editor.kind === "commands") {
        setEditor({ kind: "commands", detail: await api.saveCommands(workspace.project_id, editor.detail.payload, editor.detail.revision) });
      } else if (editor.kind === "schedule") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createSchedule(workspace.project_id, id, editor.detail.payload)
          : await api.saveSchedule(workspace.project_id, id, editor.detail.payload, editor.detail.revision);
        setEditor({ kind: "schedule", detail: saved, isNew: false });
        nextSelection = { kind: "schedule", id: saved.id };
      }
      setSelection(nextSelection);
      setDirty(false);
      setNotice("");
      setError("");
      setConflict(false);
      await refreshWorkspace();
    } catch (caught) {
      report(caught);
    } finally {
      setSaving(false);
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!editor || !window.confirm("Delete this resource?")) return;
    setBusy(true);
    try {
      if (editor.kind === "view" && !editor.isNew) await api.deleteView(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "template" && !editor.isNew) await api.deleteTemplate(workspace.project_id, editor.detail.path, editor.detail.revision);
      else if (editor.kind === "flow" && !editor.isNew) await api.deleteFlow(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "schedule" && !editor.isNew) await api.deleteSchedule(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "handler") await api.deleteHandler(workspace.project_id, editor.detail.id, editor.detail.revision);
      else return;
      if (activeTabKey) closeTab(activeTabKey, true);
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
    if (!window.confirm("Delete this resource?")) return;
    setBusy(true);
    void (async () => {
      if (next.kind === "view") { const detail = await api.getView(workspace.project_id, next.id); await api.deleteView(workspace.project_id, next.id, detail.revision); }
      else if (next.kind === "template") { const detail = await api.getTemplate(workspace.project_id, next.path); await api.deleteTemplate(workspace.project_id, next.path, detail.revision); }
      else if (next.kind === "flow") { const detail = await api.getFlow(workspace.project_id, next.id); await api.deleteFlow(workspace.project_id, next.id, detail.revision); }
      else if (next.kind === "schedule") { const detail = await api.getSchedule(workspace.project_id, next.id); await api.deleteSchedule(workspace.project_id, next.id, detail.revision); }
      else if (next.kind === "handler") { const detail = await api.getHandler(workspace.project_id, next.id); await api.deleteHandler(workspace.project_id, next.id, detail.revision); }
      else return;
      if (activeTabKey && selectionKeyEquals(selection, next)) closeTab(activeTabKey, true);
      setTabs((current) => current.filter((tab) => !selectionKeyEquals(selectionForEditor(tab.editor), next)));
      await refreshWorkspace();
    })().catch(report).finally(() => setBusy(false));
  };

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

  return (
    <main className="studio">
      <header className="topbar">
        <div className="topbar__leading">
          <MainMenu
            canSave={Boolean(editor && !busy && canSave(editor))}
            canCloseTab={Boolean(activeTabKey)}
            onOpenProject={() => switchProject("")}
            onNewProject={createProject}
            onSave={() => void save()}
            onCloseTab={() => { if (activeTabKey) closeTab(activeTabKey); }}
            onValidate={() => void validateProject()}
          />
          <ProjectSwitcher workspace={workspace} recentProjects={recentProjects} onOpenProject={switchProject} onNewProject={createProject} />
        </div>
        <div className="topbar__actions"><button type="button" onClick={() => void validateProject()}>Validate</button></div>
      </header>
      {error && <p className="alert alert--error" role="alert"><span>{error}</span>{conflict && <button type="button" className="button--secondary" onClick={reloadCurrent}>Reload from disk</button>}<button type="button" className="button--icon" aria-label="Dismiss error" onClick={() => { setError(""); setConflict(false); }}>×</button></p>}
      {notice && <p className="alert alert--notice" role="status"><span>{notice}</span><button type="button" className="button--icon" aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button></p>}
      <div ref={workspaceRef} className="workspace" style={{ "--explorer-width": `${explorerWidth}px` } as CSSProperties}>
        <ProjectExplorer workspace={workspace} selection={selection} draft={explorerDraft} onSelect={select} onAdd={addResource} onDelete={removeFromExplorer} />
        <div className="workspace__resizer" role="separator" aria-label="Resize resource list" aria-orientation="vertical" tabIndex={0} onPointerDown={resizeExplorer} onKeyDown={resizeExplorerByKeyboard} />
        <section className="workspace__main" aria-busy={busy}>
          {tabs.length > 0 && <nav className="editor-tabs" aria-label="Open resources" role="tablist">
            {tabs.map((tab) => <div key={tab.key} className={tab.key === activeTabKey ? "editor-tab editor-tab--active" : "editor-tab"} role="presentation">
              <button type="button" className="editor-tab__select" role="tab" aria-selected={tab.key === activeTabKey} onClick={() => activateTab(tab.key)}><ResourceIcon selection={editorTabSelection(tab.editor)} title={editorTabLabel(tab.editor)} /><span className="editor-tab__label">{editorTabLabel(tab.editor)}</span>{tab.dirty && <span className="editor-tab__dirty" aria-label="Unsaved changes" />}</button>
              <button type="button" className="editor-tab__close" aria-label={`Close ${editorTabLabel(tab.editor)}`} title="Close tab" onClick={() => closeTab(tab.key)}><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m5 5 6 6m0-6-6 6" /></svg></button>
            </div>)}
          </nav>}
          <div key={editorMotionKey(editor)} className="workspace__content">
            {editor && <ResourceEditorHeader category={editorCategory(editor)} title={editorHeaderTitle(editor)} saveAction={isSaveableEditor(editor) ? { disabled: busy || !canSave(editor), saving, onSave: () => void save() } : undefined} />}
            {renderEditor(editor, options, handlerActions, setEditor, setDirty, repairHandler, openHandler, findUsages, createAndOpenHandler, select)}
          {editor?.kind === "handler" && <footer className="editor__actions editor__actions--danger"><span>Deleting a binding can break the resources that use it.</span><button type="button" className="button--danger" disabled={busy} onClick={() => void remove()}>Delete binding</button></footer>}
          {!editor && <div className="workspace__empty"><div><p className="eyebrow">Ready to edit</p><h2>Select a resource</h2><p>Choose an item from the explorer, or add a view, flow, schedule or handler to begin.</p></div></div>}
          </div>
        </section>
      </div>
    </main>
  );
}

function editorMotionKey(editor: EditorState): string {
  if (!editor) return "empty";
  if (editor.kind === "new-handler") return "new-handler";
  if ("isNew" in editor && editor.isNew) return `${editor.kind}:new`;
  if (editor.kind === "template") return `${editor.kind}:${editor.detail.path}`;
  if (editor.kind === "commands") return editor.kind;
  return `${editor.kind}:${editor.detail.id}`;
}

function selectionTabKey(selection: Selection): string {
  if (selection.kind === "template") return `template:${selection.path}`;
  if (selection.kind === "commands") return "commands";
  return `${selection.kind}:${selection.id}`;
}

function selectionForEditor(editor: Exclude<EditorState, null>): Selection | null {
  if (editor.kind === "new-handler" || ("isNew" in editor && editor.isNew)) return null;
  if (editor.kind === "template") return { kind: "template", path: editor.detail.path };
  if (editor.kind === "commands") return { kind: "commands" };
  return { kind: editor.kind, id: editor.detail.id };
}

function selectionKeyEquals(left: Selection | null, right: Selection): boolean {
  return left !== null && selectionTabKey(left) === selectionTabKey(right);
}

function editorTabLabel(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "new-handler") return "New handler";
  if (editor.kind === "template") return editor.detail.path || "New template";
  if (editor.kind === "commands") return "commands.json";
  return editor.detail.id || `New ${editor.kind}`;
}

function editorTabSelection(editor: Exclude<EditorState, null>): Selection {
  const selection = selectionForEditor(editor);
  if (selection) return selection;
  if (editor.kind === "commands") return { kind: "commands" };
  if (editor.kind === "template") return { kind: "template", path: editor.detail.path };
  if (editor.kind === "new-handler") return { kind: "handler", id: "" };
  return { kind: editor.kind, id: editor.detail.id };
}

function editorCategory(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "new-handler") return "Handler";
  if (editor.kind === "commands") return "Commands";
  return editor.kind[0].toUpperCase() + editor.kind.slice(1);
}

function editorHeaderTitle(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "new-handler") return "New handler";
  if (editor.kind === "commands") return "Commands";
  if (editor.kind === "template") return editor.detail.path || "New template";
  return editor.detail.id || `New ${editor.kind}`;
}

function renderEditor(
  editor: EditorState,
  options: ActionOptions,
  handlerActions: HandlerActions,
  setEditor: React.Dispatch<React.SetStateAction<EditorState>>,
  setDirty: React.Dispatch<React.SetStateAction<boolean>>,
  repairHandler: (id: string) => Promise<void>,
  openHandler: (id: string) => Promise<void>,
  findUsages: (id: string) => Promise<HandlerUsage[]>,
  createHandler: (id: string, kind: HandlerKind, outcomes?: string[], description?: string, createOptions?: HandlerCreateOptions) => Promise<void>,
  select: (selection: Selection) => void,
) {
  if (!editor) return null;
  if (editor.kind === "view") return <ViewEditor value={editor.detail.payload} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onOpenTemplate={(path) => select({ kind: "template", path })} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "template") return <TemplateEditor path={editor.detail.path} content={editor.detail.content} onContentChange={(content) => { setEditor({ ...editor, detail: { ...editor.detail, content } }); setDirty(true); }} />;
  if (editor.kind === "flow") return <FlowEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "commands") return <CommandsEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} revision={editor.detail.revision} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "schedule") return <ScheduleEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "handler") return <HandlerInspector handler={editor.detail} onRepair={repairHandler} onOpen={openHandler} onFindUsages={findUsages} />;
  return <NewHandlerEditor onCreate={async (id, kind, outcomes, description) => { await createHandler(id, kind, outcomes, description); select({ kind: "handler", id }); }} />;
}

function canSave(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "view") {
    const text = editor.detail.payload.text;
    const hasTextSource = typeof text.inline === "string"
      ? Boolean(text.inline.trim())
      : Boolean(text.template?.trim());
    return Boolean(editor.detail.payload.id.trim()) && hasTextSource;
  }
  if (editor.kind === "flow" || editor.kind === "schedule") return Boolean(editor.detail.payload.id.trim());
  if (editor.kind === "template") return Boolean(editor.detail.path.trim());
  return editor.kind === "commands";
}

function isNewEditor(editor: Exclude<EditorState, null>): boolean {
  return "isNew" in editor && editor.isNew;
}

function canDelete(editor: Exclude<EditorState, null>): boolean {
  return (editor.kind === "view" || editor.kind === "template" || editor.kind === "flow" || editor.kind === "schedule") && !editor.isNew;
}

function isSaveableEditor(editor: Exclude<EditorState, null>): boolean {
  return editor.kind !== "handler" && editor.kind !== "new-handler";
}

function draftForEditor(editor: EditorState): ExplorerDraft | null {
  if (!editor) return null;
  if (editor.kind === "new-handler") return { kind: "handler", label: "New handler" };
  if (editor.kind === "commands" || editor.kind === "handler") return null;
  if (!editor.isNew) return null;
  if (editor.kind === "template") return { kind: "template", label: editor.detail.path || "New template" };
  if (editor.kind === "view") return { kind: "view", label: editor.detail.payload.id || "New view" };
  if (editor.kind === "flow") return { kind: "flow", label: editor.detail.payload.id || "New flow" };
  if (editor.kind === "schedule") return { kind: "schedule", label: editor.detail.payload.id || "New schedule" };
  return null;
}

export function emptyCommandsDetail(): CommandsDetail {
  return { source_path: "commands.json", revision: "", payload: { schema_version: SCHEMA_VERSION, commands: [] } };
}
