import { memo, useLayoutEffect, useRef, useState, type ClipboardEvent, type FormEvent, type KeyboardEvent } from "react";

import { ContextAutocomplete, UserIcon } from "./autocomplete";
import { findContextField, searchContextFields, SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument, TemplateNode } from "./model";
import { serializeTemplate } from "./serializer";

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
  const editorRef = useRef<HTMLDivElement>(null);
  const pendingCaret = useRef<number | null>(null);
  const [autocomplete, setAutocomplete] = useState<AutocompleteState | null>(null);
  const suggestions = autocomplete ? searchContextFields(autocomplete.query) : [];

  useLayoutEffect(() => {
    if (pendingCaret.current === null || !editorRef.current) return;
    restoreCaretOffset(editorRef.current, pendingCaret.current);
    pendingCaret.current = null;
  }, [document]);

  const commitDom = (caretOffset?: number) => {
    const editor = editorRef.current;
    if (!editor) return;
    pendingCaret.current = caretOffset ?? getCaretOffset(editor);
    onChange(serializeTemplate(readEditorDocument(editor)));
  };

  const updateAutocomplete = () => {
    const editor = editorRef.current;
    if (!editor) return;
    const trigger = getAutocompleteTrigger(editor);
    if (!trigger) {
      setAutocomplete(null);
      return;
    }
    const rect = typeof trigger.range.getBoundingClientRect === "function"
      ? trigger.range.getBoundingClientRect()
      : editor.getBoundingClientRect();
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
    const caretBefore = getCaretOffset(editor) - trigger.query.length - 1;
    const nextDocument = readEditorDocument(editor);
    const textNode = nextDocument.nodes[trigger.nodeIndex];
    if (textNode?.type !== "text") return;
    const before = textNode.text.slice(0, trigger.range.startOffset);
    const after = textNode.text.slice(trigger.range.endOffset);
    nextDocument.nodes.splice(
      trigger.nodeIndex,
      1,
      ...(before ? [{ type: "text" as const, text: before }] : []),
      { type: "context-token", fieldId: field.id, path: field.path },
      ...(after ? [{ type: "text" as const, text: after }] : []),
    );
    setAutocomplete(null);
    pendingCaret.current = caretBefore + 1;
    onChange(serializeTemplate(nextDocument));
  };

  const handleInput = (_event: FormEvent<HTMLDivElement>) => {
    commitDom();
    updateAutocomplete();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
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
        const caret = getCaretOffset(editorRef.current) - (event.key === "Backspace" ? 1 : 0);
        const nextDocument = readEditorDocument(editorRef.current);
        const nodeIndex = Number(token.dataset.nodeIndex);
        if (!Number.isInteger(nodeIndex)) return;
        nextDocument.nodes.splice(nodeIndex, 1);
        setAutocomplete(null);
        pendingCaret.current = Math.max(0, caret);
        onChange(serializeTemplate(nextDocument));
      }
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    event.preventDefault();
    insertPlainText(event.clipboardData.getData("text/plain"));
    commitDom();
    updateAutocomplete();
  };

  return (
    <div className="template-visual-shell">
      <div
        ref={editorRef}
        className="template-visual-editor"
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-label="Visual template content"
        aria-multiline="true"
        data-empty={document.nodes.length === 0 || (document.nodes.length === 1 && document.nodes[0].type === "text" && !document.nodes[0].text) ? "true" : "false"}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        onKeyUp={(event) => {
          if (!["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(event.key)) updateAutocomplete();
        }}
        onPaste={handlePaste}
      >
        {(document.nodes.length ? document.nodes : [{ type: "text" as const, text: "" }]).map((node, index) => <TemplateNodeView key={`${index}-${nodeKey(node)}`} node={node} index={index} />)}
      </div>
      {autocomplete && <ContextAutocomplete fields={suggestions} activeIndex={autocomplete.activeIndex} position={autocomplete.position} onChoose={chooseField} />}
    </div>
  );
});

function TemplateNodeView({ node, index }: { node: TemplateNode; index: number }) {
  if (node.type === "text") return <span data-template-node="text" data-node-index={index}>{node.text}</span>;
  if (node.type === "context-token") {
    const field = findContextField(node.path);
    if (!field) return <UnresolvedToken path={node.path} source={node.source ?? `{{ ${node.path} }}`} />;
    return (
      <span
        className="context-token"
        contentEditable={false}
        data-template-node="context-token"
        data-field-id={field.id}
        data-path={field.path}
        data-source={node.source ?? ""}
        data-node-index={index}
        tabIndex={0}
        title={fieldTooltip(field)}
        aria-label={`${field.group}: ${field.label}`}
      >
        <UserIcon /><span>{field.group}</span><span className="context-token__separator">·</span><strong>{field.label}</strong>
      </span>
    );
  }
  if (node.type === "unresolved-token") return <UnresolvedToken path={node.path} source={node.source} index={index} />;
  return (
    <span
      className="context-token context-token--raw"
      contentEditable={false}
      data-template-node="raw-fragment"
      data-source={node.source}
      data-node-index={index}
      tabIndex={0}
      title={`This Jinja fragment is preserved, but cannot be represented in Visual mode.\n\n${node.source}`}
      aria-label={`Unsupported Jinja fragment: ${node.source}`}
    ><WarningIcon /><code>{node.source}</code></span>
  );
}

