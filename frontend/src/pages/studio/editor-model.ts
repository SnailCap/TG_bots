import {
  SCHEMA_VERSION,
  type CommandSpec,
  type CommandsDetail,
  type FlowDetail,
  type HandlerDetail,
  type ScheduleDetail,
  type Selection,
  type ViewDetail,
} from "../../domain/project";
import type { PreviewEditor } from "../../features/telegram-preview/preview-model";
import type { ExplorerDraft } from "../../widgets/project-explorer/ProjectExplorer";

export type EditorState =
  | { kind: "view"; detail: ViewDetail; isNew: boolean }
  | { kind: "view-text"; viewId: string; displayName: string }
  | { kind: "flow"; detail: FlowDetail; isNew: boolean }
  | { kind: "command"; detail: CommandsDetail; commandIndex: number }
  | { kind: "commands"; detail: CommandsDetail }
  | { kind: "schedule"; detail: ScheduleDetail; isNew: boolean }
  | { kind: "handler"; detail: HandlerDetail }
  | { kind: "new-handler" }
  | null;

export type EditorTab = { key: string; editor: Exclude<EditorState, null>; dirty: boolean };

export type OpenViewTextTabResult = {
  tabKey: string;
  editor: Extract<Exclude<EditorState, null>, { kind: "view-text" }>;
  tabs: EditorTab[];
  dirty: boolean;
};

export type StudioStatus = { label: string; tone: string };

export type DeletedResource =
  | { kind: "view"; detail: ViewDetail }
  | { kind: "flow"; detail: FlowDetail }
  | { kind: "command"; command: CommandSpec; index: number }
  | { kind: "schedule"; detail: ScheduleDetail }
  | { kind: "handler"; detail: HandlerDetail };

export function previewEditor(editor: EditorState): PreviewEditor | null {
  if (!editor || editor.kind === "new-handler") return editor;
  if (editor.kind === "view-text") return null;
  if (editor.kind === "view") return { kind: "view", detail: editor.detail };
  if (editor.kind === "flow") return { kind: "flow", payload: editor.detail.payload };
  if (editor.kind === "schedule") return { kind: "schedule", payload: editor.detail.payload };
  if (editor.kind === "commands" || editor.kind === "command") return { kind: "commands", payload: editor.detail.payload };
  return { kind: "handler" };
}

export function selectionTabKey(selection: Selection): string {
  if (selection.kind === "command") return `command:${selection.name}`;
  if (selection.kind === "commands") return "commands";
  return `${selection.kind}:${selection.id}`;
}

export function viewTextTabKey(viewId: string): string {
  return `view-text:${viewId}`;
}

export function openViewTextTab(
  tabs: readonly EditorTab[],
  activeTabKey: string | null,
  activeEditor: EditorState,
  activeDirty: boolean,
  viewId: string,
  displayName: string,
): OpenViewTextTabResult {
  const tabKey = viewTextTabKey(viewId);
  const existing = tabs.find((tab) => tab.key === tabKey);
  if (existing?.editor.kind === "view-text") {
    return { tabKey, editor: existing.editor, tabs: [...tabs], dirty: existing.dirty };
  }

  const nextTabs = activeEditor && activeTabKey
    ? tabs.map((tab) => tab.key === activeTabKey ? { ...tab, editor: activeEditor, dirty: activeDirty } : tab)
    : [...tabs];
  const editor = { kind: "view-text" as const, viewId, displayName };
  return {
    tabKey,
    editor,
    tabs: [...nextTabs, { key: tabKey, editor, dirty: false }],
    dirty: false,
  };
}

export function studioStatus({
  error,
  saving,
  busy,
  dirty,
  hasEditor,
}: {
  error: boolean;
  saving: boolean;
  busy: boolean;
  dirty: boolean;
  hasEditor: boolean;
}): StudioStatus {
  if (error) return { label: "Error", tone: "error" };
  if (saving) return { label: "Saving…", tone: "working" };
  if (busy) return { label: "Working…", tone: "working" };
  if (dirty) return { label: "Unsaved changes", tone: "dirty" };
  return hasEditor ? { label: "Saved", tone: "saved" } : { label: "Ready", tone: "ready" };
}

export function deletedResourceSnapshot(editor: Exclude<EditorState, null>): DeletedResource | null {
  if (editor.kind === "view-text") return null;
  if (editor.kind === "handler") return { kind: "handler", detail: editor.detail };
  if (editor.kind === "command") return { kind: "command", command: commandAt(editor), index: editor.commandIndex };
  if (editor.kind === "commands" || editor.kind === "new-handler" || editor.isNew) return null;
  if (editor.kind === "view") return { kind: "view", detail: editor.detail };
  if (editor.kind === "flow") return { kind: "flow", detail: editor.detail };
  return { kind: "schedule", detail: editor.detail };
}

