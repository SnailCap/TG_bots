import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import type { ProjectProcessEvent } from "../../../electron/contracts";
import botStudioIcon from "../../assets/bot-studio-logo.svg";
import {
  SCHEMA_VERSION,
  emptyFlow,
  emptySchedule,
  emptyView,
  type ActionOptions,
  type CommandSpec,
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
import { CommandEditor, CommandFallbacksEditor } from "../../features/commands-editor/CommandsEditor";
import { FlowEditor } from "../../features/flow-editor/FlowEditor";
import { ResourceDragProvider } from "../../features/resource-dnd";
import { HandlerInspector, NewHandlerEditor } from "../../features/handler-inspector/HandlerInspector";
import { ProjectSettingsDialog } from "../../features/project-settings/ProjectSettingsDialog";
import { ScheduleEditor } from "../../features/schedule-editor/ScheduleEditor";
import { StudioActivityRail, type StudioActivity } from "../../features/studio-activity/StudioActivityRail";
import { StudioTerminal } from "../../features/studio-terminal/StudioTerminal";
import { TemplateEditor } from "../../features/template-editor/TemplateEditor";
import { createTelegramPreviewModel, type PreviewEditor } from "../../features/telegram-preview/preview-model";
import { PreviewToolRail } from "../../features/telegram-preview/PreviewToolRail";
import { TelegramPreview } from "../../features/telegram-preview/TelegramPreview";
import { UsersPage } from "../../features/users/UsersPage";
import { ViewEditor } from "../../features/view-editor/ViewEditor";
import { MainMenu } from "../../shared/ui/MainMenu";
import { ResourceEditorHeader } from "../../shared/ui/ResourceEditorHeader";
import { ResizeHandle } from "../../shared/ui/ResizeHandle";
import { ResourceIcon } from "../../shared/ui/ResourceIcon";
import { ProjectSwitcher } from "../../shared/ui/ProjectSwitcher";
import { Toast } from "../../shared/ui/Toast";
import { type ProjectSettings, type StudioApiClient, StudioApiError } from "../../studio/api";
import { approveProjectRoot, localProjectStatus, onLocalProjectOutput, openCode, runLocalProject, stopLocalProject } from "../../studio/desktop";
import { ProjectExplorer, type CreatableResource, type ExplorerDraft } from "../../widgets/project-explorer/ProjectExplorer";

type EditorState =
  | { kind: "view"; detail: ViewDetail; isNew: boolean }
  | { kind: "template"; detail: TemplateDetail; isNew: boolean }
  | { kind: "flow"; detail: FlowDetail; isNew: boolean }
  | { kind: "command"; detail: CommandsDetail; commandIndex: number }
  | { kind: "commands"; detail: CommandsDetail }
  | { kind: "schedule"; detail: ScheduleDetail; isNew: boolean }
  | { kind: "handler"; detail: HandlerDetail }
  | { kind: "new-handler" }
  | null;

type EditorTab = { key: string; editor: Exclude<EditorState, null>; dirty: boolean };

type DeletedResource =
  | { kind: "view"; detail: ViewDetail }
  | { kind: "template"; detail: TemplateDetail }
  | { kind: "flow"; detail: FlowDetail }
  | { kind: "command"; command: CommandSpec; index: number }
  | { kind: "schedule"; detail: ScheduleDetail }
  | { kind: "handler"; detail: HandlerDetail };

type UndoEntry = { undo: () => Promise<void> };
const MAX_TERMINAL_ENTRIES = 2000;

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
  const [startingLocalRun, setStartingLocalRun] = useState(false);
  const [stoppingLocalRun, setStoppingLocalRun] = useState(false);
  const [localRunPid, setLocalRunPid] = useState<number | null>(null);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [terminalEntries, setTerminalEntries] = useState<ProjectProcessEvent[]>([]);
  const [dirty, setDirty] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [activeActivity, setActiveActivity] = useState<StudioActivity>("resources");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [projectSettings, setProjectSettings] = useState<ProjectSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [explorerWidth, setExplorerWidth] = useState(262);
  const [terminalHeight, setTerminalHeight] = useState(280);
  const explorerWidthRef = useRef(explorerWidth);
  const terminalHeightRef = useRef(terminalHeight);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const tabsRef = useRef(tabs);
  const activeTabKeyRef = useRef(activeTabKey);
  const undoStackRef = useRef<UndoEntry[]>([]);
  const saveShortcutRef = useRef<() => void>(() => undefined);
  const [undoAvailable, setUndoAvailable] = useState(false);
  tabsRef.current = tabs;
  activeTabKeyRef.current = activeTabKey;
  const nextNewTabId = useRef(1);
  const firstContentKey = useRef<string | null>(null);
  const localRunCommandRevision = useRef(0);
  if (!firstContentKey.current && activeTabKey) firstContentKey.current = activeTabKey;

  const maximumExplorerWidth = useCallback((workspaceWidth: number) => {
    const previewWidth = previewOpen ? Math.min(340, Math.max(220, workspaceWidth * 0.27)) : 0;
    return Math.max(180, workspaceWidth - previewWidth - 321);
  }, [previewOpen]);

  const maximumTerminalHeight = useCallback((workspaceHeight: number) => Math.max(120, workspaceHeight - 165), []);

  useEffect(() => {
    const clampDimensions = () => {
      const workspaceElement = workspaceRef.current;
      if (!workspaceElement) return;
      const width = Math.min(maximumExplorerWidth(workspaceElement.clientWidth), explorerWidthRef.current);
      const height = Math.min(maximumTerminalHeight(workspaceElement.clientHeight), terminalHeightRef.current);
      if (width !== explorerWidthRef.current) {
        explorerWidthRef.current = width;
        setExplorerWidth(width);
      }
      if (height !== terminalHeightRef.current) {
        terminalHeightRef.current = height;
        setTerminalHeight(height);
      }
    };
    clampDimensions();
    window.addEventListener("resize", clampDimensions);
    return () => window.removeEventListener("resize", clampDimensions);
  }, [maximumExplorerWidth, maximumTerminalHeight]);

  const report = useCallback((caught: unknown) => {
    const message = caught instanceof Error ? caught.message : "Unexpected error";
    setError(message);
    setConflict(caught instanceof StudioApiError && caught.code === "revision_conflict");
  }, []);

  useEffect(() => onLocalProjectOutput((event) => {
    if (!sameProjectRoot(event.projectRoot, workspace.project_root)) return;
    setTerminalEntries((current) => [...current.slice(-(MAX_TERMINAL_ENTRIES - 1)), event]);
    if (event.running === true) {
      setLocalRunPid(event.pid ?? null);
      setStoppingLocalRun(false);
    } else if (event.running === false) {
      setLocalRunPid(null);
      setStoppingLocalRun(false);
    }
  }), [workspace.project_root]);

  useEffect(() => {
    let cancelled = false;
    if (!window.studioDesktop?.projectRunStatus) return undefined;
    const revision = localRunCommandRevision.current;
    void approveProjectRoot(workspace.project_root)
      .then(() => localProjectStatus(workspace.project_root))
      .then((runStatus) => {
        if (!cancelled && revision === localRunCommandRevision.current) {
          setLocalRunPid(runStatus.running ? runStatus.pid : null);
        }
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [workspace.project_root]);

  const refreshWorkspace = useCallback(async () => {
    const next = await api.describe(workspace.project_id);
    setWorkspace(next);
    return next;
  }, [api, workspace.project_id]);

  const loadProjectSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError("");
    try {
      setProjectSettings(await api.getProjectSettings(workspace.project_id));
    } catch (caught) {
      setSettingsError(caught instanceof Error ? caught.message : "Could not load project settings.");
    } finally {
      setSettingsLoading(false);
    }
  }, [api, workspace.project_id]);

  const openProjectSettings = useCallback(() => {
    setSettingsOpen(true);
    void loadProjectSettings();
  }, [loadProjectSettings]);

  const saveProjectSettings = useCallback(async (telegramBotToken: string) => {
    if (!projectSettings) throw new Error(settingsError || "Project settings are still loading.");
    setSettingsSaving(true);
    try {
      const next = await api.saveProjectSettings(workspace.project_id, {
        telegram_bot_token: telegramBotToken,
        revision: projectSettings.revision,
      });
      setProjectSettings(next);
      setSettingsError("");
    } finally {
      setSettingsSaving(false);
    }
  }, [api, projectSettings, settingsError, workspace.project_id]);

  const clearProjectSettings = useCallback(async () => {
    if (!projectSettings) throw new Error("Project settings are still loading.");
    setSettingsSaving(true);
    try {
      const next = await api.saveProjectSettings(workspace.project_id, {
        clear_telegram_bot_token: true,
        revision: projectSettings.revision,
      });
      setProjectSettings(next);
      setSettingsError("");
    } finally {
      setSettingsSaving(false);
    }
  }, [api, projectSettings, workspace.project_id]);

  const setExplorerSize = useCallback((width: number) => {
    explorerWidthRef.current = width;
    workspaceRef.current?.style.setProperty("--explorer-width", `${width}px`);
  }, []);

  const commitExplorerSize = useCallback(() => setExplorerWidth(explorerWidthRef.current), []);

  const setTerminalSize = useCallback((height: number) => {
    terminalHeightRef.current = height;
    workspaceRef.current?.style.setProperty("--terminal-height", `${height}px`);
  }, []);

  const commitTerminalSize = useCallback(() => setTerminalHeight(terminalHeightRef.current), []);

  const loadSelection = useCallback(async (next: Selection, tabKey?: string) => {
    let nextEditor: Exclude<EditorState, null>;
    switch (next.kind) {
      case "view": nextEditor = { kind: "view", detail: await api.getView(workspace.project_id, next.id), isNew: false }; break;
      case "template": nextEditor = { kind: "template", detail: await api.getTemplate(workspace.project_id, next.path), isNew: false }; break;
      case "flow": nextEditor = { kind: "flow", detail: await api.getFlow(workspace.project_id, next.id), isNew: false }; break;
      case "command": {
        const detail = await api.getCommands(workspace.project_id);
        nextEditor = { kind: "command", detail, commandIndex: findCommandIndex(detail, next.name) };
        break;
      }
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

  const pushUndo = useCallback((entry: UndoEntry) => {
    undoStackRef.current.push(entry);
    setUndoAvailable(true);
  }, []);

  const performUndo = useCallback(async () => {
    if (busy) return;
    const entry = undoStackRef.current.pop();
    setUndoAvailable(undoStackRef.current.length > 0);
    if (!entry) return;
    setBusy(true);
    try {
      await entry.undo();
      setError("");
      setConflict(false);
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [busy, report]);

  const restoreDeletedResource = useCallback(async (snapshot: DeletedResource) => {
    if (snapshot.kind === "view") await api.createView(workspace.project_id, snapshot.detail.id, snapshot.detail.payload);
    else if (snapshot.kind === "flow") await api.createFlow(workspace.project_id, snapshot.detail.id, snapshot.detail.payload);
    else if (snapshot.kind === "schedule") await api.createSchedule(workspace.project_id, snapshot.detail.id, snapshot.detail.payload);
    else if (snapshot.kind === "template") await api.saveTemplate(workspace.project_id, snapshot.detail.path, snapshot.detail.content);
    else if (snapshot.kind === "command") {
      const detail = await api.getCommands(workspace.project_id);
      const commands = [...detail.payload.commands];
      commands.splice(Math.min(snapshot.index, commands.length), 0, snapshot.command);
      await api.saveCommands(workspace.project_id, { ...detail.payload, commands }, detail.revision);
    }
    else {
      const fresh = await api.describe(workspace.project_id);
      await api.createHandler(workspace.project_id, {
        handler_id: snapshot.detail.id,
        kind: snapshot.detail.kind,
        registry_revision: fresh.handlers_revision,
        outcomes: snapshot.detail.outcomes,
        description: snapshot.detail.description,
      });
    }
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
    if (activeTabKeyRef.current === selectionTabKey(target)) {
      const fallback = remaining[remaining.length - 1] ?? null;
      setActiveTabKey(fallback?.key ?? null);
      setEditor(fallback?.editor ?? null);
      setSelection(null);
      setDirty(fallback?.dirty ?? false);
    }
  }, []);

  const deletePersistedResource = useCallback(async (target: Selection) => {
    if (target.kind === "view") { const detail = await api.getView(workspace.project_id, target.id); await api.deleteView(workspace.project_id, target.id, detail.revision); }
    else if (target.kind === "template") { const detail = await api.getTemplate(workspace.project_id, target.path); await api.deleteTemplate(workspace.project_id, target.path, detail.revision); }
    else if (target.kind === "flow") { const detail = await api.getFlow(workspace.project_id, target.id); await api.deleteFlow(workspace.project_id, target.id, detail.revision); }
    else if (target.kind === "schedule") { const detail = await api.getSchedule(workspace.project_id, target.id); await api.deleteSchedule(workspace.project_id, target.id, detail.revision); }
    else if (target.kind === "handler") { const detail = await api.getHandler(workspace.project_id, target.id); await api.deleteHandler(workspace.project_id, target.id, detail.revision); }
    else if (target.kind === "command") {
      const detail = await api.getCommands(workspace.project_id);
      await api.saveCommands(workspace.project_id, {
        ...detail.payload,
        commands: detail.payload.commands.filter((command) => command.name !== target.name),
      }, detail.revision);
    }
  }, [api, workspace.project_id]);

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
  const previewModel = useMemo(() => createTelegramPreviewModel(workspace, previewEditor(editor)), [editor, workspace]);

  const addResource = async (kind: CreatableResource, templatePath = "") => {
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
      let nextEditor: Exclude<EditorState, null>;
      let nextSelection: Selection;
      if (kind === "view") {
        const id = nextAvailableResourceName("new-view", workspace.views.map((item) => item.id));
        const saved = await api.createView(workspace.project_id, id, emptyView(id));
        nextEditor = { kind, isNew: false, detail: saved };
        nextSelection = { kind, id: saved.id };
      } else if (kind === "template") {
        const path = templatePath || nextAvailableTemplatePath(workspace.templates.map((item) => item.path));
        const saved = await api.saveTemplate(workspace.project_id, path, "");
        nextEditor = { kind, isNew: false, detail: saved };
        nextSelection = { kind, path: saved.path };
      } else if (kind === "flow") {
        const id = nextAvailableResourceName("new-flow", workspace.flows.map((item) => item.id));
        const saved = await api.createFlow(workspace.project_id, id, emptyFlow(id));
        nextEditor = { kind, isNew: false, detail: saved };
        nextSelection = { kind, id: saved.id };
      } else if (kind === "command") {
        const detail = await api.getCommands(workspace.project_id);
        const name = nextAvailableCommandName(detail.payload.commands.map((command) => command.name));
        const saved = await api.saveCommands(workspace.project_id, {
          ...detail.payload,
          commands: [...detail.payload.commands, { name, action: { type: "noop" } }],
        }, detail.revision);
        nextEditor = { kind, detail: saved, commandIndex: findCommandIndex(saved, name) };
        nextSelection = { kind, name };
      } else {
        const id = nextAvailableResourceName("new-schedule", workspace.schedules.map((item) => item.id));
        const saved = await api.createSchedule(workspace.project_id, id, emptySchedule(id));
        nextEditor = { kind, isNew: false, detail: saved };
        nextSelection = { kind, id: saved.id };
      }
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
      let nextEditor: Exclude<EditorState, null> = editor;
      let nextSelection: Selection | null = selection;
      if (editor.kind === "view") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createView(workspace.project_id, id, editor.detail.payload)
          : editor.detail.id !== id
            ? await api.renameView(workspace.project_id, editor.detail.id, id, editor.detail.revision)
            : await api.saveView(workspace.project_id, id, editor.detail.payload, editor.detail.revision);
        nextEditor = { kind: "view", detail: saved, isNew: false };
        nextSelection = { kind: "view", id: saved.id };
      } else if (editor.kind === "template") {
        const saved = await api.saveTemplate(workspace.project_id, editor.detail.path, editor.detail.content, editor.isNew ? undefined : editor.detail.revision);
        nextEditor = { kind: "template", detail: saved, isNew: false };
        nextSelection = { kind: "template", path: saved.path };
      } else if (editor.kind === "flow") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createFlow(workspace.project_id, id, editor.detail.payload)
          : await api.saveFlow(workspace.project_id, id, editor.detail.payload, editor.detail.revision);
        nextEditor = { kind: "flow", detail: saved, isNew: false };
        nextSelection = { kind: "flow", id: saved.id };
      } else if (editor.kind === "command") {
        const command = commandAt(editor);
        const saved = await api.saveCommands(workspace.project_id, editor.detail.payload, editor.detail.revision);
        nextEditor = {
          kind: "command",
          detail: saved,
          commandIndex: findCommandIndex(saved, command.name),
        };
        nextSelection = { kind: "command", name: command.name };
      } else if (editor.kind === "commands") {
        nextEditor = { kind: "commands", detail: await api.saveCommands(workspace.project_id, editor.detail.payload, editor.detail.revision) };
      } else if (editor.kind === "schedule") {
        const id = editor.detail.payload.id;
        const saved = editor.isNew
          ? await api.createSchedule(workspace.project_id, id, editor.detail.payload)
          : await api.saveSchedule(workspace.project_id, id, editor.detail.payload, editor.detail.revision);
        nextEditor = { kind: "schedule", detail: saved, isNew: false };
        nextSelection = { kind: "schedule", id: saved.id };
      }

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

  saveShortcutRef.current = () => {
    if (editor && !busy && canSave(editor)) void save();
  };

  const remove = async () => {
    if (!editor) return;
    const snapshot = deletedResourceSnapshot(editor);
    if (!snapshot) return;
    setBusy(true);
    try {
      if (editor.kind === "view" && !editor.isNew) await api.deleteView(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "template" && !editor.isNew) await api.deleteTemplate(workspace.project_id, editor.detail.path, editor.detail.revision);
      else if (editor.kind === "flow" && !editor.isNew) await api.deleteFlow(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "command") {
        const command = commandAt(editor);
        await api.saveCommands(workspace.project_id, {
          ...editor.detail.payload,
          commands: editor.detail.payload.commands.filter((_, index) => index !== editor.commandIndex),
        }, editor.detail.revision);
        setSelection({ kind: "command", name: command.name });
      }
      else if (editor.kind === "schedule" && !editor.isNew) await api.deleteSchedule(workspace.project_id, editor.detail.id, editor.detail.revision);
      else if (editor.kind === "handler") await api.deleteHandler(workspace.project_id, editor.detail.id, editor.detail.revision);
      else return;
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
      let snapshot: DeletedResource;
      if (next.kind === "view") { const detail = await api.getView(workspace.project_id, next.id); snapshot = { kind: "view", detail }; await api.deleteView(workspace.project_id, next.id, detail.revision); }
      else if (next.kind === "template") { const detail = await api.getTemplate(workspace.project_id, next.path); snapshot = { kind: "template", detail }; await api.deleteTemplate(workspace.project_id, next.path, detail.revision); }
      else if (next.kind === "flow") { const detail = await api.getFlow(workspace.project_id, next.id); snapshot = { kind: "flow", detail }; await api.deleteFlow(workspace.project_id, next.id, detail.revision); }
      else if (next.kind === "command") {
        const detail = await api.getCommands(workspace.project_id);
        const index = findCommandIndex(detail, next.name);
        snapshot = { kind: "command", command: detail.payload.commands[index], index };
        await api.saveCommands(workspace.project_id, {
          ...detail.payload,
          commands: detail.payload.commands.filter((_, current) => current !== index),
        }, detail.revision);
      }
      else if (next.kind === "schedule") { const detail = await api.getSchedule(workspace.project_id, next.id); snapshot = { kind: "schedule", detail }; await api.deleteSchedule(workspace.project_id, next.id, detail.revision); }
      else if (next.kind === "handler") { const detail = await api.getHandler(workspace.project_id, next.id); snapshot = { kind: "handler", detail }; await api.deleteHandler(workspace.project_id, next.id, detail.revision); }
      else return;
      if (activeTabKey && selectionKeyEquals(selection, next)) closeTab(activeTabKey, true);
      setTabs((current) => current.filter((tab) => !selectionKeyEquals(selectionForEditor(tab.editor), next)));
      pushDeleteUndo(snapshot);
      await refreshWorkspace();
    })().catch(report).finally(() => setBusy(false));
  };

  const renameResource = useCallback(async (next: Exclude<Selection, { kind: "commands" }>, name: string): Promise<{ selection: Exclude<Selection, { kind: "commands" }>; editor: Exclude<EditorState, null> }> => {
    if (next.kind === "view") {
      const detail = await api.getView(workspace.project_id, next.id);
      const renamed = await api.renameView(workspace.project_id, next.id, name, detail.revision);
      return { selection: { kind: "view", id: renamed.id }, editor: { kind: "view", detail: renamed, isNew: false } };
    }
    if (next.kind === "template") {
      const detail = await api.getTemplate(workspace.project_id, next.path);
      const renamed = await api.renameTemplate(workspace.project_id, next.path, name, detail.revision);
      return { selection: { kind: "template", path: renamed.path }, editor: { kind: "template", detail: renamed, isNew: false } };
    }
    if (next.kind === "flow") {
      const detail = await api.getFlow(workspace.project_id, next.id);
      const renamed = await api.renameFlow(workspace.project_id, next.id, name, detail.revision);
      return { selection: { kind: "flow", id: renamed.id }, editor: { kind: "flow", detail: renamed, isNew: false } };
    }
    if (next.kind === "schedule") {
      const detail = await api.getSchedule(workspace.project_id, next.id);
      const renamed = await api.renameSchedule(workspace.project_id, next.id, name, detail.revision);
      return { selection: { kind: "schedule", id: renamed.id }, editor: { kind: "schedule", detail: renamed, isNew: false } };
    }
    if (next.kind === "command") {
      const detail = await api.getCommands(workspace.project_id);
      const index = findCommandIndex(detail, next.name);
      const commandName = normalizeCommandName(name);
      const renamed = await api.saveCommands(workspace.project_id, {
        ...detail.payload,
        commands: detail.payload.commands.map((command, current) => current === index
          ? { ...command, name: commandName }
          : command),
      }, detail.revision);
      return {
        selection: { kind: "command", name: commandName },
        editor: { kind: "command", detail: renamed, commandIndex: findCommandIndex(renamed, commandName) },
      };
    }
    const detail = await api.getHandler(workspace.project_id, next.id);
    const renamed = await api.renameHandler(workspace.project_id, next.id, name, detail.revision);
    return { selection: { kind: "handler", id: renamed.id }, editor: { kind: "handler", detail: renamed } };
  }, [api, workspace.project_id]);

  const applyRenameToTabs = useCallback((from: Selection, to: Selection, toEditor: Exclude<EditorState, null>) => {
    const previousTabKey = selectionTabKey(from);
    const nextTabKey = selectionTabKey(to);
    setTabs((current) => current.map((tab) => selectionKeyEquals(selectionForEditor(tab.editor), from)
      ? { ...tab, key: nextTabKey, editor: toEditor, dirty: false }
      : tab));
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
      const previousName = next.kind === "template" ? next.path : next.kind === "command" ? next.name : next.id;
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
  const runProject = useCallback(async () => {
    if (dirty || busy || saving || startingLocalRun) return;
    localRunCommandRevision.current += 1;
    setTerminalOpen(true);
    setStartingLocalRun(true);
    try {
      await approveProjectRoot(workspace.project_root);
      const result = await runLocalProject({ projectRoot: workspace.project_root, packageName: workspace.package });
      setLocalRunPid(result.pid || null);
      setNotice("");
      setError("");
    } catch (caught) {
      report(caught);
    } finally {
      setStartingLocalRun(false);
    }
  }, [busy, dirty, report, saving, startingLocalRun, workspace.package, workspace.project_root]);
  const stopProject = useCallback(async () => {
    if (!localRunPid || stoppingLocalRun) return;
    localRunCommandRevision.current += 1;
    setTerminalOpen(true);
    setStoppingLocalRun(true);
    try {
      await stopLocalProject(workspace.project_root);
    } catch (caught) {
      setStoppingLocalRun(false);
      report(caught);
    }
  }, [localRunPid, report, stoppingLocalRun, workspace.project_root]);
  const localRunActive = localRunPid !== null;
  const canRunLocalProject = Boolean(window.studioDesktop?.runProject && window.studioDesktop?.stopProject);
  const status = error
    ? { label: "Error", tone: "error" }
    : saving
      ? { label: "Saving…", tone: "working" }
      : busy
        ? { label: "Working…", tone: "working" }
        : dirty
          ? { label: "Unsaved changes", tone: "dirty" }
          : editor
            ? { label: "Saved", tone: "saved" }
            : { label: "Ready", tone: "ready" };

  return (
    <ResourceDragProvider>
    <main className="studio">
      <header className="topbar">
        <div className="topbar__leading">
          <img className="topbar__brand" src={botStudioIcon} alt="Bot Studio" />
          <MainMenu
            canSave={Boolean(editor && !busy && canSave(editor))}
            canCloseTab={Boolean(activeTabKey)}
            canUndo={undoAvailable && !busy}
            onOpenProject={() => switchProject("")}
            onNewProject={createProject}
            onSave={() => void save()}
            onCloseTab={() => { if (activeTabKey) closeTab(activeTabKey); }}
            onUndo={() => void performUndo()}
          />
          <ProjectSwitcher workspace={workspace} recentProjects={recentProjects} onOpenProject={switchProject} onNewProject={createProject} />
        </div>
        <div className="topbar__actions">
          <button
            type="button"
            className={localRunActive ? "topbar__run topbar__run--stop" : "topbar__run"}
            aria-label={localRunActive ? "Stop local bot" : "Run local bot"}
            aria-busy={startingLocalRun || stoppingLocalRun || undefined}
            disabled={!canRunLocalProject || startingLocalRun || stoppingLocalRun || (!localRunActive && (dirty || busy || saving))}
            title={!canRunLocalProject ? "Local run is available in the desktop Studio application" : localRunActive ? `Stop local bot${localRunPid ? ` (PID ${localRunPid})` : ""}` : dirty ? "Save changes before running" : "Run local bot"}
            onClick={() => void (localRunActive ? stopProject() : runProject())}
          >
            {localRunActive ? <StopIcon /> : <RunIcon />}
          </button>
        </div>
      </header>
      {error && <Toast message={error} tone="error" action={conflict && <button type="button" className="button--secondary" onClick={reloadCurrent}>Reload from disk</button>} onDismiss={() => { setError(""); setConflict(false); }} />}
      {notice && <Toast message={notice} tone="notice" onDismiss={() => setNotice("")} />}
      <div ref={workspaceRef} className={`workspace${activeActivity === "users" ? " workspace--users" : ""}${activeActivity === "resources" && previewOpen ? " workspace--preview-open" : ""}${terminalOpen ? " workspace--terminal-open" : ""}`} style={{ "--explorer-width": `${explorerWidth}px`, "--terminal-height": `${terminalHeight}px` } as CSSProperties}>
        <StudioActivityRail active={activeActivity} onSelect={setActiveActivity} terminalOpen={terminalOpen} onToggleTerminal={() => setTerminalOpen((open) => !open)} settingsOpen={settingsOpen} onOpenSettings={openProjectSettings} />
        {activeActivity === "resources" && <><ProjectExplorer workspace={workspace} selection={selection} draft={explorerDraft} onSelect={select} onAdd={addResource} onRename={renameFromExplorer} onDelete={removeFromExplorer} />
        <ResizeHandle className="workspace__resizer" axis="horizontal" label="Resize resource list" value={explorerWidth} min={180} max={() => maximumExplorerWidth(workspaceRef.current?.clientWidth ?? 0)} onResize={setExplorerSize} onResizeEnd={commitExplorerSize} />
        <section className="workspace__main" aria-busy={busy}>
          {tabs.length > 0 && <nav className="editor-tabs" aria-label="Open resources" role="tablist">
            {tabs.map((tab) => <div key={tab.key} className={tab.key === activeTabKey ? "editor-tab editor-tab--active" : "editor-tab"} role="presentation">
              <button type="button" className="editor-tab__select" role="tab" aria-selected={tab.key === activeTabKey} onClick={() => activateTab(tab.key)}><span className="editor-tab__dirty-slot">{tab.dirty && <span className={isEditorInvalid(tab.editor) ? "editor-tab__dirty editor-tab__dirty--invalid" : "editor-tab__dirty"} aria-label={isEditorInvalid(tab.editor) ? "Invalid unsaved changes" : "Unsaved changes"} title={isEditorInvalid(tab.editor) ? "This resource needs attention before it can be used" : "Unsaved changes"} />}</span><ResourceIcon selection={editorTabSelection(tab.editor)} title={editorTabLabel(tab.editor)} /><span className="editor-tab__label">{editorTabLabel(tab.editor)}</span></button>
              <button type="button" className="editor-tab__close" aria-label={`Close ${editorTabLabel(tab.editor)}`} title="Close tab" onClick={() => closeTab(tab.key)}><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m5 5 6 6m0-6-6 6" /></svg></button>
            </div>)}
          </nav>}
          <div key={firstContentKey.current ?? "empty"} className={firstContentKey.current ? "workspace__content workspace__content--enter" : "workspace__content"}>
            {editor && <ResourceEditorHeader category={editorCategory(editor)} title={editorHeaderTitle(editor)} saveAction={isSaveableEditor(editor) ? { disabled: busy || !canSave(editor), saving, onSave: () => void save() } : undefined} />}
            {renderEditor(editor, options, handlerActions, setEditor, setDirty, repairHandler, openHandler, findUsages, createAndOpenHandler, select, (suggestedPath) => addResource("template", suggestedPath))}
          {editor?.kind === "handler" && <footer className="editor__actions editor__actions--danger"><span>Deleting a binding can break the resources that use it.</span><button type="button" className="button--danger" disabled={busy} onClick={() => void remove()}>Delete binding</button></footer>}
          {!editor && <div className="workspace__empty"><div><p className="eyebrow">Ready to edit</p><h2>Select a resource</h2><p>Choose an item from the explorer, or add a view, flow, schedule or handler to begin.</p></div></div>}
          </div>
        </section>
        <TelegramPreview open={previewOpen} model={previewModel} onClose={() => setPreviewOpen(false)} />
        <PreviewToolRail open={previewOpen} onToggle={() => setPreviewOpen((open) => !open)} /></>}
        {activeActivity === "users" && <UsersPage api={api} apiBaseUrl={apiBaseUrl} projectId={workspace.project_id} />}
        {terminalOpen && <>
          <ResizeHandle className="workspace__terminal-resizer" axis="vertical" label="Resize terminal" value={terminalHeight} min={120} max={() => maximumTerminalHeight(workspaceRef.current?.clientHeight ?? 0)} inverted onResize={setTerminalSize} onResizeEnd={commitTerminalSize} />
          <StudioTerminal entries={terminalEntries} running={localRunActive} pid={localRunPid} onClose={() => setTerminalOpen(false)} />
        </>}
      </div>
      <footer className="studio-statusbar" aria-label="Studio status">
        <div className="studio-statusbar__group">
          <span className={`studio-statusbar__state studio-statusbar__state--${status.tone}`} role="status" aria-live="polite">
            <span className="studio-statusbar__dot" aria-hidden="true" />
            {status.label}
          </span>
          {activeActivity === "resources" && editor && <span className="studio-statusbar__resource" title={`${editorCategory(editor)}: ${editorHeaderTitle(editor)}`}>
            <ResourceIcon selection={editorTabSelection(editor)} title={editorTabLabel(editor)} />
            <span>{editorCategory(editor)} · {editorHeaderTitle(editor)}</span>
          </span>}
        </div>
        <div className="studio-statusbar__group studio-statusbar__group--end">
          <span className="studio-statusbar__item" title={workspace.project_root}>{workspace.name}</span>
          <span className="studio-statusbar__item">Schema v{workspace.schema_version}</span>
        </div>
      </footer>
      <ProjectSettingsDialog open={settingsOpen} settings={projectSettings} loading={settingsLoading} saving={settingsSaving} onClose={() => setSettingsOpen(false)} onSave={saveProjectSettings} onClear={clearProjectSettings} />
    </main>
    </ResourceDragProvider>
  );
}

function RunIcon() {
  return (
    <svg className="topbar__run-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="m6.25 3.9 9.1 6.1-9.1 6.1V3.9Z" />
    </svg>
  );
}

function StopIcon() {
  return <svg className="topbar__stop-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="5.2" y="5.2" width="9.6" height="9.6" rx=".8" /></svg>;
}

function sameProjectRoot(left: string, right: string): boolean {
  const normalize = (value: string) => value.replaceAll("\\", "/").replace(/\/$/, "").toLowerCase();
  return normalize(left) === normalize(right);
}

function previewEditor(editor: EditorState): PreviewEditor | null {
  if (!editor || editor.kind === "new-handler") return editor;
  if (editor.kind === "view") return { kind: "view", payload: editor.detail.payload };
  if (editor.kind === "flow") return { kind: "flow", payload: editor.detail.payload };
  if (editor.kind === "schedule") return { kind: "schedule", payload: editor.detail.payload };
  if (editor.kind === "template") return { kind: "template", detail: editor.detail };
  if (editor.kind === "commands" || editor.kind === "command") return { kind: "commands", payload: editor.detail.payload };
  return { kind: "handler" };
}

function selectionTabKey(selection: Selection): string {
  if (selection.kind === "template") return `template:${selection.path}`;
  if (selection.kind === "command") return `command:${selection.name}`;
  if (selection.kind === "commands") return "commands";
  return `${selection.kind}:${selection.id}`;
}

function deletedResourceSnapshot(editor: Exclude<EditorState, null>): DeletedResource | null {
  if (editor.kind === "handler") return { kind: "handler", detail: editor.detail };
  if (editor.kind === "command") return { kind: "command", command: commandAt(editor), index: editor.commandIndex };
  if (editor.kind === "commands" || editor.kind === "new-handler" || editor.isNew) return null;
  if (editor.kind === "view") return { kind: "view", detail: editor.detail };
  if (editor.kind === "template") return { kind: "template", detail: editor.detail };
  if (editor.kind === "flow") return { kind: "flow", detail: editor.detail };
  return { kind: "schedule", detail: editor.detail };
}

function selectionForDeletedResource(snapshot: DeletedResource): Selection {
  if (snapshot.kind === "template") return { kind: "template", path: snapshot.detail.path };
  if (snapshot.kind === "command") return { kind: "command", name: snapshot.command.name };
  return { kind: snapshot.kind, id: snapshot.detail.id };
}

function selectionForEditor(editor: Exclude<EditorState, null>): Selection | null {
  if (editor.kind === "new-handler" || ("isNew" in editor && editor.isNew)) return null;
  if (editor.kind === "template") return { kind: "template", path: editor.detail.path };
  if (editor.kind === "command") return { kind: "command", name: commandAt(editor).name };
  if (editor.kind === "commands") return { kind: "commands" };
  return { kind: editor.kind, id: editor.detail.id };
}

function selectionKeyEquals(left: Selection | null, right: Selection): boolean {
  return left !== null && selectionTabKey(left) === selectionTabKey(right);
}

function editorTabLabel(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "new-handler") return "New handler";
  if (editor.kind === "template") return editor.detail.path || "New template";
  if (editor.kind === "command") return `/${commandAt(editor).name}`;
  if (editor.kind === "commands") return "fallbacks";
  return editor.detail.id || `New ${editor.kind}`;
}

function editorTabSelection(editor: Exclude<EditorState, null>): Selection {
  const selection = selectionForEditor(editor);
  if (selection) return selection;
  if (editor.kind === "command") return { kind: "command", name: commandAt(editor).name };
  if (editor.kind === "commands") return { kind: "commands" };
  if (editor.kind === "template") return { kind: "template", path: editor.detail.path };
  if (editor.kind === "new-handler") return { kind: "handler", id: "" };
  return { kind: editor.kind, id: editor.detail.id };
}

function editorCategory(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "new-handler") return "Handler";
  if (editor.kind === "command") return "Command";
  if (editor.kind === "commands") return "Commands";
  return editor.kind[0].toUpperCase() + editor.kind.slice(1);
}

function editorHeaderTitle(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "new-handler") return "New handler";
  if (editor.kind === "command") return `/${commandAt(editor).name}`;
  if (editor.kind === "commands") return "Fallbacks";
  if (editor.kind === "template") return editor.detail.path || "New template";
  return editor.detail.id || `New ${editor.kind}`;
}

function matchesPhysicalKey(event: KeyboardEvent, code: string, fallbackKey: string): boolean {
  return event.code === code || (!event.code && event.key.toLowerCase() === fallbackKey);
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
  createTemplate: (suggestedPath: string) => void,
) {
  if (!editor) return null;
  if (editor.kind === "view") return <ViewEditor value={editor.detail.payload} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onOpenTemplate={(path) => select({ kind: "template", path })} onCreateTemplate={createTemplate} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "template") return <TemplateEditor path={editor.detail.path} content={editor.detail.content} onContentChange={(content) => { setEditor({ ...editor, detail: { ...editor.detail, content } }); setDirty(true); }} />;
  if (editor.kind === "flow") return <FlowEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "command") return <CommandEditor value={commandAt(editor)} revision={editor.detail.revision} options={options} handlerActions={handlerActions} onOpenResource={select} onChange={(command) => { setEditor({ ...editor, detail: { ...editor.detail, payload: { ...editor.detail.payload, commands: editor.detail.payload.commands.map((item, index) => index === editor.commandIndex ? command : item) } } }); setDirty(true); }} />;
  if (editor.kind === "commands") return <CommandFallbacksEditor value={editor.detail.payload} revision={editor.detail.revision} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "schedule") return <ScheduleEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "handler") return <HandlerInspector handler={editor.detail} onRepair={repairHandler} onOpen={openHandler} onFindUsages={findUsages} />;
  return <NewHandlerEditor onCreate={async (id, kind, outcomes, description) => { await createHandler(id, kind, outcomes, description); select({ kind: "handler", id }); }} />;
}

