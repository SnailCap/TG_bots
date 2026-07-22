import { useEffect, useLayoutEffect, useRef, useState, type DragEvent, type MouseEvent } from "react";
import { createPortal } from "react-dom";

import { actionFor, type ActionOptions, type ButtonSpec, type HandlerCreateOptions, type ViewSpec } from "../../domain/project";
import { useInertialDragPreview } from "../../shared/lib/useInertialDragPreview";
import { ContextMenu, type ContextMenuItem } from "../../shared/ui/ContextMenu";
import { ActionEditor, type HandlerActions, VIEW_BUTTON_ACTION_TYPES } from "../action-editor/ActionEditor";

type ButtonLocation = { row: number; button: number };
type DropLocation = { row: number; index: number };
type ButtonDragPreview = { button: ButtonSpec; invalid: boolean; width: number; height: number };
type KeyboardContextTarget =
  | { kind: "button"; location: ButtonLocation }
  | { kind: "row"; row: number }
  | { kind: "canvas" };
type KeyboardContext = KeyboardContextTarget & { x: number; y: number };
let emptyDragImage: HTMLImageElement | null = null;

export function KeyboardComposer({
  viewId,
  keyboard,
  options,
  handlerActions,
  createOptions,
  onChange,
}: {
  viewId: string;
  keyboard: ViewSpec["keyboard"];
  options: ActionOptions;
  handlerActions: HandlerActions;
  createOptions?: HandlerCreateOptions;
  onChange(keyboard: ViewSpec["keyboard"]): void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusText, setFocusText] = useState(false);
  const [dragging, setDragging] = useState<ButtonLocation | null>(null);
  const [dropTarget, setDropTarget] = useState<DropLocation | null>(null);
  const [dragPreview, setDragPreview] = useState<ButtonDragPreview | null>(null);
  const [context, setContext] = useState<KeyboardContext | null>(null);
  const labelInputRef = useRef<HTMLInputElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const slotPositionsRef = useRef(new Map<string, { left: number; top: number }>());
  const pendingButtonEntranceIdsRef = useRef(new Set<string>());
  const { previewRef, startPreview, movePreview, stopPreview } = useInertialDragPreview();
  const rows = keyboard.filter((row) => row.length > 0);
  const selected = findButtonLocation(rows, selectedId);
  const selectedButton = selected ? rows[selected.row]?.[selected.button] : undefined;
  const selectedCreateOptions = selectedButton && createOptions?.attachment?.type === "view_button"
    ? { ...createOptions, attachment: { ...createOptions.attachment, button_id: selectedButton.id } }
    : createOptions;
  const existingIds = rows.flat().map((button) => button.id);
  const hasButtons = rows.some((row) => row.length > 0);

  useEffect(() => {
    if (selectedId && !selectedButton) setSelectedId(null);
  }, [selectedButton, selectedId]);
  useEffect(() => {
    if (!focusText || !selectedButton) return;
    labelInputRef.current?.focus();
    labelInputRef.current?.select();
    setFocusText(false);
  }, [focusText, selectedButton]);
  useLayoutEffect(() => {
    const grid = gridRef.current;
    if (!grid) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const nextPositions = new Map<string, { left: number; top: number }>();
    const slots = grid.querySelectorAll<HTMLElement>("[data-keyboard-button-id]");
    slots.forEach((slot) => {
      const id = slot.dataset.keyboardButtonId;
      if (!id) return;
      const rect = slot.getBoundingClientRect();
      const previous = slotPositionsRef.current.get(id);
      nextPositions.set(id, { left: rect.left, top: rect.top });
      if (pendingButtonEntranceIdsRef.current.delete(id)) {
        const button = slot.querySelector<HTMLElement>(".keyboard-composer__button");
        if (!reduceMotion && typeof button?.animate === "function") {
          button.animate(
            [
              { opacity: 0, transform: "scale(.96)" },
              { opacity: 1, transform: "scale(1)" },
            ],
            { duration: 220, easing: "cubic-bezier(.2, .8, .2, 1)" },
          );
        }
      }
      if (!previous || reduceMotion || typeof slot.animate !== "function") return;
      const deltaX = previous.left - rect.left;
      const deltaY = previous.top - rect.top;
      if (Math.abs(deltaX) < 0.5 && Math.abs(deltaY) < 0.5) return;
      slot.animate(
        [
          { transform: `translate3d(${deltaX}px, ${deltaY}px, 0)` },
          { transform: "translate3d(0, 0, 0)" },
        ],
        { duration: 220, easing: "cubic-bezier(.2, .8, .2, 1)" },
      );
    });
    slotPositionsRef.current = nextPositions;
  }, [keyboard]);

  const updateButton = (location: ButtonLocation, button: ButtonSpec) => {
    const current = rows[location.row]?.[location.button];
    if (current?.id === selectedId && current.id !== button.id) setSelectedId(button.id);
    onChange(rows.map((row, rowIndex) => rowIndex === location.row
      ? row.map((item, buttonIndex) => buttonIndex === location.button ? button : item)
      : row));
  };
  const addButton = (rowIndex: number) => {
    const button = newButton(viewId, existingIds);
    pendingButtonEntranceIdsRef.current.add(button.id);
    const next = rows.map((row, index) => index === rowIndex ? [...row, button] : row);
    onChange(next);
    setSelectedId(button.id);
    setFocusText(true);
  };
  const addRow = () => {
    const button = newButton(viewId, existingIds);
    pendingButtonEntranceIdsRef.current.add(button.id);
    onChange([...rows, [button]]);
    setSelectedId(button.id);
    setFocusText(true);
  };
  const duplicateButton = (location: ButtonLocation) => {
    const source = rows[location.row]?.[location.button];
    if (!source) return;
    const copy = { ...structuredClone(source), id: nextButtonId(viewId, existingIds) };
    pendingButtonEntranceIdsRef.current.add(copy.id);
    const next = rows.map((row, rowIndex) => rowIndex === location.row
      ? [...row.slice(0, location.button + 1), copy, ...row.slice(location.button + 1)]
      : row);
    onChange(next);
    setSelectedId(copy.id);
  };
  const deleteButton = (location: ButtonLocation) => {
    const deletedId = rows[location.row]?.[location.button]?.id;
    const rowRemains = (rows[location.row]?.length ?? 0) > 1;
    const next = rows
      .map((row, rowIndex) => rowIndex === location.row ? row.filter((_, index) => index !== location.button) : row)
      .filter((row) => row.length > 0);
    onChange(next);
    if (selectedId === deletedId) {
      const nextRow = next[location.row];
      const nearest = rowRemains ? nextRow?.[Math.min(location.button, Math.max(0, nextRow.length - 1))] : undefined;
      setSelectedId(nearest?.id ?? null);
    }
  };
  const deleteRow = (rowIndex: number) => {
    const removesSelection = rows[rowIndex]?.some((button) => button.id === selectedId) ?? false;
    onChange(rows.filter((_, index) => index !== rowIndex));
    if (removesSelection) setSelectedId(null);
  };
  const startDrag = (event: DragEvent<HTMLButtonElement>, location: ButtonLocation, button: ButtonSpec, invalid: boolean) => {
    setContext(null);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", `${location.row}:${location.button}`);
    if (typeof event.dataTransfer.setDragImage === "function") event.dataTransfer.setDragImage(transparentDragImage(), 0, 0);
    const rect = event.currentTarget.getBoundingClientRect();
    setDragPreview({ button, invalid, width: rect.width, height: rect.height });
    startPreview(event.clientX, event.clientY);
    setDragging(location);
  };
  const finishDrag = () => {
    stopPreview();
    setDragPreview(null);
    setDragging(null);
    setDropTarget(null);
  };
  const resolveDrop = (event: DragEvent<HTMLElement>, rowIndex: number): DropLocation => {
    const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("[data-keyboard-button]"));
    const targetIndex = buttons.findIndex((element) => event.clientX < element.getBoundingClientRect().left + element.getBoundingClientRect().width / 2);
    return { row: rowIndex, index: targetIndex < 0 ? rows[rowIndex].length : targetIndex };
  };
  const moveButton = (target: DropLocation) => {
    if (!dragging) return;
    const sourceButton = rows[dragging.row]?.[dragging.button];
    if (!sourceButton) return;
    const next = rows.map((row) => [...row]);
    next[dragging.row].splice(dragging.button, 1);
    const index = dragging.row === target.row && dragging.button < target.index ? target.index - 1 : target.index;
    if (dragging.row === target.row && dragging.button === index) return;
    let targetRow = target.row;
    if (dragging.row !== target.row && next[dragging.row].length === 0) {
      next.splice(dragging.row, 1);
      if (dragging.row < target.row) targetRow -= 1;
    }
    next[targetRow].splice(Math.max(0, index), 0, sourceButton);
    onChange(next);
    const location = { row: targetRow, button: Math.max(0, index) };
    setDragging(location);
  };
  const openContext = (event: MouseEvent, target: KeyboardContextTarget) => {
    event.preventDefault();
    event.stopPropagation();
    if (target.kind === "button") setSelectedId(rows[target.location.row]?.[target.location.button]?.id ?? null);
    setContext({ ...target, x: event.clientX, y: event.clientY });
  };
  const contextItems: ContextMenuItem[] = context?.kind === "button"
    ? [
        { id: "edit", label: "Edit label", icon: <Icon name="edit" />, onSelect: () => { const button = rows[context.location.row]?.[context.location.button]; if (button) setSelectedId(button.id); setFocusText(true); } },
        { id: "duplicate", label: "Duplicate", icon: <Icon name="copy" />, onSelect: () => duplicateButton(context.location) },
        { id: "delete", label: "Delete", icon: <Icon name="trash" />, danger: true, onSelect: () => deleteButton(context.location) },
      ]
    : context?.kind === "row"
      ? [
          { id: "add-button", label: "Add button", icon: <Icon name="plus" />, onSelect: () => addButton(context.row) },
          { id: "delete-row", label: "Delete row", icon: <Icon name="trash" />, danger: true, onSelect: () => deleteRow(context.row) },
        ]
      : context?.kind === "canvas"
        ? [{ id: "add-row", label: "Add row", icon: <Icon name="plus" />, onSelect: addRow }]
        : [];

  return <fieldset className="keyboard-composer" aria-label="Telegram keyboard builder">
    <legend>Inline keyboard</legend>
    <div className="keyboard-composer__workspace keyboard-composer__workspace--editing">
      <section className={rows.length === 0 ? "keyboard-composer__canvas keyboard-composer__canvas--empty" : "keyboard-composer__canvas"} onContextMenu={(event) => openContext(event, { kind: "canvas" })}>
        <div ref={gridRef} className="keyboard-composer__grid" aria-label="Keyboard rows">
          {rows.map((row, rowIndex) => <div
            className={dropTarget?.row === rowIndex ? "keyboard-composer__row keyboard-composer__row--drop-active" : "keyboard-composer__row"}
            key={`row-${rowIndex}`}
            onContextMenu={(event) => openContext(event, { kind: "row", row: rowIndex })}
            onDragOver={(event) => { event.preventDefault(); const target = resolveDrop(event, rowIndex); setDropTarget(target); moveButton(target); }}
            onDrop={(event) => { event.preventDefault(); moveButton(resolveDrop(event, rowIndex)); finishDrag(); }}
          >
                <div className="keyboard-composer__button-list">
                  {row.map((button, buttonIndex) => {
                  const location = { row: rowIndex, button: buttonIndex };
                  const issue = buttonIssue(button);
                  const isSelected = selected?.row === rowIndex && selected.button === buttonIndex;
                  const isDragging = dragging?.row === rowIndex && dragging.button === buttonIndex;
                  const insertionActive = dropTarget?.row === rowIndex && dropTarget.index === buttonIndex;
                  return <div data-keyboard-button-id={button.id} className={["keyboard-composer__button-slot", insertionActive ? "keyboard-composer__button-slot--active" : "", isDragging ? "keyboard-composer__button-slot--dragging" : ""].filter(Boolean).join(" ")} key={button.id}>
                    <button
                      type="button"
                      draggable
                      data-keyboard-button
                      aria-pressed={isSelected}
                      className={["keyboard-composer__button", isSelected ? "keyboard-composer__button--selected" : "", issue ? "keyboard-composer__button--invalid" : "keyboard-composer__button--valid", dragging?.row === rowIndex && dragging.button === buttonIndex ? "keyboard-composer__button--dragging" : ""].filter(Boolean).join(" ")}
                      onClick={() => setSelectedId(button.id)}
                      onContextMenu={(event) => openContext(event, { kind: "button", location })}
                      onDragStart={(event) => startDrag(event, location, button, Boolean(issue))}
                      onDrag={(event) => { if (event.clientX !== 0 || event.clientY !== 0) movePreview(event.clientX, event.clientY); }}
                      onDragEnd={finishDrag}
                      title={issue ?? "Configured"}
                    >
                      <span className="keyboard-composer__button-label">{button.text.trim() || "Untitled"}</span>
                    </button>
                  </div>;
                  })}
                </div>
                <div
                  className="keyboard-composer__row-actions"
                onDragOver={(event) => { event.preventDefault(); const target = { row: rowIndex, index: row.length }; setDropTarget(target); moveButton(target); }}
                onDrop={(event) => { event.preventDefault(); moveButton({ row: rowIndex, index: row.length }); finishDrag(); }}
              >
                <div className={dropTarget?.row === rowIndex && dropTarget.index === row.length ? "keyboard-composer__button-slot keyboard-composer__append-slot keyboard-composer__button-slot--active" : "keyboard-composer__button-slot keyboard-composer__append-slot"}>
                  <button type="button" className="keyboard-composer__append" aria-label={`Add button to row ${rowIndex + 1}`} title="Add button" onClick={() => addButton(rowIndex)}><Icon name="plus" /></button>
                </div>
                  <div className="keyboard-composer__row-delete-control"><button type="button" className="keyboard-composer__icon-button keyboard-composer__row-delete" aria-label={`Delete row ${rowIndex + 1}`} title="Delete row" onClick={() => deleteRow(rowIndex)}><Icon name="trash" /></button></div>
                </div>
          </div>)}
        </div>
        <button type="button" className="keyboard-composer__add-row" aria-label="Add row" title="Add row" onClick={addRow}><Icon name="plus" /></button>
      </section>
      <aside className="keyboard-composer__inspector" aria-label="Selected button settings">
        {selected && selectedButton
          ? <div className="keyboard-composer__inspector-content">
              <header className="keyboard-composer__inspector-header"><h3>Button settings</h3><button type="button" className="keyboard-composer__inspector-delete" aria-label="Delete selected button" title="Delete button" onClick={() => deleteButton(selected)}><Icon name="trash" /></button></header>
              <div className="keyboard-composer__settings-divider" />
              <div className="keyboard-composer__label-settings"><span className="keyboard-composer__section-label">Label</span><input ref={labelInputRef} aria-label="Button text" value={selectedButton.text} placeholder="Button label" onChange={(event) => updateButton(selected, { ...selectedButton, text: event.target.value })} /></div>
              <div className="keyboard-composer__action-settings"><span className="keyboard-composer__section-label">Action</span><ActionEditor action={selectedButton.action} compact hideActionLabel options={options} scope={{ expectedKind: "button", placement: "view_button" }} handlerActions={handlerActions} createOptions={selectedCreateOptions} onChange={(action) => updateButton(selected, { ...selectedButton, action })} /></div>
            </div>
          : <div className="keyboard-composer__empty-state keyboard-composer__inspector-content"><KeyboardIcon /><strong>{hasButtons ? "Select a button" : "No buttons added yet"}</strong></div>}
      </aside>
    </div>
    {dragPreview && createPortal(
      <div ref={previewRef} className="keyboard-composer__drag-preview" style={{ width: dragPreview.width, height: dragPreview.height }} aria-hidden="true">
        <div className="keyboard-composer__drag-preview-surface keyboard-composer__button-slot">
          <div className={`keyboard-composer__button ${dragPreview.invalid ? "keyboard-composer__button--invalid" : "keyboard-composer__button--valid"}`}>
            <span className="keyboard-composer__button-label">{dragPreview.button.text.trim() || "Untitled"}</span>
          </div>
        </div>
      </div>,
      document.body,
    )}
    {context && <ContextMenu x={context.x} y={context.y} label="Keyboard actions" items={contextItems} onClose={() => setContext(null)} />}
  </fieldset>;
}