export function selectionForDeletedResource(snapshot: DeletedResource): Selection {
  if (snapshot.kind === "command") return { kind: "command", name: snapshot.command.name };
  return { kind: snapshot.kind, id: snapshot.detail.id };
}

export function selectionForEditor(editor: Exclude<EditorState, null>): Selection | null {
  if (editor.kind === "view-text") return { kind: "view", id: editor.viewId };
  if (editor.kind === "new-handler" || ("isNew" in editor && editor.isNew)) return null;
  if (editor.kind === "command") return { kind: "command", name: commandAt(editor).name };
  if (editor.kind === "commands") return { kind: "commands" };
  return { kind: editor.kind, id: editor.detail.id };
}

export function selectionKeyEquals(left: Selection | null, right: Selection): boolean {
  return left !== null && selectionTabKey(left) === selectionTabKey(right);
}

export function editorTabLabel(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "view-text") return `${editor.displayName} text`;
  if (editor.kind === "new-handler") return "New handler";
  if (editor.kind === "command") return `/${commandAt(editor).name}`;
  if (editor.kind === "commands") return "fallbacks";
  return editor.detail.id || `New ${editor.kind}`;
}

export function editorTabSelection(editor: Exclude<EditorState, null>): Selection {
  if (editor.kind === "view-text") return { kind: "view", id: editor.viewId };
  const selection = selectionForEditor(editor);
  if (selection) return selection;
  if (editor.kind === "command") return { kind: "command", name: commandAt(editor).name };
  if (editor.kind === "commands") return { kind: "commands" };
  if (editor.kind === "new-handler") return { kind: "handler", id: "" };
  return { kind: editor.kind, id: editor.detail.id };
}

export function editorCategory(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "view-text") return "Text editor";
  if (editor.kind === "new-handler") return "Handler";
  if (editor.kind === "command") return "Command";
  if (editor.kind === "commands") return "Commands";
  return editor.kind[0].toUpperCase() + editor.kind.slice(1);
}

export function editorHeaderTitle(editor: Exclude<EditorState, null>): string {
  if (editor.kind === "view-text") return editor.displayName;
  if (editor.kind === "new-handler") return "New handler";
  if (editor.kind === "command") return `/${commandAt(editor).name}`;
  if (editor.kind === "commands") return "Fallbacks";
  return editor.detail.id || `New ${editor.kind}`;
}

export function canSave(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "view") return Boolean(editor.detail.payload.id.trim());
  if (editor.kind === "flow" || editor.kind === "schedule") return Boolean(editor.detail.payload.id.trim());
  if (editor.kind === "command") return Boolean(commandAt(editor).name.trim());
  return editor.kind === "commands";
}

export function canDelete(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "command") return true;
  return (editor.kind === "view" || editor.kind === "flow" || editor.kind === "schedule") && !editor.isNew;
}

export function isEditorInvalid(editor: Exclude<EditorState, null>): boolean {
  if (editor.kind === "view") {
    return !editor.detail.payload.id.trim() || !editor.detail.text_content.trim();
  }
  if (editor.kind === "flow") {
    const { id, initial_state, states } = editor.detail.payload;
    return !id.trim() || !initial_state.trim() || !(initial_state in states) || Object.values(states).some((state) => !state.view.trim());
  }
  if (editor.kind === "schedule") {
    const { id, handler, trigger } = editor.detail.payload;
    return !id.trim() || !handler.trim() || trigger.seconds <= 0;
  }
  return false;
}

export function findCommandIndex(detail: CommandsDetail, name: string): number {
  const index = detail.payload.commands.findIndex((command) => command.name === name);
  if (index < 0) throw new Error(`Command '/${name}' no longer exists. Refresh the project resources.`);
  return index;
}

export function commandAt(editor: Extract<Exclude<EditorState, null>, { kind: "command" }>): CommandSpec {
  const command = editor.detail.payload.commands[editor.commandIndex];
  if (!command) throw new Error("The selected command no longer exists. Refresh the project resources.");
  return command;
}

export function isSaveableEditor(editor: Exclude<EditorState, null>): boolean {
  return editor.kind !== "handler" && editor.kind !== "new-handler" && editor.kind !== "view-text";
}

export function draftForEditor(editor: EditorState): ExplorerDraft | null {
  if (!editor) return null;
  if (editor.kind === "new-handler") return { kind: "handler", label: "New handler" };
  if (editor.kind === "command" || editor.kind === "commands" || editor.kind === "handler" || editor.kind === "view-text") return null;
  if (!editor.isNew) return null;
  if (editor.kind === "view") return { kind: "view", label: editor.detail.payload.id || "New view" };
  if (editor.kind === "flow") return { kind: "flow", label: editor.detail.payload.id || "New flow" };
  return { kind: "schedule", label: editor.detail.payload.id || "New schedule" };
}

export function emptyCommandsDetail(): CommandsDetail {
  return { source_path: "commands.json", revision: "", payload: { schema_version: SCHEMA_VERSION, commands: [] } };
}
