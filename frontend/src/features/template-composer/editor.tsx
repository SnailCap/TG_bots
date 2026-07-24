import {
  type CompositionEvent,
  memo,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { ContextAutocomplete, UserIcon } from "./autocomplete";
import { findContextField, searchContextFields, type ContextFieldDefinition } from "./context-catalog";
import {
  FormattingDialog,
  type FormattingDialogResult,
  type FormattingDialogState,
} from "./formatting-dialog";
import { FormattingToolbar, type FormattingToolbarState } from "./formatting-toolbar";
import type { TemplateDocument, TemplateFormatNode, TemplateNode } from "./model";
import { sanitizePastedHtml } from "./paste-sanitizer";
import { serializeTemplate } from "./serializer";
import {
  CODE_FORMATS,
  EXCLUSIVE_INLINE_FORMATS,
  FORMAT_KIND_BY_ALIAS,
  QUOTE_FORMATS,
  formattingActionForHotkey,
  parseTelegramMentionHref,
  renderTelegramDateTime,
  telegramMentionHref,
  type TelegramFormattingAction,
  type TelegramFormatKind,
} from "./telegram-formatting";

type AutocompleteState = {
  query: string;
  activeIndex: number;
  position: { left: number; top: number };
};

export const VisualTemplateEditor = memo(function VisualTemplateEditor({
  document,
  onChange,
}: {
  document: TemplateDocument;
  onChange(source: string): void;
}) {
  const shellRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const isComposingRef = useRef(false);
  const pendingCaret = useRef<number | null>(null);
  const savedRange = useRef<Range | null>(null);
  const source = serializeTemplate(document);
  const historyRef = useRef({ entries: [source], index: 0 });
  const [autocomplete, setAutocomplete] = useState<AutocompleteState | null>(null);
  const [formatToolbar, setFormatToolbar] = useState<FormattingToolbarState | null>(null);
  const [dialog, setDialog] = useState<FormattingDialogState | null>(null);
  const suggestions = autocomplete ? searchContextFields(autocomplete.query) : [];
  const renderedNodes = document.nodes.length ? document.nodes : [{ type: "text" as const, text: "" }];
  const needsTrailingTextSlot = renderedNodes.at(-1)?.type !== "text";

  const restorePendingCaret = () => {
    const editor = editorRef.current;
    const caret = pendingCaret.current;
    if (caret === null || !editor) return;
    restoreCaretOffset(editor, caret);
    pendingCaret.current = null;
  };
  const deferCaretRestore = () => queueMicrotask(restorePendingCaret);

  if (historyRef.current.entries[historyRef.current.index] !== source) {
    historyRef.current = { entries: [source], index: 0 };
  }

  const publishSource = (nextSource: string) => {
    const history = historyRef.current;
    if (history.entries[history.index] !== nextSource) {
      history.entries.splice(history.index + 1);
      history.entries.push(nextSource);
      if (history.entries.length > 100) history.entries.shift();
      history.index = history.entries.length - 1;
    }
    onChange(nextSource);
    return nextSource !== source;
  };

  const replayHistory = (direction: -1 | 1) => {
    const history = historyRef.current;
    const nextIndex = history.index + direction;
    if (nextIndex < 0 || nextIndex >= history.entries.length) return;
    history.index = nextIndex;
    const editor = editorRef.current;
    if (editor) pendingCaret.current = getSelectionOffset(editor);
    onChange(history.entries[nextIndex]);
  };

  useLayoutEffect(() => {
    restorePendingCaret();
  }, [document]);

  useEffect(() => {
    const updateSelectionUi = () => {
      if (dialog) return;
      const editor = editorRef.current;
      const shell = shellRef.current;
      const selection = window.getSelection();
      if (!editor || !shell || !selection?.rangeCount || selection.isCollapsed || !selectionInside(editor, selection)) {
        setFormatToolbar(null);
        return;
      }
      const range = selection.getRangeAt(0);
      savedRange.current = range.cloneRange();
      const rangeRect = safeRangeRect(range, editor);
      const shellRect = shell.getBoundingClientRect();
      const estimatedWidth = Math.min(390, Math.max(shellRect.width - 8, 220));
      const left = clamp(rangeRect.left - shellRect.left + rangeRect.width / 2 - estimatedWidth / 2, 4, Math.max(shellRect.width - estimatedWidth - 4, 4));
      const above = rangeRect.top - shellRect.top - 45;
      const top = above >= 4 ? above : rangeRect.bottom - shellRect.top + 8;
      const activeFormats = activeFormatsForRange(range, editor);
      setFormatToolbar({
        position: { left, top },
        activeFormats,
        multiline: range.toString().includes("\n"),
        codeLocked: activeFormats.has("inline-code") || activeFormats.has("code-block"),
      });
    };
    window.document.addEventListener("selectionchange", updateSelectionUi);
    window.addEventListener("resize", updateSelectionUi);
    return () => {
      window.document.removeEventListener("selectionchange", updateSelectionUi);
      window.removeEventListener("resize", updateSelectionUi);
    };
  }, [dialog]);

  const commitDom = (caretOffset?: number) => {
    const editor = editorRef.current;
    if (!editor) return;
    const nextSource = serializeTemplate(readEditorDocument(editor));
    pendingCaret.current = caretOffset ?? getSelectionOffset(editor);
    const willRerender = publishSource(nextSource);
    setAutocomplete(null);
    setFormatToolbar(null);
    if (!willRerender) deferCaretRestore();
  };

  const publishEditedDom = (editedRoot: HTMLElement, editedRange: Range) => {
    const nextSource = serializeTemplate(readEditorDocument(editedRoot));
    pendingCaret.current = getRangeOffset(editedRoot, editedRange, true);
    const willRerender = publishSource(nextSource);
    savedRange.current = null;
    setAutocomplete(null);
    setFormatToolbar(null);
    if (!willRerender) deferCaretRestore();
  };

  const updateAutocomplete = () => {
    const editor = editorRef.current;
    if (!editor) return;
    const trigger = getAutocompleteTrigger(editor);
    if (!trigger) {
      setAutocomplete(null);
      return;
    }
    const rect = safeRangeRect(trigger.range, editor);
    const editorRect = editor.getBoundingClientRect();
    setAutocomplete((current) => ({
      query: trigger.query,
      activeIndex: Math.min(current?.activeIndex ?? 0, Math.max(searchContextFields(trigger.query).length - 1, 0)),
      position: {
        left: Math.max(4, Math.min(rect.left - editorRect.left, Math.max(editorRect.width - 272, 4))),
        top: Math.max(36, rect.bottom - editorRect.top + 6),
      },
    }));
  };

  const chooseField = (field: ContextFieldDefinition) => {
    const editor = editorRef.current;
    if (!editor) return;
    const trigger = getAutocompleteTrigger(editor);
    if (!trigger) return;
    trigger.range.deleteContents();
    const inserted = window.document.createTextNode(`{{ ${field.path} }}`);
    trigger.range.insertNode(inserted);
    setCaret(inserted, inserted.textContent?.length ?? 0);
    setAutocomplete(null);
    commitDom();
  };

  const handleInput = (_event: FormEvent<HTMLDivElement>) => {
    if (isComposingRef.current) return;
    commitDom();
    updateAutocomplete();
  };

  const handleCompositionStart = (_event: CompositionEvent<HTMLDivElement>) => {
    isComposingRef.current = true;
    setAutocomplete(null);
  };

  const handleCompositionEnd = (_event: CompositionEvent<HTMLDivElement>) => {
    isComposingRef.current = false;
    commitDom();
    updateAutocomplete();
  };

  const runFormattingAction = (action: TelegramFormattingAction): boolean => {
    const editor = editorRef.current;
    if (!editor) return false;
    const range = currentEditorRange(editor, savedRange.current);
    if (!range) return false;
    if (range.collapsed) return applyPendingNativeFormat(action.kind);
    savedRange.current = range.cloneRange();

    if (action.dialog) {
      const existing = existingFormatDetails(range, action.kind);
      setDialog({
        kind: action.dialog,
        selectedText: range.toString(),
        existing,
      });
      return true;
    }

    const snapshot = cloneEditingRange(editor, range);
    if (!snapshot) return false;
    const commandRange = action.kind === "quote" || action.kind === "expandable-quote"
      ? removeOtherQuoteType(snapshot.range, action.kind, snapshot.root)
      : snapshot.range;
    const resultRange = toggleFormat(commandRange, action.kind, snapshot.root);
    publishEditedDom(snapshot.root, resultRange);
    return true;
  };

  const clearFormatting = (): boolean => {
    const editor = editorRef.current;
    if (!editor) return false;
    const range = currentEditorRange(editor, savedRange.current);
    if (!range || range.collapsed) return false;
    const snapshot = cloneEditingRange(editor, range);
    if (!snapshot) return false;
    const resultRange = clearRangeFormatting(snapshot.range, snapshot.root);
    publishEditedDom(snapshot.root, resultRange);
    return true;
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (isComposingRef.current) return;

    if ((event.ctrlKey || event.metaKey) && !event.altKey) {
      const key = event.key.toLowerCase();
      const redo = key === "y" || (key === "z" && event.shiftKey);
      const undo = key === "z" && !event.shiftKey;
      if (undo || redo) {
        event.preventDefault();
        event.stopPropagation();
        replayHistory(redo ? 1 : -1);
        return;
      }

      if (event.code === "KeyN" && event.shiftKey && clearFormatting()) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }

      const action = formattingActionForHotkey(event.nativeEvent);
      if (action && runFormattingAction(action)) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
    }

    if (autocomplete) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        setAutocomplete((current) => current ? {
          ...current,
          activeIndex: suggestions.length ? (current.activeIndex + direction + suggestions.length) % suggestions.length : 0,
        } : null);
        return;
      }
      if (event.key === "Enter" && suggestions.length) {
        event.preventDefault();
        chooseField(suggestions[autocomplete.activeIndex] ?? suggestions[0]);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setAutocomplete(null);
        return;
      }
    }

    if ((event.key === "Backspace" || event.key === "Delete") && editorRef.current) {
      const token = adjacentAtomicToken(editorRef.current, event.key === "Backspace" ? -1 : 1);
      if (token) {
        event.preventDefault();
        const caret = getSelectionOffset(editorRef.current) - (event.key === "Backspace" ? 1 : 0);
        const nodePath = parseNodePath(token.dataset.nodePath);
        if (!nodePath) return;
        const nextDocument = removeNodeAtPath(document, nodePath);
        pendingCaret.current = Math.max(0, caret);
        const willRerender = publishSource(serializeTemplate(nextDocument));
        setAutocomplete(null);
        setFormatToolbar(null);
        if (!willRerender) deferCaretRestore();
      }
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    event.preventDefault();
    const html = event.clipboardData.getData("text/html");
    if (html) insertHtml(sanitizePastedHtml(html));
    else insertPlainText(event.clipboardData.getData("text/plain"));
    collapseSelectionToEnd();
    commitDom();
    updateAutocomplete();
  };

  const applyDialog = (result: FormattingDialogResult) => {
    const editor = editorRef.current;
    const range = savedRange.current;
    if (!editor || !range) return;
    const snapshot = cloneEditingRange(editor, range);
    if (!snapshot) return;
    let commandRange = snapshot.range;
    if (result.kind === "custom-emoji") {
      commandRange = replaceRangeWithSpecial(commandRange, result.kind, { emojiId: result.emojiId, fallback: result.fallback });
    } else if (result.kind === "date-time") {
      commandRange = replaceRangeWithSpecial(commandRange, result.kind, {
        unix: String(result.unix),
        dateTimeFormat: result.dateTimeFormat,
        fallback: result.fallback,
      });
    } else {
      if (result.kind === "link" || result.kind === "mention") commandRange = removeExclusiveFormats(commandRange, snapshot.root);
      if (result.kind === "code-block") {
        commandRange = clearRangeFormatting(commandRange, snapshot.root);
      }
      commandRange = wrapRange(commandRange, result.kind, snapshot.root, { ...result });
    }
    setDialog(null);
    publishEditedDom(snapshot.root, commandRange);
  };

  const removeDialogFormatting = () => {
    const editor = editorRef.current;
    const range = savedRange.current;
    if (!editor || !range || !dialog) return;
    const snapshot = cloneEditingRange(editor, range);
    if (!snapshot) return;
    const resultRange = removeFormatFromRange(snapshot.range, dialog.kind, snapshot.root);
    setDialog(null);
    publishEditedDom(snapshot.root, resultRange);
  };

  const cancelDialog = () => {
    const editor = editorRef.current;
    const range = savedRange.current;
    setDialog(null);
    if (editor && range) {
      editor.focus();
      restoreRange(range);
    }
  };

  return (
    <div className="template-visual-shell" ref={shellRef}>
      <div
        ref={editorRef}
      className="template-visual-editor"
        contentEditable
        suppressContentEditableWarning
        spellCheck={false}
        role="textbox"
        aria-label="Visual message content"
        aria-multiline="true"
        data-empty={document.nodes.length === 0 || (document.nodes.length === 1 && document.nodes[0].type === "text" && !document.nodes[0].text) ? "true" : "false"}
        onInput={handleInput}
        onCompositionStart={handleCompositionStart}
        onCompositionEnd={handleCompositionEnd}
        onKeyDown={handleKeyDown}
        onKeyUp={(event) => {
          if (!isComposingRef.current && !["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(event.key)) updateAutocomplete();
        }}
        onPaste={handlePaste}
      >
        {renderedNodes.map((node, index) => <TemplateNodeView key={`${index}-${nodeKey(node)}`} node={node} path={[index]} />)}
        {needsTrailingTextSlot ? <TemplateNodeView key="trailing-text-slot" node={{ type: "text", text: "" }} path={[renderedNodes.length]} /> : null}
      </div>
      {autocomplete ? <ContextAutocomplete fields={suggestions} activeIndex={autocomplete.activeIndex} position={autocomplete.position} onChoose={chooseField} /> : null}
      {formatToolbar ? <FormattingToolbar state={formatToolbar} onAction={runFormattingAction} onClear={clearFormatting} /> : null}
      {dialog ? (
        <FormattingDialog
          key={dialog.kind}
          dialog={dialog}
          position={{
            left: formatToolbar?.position.left ?? 8,
            top: (formatToolbar?.position.top ?? 8) + 42,
          }}
          onApply={applyDialog}
          onRemove={removeDialogFormatting}
          onCancel={cancelDialog}
        />
      ) : null}
    </div>
  );
});

function TemplateNodeView({ node, path }: { node: TemplateNode; path: readonly number[] }) {
  const nodePath = path.join(".");
  if (node.type === "text") return <span data-template-node="text" data-node-path={nodePath}>{node.text}</span>;
  if (node.type === "context-token") {
    const field = findContextField(node.path);
    if (!field) return <UnresolvedToken path={node.path} source={node.source ?? `{{ ${node.path} }}`} nodePath={nodePath} />;
    return (
      <span
        className="context-token"
        contentEditable={false}
        data-template-node="context-token"
        data-template-atomic="true"
        data-node-path={nodePath}
        data-field-id={field.id}
        data-path={field.path}
        data-source={node.source ?? ""}
        tabIndex={0}
        title={fieldTooltip(field)}
        aria-label={`${field.group}: ${field.label}`}
      >
        <UserIcon /><span>{field.group}</span><span className="context-token__separator">·</span><strong>{field.label}</strong>
      </span>
    );
  }
  if (node.type === "unresolved-token") return <UnresolvedToken path={node.path} source={node.source} nodePath={nodePath} />;
  if (node.type === "raw-fragment") {
    return (
      <span
        className="context-token context-token--raw"
        contentEditable={false}
        data-template-node="raw-fragment"
        data-template-atomic="true"
        data-node-path={nodePath}
        data-fragment-kind={node.fragmentKind ?? "jinja"}
        data-source={node.source}
        tabIndex={0}
        title={`This fragment is preserved, but cannot be represented in Visual mode.\n\n${node.source}`}
        aria-label={`Unsupported ${node.fragmentKind === "html" ? "HTML" : "Jinja"} fragment: ${node.source}`}
      ><WarningIcon /><code>{node.source}</code></span>
    );
  }
  return <TelegramFormatView node={node} path={path} />;
}

function TelegramFormatView({ node, path }: { node: TemplateFormatNode; path: readonly number[] }) {
  const common = {
    "data-telegram-format": node.format,
  };
  const children = node.children.map((child, index) => <TemplateNodeView node={child} path={[...path, index]} key={`${index}-${nodeKey(child)}`} />);
  if (node.format === "bold") return <b {...common}>{children}</b>;
  if (node.format === "italic") return <i {...common}>{children}</i>;
  if (node.format === "underline") return <u {...common}>{children}</u>;
  if (node.format === "strikethrough") return <s {...common}>{children}</s>;
  if (node.format === "spoiler") return <span {...common} className="telegram-spoiler" tabIndex={0} title="Spoiler — focus or hover to reveal while editing">{children}</span>;
  if (node.format === "link") return <a {...common} data-href={node.href} href={node.href} onClick={(event) => event.preventDefault()}>{children}</a>;
  if (node.format === "mention") return <a {...common} data-user-id={node.userId} href={node.href ?? telegramMentionHref(node.userId ?? "")} onClick={(event) => event.preventDefault()}>{children}</a>;
  if (node.format === "inline-code") return <code {...common}>{children}</code>;
  if (node.format === "code-block") {
    return <pre {...common} data-language={node.language ?? ""}>{node.language ? <span className="telegram-code-language" data-template-decoration="true" contentEditable={false}>{node.language}</span> : null}{children}</pre>;
  }
  if (node.format === "quote" || node.format === "expandable-quote") {
    return (
      <blockquote {...common} data-expandable={node.format === "expandable-quote" ? "true" : "false"}>
        {children}
        {node.format === "expandable-quote" ? <span className="telegram-expandable-indicator" data-template-decoration="true" contentEditable={false} aria-label="Expandable quote">Expandable</span> : null}
      </blockquote>
    );
  }
  if (node.format === "custom-emoji") {
    return (
      <span
        {...common}
        className="telegram-custom-emoji"
        contentEditable={false}
        data-template-atomic="true"
        data-node-path={path.join(".")}
        data-emoji-id={node.emojiId}
        data-fallback={node.fallback}
        tabIndex={0}
        title={`Custom emoji ${node.emojiId}`}
        aria-label={`Custom emoji: ${node.fallback}`}
      >{node.fallback}</span>
    );
  }
  const preview = renderTelegramDateTime(node.unix ?? Number.NaN, node.dateTimeFormat ?? "", node.fallback ?? "");
  return (
    <span
      {...common}
      className="telegram-date-time"
      contentEditable={false}
      data-template-atomic="true"
      data-node-path={path.join(".")}
      data-unix={node.unix}
      data-date-time-format={node.dateTimeFormat ?? ""}
      data-fallback={node.fallback}
      tabIndex={0}
      title={`Dynamic date · Unix ${node.unix} · format ${node.dateTimeFormat || "fallback"}`}
      aria-label={`Dynamic date and time: ${preview}`}
    ><ClockIcon />{preview}</span>
  );
}

function UnresolvedToken({ path, source, nodePath }: { path: string; source: string; nodePath: string }) {
  return (
    <span
      className="context-token context-token--unresolved"
      contentEditable={false}
      data-template-node="unresolved-token"
      data-template-atomic="true"
      data-node-path={nodePath}
      data-path={path}
      data-source={source}
      tabIndex={0}
      title={`Unknown field in the current context catalog.\n\n${path}`}
      aria-label={`Unknown context field: ${path}`}
    ><WarningIcon /><code>{path}</code></span>
  );
}

function WarningIcon() {
  return <svg className="context-warning-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.1 14 13H2L8 2.1Z" /><path d="M8 5.6v3.6M8 11.4v.1" /></svg>;
}

function ClockIcon() {
  return <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.4" /><path d="M8 5v3l2.2 1.3" /></svg>;
}

function fieldTooltip(field: ContextFieldDefinition): string {
  return `${field.group} · ${field.label}\n\n${field.path}\nType: ${field.valueType}\n${field.optional ? "Optional field" : "Required field"}\n${field.description}`;
}

function nodeKey(node: TemplateNode): string {
  if (node.type === "text") return node.text;
  if (node.type === "context-token") return `${node.path}:${node.source ?? ""}`;
  if (node.type === "format") return `${node.format}:${node.href ?? node.userId ?? node.language ?? node.emojiId ?? node.unix ?? ""}`;
  return node.source;
}

function parseNodePath(value: string | undefined): number[] | null {
  if (!value || !/^\d+(?:\.\d+)*$/.test(value)) return null;
  return value.split(".").map(Number);
}

function removeNodeAtPath(document: TemplateDocument, path: readonly number[]): TemplateDocument {
  const nextDocument = structuredClone(document);
  let nodes = nextDocument.nodes;
  for (const index of path.slice(0, -1)) {
    const parent = nodes[index];
    if (parent?.type !== "format") return nextDocument;
    nodes = parent.children;
  }
  nodes.splice(path.at(-1) ?? -1, 1);
  return nextDocument;
}

export function readEditorDocument(root: HTMLElement): TemplateDocument {
  return { nodes: mergeTextNodes(readDomChildren(root, root)) };
}

function readDomChildren(parent: ParentNode, root: HTMLElement): TemplateNode[] {
  const nodes: TemplateNode[] = [];
  for (const child of Array.from(parent.childNodes)) readDomNode(child, nodes, root);
  return mergeTextNodes(nodes);
}

function readDomNode(node: Node, nodes: TemplateNode[], root: HTMLElement): void {
  if (node.nodeType === Node.TEXT_NODE) {
    pushText(nodes, node.textContent ?? "");
    return;
  }
  if (!(node instanceof HTMLElement)) return;
  if (node.dataset.templateDecoration === "true") return;
  const kind = node.dataset.templateNode;
  if (kind === "context-token") {
    nodes.push({
      type: "context-token",
      fieldId: node.dataset.fieldId ?? "",
      path: node.dataset.path ?? "",
      source: node.dataset.source || undefined,
    });
    return;
  }
  if (kind === "unresolved-token") {
    nodes.push({ type: "unresolved-token", path: node.dataset.path ?? "", source: node.dataset.source ?? "" });
    return;
  }
  if (kind === "raw-fragment") {
    nodes.push({
      type: "raw-fragment",
      source: node.dataset.source ?? "",
      fragmentKind: node.dataset.fragmentKind === "html" ? "html" : "jinja",
    });
    return;
  }
  if (node.tagName === "BR") {
    pushText(nodes, "\n");
    return;
  }

  const format = formatKindForElement(node);
  if (format) {
    nodes.push(readFormatNode(node, format, root));
    return;
  }

  const isBlock = node.parentElement === root && /^(DIV|P)$/.test(node.tagName);
  if (isBlock && nodes.length && !endsWithLineBreak(nodes)) pushText(nodes, "\n");
  for (const child of Array.from(node.childNodes)) readDomNode(child, nodes, root);
}

function readFormatNode(element: HTMLElement, format: TelegramFormatKind, root: HTMLElement): TemplateFormatNode {
  if (format === "custom-emoji") {
    const fallback = element.dataset.fallback ?? element.textContent ?? "";
    return { type: "format", format, emojiId: element.dataset.emojiId ?? element.getAttribute("emoji-id") ?? "", fallback, children: [{ type: "text", text: fallback }] };
  }
  if (format === "date-time") {
    const fallback = element.dataset.fallback ?? element.textContent ?? "";
    return {
      type: "format",
      format,
      unix: Number(element.dataset.unix ?? element.getAttribute("unix")),
      dateTimeFormat: element.dataset.dateTimeFormat ?? element.getAttribute("format") ?? "",
      fallback,
      children: [{ type: "text", text: fallback }],
    };
  }
  if (format === "code-block") {
    const languageCode = element.children.length === 1 && element.children[0].tagName.toLowerCase() === "code"
      ? element.children[0] as HTMLElement
      : null;
    const language = element.dataset.language
      || languageCode?.className.match(/(?:^|\s)language-([A-Za-z0-9_+#.-]+)(?:\s|$)/)?.[1]
      || undefined;
    const contentParent = languageCode ?? element;
    const children = readDomChildren(contentParent, root);
    return { type: "format", format, language, children };
  }
  const children = readDomChildren(element, root);
  if (format === "link") return { type: "format", format, href: element.dataset.href ?? element.getAttribute("href") ?? "", children };
  if (format === "mention") {
    const href = element.getAttribute("href") ?? "";
    return { type: "format", format, href, userId: element.dataset.userId ?? parseTelegramMentionHref(href) ?? "", children };
  }
  return { type: "format", format, children };
}

function formatKindForElement(element: HTMLElement): TelegramFormatKind | null {
  const dataFormat = element.dataset.telegramFormat as TelegramFormatKind | undefined;
  if (dataFormat) return dataFormat;
  const tag = element.tagName.toLowerCase();
  if (tag === "span" && element.classList.contains("tg-spoiler")) return "spoiler";
  if (tag === "a") return parseTelegramMentionHref(element.getAttribute("href") ?? "") ? "mention" : "link";
  if (tag === "blockquote") return element.hasAttribute("expandable") ? "expandable-quote" : "quote";
  if (tag === "pre") return "code-block";
  return FORMAT_KIND_BY_ALIAS.get(tag) ?? null;
}

function mergeTextNodes(nodes: TemplateNode[]): TemplateNode[] {
  const merged: TemplateNode[] = [];
  for (const node of nodes) {
    if (node.type === "text") pushText(merged, node.text);
    else merged.push(node);
  }
  return merged;
}

function pushText(nodes: TemplateNode[], text: string): void {
  if (!text) return;
  const previous = nodes.at(-1);
  if (previous?.type === "text") previous.text += text;
  else nodes.push({ type: "text", text });
}

function endsWithLineBreak(nodes: TemplateNode[]): boolean {
  const last = nodes.at(-1);
  return last?.type === "text" && last.text.endsWith("\n");
}

function getAutocompleteTrigger(root: HTMLElement): { query: string; range: Range } | null {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !selection.isCollapsed || !root.contains(selection.anchorNode)) return null;
  const range = selection.getRangeAt(0);
  if (range.startContainer.nodeType !== Node.TEXT_NODE) return null;
  const text = range.startContainer.textContent?.slice(0, range.startOffset) ?? "";
  const match = text.match(/\$([^\s$]*)$/u);
  if (!match) return null;
  const triggerRange = window.document.createRange();
  triggerRange.setStart(range.startContainer, range.startOffset - match[0].length);
  triggerRange.setEnd(range.startContainer, range.startOffset);
  return { query: match[1], range: triggerRange };
}

function getSelectionOffset(root: HTMLElement): number {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !root.contains(selection.anchorNode)) return textLength(root);
  return getRangeOffset(root, selection.getRangeAt(0), false);
}

function getRangeOffset(root: HTMLElement, range: Range, useEnd: boolean): number {
  const targetNode = useEnd ? range.endContainer : range.startContainer;
  const targetOffset = useEnd ? range.endOffset : range.startOffset;
  let offset = 0;
  let found = false;
  const visit = (node: Node) => {
    if (found) return;
    if (node === targetNode) {
      if (node.nodeType === Node.TEXT_NODE) {
        offset += targetOffset;
      } else {
        for (const child of Array.from(node.childNodes).slice(0, targetOffset)) offset += domNodeLength(child);
      }
      found = true;
      return;
    }
    if (node instanceof HTMLElement && node.dataset.templateAtomic === "true") {
      offset += 1;
      return;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      offset += node.textContent?.length ?? 0;
      return;
    }
    for (const child of Array.from(node.childNodes)) visit(child);
  };
  for (const child of Array.from(root.childNodes)) visit(child);
  return offset;
}

function domNodeLength(node: Node): number {
  if (node instanceof HTMLElement && node.dataset.templateDecoration === "true") return 0;
  if (node instanceof HTMLElement && node.dataset.templateAtomic === "true") return 1;
  if (node.nodeType === Node.TEXT_NODE) return node.textContent?.length ?? 0;
  return Array.from(node.childNodes).reduce((length, child) => length + domNodeLength(child), 0);
}

function restoreCaretOffset(root: HTMLElement, target: number): void {
  let consumed = 0;
  let restored = false;
  const visit = (node: Node) => {
    if (restored) return;
    if (node instanceof HTMLElement && node.dataset.templateAtomic === "true") {
      consumed += 1;
      return;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      const length = node.textContent?.length ?? 0;
      if (consumed + length >= target) {
        setCaret(node, Math.max(0, target - consumed));
        restored = true;
        return;
      }
      consumed += length;
      return;
    }
    for (const child of Array.from(node.childNodes)) visit(child);
  };
  for (const child of Array.from(root.childNodes)) visit(child);
  if (restored) return;
  const emptyTextNode = root.querySelector<HTMLElement>("[data-template-node='text']");
  if (emptyTextNode) {
    setCaret(emptyTextNode, 0);
    return;
  }
  setCaret(root, target === 0 ? 0 : root.childNodes.length);
}

function setCaret(node: Node, offset: number): void {
  const range = window.document.createRange();
  const maximumOffset = node.nodeType === Node.TEXT_NODE ? node.textContent?.length ?? 0 : node.childNodes.length;
  range.setStart(node, Math.min(offset, maximumOffset));
  range.collapse(true);
  restoreRange(range);
}

function textLength(root: HTMLElement): number {
  return readEditorDocument(root).nodes.reduce((length, node) => length + nodeLength(node), 0);
}

function nodeLength(node: TemplateNode): number {
  if (node.type === "text") return node.text.length;
  if (node.type === "format" && node.format !== "custom-emoji" && node.format !== "date-time") {
    return node.children.reduce((sum, child) => sum + nodeLength(child), 0);
  }
  return 1;
}

function adjacentAtomicToken(root: HTMLElement, direction: -1 | 1): HTMLElement | null {
  const active = window.document.activeElement;
  if (active instanceof HTMLElement && active !== root && root.contains(active) && active.dataset.templateAtomic === "true") return active;
  const selection = window.getSelection();
  if (!selection?.isCollapsed || !selection.rangeCount) return null;
  const range = selection.getRangeAt(0);
  const direct = directChildOf(root, range.startContainer);
  if (!direct) return null;
  const length = range.startContainer.textContent?.length ?? 0;
  const atBoundary = range.startContainer.nodeType === Node.TEXT_NODE
    ? direction === -1 ? range.startOffset === 0 : range.startOffset === length
    : true;
  if (!atBoundary) return null;
  const sibling = direction === -1 ? direct.previousElementSibling : direct.nextElementSibling;
  return sibling instanceof HTMLElement && sibling.dataset.templateAtomic === "true" ? sibling : null;
}

function directChildOf(root: HTMLElement, node: Node): HTMLElement | null {
  let current = node instanceof HTMLElement ? node : node.parentElement;
  while (current?.parentElement && current.parentElement !== root) current = current.parentElement;
  return current?.parentElement === root ? current : null;
}

function insertPlainText(text: string): void {
  const selection = window.getSelection();
  if (!selection?.rangeCount) return;
  const range = selection.getRangeAt(0);
  range.deleteContents();
  const node = window.document.createTextNode(text);
  range.insertNode(node);
  setCaret(node, text.length);
}

function insertHtml(html: string): void {
  const selection = window.getSelection();
  if (!selection?.rangeCount) return;
  const range = selection.getRangeAt(0);
  const template = window.document.createElement("template");
  template.innerHTML = html;
  const last = template.content.lastChild;
  range.deleteContents();
  range.insertNode(template.content);
  if (last) {
    const next = window.document.createRange();
    next.setStartAfter(last);
    next.collapse(true);
    restoreRange(next);
  }
}

function selectionInside(root: HTMLElement, selection: Selection): boolean {
  return Boolean(root.contains(selection.anchorNode) && root.contains(selection.focusNode));
}

function currentEditorRange(root: HTMLElement, fallback: Range | null): Range | null {
  const selection = window.getSelection();
  if (selection?.rangeCount && selectionInside(root, selection)) return selection.getRangeAt(0).cloneRange();
  return fallback?.cloneRange() ?? null;
}

function cloneEditingRange(root: HTMLElement, range: Range): { root: HTMLElement; range: Range } | null {
  const startPath = childNodePath(root, range.startContainer);
  const endPath = childNodePath(root, range.endContainer);
  if (!startPath || !endPath) return null;
  const clonedRoot = root.cloneNode(true) as HTMLElement;
  const startNode = resolveChildNodePath(clonedRoot, startPath);
  const endNode = resolveChildNodePath(clonedRoot, endPath);
  if (!startNode || !endNode) return null;
  const clonedRange = window.document.createRange();
  clonedRange.setStart(startNode, Math.min(range.startOffset, maximumRangeOffset(startNode)));
  clonedRange.setEnd(endNode, Math.min(range.endOffset, maximumRangeOffset(endNode)));
  return { root: clonedRoot, range: clonedRange };
}

function childNodePath(root: Node, target: Node): number[] | null {
  const path: number[] = [];
  let current: Node | null = target;
  while (current && current !== root) {
    const parent: Node | null = current.parentNode;
    if (!parent) return null;
    const index = Array.prototype.indexOf.call(parent.childNodes, current) as number;
    if (index < 0) return null;
    path.unshift(index);
    current = parent;
  }
  return current === root ? path : null;
}

function resolveChildNodePath(root: Node, path: readonly number[]): Node | null {
  let current: Node = root;
  for (const index of path) {
    const next = current.childNodes[index];
    if (!next) return null;
    current = next;
  }
  return current;
}

function maximumRangeOffset(node: Node): number {
  return node.nodeType === Node.TEXT_NODE ? node.textContent?.length ?? 0 : node.childNodes.length;
}

function safeRangeRect(range: Range, fallback: HTMLElement): DOMRect {
  if (typeof range.getBoundingClientRect === "function") {
    const rect = range.getBoundingClientRect();
    if (rect.width || rect.height || rect.left || rect.top) return rect;
  }
  return fallback.getBoundingClientRect();
}

function activeFormatsForRange(range: Range, root: HTMLElement): Set<TelegramFormatKind> {
  const leaves: Node[] = [];
  const walker = window.document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent && rangeIntersectsNode(range, node)) return NodeFilter.FILTER_ACCEPT;
      if (node instanceof HTMLElement && node.dataset.templateAtomic === "true" && rangeIntersectsNode(range, node)) return NodeFilter.FILTER_ACCEPT;
      return NodeFilter.FILTER_SKIP;
    },
  });
  while (walker.nextNode()) leaves.push(walker.currentNode);
  if (!leaves.length) return new Set();
  const formatSets = leaves.map((leaf) => formatAncestors(leaf, root));
  return new Set([...formatSets[0]].filter((format) => formatSets.every((set) => set.has(format))));
}

