import { Extension, Mark, Node, mergeAttributes, nodePasteRule } from "@tiptap/core";
import { Slice } from "@tiptap/pm/model";
import { Plugin } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { Braces, CircleAlert, UserRound } from "lucide-react";
import { memo, useState, type MouseEvent as ReactMouseEvent } from "react";

import { findContextField } from "../template-composer/context-catalog";
import { CustomEmojiMedia } from "./custom-emoji-state";
import { toggleSelectedVariableMark } from "./inline-atom-marks";
import { loadCustomEmojiLibrary, saveCustomEmojiLibrary, toggleFavoriteCustomEmoji } from "./emoji-library";
import { findSupportedVariableTokens, type SupportedVariableTokenMatch } from "./legacy-adapter";
import { isValidCustomEmojiFallback } from "./model";

export const INTERNAL_CONTENT_CLIPBOARD_MIME = "application/x-botstudio-content+json";
const MAX_INTERNAL_CLIPBOARD_BYTES = 1_000_000;

export const SpoilerMark = Mark.create({
  name: "spoiler",
  parseHTML() {
    return [
      { tag: "span[data-botstudio-spoiler]" },
      { tag: "span.tg-spoiler" },
      { tag: "tg-spoiler" },
    ];
  },
  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes(HTMLAttributes, {
      "data-botstudio-spoiler": "true",
      class: "view-rich-editor__spoiler",
    }), 0];
  },
  addKeyboardShortcuts() {
    return { "Mod-Shift-p": () => this.editor.commands.toggleMark(this.name) };
  },
});

export const VariableNode = Node.create({
  name: "variable",
  inline: true,
  group: "inline",
  atom: true,
  selectable: true,
  draggable: true,
  marks: "_",
  addAttributes() {
    return {
      fieldId: { default: null },
      path: { default: "" },
      source: { default: "" },
    };
  },
  parseHTML() {
    return [{
      tag: "span[data-botstudio-variable]",
      getAttrs: (element) => element instanceof HTMLElement ? {
        fieldId: element.dataset.fieldId || null,
        path: element.dataset.path ?? "",
        source: element.dataset.source ?? "",
      } : false,
    }];
  },
  renderHTML({ node, HTMLAttributes }) {
    const source = String(node.attrs.source || `{{ ${String(node.attrs.path)} }}`);
    return ["span", mergeAttributes(HTMLAttributes, {
      "data-botstudio-variable": "true",
      "data-field-id": node.attrs.fieldId ?? "",
      "data-path": node.attrs.path,
      "data-source": source,
    }), source];
  },
  renderText({ node }) {
    return String(node.attrs.source || `{{ ${String(node.attrs.path)} }}`);
  },
  addNodeView() {
    return ReactNodeViewRenderer(VariableNodeView);
  },
  addKeyboardShortcuts() {
    return {
      "Mod-b": () => toggleSelectedVariableMark(this.editor.view, "bold"),
      "Mod-i": () => toggleSelectedVariableMark(this.editor.view, "italic"),
      "Mod-u": () => toggleSelectedVariableMark(this.editor.view, "underline"),
      "Mod-Shift-x": () => toggleSelectedVariableMark(this.editor.view, "strike"),
      "Mod-Shift-p": () => toggleSelectedVariableMark(this.editor.view, "spoiler"),
      "Mod-e": () => toggleSelectedVariableMark(this.editor.view, "code"),
    };
  },
  addPasteRules() {
    return [nodePasteRule({
      type: this.type,
      find: (text) => findSupportedVariableTokens(text).map((token) => ({
        index: token.index,
        text: token.source,
        data: token,
      })),
      getAttributes: (match) => {
        const token = match.data as SupportedVariableTokenMatch | undefined;
        return token ? {
          fieldId: token.fieldId,
          path: token.path,
          source: token.source,
        } : false;
      },
    })];
  },
});

