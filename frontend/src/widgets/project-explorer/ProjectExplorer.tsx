import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

import type { HandlerKind, Selection, Workspace } from "../../domain/project";
import { useResourceDraggable, type DraggableResource } from "../../features/resource-dnd";
import { ResourceIcon } from "../../shared/ui/ResourceIcon";

export type CreatableResource = "view" | "template" | "flow" | "handler" | "schedule";
export type ExplorerDraft = { kind: CreatableResource; label: string };
type ResourceSection = "views" | "templates" | "flows" | "handlers" | "commands" | "schedules";
type ContextTarget = { x: number; y: number; kind?: CreatableResource; selection?: Selection } | null;

export function ProjectExplorer({ workspace, selection, draft, onSelect, onAdd, onDelete = () => undefined }: {
  workspace: Workspace;
  selection: Selection | null;
  draft?: ExplorerDraft | null;
  onSelect(selection: Selection): void;
  onAdd(kind: CreatableResource): void;
  onDelete?(selection: Selection): void;
}) {
  const [openSections, setOpenSections] = useState<Set<ResourceSection>>(() => new Set());
  const [context, setContext] = useState<ContextTarget>(null);
  useEffect(() => {
    const section = draft && draftSection(draft.kind);
    if (!section) return;
    setOpenSections((current) => current.has(section) ? current : new Set(current).add(section));
  }, [draft?.kind]);
  useEffect(() => {
    if (!context) return;
    const close = () => setContext(null);
    window.addEventListener("pointerdown", close);
    window.addEventListener("keydown", close);
    return () => { window.removeEventListener("pointerdown", close); window.removeEventListener("keydown", close); };
  }, [context]);
  const toggle = (section: ResourceSection) => setOpenSections((current) => {
    const next = new Set(current); if (next.has(section)) next.delete(section); else next.add(section); return next;
  });
  const openContext = (event: MouseEvent, target: Omit<NonNullable<ContextTarget>, "x" | "y">) => {
    event.preventDefault(); setContext({ x: event.clientX, y: event.clientY, ...target });
  };
  const item = (next: Selection, title: string, handlerKind?: HandlerKind) => <ResourceButton key={title} active={selection?.kind === next.kind && (("id" in next && "id" in selection && next.id === selection.id) || ("path" in next && "path" in selection && next.path === selection.path))} selection={next} title={title} resource={dragResource(next, title, handlerKind)} onClick={() => onSelect(next)} onContextMenu={(event) => openContext(event, { selection: next })} />;
  return <nav className="explorer explorer--ide" aria-label="Project resources" onContextMenu={(event) => { if (event.target === event.currentTarget) openContext(event, { kind: "view" }); }}>
    <Section id="views" title="views" open={openSections.has("views")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "view" })}>{draft?.kind === "view" && <DraftResource label={draft.label} kind="view" />}{workspace.views.map((view) => item({ kind: "view", id: view.id }, view.id))}</Section>
    <Section id="templates" title="templates" open={openSections.has("templates")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "template" })}>{draft?.kind === "template" && <DraftResource label={draft.label} kind="template" />}{workspace.templates.map((template) => item({ kind: "template", path: template.path }, template.path))}</Section>
    <Section id="flows" title="flows" open={openSections.has("flows")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "flow" })}>{draft?.kind === "flow" && <DraftResource label={draft.label} kind="flow" />}{workspace.flows.map((flow) => item({ kind: "flow", id: flow.id }, flow.id))}</Section>
    <Section id="handlers" title="handlers" open={openSections.has("handlers")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "handler" })}>{draft?.kind === "handler" && <DraftResource label={draft.label} kind="handler" />}{workspace.handlers.map((handler) => item({ kind: "handler", id: handler.id }, handler.id, handler.kind))}</Section>
    <Section id="commands" title="commands.json" open={openSections.has("commands")} onToggle={toggle}>{item({ kind: "commands" }, "commands.json")}</Section>
    <Section id="schedules" title="schedules" open={openSections.has("schedules")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "schedule" })}>{draft?.kind === "schedule" && <DraftResource label={draft.label} kind="schedule" />}{workspace.schedules.map((schedule) => item({ kind: "schedule", id: schedule.id }, schedule.id))}</Section>
    {context && <div className="explorer__context-menu" role="menu" style={{ left: context.x, top: context.y }} onPointerDown={(event) => event.stopPropagation()}>
      {context.kind && <button type="button" role="menuitem" onClick={() => { onAdd(context.kind!); setContext(null); }}>New {context.kind}</button>}
      {context.selection && context.selection.kind !== "commands" && <button type="button" role="menuitem" className="explorer__context-danger" onClick={() => { onDelete(context.selection!); setContext(null); }}>Delete</button>}
    </div>}
  </nav>;
}

