import { act, renderHook } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import type { BotContentDocument } from "../../domain/content";
import type { Selection, ViewDetail } from "../../domain/project";
import { contentDraftKey } from "../../features/view-text-editor/content-draft";
import type { EditorState, EditorTab } from "./editor-model";
import { useStudioTabLifecycle } from "./useStudioTabLifecycle";

const document: BotContentDocument = {
  schemaVersion: 1,
  id: "home",
  content: [{ type: "paragraph", content: [{ type: "text", text: "Hello" }] }],
  metadata: {
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    editorVersion: "1.0.0",
    source: "botstudio",
  },
};

const detail: ViewDetail = {
  id: "home",
  name: "home",
  source_path: "views/home.json",
  revision: "view-one",
  text_content: "Hello",
  text_revision: "text-one",
  content_document: document,
  content_revision: "content-one",
  payload: {
    schema_version: 3,
    id: "home",
    text: { template: "views/home.txt", document: "views/home.json" },
    keyboard: [],
  },
};

const compactEditor = { kind: "view", detail, isNew: false } as const;
const richEditor = {
  kind: "view-text",
  detail,
  document,
  version: 0,
  savedVersion: 0,
} as const;

describe("useStudioTabLifecycle", () => {
  beforeEach(() => window.localStorage.clear());

  it("closes every editor tab and discards the recovery draft for a deleted view", () => {
    const draftKey = contentDraftKey("C:/demo", "home");
    window.localStorage.setItem(draftKey, "draft");

    const { result } = renderHook(() => {
      const [tabs, setTabs] = useState<EditorTab[]>([
        { key: "view:home", editor: compactEditor, dirty: false },
        { key: "view-text:home", editor: richEditor, dirty: false },
      ]);
      const [activeTabKey, setActiveTabKey] = useState<string | null>("view:home");
      const [editor, setEditor] = useState<EditorState>(compactEditor);
      const [selection, setSelection] = useState<Selection | null>({ kind: "view", id: "home" });
      const [dirty, setDirty] = useState(false);
      const lifecycle = useStudioTabLifecycle({
        tabs,
        activeTabKey,
        dirty,
        projectRoot: "C:/demo",
        setTabs,
        setActiveTabKey,
        setEditor,
        setSelection,
        setDirty,
      });
      return { tabs, activeTabKey, editor, selection, dirty, lifecycle };
    });

    act(() => result.current.lifecycle.closeTabsFor({ kind: "view", id: "home" }));

    expect(result.current.tabs).toEqual([]);
    expect(result.current.activeTabKey).toBeNull();
    expect(result.current.editor).toBeNull();
    expect(result.current.selection).toBeNull();
    expect(result.current.dirty).toBe(false);
    expect(window.localStorage.getItem(draftKey)).toBeNull();
  });

  it("discards a crash-recovery draft even when no rich tab is currently open", () => {
    const draftKey = contentDraftKey("C:/demo", "home");
    window.localStorage.setItem(draftKey, "stale draft");

    const { result } = renderHook(() => {
      const [tabs, setTabs] = useState<EditorTab[]>([
        { key: "view:home", editor: compactEditor, dirty: false },
      ]);
      const [activeTabKey, setActiveTabKey] = useState<string | null>("view:home");
      const [, setEditor] = useState<EditorState>(compactEditor);
      const [, setSelection] = useState<Selection | null>({ kind: "view", id: "home" });
      const [dirty, setDirty] = useState(false);
      return useStudioTabLifecycle({
        tabs,
        activeTabKey,
        dirty,
        projectRoot: "C:/demo",
        setTabs,
        setActiveTabKey,
        setEditor,
        setSelection,
        setDirty,
      });
    });

    act(() => result.current.discardRichDraftsFor({ kind: "view", id: "home" }));

    expect(window.localStorage.getItem(draftKey)).toBeNull();
  });
});
