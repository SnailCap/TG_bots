import type { Editor } from "@tiptap/core";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BotContentDocument } from "../../domain/content";
import type { ResolvedCustomEmoji } from "../../studio/api";
import { EmojiPickerPopover } from "./EditorPopovers";
import {
  CUSTOM_EMOJI_RESOLVE_BATCH_SIZE,
  CustomEmojiMedia,
  CustomEmojiStateProvider,
  customEmojiCapabilityStorageKey,
  displayStateFromResolvedCustomEmoji,
  loadCustomEmojiCapability,
  resolveCustomEmojiBatches,
  saveCustomEmojiCapability,
  type CustomEmojiDisplayState,
  type CustomEmojiEditorAdapter,
} from "./custom-emoji-state";
import { ViewTextEditor } from "./ViewTextEditor";

afterEach(() => {
  window.localStorage.clear();
});

describe("custom emoji resolution", () => {
  it("deduplicates IDs and resolves them in Telegram-sized batches", async () => {
    const references = Array.from({ length: 401 }, (_, index) => ({
      id: String(index + 1),
      fallback: "🙂",
    }));
    references.push({ id: "1", fallback: "🚀" });
    const resolveCustomEmojis = vi.fn(async (
      _projectId: string,
      ids: string[],
      fallbackById: Record<string, string> = {},
    ) => ({ items: ids.map((id) => resolvedItem(id, fallbackById[id] ?? "🙂", "webp")) }));

    const result = await resolveCustomEmojiBatches({ resolveCustomEmojis }, "project-a", references);

    expect(resolveCustomEmojis).toHaveBeenCalledTimes(3);
    expect(resolveCustomEmojis.mock.calls.map((call) => call[1].length)).toEqual([
      CUSTOM_EMOJI_RESOLVE_BATCH_SIZE,
      CUSTOM_EMOJI_RESOLVE_BATCH_SIZE,
      1,
    ]);
    expect(resolveCustomEmojis.mock.calls[0][2]?.["1"]).toBe("🚀");
    expect(result.items).toHaveLength(401);
    expect(result.items[0]).toMatchObject({ id: "1", fallbackEmoji: "🚀" });
    expect(result.failures).toEqual([]);
  });

  it("keeps successful batches when another batch fails", async () => {
    const references = Array.from({ length: 201 }, (_, index) => ({ id: String(index + 1), fallback: "🙂" }));
    const resolveCustomEmojis = vi.fn(async (
      _projectId: string,
      ids: string[],
      fallbackById: Record<string, string> = {},
    ) => {
      if (ids.includes("201")) throw new Error("temporary failure");
      return { items: ids.map((id) => resolvedItem(id, fallbackById[id] ?? "🙂", "webp")) };
    });

    const result = await resolveCustomEmojiBatches({ resolveCustomEmojis }, "project-a", references);

    expect(result.items).toHaveLength(200);
    expect(result.failures).toHaveLength(1);
    expect(result.failures[0]).toMatchObject({ reference: { id: "201" } });
  });

  it("creates a versioned preview URL only after metadata resolves", () => {
    const state = displayStateFromResolvedCustomEmoji(
      resolvedItem("100", "😀", "webp"),
      "😀",
      (id) => `http://studio.test/${id}/preview`,
    );

    expect(state).toMatchObject({ status: "resolved", preview: { format: "webp" } });
    expect(state.previewUrl).toBe("http://studio.test/100/preview?v=2026-07-29T10%3A00%3A00.000Z");
  });
});