function formatAncestors(node: Node, root: HTMLElement): Set<TelegramFormatKind> {
  const formats = new Set<TelegramFormatKind>();
  let current = node instanceof HTMLElement ? node : node.parentElement;
  while (current && current !== root) {
    const format = formatKindForElement(current);
    if (format) formats.add(format);
    current = current.parentElement;
  }
  return formats;
}

function rangeIntersectsNode(range: Range, node: Node): boolean {
  try {
    return range.intersectsNode(node);
  } catch {
    return false;
  }
}

function toggleFormat(range: Range, format: TelegramFormatKind, root: HTMLElement): Range {
  const active = activeFormatsForRange(range, root).has(format);
  return active ? removeFormatFromRange(range, format, root) : wrapRange(range, format, root);
}

function wrapRange(
  range: Range,
  format: TelegramFormatKind,
  root: HTMLElement,
  attributes: Record<string, unknown> = {},
): Range {
  const wrapper = createFormatElement(format, attributes);
  const extracted = range.extractContents();
  if (CODE_FORMATS.has(format)) stripAllFormatElements(extracted);
  else stripFormatElements(extracted, format);
  wrapper.append(extracted);
  range.insertNode(wrapper);

  const ancestorsToLift = CODE_FORMATS.has(format)
    ? () => closestFormatAncestor(wrapper, root)
    : () => closestFormatAncestor(wrapper, root, format);
  let ancestor = ancestorsToLift();
  while (ancestor) {
    liftNodeOutOfAncestor(wrapper, ancestor);
    ancestor = ancestorsToLift();
  }
  return selectNodeContents(wrapper);
}

