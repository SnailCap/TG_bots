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
import { TemplateEditor } from "../../features/template-editor/TemplateEditor";
import { ViewEditor } from "../../features/view-editor/ViewEditor";
import { commandAt, type EditorState } from "./editor-model";

type StudioEditorProps = {
  editor: EditorState;
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
  createTemplate(suggestedPath: string): void;
};

export function StudioEditor({
  editor,
  options,
  handlerActions,
  setEditor,
  setDirty,
  repairHandler,
  openHandler,
  findUsages,
  createHandler,
  select,
  createTemplate,
}: StudioEditorProps) {
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