function findButtonLocation(rows: ViewSpec["keyboard"], selectedId: string | null): ButtonLocation | null {
  if (!selectedId) return null;
  for (let row = 0; row < rows.length; row += 1) {
    const button = rows[row].findIndex((item) => item.id === selectedId);
    if (button >= 0) return { row, button };
  }
  return null;
}

function transparentDragImage(): HTMLImageElement {
  if (emptyDragImage) return emptyDragImage;
  emptyDragImage = new Image();
  emptyDragImage.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
  return emptyDragImage;
}

function newButton(viewId: string, existingIds: string[]): ButtonSpec {
  return { id: nextButtonId(viewId, existingIds), text: "", action: actionFor("noop") };
}

function nextButtonId(viewId: string, existing: string[]): string {
  const prefix = `${viewId || "view"}.action`;
  let suffix = 1;
  while (existing.includes(`${prefix}_${suffix}`)) suffix += 1;
  return `${prefix}_${suffix}`;
}

function buttonIssue(button: ButtonSpec): string | null {
  if (!button.text.trim()) return "Add a button label";
  if (!VIEW_BUTTON_ACTION_TYPES.includes(button.action.type)) return "Choose a button action";
  if ((button.action.type === "view.render" || button.action.type === "flow.start" || button.action.type === "flow.event" || button.action.type === "flow.goto" || button.action.type === "task.enqueue") && !button.action.target.trim()) return "Choose an action target";
  if (button.action.type === "handler.invoke" && !button.action.handler.trim()) return "Choose a custom handler";
  return null;
}

function Icon({ name }: { name: "plus" | "trash" | "edit" | "copy" }) {
  const paths = {
    plus: <path d="M8 3.25v9.5M3.25 8h9.5" />,
    trash: <><path d="M3.75 5.1h8.5M6.2 5.1V3.65h3.6V5.1M5.1 5.1l.55 7.15h4.7l.55-7.15" /><path d="M7 7.15v3.15M9 7.15v3.15" /></>,
    edit: <><path d="m3.5 11.8.45-2.15 6.8-6.8 2.05 2.05-6.8 6.8-2.5.1Z" /><path d="m9.8 3.8 2.05 2.05" /></>,
    copy: <><rect x="5.25" y="5.25" width="7.25" height="7.25" rx="1" /><path d="M10.75 5.25V4.5a1 1 0 0 0-1-1H4.5a1 1 0 0 0-1 1v5.25a1 1 0 0 0 1 1h.75" /></>,
  };
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true">{paths[name]}</svg>;
}

function KeyboardIcon() {
  return <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M6.5 9h.01M10 9h.01M13.5 9h.01M17 9h.01M6.5 13h7M17 13h.01" /></svg>;
}