function removeFormatFromRange(range: Range, format: TelegramFormatKind, root: HTMLElement): Range {
  const marker = window.document.createElement("span");
  marker.dataset.formatMarker = "true";
  marker.append(range.extractContents());
  range.insertNode(marker);
  stripFormatElements(marker, format);
  let ancestor = closestFormatAncestor(marker, root, format);
  while (ancestor) {
    liftNodeOutOfAncestor(marker, ancestor);
    ancestor = closestFormatAncestor(marker, root, format);
  }
  return selectAndUnwrap(marker);
}

function clearRangeFormatting(range: Range, root: HTMLElement): Range {
  const marker = window.document.createElement("span");
  marker.dataset.formatMarker = "true";
  marker.append(range.extractContents());
  range.insertNode(marker);
  stripAllFormatElements(marker);
  let ancestor = closestFormatAncestor(marker, root);
  while (ancestor) {
    liftNodeOutOfAncestor(marker, ancestor);
    ancestor = closestFormatAncestor(marker, root);
  }
  return selectAndUnwrap(marker);
}

function removeExclusiveFormats(range: Range, root: HTMLElement): Range {
  let current = range;
  for (const format of EXCLUSIVE_INLINE_FORMATS) {
    if (format === "custom-emoji" || format === "date-time") continue;
    if (rangeHasFormat(current, root, format)) {
      current = removeFormatFromRange(current, format, root);
    }
  }
  return current;
}

