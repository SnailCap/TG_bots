import type { Selection } from "../../domain/project";
import {
  selectionForEditor,
  selectionKeyEquals,
  type EditorState,
  type EditorTab,
} from "./editor-model";

export function resourceHasDirtyTab(
  tabs: readonly EditorTab[],
  activeTabKey: string | null,
  activeDirty: boolean,
  target: Selection,
): boolean {
  return tabs.some((tab) => selectionKeyEquals(selectionForEditor(tab.editor), target)
    && (tab.key === activeTabKey ? activeDirty : tab.dirty));
}

export function isDirtyViewModeSwitch(
  current: EditorState,
  currentDirty: boolean,
  next: EditorState,
): boolean {
  if (!currentDirty || !current || !next || current.kind === next.kind) return false;
  const currentId = current.kind === "view" || current.kind === "view-text" ? current.detail.id : null;
  const nextId = next.kind === "view" || next.kind === "view-text" ? next.detail.id : null;
  return currentId !== null && currentId === nextId;
}

export function dirtyViewModeConflicts(tabs: readonly EditorTab[]): string[] {
  const modesByView = new Map<string, Set<"view" | "view-text">>();
  for (const tab of tabs) {
    if (!tab.dirty || (tab.editor.kind !== "view" && tab.editor.kind !== "view-text")) continue;
    const modes = modesByView.get(tab.editor.detail.id) ?? new Set<"view" | "view-text">();
    modes.add(tab.editor.kind);
    modesByView.set(tab.editor.detail.id, modes);
  }
  return [...modesByView].filter(([, modes]) => modes.size > 1).map(([viewId]) => viewId);
}