export const CustomEmojiNode = Node.create({
  name: "customEmoji",
  inline: true,
  group: "inline",
  atom: true,
  selectable: true,
  draggable: true,
  marks: "",
  addAttributes() {
    return {
      customEmojiId: { default: "" },
      fallbackEmoji: { default: "🙂" },
    };
  },
  parseHTML() {
    return [{
      tag: "span[data-botstudio-custom-emoji]",
      getAttrs: (element) => element instanceof HTMLElement
        ? customEmojiAttributes(
          element.dataset.customEmojiId ?? "",
          element.dataset.fallbackEmoji ?? element.textContent ?? "🙂",
        )
        : false,
    }, {
      tag: "tg-emoji",
      getAttrs: (element) => element instanceof HTMLElement
        ? customEmojiAttributes(element.getAttribute("emoji-id") ?? "", element.textContent ?? "🙂")
        : false,
    }];
  },
  renderHTML({ node, HTMLAttributes }) {
    return ["span", mergeAttributes(HTMLAttributes, {
      "data-botstudio-custom-emoji": "true",
      "data-custom-emoji-id": node.attrs.customEmojiId,
      "data-fallback-emoji": node.attrs.fallbackEmoji,
    }), String(node.attrs.fallbackEmoji)];
  },
  renderText({ node }) {
    return String(node.attrs.fallbackEmoji);
  },
  addNodeView() {
    return ReactNodeViewRenderer(CustomEmojiNodeView);
  },
});

function customEmojiAttributes(customEmojiId: string, fallbackEmoji: string) {
  if (!/^\d+$/.test(customEmojiId) || !isValidCustomEmojiFallback(fallbackEmoji)) return false;
  return { customEmojiId, fallbackEmoji };
}

export const ExpandableBlockquote = Node.create({
  name: "expandableBlockquote",
  group: "block",
  content: "block+",
  defining: true,
  parseHTML() {
    return [{ tag: "blockquote[data-expandable='true']" }, { tag: "blockquote[expandable]" }];
  },
  renderHTML({ HTMLAttributes }) {
    return ["blockquote", mergeAttributes(HTMLAttributes, {
      "data-expandable": "true",
      class: "view-rich-editor__expandable-quote",
    }), 0];
  },
});

export const LegacyTemplateNode = Node.create({
  name: "legacyTemplate",
  group: "block",
  atom: true,
  selectable: true,
  isolating: true,
  addAttributes() {
    return { source: { default: "" } };
  },
  parseHTML() {
    return [{
      tag: "div[data-botstudio-legacy-template]",
      getAttrs: (element) => element instanceof HTMLElement
        ? { source: element.dataset.source ?? element.textContent ?? "" }
        : false,
    }];
  },
  renderHTML({ node, HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, {
      "data-botstudio-legacy-template": "true",
      "data-source": node.attrs.source,
    }), String(node.attrs.source)];
  },
  renderText({ node }) {
    return String(node.attrs.source);
  },
  addNodeView() {
    return ReactNodeViewRenderer(LegacyTemplateNodeView);
  },
});

/**
 * Adds a private ProseMirror slice alongside the normal HTML/plain-text copy.
 * It is deliberately schema-local and never crosses the Electron bridge.
 */
export const InternalClipboard = Extension.create({
  name: "botstudioInternalClipboard",
  addProseMirrorPlugins() {
    return [new Plugin({
      props: {
        handleDOMEvents: {
          copy: (view, event) => writeSelectionToClipboard(view, event as ClipboardEvent, false),
          cut: (view, event) => writeSelectionToClipboard(view, event as ClipboardEvent, true),
          paste: (view, event) => {
            const clipboardEvent = event as ClipboardEvent;
            const raw = clipboardEvent.clipboardData?.getData(INTERNAL_CONTENT_CLIPBOARD_MIME);
            if (!raw || raw.length > MAX_INTERNAL_CLIPBOARD_BYTES) return false;
            try {
              const slice = Slice.fromJSON(view.state.schema, JSON.parse(raw));
              view.dispatch(view.state.tr.replaceSelection(slice).scrollIntoView());
              clipboardEvent.preventDefault();
              return true;
            } catch {
              return false;
            }
          },
        },
      },
    })];
  },
});

function writeSelectionToClipboard(
  view: EditorView,
  event: ClipboardEvent,
  cut: boolean,
): boolean {
  const clipboard = event.clipboardData;
  if (!clipboard || view.state.selection.empty) return false;
  const slice = view.state.selection.content();
  const serialized = view.serializeForClipboard(slice);
  try {
    clipboard.clearData();
    clipboard.setData("text/html", serialized.dom.innerHTML);
    clipboard.setData("text/plain", serialized.text);
    clipboard.setData(INTERNAL_CONTENT_CLIPBOARD_MIME, JSON.stringify(slice.toJSON()));
  } catch {
    // Let ProseMirror's default path restore standard HTML/plain-text copy if
    // Chromium rejects a private MIME type.
    return false;
  }
  event.preventDefault();
  if (cut) view.dispatch(view.state.tr.deleteSelection().scrollIntoView().setMeta("uiEvent", "cut"));
  return true;
}