function canSave(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "view") return Boolean(editor.detail.payload.id.trim());
  if (editor.kind === "flow" || editor.kind === "schedule") return Boolean(editor.detail.payload.id.trim());
  if (editor.kind === "command") return Boolean(commandAt(editor).name.trim());
  if (editor.kind === "template") return Boolean(editor.detail.path.trim());
  return editor.kind === "commands";
}

function isNewEditor(editor: Exclude<EditorState, null>): boolean {
  return "isNew" in editor && editor.isNew;
}

function canDelete(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "command") return true;
  return (editor.kind === "view" || editor.kind === "template" || editor.kind === "flow" || editor.kind === "schedule") && !editor.isNew;
}

function isEditorInvalid(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "view") {
    const text = editor.detail.payload.text;
    return !editor.detail.payload.id.trim() || !(text.inline?.trim() || text.template?.trim());
  }
  if (editor.kind === "flow") {
    const { id, initial_state, states } = editor.detail.payload;
    return !id.trim() || !initial_state.trim() || !(initial_state in states) || Object.values(states).some((state) => !state.view.trim());
  }
  if (editor.kind === "schedule") {
    const { id, handler, trigger } = editor.detail.payload;
    return !id.trim() || !handler.trim() || trigger.seconds <= 0;
  }
  if (editor.kind === "template") return !editor.detail.path.trim();
  return false;
}