describe("custom emoji media", () => {
  it("uses image for WebP, video for WebM, and an explicit fallback for TGS", () => {
    const markPreviewUnavailable = vi.fn();
    const states = Object.fromEntries([
      displayState("webp", "1", "😀"),
      displayState("webm", "2", "🚀"),
      displayState("tgs", "3", "✨"),
      { id: "4", fallback: "⚠️", status: "unavailable", reason: "not-found" } satisfies CustomEmojiDisplayState,
      { id: "5", fallback: "⌛", status: "loading" } satisfies CustomEmojiDisplayState,
      { id: "6", fallback: "✅", status: "fallback", reason: "missing-token" } satisfies CustomEmojiDisplayState,
    ].map((state) => [state.id, state]));
    const adapter = createAdapter(states, { markPreviewUnavailable });

    const { container } = render(
      <CustomEmojiStateProvider adapter={adapter}>
        <CustomEmojiMedia id="1" fallback="😀" />
        <CustomEmojiMedia id="2" fallback="🚀" />
        <CustomEmojiMedia id="3" fallback="✨" />
        <CustomEmojiMedia id="4" fallback="⚠️" />
        <CustomEmojiMedia id="5" fallback="⌛" />
        <CustomEmojiMedia id="6" fallback="✅" />
      </CustomEmojiStateProvider>,
    );

    const webp = container.querySelector("[data-custom-emoji-format='webp'] img");
    expect(webp).toHaveAttribute("src", "http://studio.test/1.webp?v=1");
    expect(container.querySelector("[data-custom-emoji-format='webm'] video")).toHaveAttribute("src", "http://studio.test/2.webm?v=1");
    const tgs = container.querySelector("[data-custom-emoji-format='tgs']");
    expect(tgs).toHaveTextContent("✨TGS");
    expect(tgs?.querySelector("img, video")).toBeNull();
    expect(tgs).toHaveAttribute("title", expect.stringContaining("animated TGS"));
    expect(container.querySelector("[data-custom-emoji-state='unavailable']")).toHaveTextContent("⚠️!");
    expect(container.querySelector("[data-custom-emoji-state='loading']")).toHaveTextContent("⌛…");
    expect(container.querySelector("[data-custom-emoji-state='fallback']")).toHaveTextContent("✅");

    fireEvent.error(webp!);
    expect(markPreviewUnavailable).toHaveBeenCalledWith("1", "preview-load-failed");
    expect(webp).not.toHaveAttribute("hidden");
    expect(container).toHaveTextContent("😀");
  });

  it("shares resolved media with the editor node view", async () => {
    const state = displayState("webp", "100", "😀");
    const document: BotContentDocument = {
      schemaVersion: 1,
      id: "home",
      content: [{
        type: "paragraph",
        content: [{ type: "customEmoji", customEmojiId: "100", fallbackEmoji: "😀" }],
      }],
      metadata: {
        createdAt: "2026-07-29T10:00:00.000Z",
        updatedAt: "2026-07-29T10:00:00.000Z",
        editorVersion: "1.0.0",
      },
    };

    render(
      <ViewTextEditor
        document={document}
        compileResult={null}
        previewValues={{}}
        saveState="idle"
        onDocumentChange={() => undefined}
        onPreviewValuesChange={() => undefined}
        customEmojiAdapter={createAdapter({ "100": state })}
      />,
    );

    const node = await screen.findByTestId("rich-custom-emoji");
    expect(node.querySelector("[data-custom-emoji-state='resolved'] img")).toHaveAttribute(
      "src",
      "http://studio.test/100.webp?v=1",
    );
  });
});

describe("custom emoji capability persistence", () => {
  it("is project-scoped and survives reopening the picker", () => {
    const snapshot = {
      capability: "available" as const,
      customEmojiId: "100",
      checkedAt: "2026-07-29T10:00:00.000Z",
    };
    saveCustomEmojiCapability(window.localStorage, "project-a", snapshot);

    expect(loadCustomEmojiCapability(window.localStorage, "project-a")).toEqual(snapshot);
    expect(loadCustomEmojiCapability(window.localStorage, "project-b")).toBeNull();
    expect(window.localStorage.getItem(customEmojiCapabilityStorageKey("project-a"))).not.toContain("project-b");

    const restored = loadCustomEmojiCapability(window.localStorage, "project-a");
    render(
      <CustomEmojiStateProvider adapter={createAdapter({}, { capability: restored })}>
        <EmojiPickerPopover
          editor={{} as Editor}
          open
          onClose={() => undefined}
          adapter={createAdapter({}, { capability: restored })}
        />
      </CustomEmojiStateProvider>,
    );
    expect(screen.getByText(/Bot capability: available/)).toBeInTheDocument();
    expect(screen.getByText(/Checked/)).toHaveAttribute("data-custom-emoji-capability", "available");
  });

  it("ignores malformed persisted capability records", () => {
    window.localStorage.setItem(customEmojiCapabilityStorageKey("project-a"), "{bad json");
    expect(loadCustomEmojiCapability(window.localStorage, "project-a")).toBeNull();
  });
});

function resolvedItem(
  id: string,
  fallbackEmoji: string,
  format: "webp" | "webm" | "tgs",
): ResolvedCustomEmoji {
  return {
    id,
    fallbackEmoji,
    status: "resolved",
    source: "manual-id",
    lastUsedAt: "2026-07-29T10:00:00.000Z",
    lastCheckedAt: "2026-07-29T10:00:00.000Z",
    cached: true,
    previewKey: id,
    preview: {
      key: id,
      format,
      mimeType: format === "webp" ? "image/webp" : format === "webm" ? "video/webm" : "application/x-tgsticker",
      loadedAt: "2026-07-29T10:00:00.000Z",
    },
  };
}

function displayState(format: "webp" | "webm" | "tgs", id: string, fallback: string): CustomEmojiDisplayState {
  return {
    id,
    fallback,
    status: "resolved",
    preview: resolvedItem(id, fallback, format).preview,
    previewUrl: `http://studio.test/${id}.${format}?v=1`,
  };
}

function createAdapter(
  states: Readonly<Record<string, CustomEmojiDisplayState>>,
  overrides: Partial<CustomEmojiEditorAdapter> = {},
): CustomEmojiEditorAdapter {
  return {
    states,
    capability: null,
    resolve: vi.fn(),
    resolveMany: vi.fn().mockResolvedValue([]),
    markPreviewUnavailable: vi.fn(),
    testCapability: vi.fn(),
    ...overrides,
  };
}