function Section({ id, title, open, onToggle, onContextMenu, children }: { id: ResourceSection; title: string; open: boolean; onToggle(section: ResourceSection): void; onContextMenu?(event: MouseEvent): void; children: ReactNode }) {
  const contentId = `explorer-${id}`;
  return <section className={open ? "explorer__section explorer__section--open" : "explorer__section"} onContextMenu={onContextMenu}>
    <button type="button" className="explorer__section-toggle" aria-expanded={open} aria-controls={contentId} onClick={() => onToggle(id)}><span className="explorer__tree-arrow" aria-hidden="true"><ChevronIcon /></span><CategoryIcon category={id} /><span>{title}</span></button>
    <div id={contentId} className="explorer__section-content"><div className="explorer__items">{children}</div></div>
  </section>;
}

function ResourceButton({ active, selection, title, resource, onClick, onContextMenu }: { active: boolean; selection: Selection; title: string; resource: DraggableResource | null; onClick(): void; onContextMenu(event: MouseEvent): void }) {
  const dragProps = useResourceDraggable(resource);
  const className = ["explorer__item", active ? "explorer__item--active" : "", resource ? "explorer__item--draggable" : ""].filter(Boolean).join(" ");
  return <button type="button" aria-current={active ? "page" : undefined} className={className} onClick={onClick} onContextMenu={onContextMenu} onPointerDown={dragProps.onPointerDown} onClickCapture={dragProps.onClickCapture}><ResourceIcon selection={selection} title={title} /> <strong>{title}</strong></button>;
}

function DraftResource({ kind, label }: ExplorerDraft) {
  return <div className="explorer__item explorer__item--active explorer__item--draft" aria-current="page"><ResourceIcon selection={kind === "template" ? { kind, path: label } : { kind, id: label }} title={label} /><strong>{label}</strong><span className="explorer__draft-indicator">new</span></div>;
}

function ChevronIcon() {
  return <svg viewBox="0 0 16 16" focusable="false"><path d="m4.5 6.25 3.5 3.5 3.5-3.5" /></svg>;
}

function CategoryIcon({ category }: { category: ResourceSection }) {
  const paths: Record<ResourceSection, ReactNode> = {
    views: <><rect x="3" y="3" width="4" height="4" rx=".65" /><rect x="9" y="3" width="4" height="4" rx=".65" /><rect x="3" y="9" width="4" height="4" rx=".65" /><rect x="9" y="9" width="4" height="4" rx=".65" /></>,
    templates: <><path d="m6.25 4-3 4 3 4M9.75 4l3 4-3 4" /><path d="m9 3-2 10" /></>,
    flows: <><circle cx="4" cy="4" r="1.5" /><circle cx="12" cy="4" r="1.5" /><circle cx="12" cy="12" r="1.5" /><path d="M5.5 4h2A2.5 2.5 0 0 1 10 6.5v4" /></>,
    handlers: <><path d="m9.25 2.5-4.5 6h3l-.75 5 4.5-6h-3l.75-5Z" /></>,
    commands: <><path d="m3.5 5 2.5 3-2.5 3M8 11h4.5" /></>,
    schedules: <><rect x="3" y="4" width="10" height="9" rx="1.25" /><path d="M5.5 2.75v2.5M10.5 2.75v2.5M3 7h10M5.5 9.5h.01M8 9.5h.01M10.5 9.5h.01" /></>,
  };
  return <span className={`explorer__category-icon explorer__category-icon--${category}`} aria-hidden="true"><svg viewBox="0 0 16 16" focusable="false">{paths[category]}</svg></span>;
}

function draftSection(kind: CreatableResource): ResourceSection {
  return kind === "schedule" ? "schedules" : `${kind}s` as ResourceSection;
}

function dragResource(selection: Selection, label: string, handlerKind?: HandlerKind): DraggableResource | null {
  if (selection.kind === "commands") return null;
  return {
    kind: selection.kind,
    value: "path" in selection ? selection.path : selection.id,
    label,
    selection,
    handlerKind,
  };
}