function nextAvailableResourceName(base: string, existing: string[]): string {
  const names = new Set(existing);
  if (!names.has(base)) return base;
  let suffix = 2;
  while (names.has(`${base}-${suffix}`)) suffix += 1;
  return `${base}-${suffix}`;
}

function nextAvailableTemplatePath(existing: string[]): string {
  const paths = new Set(existing);
  if (!paths.has("new-template.txt")) return "new-template.txt";
  let suffix = 2;
  while (paths.has(`new-template-${suffix}.txt`)) suffix += 1;
  return `new-template-${suffix}.txt`;
}

function nextAvailableCommandName(existing: string[]): string {
  const names = new Set(existing);
  if (!names.has("new_command")) return "new_command";
  let suffix = 2;
  while (names.has(`new_command_${suffix}`)) suffix += 1;
  return `new_command_${suffix}`;
}

function normalizeCommandName(value: string): string {
  return value.trim().replace(/^\//, "").toLowerCase();
}

function findCommandIndex(detail: CommandsDetail, name: string): number {
  const index = detail.payload.commands.findIndex((command) => command.name === name);
  if (index < 0) throw new Error(`Command '/${name}' no longer exists. Refresh the project resources.`);
  return index;
}

function commandAt(editor: Extract<Exclude<EditorState, null>, { kind: "command" }>): CommandSpec {
  const command = editor.detail.payload.commands[editor.commandIndex];
  if (!command) throw new Error("The selected command no longer exists. Refresh the project resources.");
  return command;
}

function isSaveableEditor(editor: Exclude<EditorState, null>): boolean {
  return editor.kind !== "handler" && editor.kind !== "new-handler";
}

function draftForEditor(editor: EditorState): ExplorerDraft | null {
  if (!editor) return null;
  if (editor.kind === "new-handler") return { kind: "handler", label: "New handler" };
  if (editor.kind === "command" || editor.kind === "commands" || editor.kind === "handler") return null;
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