function removeOtherQuoteType(range: Range, format: TelegramFormatKind, root: HTMLElement): Range {
  const other = format === "quote" ? "expandable-quote" : "quote";
  if (!rangeHasFormat(range, root, other)) return range;
  return removeFormatFromRange(range, other, root);
}

function rangeHasFormat(range: Range, root: HTMLElement, format: TelegramFormatKind): boolean {
  if (activeFormatsForRange(range, root).has(format)) return true;
  return Boolean(closestFormatAncestor(range.commonAncestorContainer, root, format));
}

function replaceRangeWithSpecial(
  range: Range,
  format: "custom-emoji" | "date-time",
  attributes: Record<string, string>,
): Range {
  const element = createFormatElement(format, attributes);
  element.textContent = attributes.fallback;
  range.deleteContents();
  range.insertNode(element);
  return selectNodeContents(element);
}

function createFormatElement(format: TelegramFormatKind, attributes: Record<string, unknown> = {}): HTMLElement {
  const tag = format === "bold" ? "b"
    : format === "italic" ? "i"
      : format === "underline" ? "u"
        : format === "strikethrough" ? "s"
          : format === "spoiler" ? "tg-spoiler"
            : format === "link" || format === "mention" ? "a"
              : format === "inline-code" ? "code"
                : format === "code-block" ? "pre"
                  : format === "quote" || format === "expandable-quote" ? "blockquote"
                    : format === "custom-emoji" ? "tg-emoji"
                      : "tg-time";
  const element = window.document.createElement(tag);
  element.dataset.telegramFormat = format;
  if (format === "link" && "href" in attributes) {
    const href = String(attributes.href);
    element.setAttribute("href", href);
    element.dataset.href = href;
  }
  if (format === "mention" && "userId" in attributes) {
    const userId = String(attributes.userId);
    element.setAttribute("href", telegramMentionHref(userId));
    element.dataset.userId = userId;
  }
  if (format === "code-block" && "language" in attributes && attributes.language) element.dataset.language = String(attributes.language);
  if (format === "expandable-quote") element.setAttribute("expandable", "");
  if (format === "custom-emoji") {
    element.dataset.templateAtomic = "true";
    element.dataset.emojiId = String(attributes.emojiId);
    element.dataset.fallback = String(attributes.fallback);
  }
  if (format === "date-time") {
    element.dataset.templateAtomic = "true";
    element.dataset.unix = String(attributes.unix);
    element.dataset.dateTimeFormat = String(attributes.dateTimeFormat);
    element.dataset.fallback = String(attributes.fallback);
  }
  return element;
}

