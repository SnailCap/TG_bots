import type { Editor } from "@tiptap/core";
import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { Copy, Search, Star, Trash2, UserRound, X } from "lucide-react";

import {
  searchContextFields,
  type ContextFieldDefinition,
} from "../template-composer/context-catalog";
import { isValidCustomEmojiFallback } from "./model";
import {
  loadCustomEmojiLibrary,
  rememberCustomEmoji,
  removeRecentCustomEmoji,
  saveCustomEmojiLibrary,
  toggleFavoriteCustomEmoji,
  type CustomEmojiLibrary,
  type SavedCustomEmoji,
} from "./emoji-library";
import { CustomEmojiMedia, type CustomEmojiEditorAdapter } from "./custom-emoji-state";
import { inlineMarkAttributes, isInlineMarkActive, setInlineMark, unsetInlineMark } from "./inline-atom-marks";
import { isSafeContentLink } from "./model";

const UNICODE_EMOJI = [
  "😀", "😂", "🥹", "😍", "🤔", "😎", "😭", "😡",
  "👍", "👎", "👏", "🙏", "💪", "🤝", "❤️", "🔥",
  "✨", "🎉", "✅", "❌", "⚠️", "📌", "🚀", "💬",
] as const;

type PopoverProps = {
  editor: Editor;
  open: boolean;
  onClose(): void;
};

export function VariablePickerPopover({
  editor,
  open,
  onClose,
  fields: catalog,
}: PopoverProps & { fields: readonly ContextFieldDefinition[] }) {
  const titleId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const fields = useMemo(() => searchContextFields(query, catalog), [query, catalog]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    queueMicrotask(() => searchRef.current?.focus());
  }, [open]);

  if (!open) return null;
  const insert = (field: ContextFieldDefinition) => {
    editor.chain().focus().insertContent({
      type: "variable",
      attrs: {
        fieldId: field.id,
        path: field.path,
        source: `{{ ${field.path} }}`,
      },
    }).run();
    onClose();
  };

  return (
    <EditorPopover className="view-rich-picker view-rich-picker--variables" labelId={titleId} onClose={onClose}>
      <PopoverHeader title="Insert variable" titleId={titleId} onClose={onClose} />
      <label className="view-rich-picker__search">
        <Search aria-hidden="true" />
        <span className="sr-only">Search variables</span>
        <input ref={searchRef} aria-label="Search variables" value={query} placeholder="Name or context path" onChange={(event) => setQuery(event.target.value)} />
      </label>
      <div className="view-rich-picker__list" role="listbox" aria-label="Available variables">
        {fields.length === 0 ? <p className="view-rich-picker__empty">No matching variables.</p> : fields.map((field) => (
          <button type="button" role="option" aria-selected="false" key={field.id} onClick={() => insert(field)}>
            <UserRound aria-hidden="true" />
            <span><strong>{field.label}</strong><small>{field.path}</small></span>
          </button>
        ))}
      </div>
    </EditorPopover>
  );
}

export function LinkEditorPopover({ editor, open, onClose }: PopoverProps) {
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [href, setHref] = useState("https://");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    const existing = inlineMarkAttributes(editor, "link").href;
    setHref(typeof existing === "string" && existing ? existing : "https://");
    setError("");
    queueMicrotask(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
  }, [editor, open]);

  if (!open) return null;
  const apply = (event: FormEvent) => {
    event.preventDefault();
    if (!isSafeContentLink(href.trim())) {
      setError("Use an http(s), tg://, or mailto: address.");
      return;
    }
    setInlineMark(editor, "link", { href: href.trim() });
    onClose();
  };
  const remove = () => {
    unsetInlineMark(editor, "link");
    onClose();
  };

  return (
    <EditorPopover className="view-rich-picker view-rich-picker--link" labelId={titleId} onClose={onClose}>
      <PopoverHeader title="Text link" titleId={titleId} onClose={onClose} />
      <form className="view-rich-picker__form" onSubmit={apply}>
        <label><span>Web address</span><input ref={inputRef} aria-label="Web address" value={href} onChange={(event) => setHref(event.target.value)} /></label>
        {error ? <p role="alert">{error}</p> : null}
        <footer>
          {isInlineMarkActive(editor, "link") ? <button type="button" className="view-rich-picker__danger" onClick={remove}>Remove link</button> : <span />}
          <button type="submit">Apply</button>
        </footer>
      </form>
    </EditorPopover>
  );
}

