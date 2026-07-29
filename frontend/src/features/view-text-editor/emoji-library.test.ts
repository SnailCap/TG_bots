import { describe, expect, it } from "vitest";

import {
  CUSTOM_EMOJI_STORAGE_KEY,
  loadCustomEmojiLibrary,
  rememberCustomEmoji,
  removeRecentCustomEmoji,
  saveCustomEmojiLibrary,
  toggleFavoriteCustomEmoji,
} from "./emoji-library";

class MemoryStorage {
  readonly values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
}

describe("custom emoji local library", () => {
  it("stores a minimized, versioned payload and restores valid entries", () => {
    const storage = new MemoryStorage();
    saveCustomEmojiLibrary(storage, {
      recent: [{ id: "100", fallback: "🙂" }],
      favorites: [{ id: "200", fallback: "🔥" }],
    });

    expect(JSON.parse(storage.getItem(CUSTOM_EMOJI_STORAGE_KEY)!)).toEqual({
      v: 1,
      r: [["100", "🙂"]],
      f: [["200", "🔥"]],
    });
    expect(loadCustomEmojiLibrary(storage)).toEqual({
      recent: [{ id: "100", fallback: "🙂" }],
      favorites: [{ id: "200", fallback: "🔥" }],
    });
  });

  it("ignores malformed and differently versioned storage", () => {
    const storage = new MemoryStorage();
    storage.setItem(CUSTOM_EMOJI_STORAGE_KEY, "{broken");
    expect(loadCustomEmojiLibrary(storage)).toEqual({ recent: [], favorites: [] });

    storage.setItem(CUSTOM_EMOJI_STORAGE_KEY, JSON.stringify({ v: 2, r: [], f: [] }));
    expect(loadCustomEmojiLibrary(storage)).toEqual({ recent: [], favorites: [] });
  });

  it("deduplicates recents and supports favorites and removal", () => {
    const first = { id: "100", fallback: "🙂" };
    const second = { id: "200", fallback: "🔥" };
    let library = rememberCustomEmoji({ recent: [first], favorites: [] }, second);
    library = rememberCustomEmoji(library, first);
    expect(library.recent).toEqual([first, second]);

    library = toggleFavoriteCustomEmoji(library, second);
    expect(library.favorites).toEqual([second]);
    library = toggleFavoriteCustomEmoji(library, second);
    expect(library.favorites).toEqual([]);
    expect(removeRecentCustomEmoji(library, first.id).recent).toEqual([second]);
  });
});