function stripFormatElements(parent: ParentNode, format: TelegramFormatKind): void {
  const elements = Array.from(parent.querySelectorAll<HTMLElement>("[data-telegram-format],b,strong,i,em,u,ins,s,strike,del,tg-spoiler,code,pre,blockquote,a,tg-emoji,tg-time"));
  for (const element of elements.reverse()) {
    if (formatKindForElement(element) === format) unwrapElement(element);
  }
}

function stripAllFormatElements(parent: ParentNode): void {
  const elements = Array.from(parent.querySelectorAll<HTMLElement>("[data-telegram-format],b,strong,i,em,u,ins,s,strike,del,tg-spoiler,code,pre,blockquote,a,tg-emoji,tg-time"));
  for (const element of elements.reverse()) unwrapElement(element);
}

function closestFormatAncestor(node: Node, root: HTMLElement, format?: TelegramFormatKind): HTMLElement | null {
  let current = node instanceof HTMLElement ? node.parentElement : node.parentElement;
  while (current && current !== root) {
    const currentFormat = formatKindForElement(current);
    if (currentFormat && (!format || currentFormat === format)) return current;
    current = current.parentElement;
  }
  return null;
}

function liftNodeOutOfAncestor(node: HTMLElement, ancestor: HTMLElement): void {
  while (node.parentElement && node.parentElement !== ancestor) splitParentAroundNode(node);
  if (node.parentElement === ancestor) splitParentAroundNode(node);
}

