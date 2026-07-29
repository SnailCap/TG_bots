import { useCallback, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import type { Selection } from "../../domain/project";
import { discardViewTextDraft } from "../../features/view-text-editor/content-draft";
import {
  selectionForEditor,
  selectionKeyEquals,
  type EditorState,
  type EditorTab,
} from "./editor-model";

type StudioTabLifecycleOptions = {
  tabs: readonly EditorTab[];
  activeTabKey: string | null;
  dirty: boolean;
  projectRoot: string;
  setTabs: Dispatch<SetStateAction<EditorTab[]>>;
  setActiveTabKey: Dispatch<SetStateAction<string | null>>;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  setSelection: Dispatch<SetStateAction<Selection | null>>;
  setDirty: Dispatch<SetStateAction<boolean>>;
};

type StudioTabLifecycle = {
  tabsRef: MutableRefObject<readonly EditorTab[]>;
  activeTabKeyRef: MutableRefObject<string | null>;
  discardRichDraftsFor(target: Selection): void;
  closeTabsFor(target: Selection): void;
  closeTab(tabKey: string, force?: boolean): void;
};

export function useStudioTabLifecycle({
  tabs,
  activeTabKey,
  dirty,
  projectRoot,
  setTabs,
  setActiveTabKey,
  setEditor,
  setSelection,
  setDirty,
}: StudioTabLifecycleOptions): StudioTabLifecycle {
  const tabsRef = useRef<readonly EditorTab[]>(tabs);
  const activeTabKeyRef = useRef<string | null>(activeTabKey);
  tabsRef.current = tabs;
  activeTabKeyRef.current = activeTabKey;

  const discardRichDraftsFor = useCallback((target: Selection) => {
    if (target.kind !== "view") return;
    // A recovery draft may survive a previous app crash even when no rich tab
    // is currently mounted. Rename/delete must remove that stale identity too.
    discardViewTextDraft(projectRoot, target.id);
  }, [projectRoot]);

  const closeTabsFor = useCallback((target: Selection) => {
    discardRichDraftsFor(target);
    const remaining = tabsRef.current.filter((tab) => !selectionKeyEquals(selectionForEditor(tab.editor), target));
    setTabs(remaining);
    const activeTab = tabsRef.current.find((tab) => tab.key === activeTabKeyRef.current);
    if (!activeTab || !selectionKeyEquals(selectionForEditor(activeTab.editor), target)) return;
    const fallback = remaining.at(-1) ?? null;
    setActiveTabKey(fallback?.key ?? null);
    setEditor(fallback?.editor ?? null);
    setSelection(null);
    setDirty(fallback?.dirty ?? false);
  }, [discardRichDraftsFor, setActiveTabKey, setDirty, setEditor, setSelection, setTabs]);

  const closeTab = useCallback((tabKey: string, force = false) => {
    const tab = tabs.find((item) => item.key === tabKey);
    if (!tab) return;
    const needsConfirmation = tabKey === activeTabKey ? dirty : tab.dirty;
    if (!force && needsConfirmation && !window.confirm("Discard unsaved changes?")) return;
    if (needsConfirmation && tab.editor.kind === "view-text") {
      discardViewTextDraft(projectRoot, tab.editor.detail.id);
    }
    const tabIndex = tabs.findIndex((item) => item.key === tabKey);
    const nextTabs = tabs.filter((item) => item.key !== tabKey);
    setTabs(nextTabs);
    if (tabKey !== activeTabKey) return;
    const nextTab = nextTabs[Math.max(0, tabIndex - 1)] ?? null;
    setActiveTabKey(nextTab?.key ?? null);
    setEditor(nextTab?.editor ?? null);
    setDirty(nextTab?.dirty ?? false);
  }, [activeTabKey, dirty, projectRoot, setActiveTabKey, setDirty, setEditor, setTabs, tabs]);

  return { tabsRef, activeTabKeyRef, discardRichDraftsFor, closeTabsFor, closeTab };
}
