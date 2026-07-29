import type { Editor } from "@tiptap/core";
import type { Attrs, Mark } from "@tiptap/pm/model";
import { NodeSelection } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";

type SelectedVariable = {
  position: number;
  attrs: Attrs;
  marks: readonly Mark[];
};

export function isInlineMarkActive(editor: Editor, markName: string): boolean {
  const selected = selectedVariable(editor.view);
  if (!selected) return editor.isActive(markName);
  const markType = editor.schema.marks[markName];
  return Boolean(markType && selected.marks.some((mark) => mark.type === markType));
}

export function inlineMarkAttributes(editor: Editor, markName: string): Attrs {
  const selected = selectedVariable(editor.view);
  if (!selected) return editor.getAttributes(markName);
  const markType = editor.schema.marks[markName];
  return selected.marks.find((mark) => mark.type === markType)?.attrs ?? {};
}

export function toggleInlineMark(editor: Editor, markName: string): void {
  if (toggleSelectedVariableMark(editor.view, markName)) return;
  editor.chain().focus().toggleMark(markName).run();
}

export function setInlineMark(editor: Editor, markName: string, attrs?: Attrs): void {
  if (setSelectedVariableMark(editor.view, markName, attrs)) return;
  editor.chain().focus().extendMarkRange(markName).setMark(markName, attrs).run();
}

export function unsetInlineMark(editor: Editor, markName: string): void {
  const selected = selectedVariable(editor.view);
  const markType = editor.schema.marks[markName];
  if (!selected || !markType) {
    editor.chain().focus().extendMarkRange(markName).unsetMark(markName).run();
    return;
  }
  updateSelectedVariableMarks(editor.view, selected, selected.marks.filter((mark) => mark.type !== markType));
}

export function clearInlineFormatting(editor: Editor): void {
  const selected = selectedVariable(editor.view);
  if (!selected) {
    editor.chain().focus().unsetAllMarks().clearNodes().run();
    return;
  }
  updateSelectedVariableMarks(editor.view, selected, []);
}

/** Handles mark shortcuts that ProseMirror cannot apply to a NodeSelection. */
export function toggleSelectedVariableMark(view: EditorView, markName: string): boolean {
  const selected = selectedVariable(view);
  const markType = view.state.schema.marks[markName];
  if (!selected || !markType) return false;
  const active = selected.marks.some((mark) => mark.type === markType);
  const compatible = markName === "code"
    ? []
    : selected.marks.filter((mark) => mark.type.name !== "code");
  const marks = active
    ? selected.marks.filter((mark) => mark.type !== markType)
    : markType.create().addToSet(compatible);
  updateSelectedVariableMarks(view, selected, marks);
  return true;
}

function setSelectedVariableMark(view: EditorView, markName: string, attrs?: Attrs): boolean {
  const selected = selectedVariable(view);
  const markType = view.state.schema.marks[markName];
  if (!selected || !markType) return false;
  const compatible = markName === "code"
    ? []
    : selected.marks.filter((mark) => mark.type.name !== "code" && mark.type !== markType);
  updateSelectedVariableMarks(view, selected, markType.create(attrs).addToSet(compatible));
  return true;
}

function selectedVariable(view: EditorView): SelectedVariable | null {
  const { selection } = view.state;
  return selection instanceof NodeSelection && selection.node.type.name === "variable"
    ? { position: selection.from, attrs: selection.node.attrs, marks: selection.node.marks }
    : null;
}

function updateSelectedVariableMarks(
  view: EditorView,
  selected: SelectedVariable,
  marks: readonly Mark[],
): void {
  const transaction = view.state.tr.setNodeMarkup(selected.position, undefined, selected.attrs, marks);
  transaction.setSelection(NodeSelection.create(transaction.doc, selected.position));
  view.dispatch(transaction);
  view.focus();
}
