import { useEffect, useRef } from "react";

const HISTORY_LIMIT = 100;

type FieldSnapshot =
  | { kind: "value"; value: string; selectionStart: number | null; selectionEnd: number | null }
  | { kind: "checked"; checked: boolean };

type FieldHistory = { entries: FieldSnapshot[]; index: number };

type EditableField = HTMLInputElement | HTMLTextAreaElement;

/**
 * Gives controlled native form controls the same local undo/redo behaviour as
 * browser inputs. Histories are intentionally scoped to each DOM field so
 * changes in one editor never undo a different editor's value.
 */
export function useFieldHistory() {
  const historiesRef = useRef(new WeakMap<EditableField, FieldHistory>());
  const replayingRef = useRef(new WeakSet<EditableField>());

  useEffect(() => {
    const ensureHistory = (field: EditableField) => {
      const snapshot = snapshotField(field);
      const current = historiesRef.current.get(field);
      if (current) return current;
      const created = { entries: [snapshot], index: 0 };
      historiesRef.current.set(field, created);
      return created;
    };

    const record = (field: EditableField) => {
      if (replayingRef.current.has(field)) return;
      const history = ensureHistory(field);
      const snapshot = snapshotField(field);
      if (snapshotsEqual(history.entries[history.index], snapshot)) return;
      history.entries.splice(history.index + 1);
      history.entries.push(snapshot);
      if (history.entries.length > HISTORY_LIMIT) history.entries.shift();
      history.index = history.entries.length - 1;
    };

    const replay = (field: EditableField, direction: -1 | 1) => {
      const history = ensureHistory(field);
      const nextIndex = history.index + direction;
      if (nextIndex < 0 || nextIndex >= history.entries.length) return;
      history.index = nextIndex;
      replayingRef.current.add(field);
      restoreField(field, history.entries[nextIndex]);
      field.dispatchEvent(new Event("input", { bubbles: true }));
      queueMicrotask(() => replayingRef.current.delete(field));
    };

    const handleFocus = (event: FocusEvent) => {
      const field = editableField(event.target);
      if (field) ensureHistory(field);
    };
    const handleInput = (event: Event) => {
      const field = editableField(event.target);
      if (field) record(field);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((!event.ctrlKey && !event.metaKey) || event.altKey) return;
      const field = editableField(event.target);
      if (!field) return;
      const key = event.key.toLowerCase();
      const redo = key === "y" || (key === "z" && event.shiftKey);
      const undo = key === "z" && !event.shiftKey;
      if (!undo && !redo) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      replay(field, redo ? 1 : -1);
    };

    window.addEventListener("focusin", handleFocus, true);
    window.addEventListener("input", handleInput, true);
    window.addEventListener("change", handleInput, true);
    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.removeEventListener("focusin", handleFocus, true);
      window.removeEventListener("input", handleInput, true);
      window.removeEventListener("change", handleInput, true);
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, []);
}

function editableField(target: EventTarget | null): EditableField | null {
  const element = target instanceof Element ? target : document.activeElement;
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    return !element.disabled && !element.readOnly ? element : null;
  }
  return null;
}

function snapshotField(field: EditableField): FieldSnapshot {
  if (field instanceof HTMLInputElement) {
    if (field.type === "checkbox" || field.type === "radio") return { kind: "checked", checked: field.checked };
    return { kind: "value", value: field.value, selectionStart: field.selectionStart, selectionEnd: field.selectionEnd };
  }
  return { kind: "value", value: field.value, selectionStart: field.selectionStart, selectionEnd: field.selectionEnd };
}

function snapshotsEqual(left: FieldSnapshot, right: FieldSnapshot): boolean {
  if (left.kind !== right.kind) return false;
  if (left.kind === "value" && right.kind === "value") return left.value === right.value;
  if (left.kind === "checked" && right.kind === "checked") return left.checked === right.checked;
  return false;
}

function restoreField(field: EditableField, snapshot: FieldSnapshot): void {
  if (snapshot.kind === "checked" && field instanceof HTMLInputElement) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set?.call(field, snapshot.checked);
    return;
  }
  if (snapshot.kind !== "value") return;
  const prototype = field instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, snapshot.value);
  if (snapshot.selectionStart === null || snapshot.selectionEnd === null) return;
  try {
    field.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
  } catch {
    // Numeric and date controls do not expose a text selection range.
  }
}
