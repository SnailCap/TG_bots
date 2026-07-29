import { useCallback, type Dispatch, type SetStateAction } from "react";

import type { Selection } from "../../domain/project";
import type { StudioApiClient } from "../../studio/api";
import { viewTextTabKey, type EditorState, type EditorTab } from "./editor-model";
import { saveEditor, viewTextEditorFromDetail } from "./studio-resource-api";

type OpenViewTextEditorOptions = {
  api: StudioApiClient;
  projectId: string;
  tabs: readonly EditorTab[];
  activeTabKey: string | null;
  editor: EditorState;
  dirty: boolean;
  setTabs: Dispatch<SetStateAction<EditorTab[]>>;
  setActiveTabKey: Dispatch<SetStateAction<string | null>>;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  setSelection: Dispatch<SetStateAction<Selection | null>>;
  setDirty: Dispatch<SetStateAction<boolean>>;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  clearMessages(): void;
  report(error: unknown): void;
};

export function useOpenViewTextEditor({
  api,
  projectId,
  tabs,
  activeTabKey,
  editor,
  dirty,
  setTabs,
  setActiveTabKey,
  setEditor,
  setSelection,
  setDirty,
  setBusy,
  setSaving,
  clearMessages,
  report,
}: OpenViewTextEditorOptions) {
  return useCallback((viewId: string, _displayName: string) => {
    const tabKey = viewTextTabKey(viewId);
    const currentTabs = editor && activeTabKey
      ? tabs.map((tab) => tab.key === activeTabKey ? { ...tab, editor, dirty } : tab)
      : [...tabs];
    const existing = currentTabs.find((tab) => tab.key === tabKey);
    if (existing?.editor.kind === "view-text") {
      setTabs(currentTabs);
      setActiveTabKey(tabKey);
      setSelection({ kind: "view", id: viewId });
      setEditor(existing.editor);
      setDirty(existing.dirty);
      clearMessages();
      return;
    }

    setTabs(currentTabs);
    setBusy(true);
    void (async () => {
      const sibling = currentTabs.find((tab) =>
        tab.editor.kind === "view" && tab.editor.detail.id === viewId,
      );
      if (sibling?.dirty) setSaving(true);
      const savedSibling = sibling?.dirty && sibling.editor.kind === "view"
        ? await saveEditor(api, projectId, sibling.editor, { kind: "view", id: viewId })
        : null;
      const detail = savedSibling?.editor.kind === "view"
        ? savedSibling.editor.detail
        : sibling?.editor.kind === "view"
          ? sibling.editor.detail
          : await api.getView(projectId, viewId);
      const nextEditor = viewTextEditorFromDetail(detail);
      const nextDirty = nextEditor.version !== nextEditor.savedVersion;
      setActiveTabKey(tabKey);
      setSelection({ kind: "view", id: viewId });
      setTabs((current) => {
        const synced = savedSibling?.editor.kind === "view"
          ? current.map((tab) => tab.key === sibling?.key
            ? { ...tab, editor: savedSibling.editor, dirty: false }
            : tab)
          : current;
        return synced.some((tab) => tab.key === tabKey)
          ? synced.map((tab) => tab.key === tabKey
            ? { ...tab, editor: nextEditor, dirty: nextDirty }
            : tab)
          : [...synced, { key: tabKey, editor: nextEditor, dirty: nextDirty }];
      });
      setEditor(nextEditor);
      setDirty(nextDirty);
      clearMessages();
    })().catch(report).finally(() => { setSaving(false); setBusy(false); });
  }, [
    activeTabKey,
    api,
    clearMessages,
    dirty,
    editor,
    projectId,
    report,
    setActiveTabKey,
    setBusy,
    setDirty,
    setEditor,
    setSelection,
    setSaving,
    setTabs,
    tabs,
  ]);
}