export function EmojiPickerPopover({ editor, open, onClose, adapter }: PopoverProps & { adapter?: CustomEmojiEditorAdapter }) {
  const titleId = useId();
  const idInputRef = useRef<HTMLInputElement>(null);
  const [customEmojiId, setCustomEmojiId] = useState("");
  const [fallback, setFallback] = useState("🙂");
  const [error, setError] = useState("");
  const [resolution, setResolution] = useState("");
  const [chatId, setChatId] = useState("");
  const [checking, setChecking] = useState(false);
  const [library, setLibrary] = useState<CustomEmojiLibrary>(() => loadCustomEmojiLibrary(safeLocalStorage()));
  const shelfItems = useMemo(
    () => [...new Map([...library.favorites, ...library.recent].map((item) => [item.id, item])).values()],
    [library],
  );
  const shelfKey = useMemo(() => JSON.stringify(shelfItems), [shelfItems]);
  const resolveMany = adapter?.resolveMany;

  useEffect(() => saveCustomEmojiLibrary(safeLocalStorage(), library), [library]);
  useEffect(() => {
    if (!open) return;
    setError("");
    setResolution("");
  }, [open]);
  useEffect(() => {
    if (!open || !resolveMany || shelfItems.length === 0) return;
    void resolveMany(shelfItems).catch(() => undefined);
    // The serialized key avoids resolving again for unrelated adapter-state updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, resolveMany, shelfKey]);

  if (!open) return null;
  const insertUnicode = (emoji: string) => {
    editor.chain().focus().insertContent(emoji).run();
    onClose();
  };
  const insertCustom = (emoji: SavedCustomEmoji, close = true) => {
    editor.chain().focus().insertContent({
      type: "customEmoji",
      attrs: { customEmojiId: emoji.id, fallbackEmoji: emoji.fallback },
    }).run();
    setLibrary((current) => rememberCustomEmoji(current, emoji));
    void adapter?.resolve(emoji.id, emoji.fallback).catch(() => undefined);
    if (close) onClose();
  };
  const addCustom = (event: FormEvent) => {
    event.preventDefault();
    const emoji = { id: customEmojiId.trim(), fallback: fallback.trim() };
    if (!/^\d+$/.test(emoji.id)) {
      setError("Custom emoji ID must contain digits only.");
      idInputRef.current?.focus();
      return;
    }
    if (!isValidCustomEmojiFallback(emoji.fallback)) {
      setError("Fallback must be one Unicode emoji.");
      return;
    }
    setError("");
    insertCustom(emoji);
  };
  const validCustomEmoji = (): SavedCustomEmoji | null => {
    const emoji = { id: customEmojiId.trim(), fallback: fallback.trim() };
    if (!/^\d+$/.test(emoji.id)) {
      setError("Custom emoji ID must contain digits only.");
      idInputRef.current?.focus();
      return null;
    }
    if (!isValidCustomEmojiFallback(emoji.fallback)) {
      setError("Fallback must be one Unicode emoji.");
      return null;
    }
    setError("");
    return emoji;
  };
  const checkPreview = async () => {
    const emoji = validCustomEmoji();
    if (!emoji || !adapter) return;
    setChecking(true);
    setResolution("Loading Telegram metadata…");
    try {
      const result = await adapter.resolve(emoji.id, emoji.fallback);
      setResolution(result.status === "resolved"
        ? "Telegram preview is cached."
        : `Fallback will be used${result.reason ? `: ${result.reason}` : "."}`);
    } catch (caught) {
      setResolution(caught instanceof Error ? caught.message : "Telegram metadata is unavailable.");
    } finally {
      setChecking(false);
    }
  };
  const testCapability = async () => {
    const emoji = validCustomEmoji();
    if (!emoji || !adapter || !chatId.trim()) {
      if (!chatId.trim()) setError("Enter a Telegram chat ID for the explicit capability test.");
      return;
    }
    setChecking(true);
    setResolution("Sending a silent capability test…");
    try {
      const result = await adapter.testCapability(emoji.id, emoji.fallback, chatId.trim());
      setResolution(`Capability test completed: ${result.capability}${result.reason ? ` (${result.reason})` : ""}.`);
    } catch (caught) {
      setResolution(caught instanceof Error ? caught.message : "Capability test failed.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <EditorPopover className="view-rich-picker view-rich-picker--emoji" labelId={titleId} onClose={onClose}>
      <PopoverHeader title="Insert emoji" titleId={titleId} onClose={onClose} />
      <section className="view-rich-picker__section" aria-label="Unicode emoji">
        <span className="view-rich-picker__section-title">Unicode</span>
        <div className="view-rich-emoji-grid">
          {UNICODE_EMOJI.map((emoji) => <button type="button" aria-label={`Insert ${emoji}`} title={`Insert ${emoji}`} key={emoji} onClick={() => insertUnicode(emoji)}>{emoji}</button>)}
        </div>
      </section>
      {library.favorites.length > 0 ? (
        <EmojiShelf title="Favorites" items={library.favorites} favorites={library.favorites} onInsert={insertCustom} onToggleFavorite={(emoji) => setLibrary((current) => toggleFavoriteCustomEmoji(current, emoji))} onRemoveRecent={() => undefined} />
      ) : null}
      {library.recent.length > 0 ? (
        <EmojiShelf title="Recent custom emoji" items={library.recent} favorites={library.favorites} onInsert={insertCustom} onToggleFavorite={(emoji) => setLibrary((current) => toggleFavoriteCustomEmoji(current, emoji))} onRemoveRecent={(emoji) => setLibrary((current) => removeRecentCustomEmoji(current, emoji.id))} />
      ) : null}
      <form className="view-rich-picker__form view-rich-picker__custom-form" onSubmit={addCustom}>
        <span className="view-rich-picker__section-title">Custom emoji by ID</span>
        <div>
          <label><span>ID</span><input ref={idInputRef} aria-label="Custom emoji ID" inputMode="numeric" value={customEmojiId} placeholder="5368324170671202286" onChange={(event) => setCustomEmojiId(event.target.value)} /></label>
          <label className="view-rich-picker__fallback"><span>Fallback</span><input aria-label="Custom emoji fallback" value={fallback} onChange={(event) => setFallback(event.target.value)} /></label>
        </div>
        {error ? <p role="alert">{error}</p> : null}
        {resolution ? <p role="status">{resolution}</p> : null}
        {adapter ? <CapabilityStatus capability={adapter.capability} /> : null}
        {adapter ? <label><span>Capability test chat ID</span><input aria-label="Capability test chat ID" value={chatId} placeholder="123456789" onChange={(event) => setChatId(event.target.value)} /></label> : null}
        <footer>
          {adapter ? <><button type="button" disabled={checking} onClick={() => void checkPreview()}>Check preview</button><button type="button" disabled={checking} title="Sends one silent test message" onClick={() => void testCapability()}>Test bot</button></> : <span />}
          <button type="submit">Insert custom emoji</button>
        </footer>
      </form>
    </EditorPopover>
  );
}

function EmojiShelf({ title, items, favorites, onInsert, onToggleFavorite, onRemoveRecent }: {
  title: string;
  items: readonly SavedCustomEmoji[];
  favorites: readonly SavedCustomEmoji[];
  onInsert(emoji: SavedCustomEmoji): void;
  onToggleFavorite(emoji: SavedCustomEmoji): void;
  onRemoveRecent(emoji: SavedCustomEmoji): void;
}) {
  return (
    <section className="view-rich-picker__section" aria-label={title}>
      <span className="view-rich-picker__section-title">{title}</span>
      <div className="view-rich-custom-shelf">
        {items.map((emoji) => {
          const favorite = favorites.some((item) => item.id === emoji.id);
          return <div key={emoji.id}>
            <button type="button" className="view-rich-custom-shelf__emoji" title={`Insert custom emoji ${emoji.id}`} onClick={() => onInsert(emoji)}><CustomEmojiMedia id={emoji.id} fallback={emoji.fallback} /></button>
            <button type="button" aria-label={favorite ? `Remove ${emoji.id} from favorites` : `Add ${emoji.id} to favorites`} title={favorite ? "Remove from favorites" : "Add to favorites"} onClick={() => onToggleFavorite(emoji)}><Star aria-hidden="true" fill={favorite ? "currentColor" : "none"} /></button>
            {title.startsWith("Recent") ? <button type="button" aria-label={`Remove ${emoji.id} from recent`} title="Remove from recent" onClick={() => onRemoveRecent(emoji)}><Trash2 aria-hidden="true" /></button> : null}
            <button type="button" aria-label={`Copy custom emoji ID ${emoji.id}`} title="Copy ID" onClick={() => void copyText(emoji.id)}><Copy aria-hidden="true" /></button>
          </div>;
        })}
      </div>
    </section>
  );
}

function CapabilityStatus({ capability }: { capability: CustomEmojiEditorAdapter["capability"] }) {
  if (!capability) {
    return <p className="view-rich-picker__capability is-unknown" data-custom-emoji-capability="unknown">Bot capability has not been tested for this project.</p>;
  }
  const checkedAt = new Date(capability.checkedAt).toLocaleString();
  return (
    <p className={`view-rich-picker__capability is-${capability.capability}`} data-custom-emoji-capability={capability.capability}>
      Bot capability: {capability.capability}{capability.reason ? ` (${capability.reason})` : ""}. Checked {checkedAt}.
    </p>
  );
}

function EditorPopover({ className, labelId, onClose, children }: {
  className: string;
  labelId: string;
  onClose(): void;
  children: ReactNode;
}) {
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    onClose();
  };
  return <div className={className} role="dialog" aria-modal="false" aria-labelledby={labelId} onKeyDown={handleKeyDown}>{children}</div>;
}

function PopoverHeader({ title, titleId, onClose }: { title: string; titleId: string; onClose(): void }) {
  return <header><strong id={titleId}>{title}</strong><button type="button" aria-label={`Close ${title.toLowerCase()}`} title="Close" onClick={onClose}><X aria-hidden="true" /></button></header>;
}

function safeLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

async function copyText(value: string): Promise<void> {
  try {
    await navigator.clipboard?.writeText(value);
  } catch {
    // Clipboard permission failures do not affect editing.
  }
}