function UnresolvedToken({ path, source, index }: { path: string; source: string; index?: number }) {
  return (
    <span
      className="context-token context-token--unresolved"
      contentEditable={false}
      data-template-node="unresolved-token"
      data-path={path}
      data-source={source}
      data-node-index={index}
      tabIndex={0}
      title={`Unknown field in the current context catalog.\n\n${path}`}
      aria-label={`Unknown context field: ${path}`}
    ><WarningIcon /><code>{path}</code></span>
  );
}

function WarningIcon() {
  return <svg className="context-warning-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.1 14 13H2L8 2.1Z" /><path d="M8 5.6v3.6M8 11.4v.1" /></svg>;
}

function fieldTooltip(field: ContextFieldDefinition): string {
  return `${field.group} · ${field.label}\n\n${field.path}\nType: ${field.valueType}\n${field.optional ? "Optional field" : "Required field"}\n${field.description}`;
}

function nodeKey(node: TemplateNode): string {
  if (node.type === "text") return node.text;
  if (node.type === "context-token") return `${node.path}:${node.source ?? ""}`;
  return node.source;
}

export function readEditorDocument(root: HTMLElement): TemplateDocument {
  const nodes: TemplateNode[] = [];
  for (const child of Array.from(root.childNodes)) readDomNode(child, nodes, root);
  return { nodes: mergeTextNodes(nodes) };
}

function readDomNode(node: Node, nodes: TemplateNode[], root: HTMLElement): void {
  if (node.nodeType === Node.TEXT_NODE) {
    pushText(nodes, node.textContent ?? "");
    return;
  }
  if (!(node instanceof HTMLElement)) return;
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
    nodes.push({ type: "raw-fragment", source: node.dataset.source ?? "" });
    return;
  }
  if (node.tagName === "BR") {
    pushText(nodes, "\n");
    return;
  }
  const isBlock = node.parentElement === root && /^(DIV|P)$/.test(node.tagName);
  if (isBlock && nodes.length && !endsWithLineBreak(nodes)) pushText(nodes, "\n");
  for (const child of Array.from(node.childNodes)) readDomNode(child, nodes, root);
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

function getAutocompleteTrigger(root: HTMLElement): { query: string; range: Range; nodeIndex: number } | null {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !selection.isCollapsed || !root.contains(selection.anchorNode)) return null;
  const range = selection.getRangeAt(0);
  if (range.startContainer.nodeType !== Node.TEXT_NODE) return null;
  const text = range.startContainer.textContent?.slice(0, range.startOffset) ?? "";
  const match = text.match(/\$([^\s$]*)$/u);
  if (!match) return null;
  const textElement = range.startContainer.parentElement?.closest<HTMLElement>("[data-template-node='text']");
  const nodeIndex = Number(textElement?.dataset.nodeIndex);
  if (!Number.isInteger(nodeIndex)) return null;
  const triggerRange = window.document.createRange();
  triggerRange.setStart(range.startContainer, range.startOffset - match[0].length);
  triggerRange.setEnd(range.startContainer, range.startOffset);
  return { query: match[1], range: triggerRange, nodeIndex };
}

function getCaretOffset(root: HTMLElement): number {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !root.contains(selection.anchorNode)) return textLength(root);
  const target = selection.getRangeAt(0);
  let offset = 0;
  let found = false;
  const visit = (node: Node) => {
    if (found) return;
    if (node === target.startContainer) {
      offset += node.nodeType === Node.TEXT_NODE ? target.startOffset : 0;
      found = true;
      return;
    }
    if (node instanceof HTMLElement && node.dataset.templateNode && node.dataset.templateNode !== "text") {
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

function restoreCaretOffset(root: HTMLElement, target: number): void {
  let consumed = 0;
  let restored = false;
  const visit = (node: Node) => {
    if (restored) return;
    if (node instanceof HTMLElement && node.dataset.templateNode && node.dataset.templateNode !== "text") {
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
  if (emptyTextNode) setCaret(emptyTextNode, 0);
}

function setCaret(node: Node, offset: number): void {
  const range = window.document.createRange();
  const maximumOffset = node.nodeType === Node.TEXT_NODE
    ? node.textContent?.length ?? 0
    : node.childNodes.length;
  range.setStart(node, Math.min(offset, maximumOffset));
  range.collapse(true);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
}

function textLength(root: HTMLElement): number {
  return readEditorDocument(root).nodes.reduce((length, node) => length + (node.type === "text" ? node.text.length : 1), 0);
}

function adjacentAtomicToken(root: HTMLElement, direction: -1 | 1): HTMLElement | null {
  const active = window.document.activeElement;
  if (active instanceof HTMLElement && active !== root && root.contains(active) && active.dataset.templateNode && active.dataset.templateNode !== "text") return active;
  const selection = window.getSelection();
  if (!selection?.isCollapsed || !selection.rangeCount) return null;
  const range = selection.getRangeAt(0);
  const direct = directChildOf(root, range.startContainer);
  if (!direct) return null;
  const textLength = range.startContainer.textContent?.length ?? 0;
  const atBoundary = range.startContainer.nodeType === Node.TEXT_NODE
    ? direction === -1 ? range.startOffset === 0 : range.startOffset === textLength
    : true;
  if (!atBoundary) return null;
  const sibling = direction === -1 ? direct.previousElementSibling : direct.nextElementSibling;
  return sibling instanceof HTMLElement && sibling.dataset.templateNode && sibling.dataset.templateNode !== "text" ? sibling : null;
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