function splitParentAroundNode(node: HTMLElement): void {
  const parent = node.parentElement;
  const grandParent = parent?.parentNode;
  if (!parent || !grandParent) return;
  const before = parent.cloneNode(false) as HTMLElement;
  const after = parent.cloneNode(false) as HTMLElement;
  while (parent.firstChild && parent.firstChild !== node) before.append(parent.firstChild);
  while (node.nextSibling) after.append(node.nextSibling);
  if (before.childNodes.length) grandParent.insertBefore(before, parent);
  grandParent.insertBefore(node, parent);
  if (after.childNodes.length) grandParent.insertBefore(after, parent);
  parent.remove();
}

function selectAndUnwrap(element: HTMLElement): Range {
  const parent = element.parentNode;
  const children = Array.from(element.childNodes);
  const first = children[0];
  const last = children.at(-1);
  if (!first || !last) {
    element.remove();
    return window.document.createRange();
  }
  element.replaceWith(...children);
  const range = (parent?.ownerDocument ?? window.document).createRange();
  range.setStartBefore(first);
  range.setEndAfter(last);
  return range;
}

function unwrapElement(element: HTMLElement): void {
  element.replaceWith(...Array.from(element.childNodes));
}

function selectNodeContents(element: HTMLElement): Range {
  const range = element.ownerDocument.createRange();
  range.selectNodeContents(element);
  return range;
}

