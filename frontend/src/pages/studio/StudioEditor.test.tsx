import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SCHEMA_VERSION, type ActionOptions, type ViewDetail } from "../../domain/project";
import type { BotContentDocument, TelegramCompileResult } from "../../domain/content";
import type { HandlerActions } from "../../features/action-editor/ActionEditor";
import { contentDraftKey } from "../../features/view-text-editor/content-draft";
import type { StudioApiClient } from "../../studio/api";
import type { EditorState } from "./editor-model";
import { StudioEditor } from "./StudioEditor";

vi.mock("../../features/view-text-editor/ViewTextEditor", () => ({
  ViewTextEditor: () => <div data-testid="rich-editor-stub" />,
}));

const EMPTY_OPTIONS: ActionOptions = { views: [], flows: [], states: [], handlers: [] };
const EMPTY_COMPILE_RESULT: TelegramCompileResult = { messages: [], warnings: [], errors: [] };
const PROJECT_ROOT = "C:/draft-isolation";

afterEach(() => {
  vi.useRealTimers();
  window.localStorage.clear();
});

describe("StudioEditor rich-view lifecycle", () => {
  it("keeps drafts and same-version autosave isolated when switching from view A to B", async () => {
    vi.useFakeTimers();
    const saveA = vi.fn().mockResolvedValue(undefined);
    const saveB = vi.fn().mockResolvedValue(undefined);
    const editorA = richEditorState("view-a", "Draft A", 7);
    const editorB = richEditorState("view-b", "Draft B", 7);
    const common = studioEditorProps();
    const { rerender } = render(<StudioEditor {...common} editor={editorA} save={saveA} />);

    await act(async () => { await vi.advanceTimersByTimeAsync(750); });
    expect(saveA).toHaveBeenCalledOnce();

    rerender(<StudioEditor {...common} editor={editorB} save={saveB} />);

    expect(readDraftDocument("view-a")).toMatchObject({ id: "view-a", content: paragraph("Draft A") });
    expect(readDraftDocument("view-b")).toMatchObject({ id: "view-b", content: paragraph("Draft B") });

    await act(async () => { await vi.advanceTimersByTimeAsync(750); });
    expect(saveB).toHaveBeenCalledOnce();
  });
});

function studioEditorProps() {
  const asyncNoop = vi.fn().mockResolvedValue(undefined);
  const handlerActions: HandlerActions = {
    create: asyncNoop,
    repair: asyncNoop,
    open: asyncNoop,
    usages: vi.fn().mockResolvedValue([]),
  };
  const api = {
    compileContent: vi.fn().mockResolvedValue(EMPTY_COMPILE_RESULT),
    resolveCustomEmojis: vi.fn().mockResolvedValue({ items: [] }),
    customEmojiPreviewUrl: vi.fn(() => ""),
    testCustomEmojiCapability: vi.fn(),
    sendPreviewMessage: vi.fn(),
  } as unknown as StudioApiClient;
  return {
    api,
    projectId: "project-one",
    projectRoot: PROJECT_ROOT,
    busy: false,
    saving: false,
    dirty: true,
    saveError: false,
    options: EMPTY_OPTIONS,
    handlerActions,
    setEditor: vi.fn(),
    setDirty: vi.fn(),
    repairHandler: asyncNoop,
    openHandler: asyncNoop,
    findUsages: vi.fn().mockResolvedValue([]),
    createHandler: asyncNoop,
    select: vi.fn(),
    openViewTextEditor: vi.fn(),
    renameDisplayName: asyncNoop,
  };
}

function richEditorState(id: string, text: string, version: number): Exclude<EditorState, null> {
  const document: BotContentDocument = {
    schemaVersion: 1,
    id,
    content: paragraph(text),
    metadata: {
      createdAt: "2026-07-29T12:00:00.000Z",
      updatedAt: "2026-07-29T12:00:00.000Z",
      editorVersion: "1.0.0",
      source: "botstudio",
    },
  };
  const detail: ViewDetail = {
    id,
    source_path: `views/${id}.json`,
    revision: "shared-view-revision",
    text_content: text,
    text_revision: "shared-text-revision",
    content_document: document,
    content_revision: "shared-content-revision",
    payload: {
      schema_version: SCHEMA_VERSION,
      id,
      text: { template: `views/${id}.txt`, document: `views/${id}.json` },
      keyboard: [],
    },
  };
  return { kind: "view-text", detail, document, version, savedVersion: version - 1 };
}

function paragraph(text: string): BotContentDocument["content"] {
  return [{ type: "paragraph", content: [{ type: "text", text }] }];
}

function readDraftDocument(viewId: string): BotContentDocument | undefined {
  const raw = window.localStorage.getItem(contentDraftKey(PROJECT_ROOT, viewId));
  return raw ? (JSON.parse(raw) as { document?: BotContentDocument }).document : undefined;
}
