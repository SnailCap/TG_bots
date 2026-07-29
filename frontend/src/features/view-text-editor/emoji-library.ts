export const CUSTOM_EMOJI_STORAGE_KEY = "botstudio.rich-editor.custom-emoji.v1";
const STORAGE_VERSION = 1 as const;
const MAX_RECENT = 24;
const MAX_FAVORITES = 48;

export type SavedCustomEmoji = {
  id: string;
  fallback: string;
};

export type CustomEmojiLibrary = {
  recent: SavedCustomEmoji[];
  favorites: SavedCustomEmoji[];
};

type StoredLibrary = {
  v: typeof STORAGE_VERSION;
  r: Array<[string, string]>;
  f: Array<[string, string]>;
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export const EMPTY_CUSTOM_EMOJI_LIBRARY: CustomEmojiLibrary = { recent: [], favorites: [] };

export function loadCustomEmojiLibrary(storage: StorageLike | null | undefined): CustomEmojiLibrary {
  if (!storage) return { ...EMPTY_CUSTOM_EMOJI_LIBRARY };
  try {
    const parsed = JSON.parse(storage.getItem(CUSTOM_EMOJI_STORAGE_KEY) ?? "null") as Partial<StoredLibrary> | null;
    if (!parsed || parsed.v !== STORAGE_VERSION || !Array.isArray(parsed.r) || !Array.isArray(parsed.f)) {
      return { recent: [], favorites: [] };
    }
    return {
      recent: decodeEntries(parsed.r).slice(0, MAX_RECENT),
      favorites: decodeEntries(parsed.f).slice(0, MAX_FAVORITES),
    };
  } catch {
    return { recent: [], favorites: [] };
  }
}

export function saveCustomEmojiLibrary(storage: StorageLike | null | undefined, library: CustomEmojiLibrary): void {
  if (!storage) return;
  const payload: StoredLibrary = {
    v: STORAGE_VERSION,
    r: encodeEntries(library.recent.slice(0, MAX_RECENT)),
    f: encodeEntries(library.favorites.slice(0, MAX_FAVORITES)),
  };
  try {
    storage.setItem(CUSTOM_EMOJI_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Storage is an enhancement. A full or unavailable store must not prevent
    // composing the message.
  }
}

export function rememberCustomEmoji(library: CustomEmojiLibrary, emoji: SavedCustomEmoji): CustomEmojiLibrary {
  if (!isSavedCustomEmoji(emoji)) return library;
  return {
    ...library,
    recent: [emoji, ...library.recent.filter((item) => item.id !== emoji.id)].slice(0, MAX_RECENT),
  };
}

export function toggleFavoriteCustomEmoji(library: CustomEmojiLibrary, emoji: SavedCustomEmoji): CustomEmojiLibrary {
  if (!isSavedCustomEmoji(emoji)) return library;
  const existing = library.favorites.some((item) => item.id === emoji.id);
  return {
    ...library,
    favorites: existing
      ? library.favorites.filter((item) => item.id !== emoji.id)
      : [emoji, ...library.favorites.filter((item) => item.id !== emoji.id)].slice(0, MAX_FAVORITES),
  };
}

export function removeRecentCustomEmoji(library: CustomEmojiLibrary, id: string): CustomEmojiLibrary {
  return { ...library, recent: library.recent.filter((item) => item.id !== id) };
}

export function isSavedCustomEmoji(value: SavedCustomEmoji): boolean {
  return /^\d+$/.test(value.id) && Boolean(value.fallback.trim());
}

function decodeEntries(entries: Array<[string, string]>): SavedCustomEmoji[] {
  const seen = new Set<string>();
  const result: SavedCustomEmoji[] = [];
  for (const entry of entries) {
    if (!Array.isArray(entry) || entry.length !== 2) continue;
    const emoji = { id: String(entry[0]), fallback: String(entry[1]) };
    if (!isSavedCustomEmoji(emoji) || seen.has(emoji.id)) continue;
    seen.add(emoji.id);
    result.push(emoji);
  }
  return result;
}

function encodeEntries(entries: readonly SavedCustomEmoji[]): Array<[string, string]> {
  return entries.filter(isSavedCustomEmoji).map((emoji) => [emoji.id, emoji.fallback]);
}