function restoreRange(range: Range): void {
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
}

function collapseSelectionToEnd(): void {
  window.getSelection()?.collapseToEnd();
}

function existingFormatDetails(range: Range, format: TelegramFormatKind): FormattingDialogState["existing"] | undefined {
  const element = closestMatchingElement(range.commonAncestorContainer, format);
  if (!element) return undefined;
  return {
    href: element.dataset.href ?? element.getAttribute("href") ?? undefined,
    userId: element.dataset.userId ?? parseTelegramMentionHref(element.getAttribute("href") ?? "") ?? undefined,
    language: element.dataset.language || undefined,
    emojiId: element.dataset.emojiId || element.getAttribute("emoji-id") || undefined,
    unix: Number(element.dataset.unix ?? element.getAttribute("unix")) || undefined,
    dateTimeFormat: element.dataset.dateTimeFormat ?? element.getAttribute("format") ?? undefined,
    fallback: element.dataset.fallback ?? element.textContent ?? undefined,
  };
}

function closestMatchingElement(node: Node, format: TelegramFormatKind): HTMLElement | null {
  let current = node instanceof HTMLElement ? node : node.parentElement;
  while (current) {
    if (formatKindForElement(current) === format) return current;
    current = current.parentElement;
  }
  return null;
}

function applyPendingNativeFormat(format: TelegramFormatKind): boolean {
  const command = format === "bold" ? "bold"
    : format === "italic" ? "italic"
      : format === "underline" ? "underline"
        : format === "strikethrough" ? "strikeThrough"
          : null;
  if (!command || typeof document.execCommand !== "function") return false;
  document.execCommand(command, false);
  return true;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}
