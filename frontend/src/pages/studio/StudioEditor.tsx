import type { Dispatch, SetStateAction } from "react";

import type {
  ActionOptions,
  HandlerCreateOptions,
  HandlerKind,
  HandlerUsage,
  Selection,
} from "../../domain/project";
import type { HandlerActions } from "../../features/action-editor/ActionEditor";
import { CommandEditor, CommandFallbacksEditor } from "../../features/commands-editor/CommandsEditor";
import { FlowEditor } from "../../features/flow-editor/FlowEditor";
import { HandlerInspector, NewHandlerEditor } from "../../features/handler-inspector/HandlerInspector";
import { ScheduleEditor } from "../../features/schedule-editor/ScheduleEditor";
import { ViewEditor } from "../../features/view-editor/ViewEditor";
import { ViewTextEditorContainer } from "../../features/view-text-editor/ViewTextEditorContainer";
import type { StudioApiClient } from "../../studio/api";
import { commandAt, type EditorState } from "./editor-model";

type StudioEditorProps = {
  editor: EditorState;
  api: StudioApiClient;
  projectId: string;
  projectRoot: string;
  busy: boolean;
  saving: boolean;
  dirty: boolean;
  saveError: boolean;
  options: ActionOptions;
  handlerActions: HandlerActions;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  setDirty: Dispatch<SetStateAction<boolean>>;
  repairHandler(id: string): Promise<void>;
  openHandler(id: string): Promise<void>;
  findUsages(id: string): Promise<HandlerUsage[]>;
  createHandler(
    id: string,
    kind: HandlerKind,
    outcomes?: string[],
    description?: string,
    createOptions?: HandlerCreateOptions,
  ): Promise<void>;
  select(selection: Selection): void;
  openViewTextEditor(viewId: string, displayName: string): void;
  renameDisplayName(selection: Exclude<Selection, { kind: "commands" }>, name: string): Promise<void>;
  save(): Promise<void>;
};

export function StudioEditor({
  editor,
  api,
  projectId,
  projectRoot,
  busy,
  saving,
  dirty,
  saveError,
  options,
  handlerActions,
  setEditor,
  setDirty,
  repairHandler,
  openHandler,
  findUsages,
  createHandler,
  select,
  openViewTextEditor,
  renameDisplayName,
  save,
}: StudioEditorProps) {
  if (!editor) return null;
  if (editor.kind === "view") return <ViewEditor api={api} projectId={projectId} value={editor.detail.payload} textContent={editor.detail.text_content} displayName={editor.detail.name} nameIsDefault={editor.detail.name_is_default} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onRename={(name) => { void renameDisplayName({ kind: "view", id: editor.detail.id }, name); }} onOpenTextEditor={() => openViewTextEditor(editor.detail.id, editor.detail.name ?? editor.detail.id)} onTextContentChange={(text_content) => { setEditor({ ...editor, detail: { ...editor.detail, text_content } }); setDirty(true); }} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "view-text") return <ViewTextEditorContainer
    key={JSON.stringify([projectId, projectRoot, editor.detail.id])}
    api={api}
    projectId={projectId}
    projectRoot={projectRoot}
    viewId={editor.detail.id}
    baseRevision={editor.detail.revision}
    document={editor.document}
    version={editor.version}
    savedVersion={editor.savedVersion}
    dirty={dirty}
    busy={busy}
    saving={saving}
    saveError={saveError}
    onDocumentChange={(document) => {
      setEditor((current) => current?.kind === "view-text" && current.detail.id === editor.detail.id
        ? {
            ...current,
            detail: { ...current.detail, content_document: document },
            document,
            version: current.version + 1,
          }
        : current);
      setDirty(true);
    }}
    onRequestSave={() => { void save(); }}
  />;
  if (editor.kind === "flow") return <FlowEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} displayName={editor.detail.name} nameIsDefault={editor.detail.name_is_default} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onRename={(name) => { void renameDisplayName({ kind: "flow", id: editor.detail.id }, name); }} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "command") return <CommandEditor value={commandAt(editor)} revision={editor.detail.revision} options={options} handlerActions={handlerActions} onOpenResource={select} onChange={(command) => { setEditor({ ...editor, detail: { ...editor.detail, payload: { ...editor.detail.payload, commands: editor.detail.payload.commands.map((item, index) => index === editor.commandIndex ? command : item) } } }); setDirty(true); }} />;
  if (editor.kind === "commands") return <CommandFallbacksEditor value={editor.detail.payload} revision={editor.detail.revision} options={options} handlerActions={handlerActions} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "schedule") return <ScheduleEditor value={editor.detail.payload} sourcePath={editor.detail.source_path} displayName={editor.detail.name} nameIsDefault={editor.detail.name_is_default} revision={editor.detail.revision} isNew={editor.isNew} options={options} handlerActions={handlerActions} onRename={(name) => { void renameDisplayName({ kind: "schedule", id: editor.detail.id }, name); }} onChange={(payload) => { setEditor({ ...editor, detail: { ...editor.detail, payload } }); setDirty(true); }} />;
  if (editor.kind === "handler") return <HandlerInspector handler={editor.detail} onRepair={repairHandler} onOpen={openHandler} onFindUsages={findUsages} />;
  return <NewHandlerEditor onCreate={async (id, kind, outcomes, description) => { await createHandler(id, kind, outcomes, description); select({ kind: "handler", id }); }} />;
}