const VariableNodeView = memo(function VariableNodeView({ node, selected }: ReactNodeViewProps) {
  const path = String(node.attrs.path ?? "");
  const field = findContextField(path);
  const label = field?.label ?? path;
  const group = field?.group ?? "Unknown variable";
  return (
    <NodeViewWrapper
      as="span"
      className={`view-rich-variable${selected ? " is-selected" : ""}${field ? "" : " is-unresolved"}`}
      data-testid="rich-variable"
      title={field ? `${field.description}\n\n${path}` : `Unknown context field: ${path}`}
      aria-label={`${group}: ${label}`}
    >
      {field ? <UserRound aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
      <span>{group}</span><span aria-hidden="true">·</span><strong>{label}</strong>
    </NodeViewWrapper>
  );
});

const CustomEmojiNodeView = memo(function CustomEmojiNodeView({ node, selected, deleteNode, updateAttributes }: ReactNodeViewProps) {
  const id = String(node.attrs.customEmojiId ?? "");
  const fallback = String(node.attrs.fallbackEmoji ?? "🙂");
  const [menuOpen, setMenuOpen] = useState(false);
  const [replacementId, setReplacementId] = useState(id);
  const [replacementFallback, setReplacementFallback] = useState(fallback);
  const [favorite, setFavorite] = useState(() =>
    loadCustomEmojiLibrary(safeLocalStorage()).favorites.some((item) => item.id === id),
  );
  const toggleFavorite = () => {
    const storage = safeLocalStorage();
    const next = toggleFavoriteCustomEmoji(loadCustomEmojiLibrary(storage), { id, fallback });
    saveCustomEmojiLibrary(storage, next);
    setFavorite(next.favorites.some((item) => item.id === id));
    setMenuOpen(false);
  };
  const replaceEmoji = () => {
    if (!/^\d+$/.test(replacementId.trim()) || !isValidCustomEmojiFallback(replacementFallback.trim())) return;
    updateAttributes({ customEmojiId: replacementId.trim(), fallbackEmoji: replacementFallback.trim() });
    setMenuOpen(false);
  };
  return (
    <NodeViewWrapper
      as="span"
      className={`view-rich-custom-emoji${selected ? " is-selected" : ""}`}
      data-testid="rich-custom-emoji"
      data-custom-emoji-id={id}
      title={`Custom emoji · ${id}`}
      aria-label={`Custom emoji ${fallback}, ID ${id}`}
      onContextMenu={(event: ReactMouseEvent) => { event.preventDefault(); setMenuOpen(true); }}
    >
      <CustomEmojiMedia id={id} fallback={fallback} />
      {menuOpen ? <span className="view-rich-custom-emoji__menu" role="dialog" aria-label={`Custom emoji ${id} actions`} contentEditable={false} onMouseDown={(event) => event.stopPropagation()}>
        <code>{id}</code>
        <button type="button" onClick={toggleFavorite}>{favorite ? "Remove from favorites" : "Add to favorites"}</button>
        <button type="button" onClick={() => void navigator.clipboard?.writeText(id).catch(() => undefined)}>Copy ID</button>
        <label><span>ID</span><input aria-label="Replacement custom emoji ID" value={replacementId} onChange={(event) => setReplacementId(event.target.value)} /></label>
        <label><span>Fallback</span><input aria-label="Replacement custom emoji fallback" value={replacementFallback} onChange={(event) => setReplacementFallback(event.target.value)} /></label>
        <button type="button" onClick={replaceEmoji}>Replace</button>
        <button type="button" className="is-danger" onClick={deleteNode}>Delete</button>
        <button type="button" onClick={() => setMenuOpen(false)}>Close</button>
      </span> : null}
    </NodeViewWrapper>
  );
});

function safeLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

const LegacyTemplateNodeView = memo(function LegacyTemplateNodeView({ node, selected }: ReactNodeViewProps) {
  const source = String(node.attrs.source ?? "");
  return (
    <NodeViewWrapper
      className={`view-rich-legacy${selected ? " is-selected" : ""}`}
      data-testid="rich-legacy-template"
      aria-label="Preserved legacy template source"
      title="This source is kept exactly and cannot be edited visually yet."
    >
      <span className="view-rich-legacy__label"><Braces aria-hidden="true" />Preserved source</span>
      <code>{source}</code>
    </NodeViewWrapper>
  );
});
