import { useCallback, useEffect, useMemo, useState } from "react";

import {
  SCHEMA_VERSION,
  emptyFlow,
  emptySchedule,
  emptyView,
  type ActionOptions,
  type CommandsDetail,
  type Diagnostic,
  type FlowDetail,
  type HandlerDetail,
  type HandlerCreateOptions,
  type HandlerKind,
  type HandlerUsage,
  type Preview,
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
import { type StudioApiClient, StudioApiError } from "../../studio/api";
import { openCode } from "../../studio/desktop";
import { ProjectExplorer, type CreatableResource } from "../../widgets/project-explorer/ProjectExplorer";
import { TelegramPreview } from "../../widgets/telegram-preview/TelegramPreview";
import { ValidationPanel } from "../../widgets/validation-panel/ValidationPanel";
import { BackendStatusCard } from "../../app/BackendStatusCard";

type EditorState =
  | { kind: "view"; detail: ViewDetail; isNew: boolean }
  | { kind: "template"; detail: TemplateDetail; isNew: boolean }
  | { kind: "flow"; detail: FlowDetail; isNew: boolean }
  | { kind: "commands"; detail: CommandsDetail }
  | { kind: "schedule"; detail: ScheduleDetail; isNew: boolean }
  | { kind: "handler"; detail: HandlerDetail }
  | { kind: "new-handler" }
  | null;

export function StudioPage({ api, apiBaseUrl, initialWorkspace }: { api: StudioApiClient; apiBaseUrl: string; initialWorkspace: Workspace }) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [editor, setEditor] = useState<EditorState>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [issues, setIssues] = useState<Diagnostic[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);

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

  const refreshValidation = useCallback(async () => {
    try {
      setIssues(await api.validate(workspace.project_id));
    } catch (caught) {
      report(caught);
    }
  }, [api, report, workspace.project_id]);

  useEffect(() => { void refreshValidation(); }, [refreshValidation]);

  const loadSelection = useCallback(async (next: Selection) => {
    switch (next.kind) {
      case "view": setEditor({ kind: "view", detail: await api.getView(workspace.project_id, next.id), isNew: false }); break;
      case "template": setEditor({ kind: "template", detail: await api.getTemplate(workspace.project_id, next.path), isNew: false }); break;
      case "flow": setEditor({ kind: "flow", detail: await api.getFlow(workspace.project_id, next.id), isNew: false }); break;
      case "commands": setEditor({ kind: "commands", detail: await api.getCommands(workspace.project_id) }); break;
      case "schedule": setEditor({ kind: "schedule", detail: await api.getSchedule(workspace.project_id, next.id), isNew: false }); break;
      case "handler": setEditor({ kind: "handler", detail: await api.getHandler(workspace.project_id, next.id) }); break;
    }
    setDirty(false);
    setNotice("");
    setError("");
    setConflict(false);
  }, [api, workspace.project_id]);

  const select = useCallback((next: Selection) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelection(next);
    setBusy(true);
    void loadSelection(next).catch(report).finally(() => setBusy(false));
  }, [dirty, loadSelection, report]);

  useEffect(() => {
    if (editor?.kind !== "view") {
      setPreview(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api.preview(workspace.project_id, editor.detail.payload)
        .then((next) => { if (!cancelled) setPreview(next); })
        .catch((caught) => { if (!cancelled) report(caught); });
    }, 150);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [api, editor, report, workspace.project_id]);

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
      await refreshValidation();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, dirty, loadSelection, refreshValidation, refreshWorkspace, report, selection, workspace.handlers_revision, workspace.project_id]);

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
      await refreshValidation();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, refreshValidation, refreshWorkspace, report, selection, workspace.handlers_revision, workspace.project_id]);

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

  const addResource = (kind: CreatableResource) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelection(null);
    setDirty(false);
    setNotice("");
    if (kind === "view") setEditor({ kind, isNew: true, detail: { id: "", source_path: "", revision: "", payload: emptyView() } });
    if (kind === "template") setEditor({ kind, isNew: true, detail: { path: "new-template.txt", content: "", revision: "" } });
    if (kind === "flow") setEditor({ kind, isNew: true, detail: { id: "", source_path: "", revision: "", payload: emptyFlow() } });
    if (kind === "schedule") setEditor({ kind, isNew: true, detail: { id: "", source_path: "", revision: "", payload: emptySchedule() } });
    if (kind === "handler") setEditor({ kind: "new-handler" });
  };

  const save = async () => {
    if (!editor) return;
    setBusy(true);
    try {
      let nextSelection: Selection | null = selection;
      if (editor.kind === "view") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createView(workspace.project_id, id, editor.detail.payload)
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
      await refreshValidation();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!editor || !window.confirm("Delete this resource?")) return;
    setBusy(true);
    try {
      if (editor.kind === "view" && !editor.isNew) await api.deleteView(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "flow" && !editor.isNew) await api.deleteFlow(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "schedule" && !editor.isNew) await api.deleteSchedule(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "handler") await api.deleteHandler(workspace.project_id, editor.detail.id, editor.detail.revision);
      else return;
      setEditor(null);
      setSelection(null);
      setDirty(false);
      setNotice("");
      await refreshWorkspace();
      await refreshValidation();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  };

  const reloadCurrent = () => {
    if (!selection) return;
    setNotice("");
    setBusy(true);
    void loadSelection(selection).catch(report).finally(() => setBusy(false));
  };

  return (
    <main className="studio">
      <header className="topbar"><div><strong>Telegram Bot Studio</strong><small>{workspace.resource_root}</small></div><BackendStatusCard apiBaseUrl={apiBaseUrl} /><div><button type="button" className="button--quiet" onClick={() => void refreshWorkspace().catch(report)}>Refresh</button><button type="button" onClick={() => void refreshValidation()}>Validate</button></div></header>
      {error && <p className="global-error"><span>{error}</span>{conflict && <button type="button" onClick={reloadCurrent}>Reload from disk</button>}<button type="button" aria-label="Dismiss error" onClick={() => { setError(""); setConflict(false); }}>×</button></p>}
      {notice && <p className="global-notice"><span>{notice}</span><button type="button" aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button></p>}
      <div className="workspace">
        <ProjectExplorer workspace={workspace} selection={selection} onSelect={select} onAdd={addResource} />
        <section className="workspace__main" aria-busy={busy}>
          {renderEditor(editor, options, handlerActions, setEditor, setDirty, repairHandler, openHandler, findUsages, createAndOpenHandler, select)}
          {editor && !["handler", "new-handler"].includes(editor.kind) && <footer className="editor__actions"><button type="button" disabled={busy || !canSave(editor)} onClick={() => void save()}>{isNewEditor(editor) ? "Create" : "Save"}</button>{canDelete(editor) && <button type="button" className="button--danger" disabled={busy} onClick={() => void remove()}>Delete</button>}{dirty && <span className="dirty-indicator">Unsaved changes</span>}</footer>}
          {editor?.kind === "handler" && <footer className="editor__actions"><button type="button" className="button--danger" disabled={busy} onClick={() => void remove()}>Delete binding</button></footer>}
          {!editor && <div className="workspace__empty"><h2>Select a v3 resource</h2><p>Choose an item from the typed project explorer.</p></div>}
        </section>
        <aside className="right-panel"><TelegramPreview preview={preview} /><ValidationPanel issues={issues} onRefresh={() => void refreshValidation()} onSelect={(issue) => selectDiagnostic(issue, select)} /></aside>
      </div>
    </main>
  );
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
  if (editor.kind === "view") return <ViewEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "template") return <TemplateEditor path={editor.detail.path} content={editor.detail.content} isNew={editor.isNew} onPathChange={(path) => { setEditor({ ...editor, detail: { ...editor.detail, path } }); setDirty(true); }} onContentChange={(content) => { setEditor({ ...editor, detail: { ...editor.detail, content } }); setDirty(true); }} />;
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
  return (editor.kind === "view" || editor.kind === "flow" || editor.kind === "schedule") && !editor.isNew;
}

function selectDiagnostic(issue: Diagnostic, select: (selection: Selection) => void) {
  const source = issue.source_path?.replace(/\\/g, "/");
  if (!source) return;
  const file = source.split("/").at(-1)?.replace(/\.json$/, "");
  if (source.startsWith("views/") && file) select({ kind: "view", id: file });
  else if (source.startsWith("flows/") && file) select({ kind: "flow", id: file });
  else if (source.startsWith("schedules/") && file) select({ kind: "schedule", id: file });
  else if (source === "commands.json") select({ kind: "commands" });
  else if (source === "handlers.json" && issue.entity_id) select({ kind: "handler", id: issue.entity_id });
}

export function emptyCommandsDetail(): CommandsDetail {
  return { source_path: "commands.json", revision: "", payload: { schema_version: SCHEMA_VERSION, commands: [] } };
}
