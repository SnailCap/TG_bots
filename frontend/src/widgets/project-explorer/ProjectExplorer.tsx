import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { Braces, CalendarDays, ChevronDown, CircleDot, FileText, LayoutGrid, Terminal, Workflow, Zap } from "lucide-react";

import type { FlowSummary, HandlerKind, Selection, VariableResourceContext, Workspace } from "../../domain/project";
import { useResourceDraggable, type DraggableResource } from "../../features/resource-dnd";
import { ContextMenu, type ContextMenuItem } from "../../shared/ui/ContextMenu";
import { ResourceIcon } from "../../shared/ui/ResourceIcon";
import { ExplorerTreeGroup, ExplorerTreeLeaf, ExplorerTreeRow } from "./ExplorerTree";

export type CreatableResource = "view" | "flow" | "handler" | "command" | "schedule";
export type ExplorerDraft = { kind: CreatableResource; label: string };
type ResourceSection = "views" | "flows" | "handlers" | "commands" | "schedules";
type ContextTarget = { x: number; y: number; kind?: CreatableResource; selection?: Selection } | null;

export function ProjectExplorer({ workspace, selection, draft, onSelect, onOpenViewTextEditor = () => undefined, onOpenVariables = () => undefined, onAdd, onRename = () => undefined, onDelete = () => undefined }: {
  workspace: Workspace;
  selection: Selection | null;
  draft?: ExplorerDraft | null;
  onSelect(selection: Selection): void;
  onOpenViewTextEditor?(viewId: string, displayName: string): void;
  onOpenVariables?(context: VariableResourceContext, displayName: string): void;
  onAdd(kind: CreatableResource): void;
  onRename?(selection: Selection, name: string): Promise<void> | void;
  onDelete?(selection: Selection): void;
}) {
  const [openSections, setOpenSections] = useState<Set<ResourceSection>>(() => new Set());
  const [openFlows, setOpenFlows] = useState<Set<string>>(() => new Set());
  const [openViews, setOpenViews] = useState<Set<string>>(() => new Set());
  const [context, setContext] = useState<ContextTarget>(null);
  const [renaming, setRenaming] = useState<Selection | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const cancelRename = useRef(false);
  useEffect(() => {
    const section = draft && draftSection(draft.kind);
    if (!section) return;
    setOpenSections((current) => current.has(section) ? current : new Set(current).add(section));
  }, [draft?.kind]);
  useEffect(() => {
    const section = selection && selectionSection(selection);
    if (!section) return;
    setOpenSections((current) => current.has(section) ? current : new Set(current).add(section));
  }, [selection]);
  useEffect(() => {
    const beginSelectedRename = (event: globalThis.KeyboardEvent) => {
      const target = event.target;
      if (event.key !== "F2" || !isRenamable(selection) || renaming || target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || (target instanceof HTMLElement && target.isContentEditable)) return;
      event.preventDefault();
      setRenameValue(resourceName(selection, workspace));
      setRenaming(selection);
    };
    window.addEventListener("keydown", beginSelectedRename);
    return () => window.removeEventListener("keydown", beginSelectedRename);
  }, [renaming, selection, workspace]);
  const toggle = (section: ResourceSection) => setOpenSections((current) => {
    const next = new Set(current); if (next.has(section)) next.delete(section); else next.add(section); return next;
  });
  const toggleFlow = (flowId: string) => setOpenFlows((current) => {
    const next = new Set(current); if (next.has(flowId)) next.delete(flowId); else next.add(flowId); return next;
  });
  const toggleView = (viewId: string) => setOpenViews((current) => {
    const next = new Set(current); if (next.has(viewId)) next.delete(viewId); else next.add(viewId); return next;
  });
  const openContext = (event: MouseEvent, target: Omit<NonNullable<ContextTarget>, "x" | "y">) => {
    event.preventDefault(); setContext({ x: event.clientX, y: event.clientY, ...target });
  };
  const beginRename = (next: Selection) => {
    if (!isRenamable(next)) return;
    cancelRename.current = false;
    setRenameValue(resourceName(next, workspace));
    setRenaming(next);
  };
  const finishRename = (next: Selection) => {
    if (cancelRename.current) {
      cancelRename.current = false;
      setRenaming(null);
      return;
    }
    if (!isRenamable(next)) return;
    const name = renameValue.trim();
    setRenaming(null);
    if (!name || name === resourceName(next, workspace)) return;
    void Promise.resolve(onRename(next, name));
  };
  const contextItems: ContextMenuItem[] = [];
  if (context?.kind) {
    const kind = context.kind;
    contextItems.push({ id: `new-${kind}`, label: `New ${kind}`, onSelect: () => onAdd(kind) });
  }
  if (context?.selection && isRenamable(context.selection)) {
    const selected = context.selection;
    contextItems.push({ id: "rename", label: "Rename", onSelect: () => beginRename(selected) });
  }
  if (context?.selection && context.selection.kind !== "commands") {
    const selected = context.selection;
    contextItems.push({ id: "delete", label: "Delete", danger: true, onSelect: () => onDelete(selected) });
  }
  if (context?.selection) {
    const selected = context.selection;
    const variableContext = variableContextForSelection(selected);
    if (variableContext) contextItems.unshift({ id: "variables", label: "Variables", onSelect: () => onOpenVariables(variableContext, resourceName(selected as Exclude<Selection, { kind: "commands" }>, workspace)) });
  }

  const item = (next: Selection, title: string, handlerKind?: HandlerKind) => <ResourceButton key={`${next.kind}:${title}`} active={selectionKeyEquals(selection, next)} selection={next} title={title} editing={selectionKeyEquals(renaming, next)} renameValue={renameValue} resource={dragResource(next, title, handlerKind)} onRenameChange={setRenameValue} onRenameFinish={() => finishRename(next)} onRenameKeyDown={(event) => { if (event.key === "Escape") { cancelRename.current = true; event.currentTarget.blur(); } if (event.key === "Enter") event.currentTarget.blur(); }} onClick={() => onSelect(next)} onContextMenu={(event) => { event.stopPropagation(); onSelect(next); openContext(event, { selection: next }); }} />;
  return <nav className="explorer explorer--ide" aria-label="Project resources" onContextMenu={(event) => { if (event.target === event.currentTarget) openContext(event, { kind: "view" }); }}>
    <Section id="views" title="views" open={openSections.has("views")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "view" })}>
      {draft?.kind === "view" && <DraftResource label={draft.label} kind="view" />}
      {workspace.views.map((view) => <ViewResource
        key={view.id}
        view={view}
        active={selectionKeyEquals(selection, { kind: "view", id: view.id })}
        editing={selectionKeyEquals(renaming, { kind: "view", id: view.id })}
        renameValue={renameValue}
        onRenameChange={setRenameValue}
        onRenameFinish={() => finishRename({ kind: "view", id: view.id })}
        onRenameKeyDown={(event) => {
          if (event.key === "Escape") {
            cancelRename.current = true;
            event.currentTarget.blur();
          }
          if (event.key === "Enter") event.currentTarget.blur();
        }}
        onClick={() => onSelect({ kind: "view", id: view.id })}
        onContextMenu={(event) => {
          event.stopPropagation();
          onSelect({ kind: "view", id: view.id });
          openContext(event, { selection: { kind: "view", id: view.id } });
        }}
        onOpenTextEditor={() => onOpenViewTextEditor(view.id, view.name ?? view.id)}
        onOpenVariables={() => onOpenVariables({ resourceType: "view", resourceId: view.id }, view.name ?? view.id)}
        open={openViews.has(view.id)}
        onToggle={() => toggleView(view.id)}
      />)}
    </Section>
    <Section id="flows" title="flows" open={openSections.has("flows")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "flow" })}>
      {draft?.kind === "flow" && <DraftResource label={draft.label} kind="flow" />}
      {workspace.flows.map((flow) => (
        <FlowResource
          key={flow.id}
          flow={flow}
          active={selectionKeyEquals(selection, { kind: "flow", id: flow.id })}
          editing={selectionKeyEquals(renaming, { kind: "flow", id: flow.id })}
          renameValue={renameValue}
          onRenameChange={setRenameValue}
          onRenameFinish={() => finishRename({ kind: "flow", id: flow.id })}
          onRenameKeyDown={(event) => {
            if (event.key === "Escape") {
              cancelRename.current = true;
              event.currentTarget.blur();
            }
            if (event.key === "Enter") event.currentTarget.blur();
          }}
          onClick={() => onSelect({ kind: "flow", id: flow.id })}
          onContextMenu={(event) => {
            event.stopPropagation();
            onSelect({ kind: "flow", id: flow.id });
            openContext(event, { selection: { kind: "flow", id: flow.id } });
          }}
          onOpenVariables={() => onOpenVariables({ resourceType: "flow", resourceId: flow.id }, flow.name ?? flow.id)}
          open={openFlows.has(flow.id)}
          onToggle={() => toggleFlow(flow.id)}
        />
      ))}
    </Section>
    <Section id="handlers" title="handlers" open={openSections.has("handlers")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "handler" })}>{draft?.kind === "handler" && <DraftResource label={draft.label} kind="handler" />}{workspace.handlers.map((handler) => item({ kind: "handler", id: handler.id }, handler.name ?? handler.id, handler.kind))}</Section>
    <Section id="commands" title="commands" open={openSections.has("commands")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "command" })}>
      {workspace.commands.items.map((command) => item({ kind: "command", name: command.name }, command.display_name ?? defaultResourceName("Command", command.name))) }
      {item({ kind: "commands" }, "fallbacks")}
    </Section>
    <Section id="schedules" title="schedules" open={openSections.has("schedules")} onToggle={toggle} onContextMenu={(event) => openContext(event, { kind: "schedule" })}>{draft?.kind === "schedule" && <DraftResource label={draft.label} kind="schedule" />}{workspace.schedules.map((schedule) => item({ kind: "schedule", id: schedule.id }, schedule.name ?? schedule.id))}</Section>
    {context && <ContextMenu x={context.x} y={context.y} label="Resource actions" items={contextItems} onClose={() => setContext(null)} />}
  </nav>;
}

function Section({ id, title, open, onToggle, onContextMenu, children }: { id: ResourceSection; title: string; open: boolean; onToggle(section: ResourceSection): void; onContextMenu?(event: MouseEvent): void; children: ReactNode }) {
  const contentId = `explorer-${id}`;
  return <section className={open ? "explorer__section explorer__section--open" : "explorer__section"} onContextMenu={onContextMenu}>
    <button type="button" className="explorer__section-toggle" aria-expanded={open} aria-controls={contentId} onClick={() => onToggle(id)}><span className="explorer__tree-arrow" aria-hidden="true"><ChevronIcon /></span><CategoryIcon category={id} /><span>{title}</span></button>
    <div id={contentId} className="explorer__section-content"><div className="explorer__items">{children}</div></div>
  </section>;
}

function FlowResource({
  flow,
  active,
  editing,
  renameValue,
  onRenameChange,
  onRenameFinish,
  onRenameKeyDown,
  onClick,
  onContextMenu,
  onOpenVariables,
  open,
  onToggle,
}: {
  flow: FlowSummary;
  active: boolean;
  editing: boolean;
  renameValue: string;
  onRenameChange(value: string): void;
  onRenameFinish(): void;
  onRenameKeyDown(event: KeyboardEvent<HTMLInputElement>): void;
  onClick(): void;
  onContextMenu(event: MouseEvent): void;
  onOpenVariables(context: VariableResourceContext, displayName: string): void;
  open: boolean;
  onToggle(): void;
}) {
  const selection: Selection = { kind: "flow", id: flow.id };
  const resource = dragResource(selection, flow.name ?? flow.id, undefined);
  const dragProps = useResourceDraggable(editing ? null : resource);
  const mainClassName = [
    "explorer__item",
    "explorer__flow-main",
    active ? "explorer__item--active" : "",
    resource ? "explorer__item--draggable" : "",
  ].filter(Boolean).join(" ");
  const contentId = `explorer-flow-${flow.id}`;

  return <div className="explorer__flow-resource" onContextMenu={onContextMenu}>
    <ExplorerTreeRow disclosure={{ label: open ? `Collapse ${flow.name ?? flow.id}` : `Expand ${flow.name ?? flow.id}`, expanded: open, controls: contentId, onToggle }}>
      {editing
        ? <div className={mainClassName} aria-current={active ? "page" : undefined}>
            <ResourceIcon selection={selection} title={flow.name ?? flow.id} />
            <input className="explorer__rename-input" aria-label={`Rename ${flow.name ?? flow.id}`} autoFocus value={renameValue} onFocus={(event) => event.currentTarget.select()} onChange={(event) => onRenameChange(event.target.value)} onBlur={onRenameFinish} onKeyDown={onRenameKeyDown} />
          </div>
        : <button
            type="button"
            aria-current={active ? "page" : undefined}
            className={mainClassName}
            onClick={onClick}
            onPointerDown={dragProps.onPointerDown}
            onClickCapture={dragProps.onClickCapture}
          >
            <ResourceIcon selection={selection} title={flow.name ?? flow.id} />
            <strong>{flow.name ?? flow.id}</strong>
          </button>}
    </ExplorerTreeRow>
    <ExplorerTreeGroup id={contentId} open={open}>
      {flow.states.map((stateId) => <span key={stateId} className="explorer-tree__state-group">
        <ExplorerTreeLeaf depth={1} icon={<CircleDot />}>{stateId}</ExplorerTreeLeaf>
        <ExplorerTreeLeaf depth={2} icon={<Braces />} ariaLabel={`Open variables for ${flow.name ?? flow.id}.${stateId}`} onClick={() => onOpenVariables({ resourceType: "state", resourceId: `${flow.id}.${stateId}`, flowId: flow.id, stateId }, `${flow.name ?? flow.id}.${stateId}`)}>Variables</ExplorerTreeLeaf>
      </span>)}
      <ExplorerTreeLeaf depth={1} icon={<Braces />} ariaLabel={`Open variables for ${flow.name ?? flow.id}`} onClick={() => onOpenVariables({ resourceType: "flow", resourceId: flow.id }, flow.name ?? flow.id)}>Variables</ExplorerTreeLeaf>
    </ExplorerTreeGroup>
  </div>;
}

function ViewResource({
  view,
  active,
  editing,
  renameValue,
  onRenameChange,
  onRenameFinish,
  onRenameKeyDown,
  onClick,
  onContextMenu,
  onOpenTextEditor,
  onOpenVariables,
  open,
  onToggle,
}: {
  view: Workspace["views"][number];
  active: boolean;
  editing: boolean;
  renameValue: string;
  onRenameChange(value: string): void;
  onRenameFinish(): void;
  onRenameKeyDown(event: KeyboardEvent<HTMLInputElement>): void;
  onClick(): void;
  onContextMenu(event: MouseEvent): void;
  onOpenTextEditor(): void;
  onOpenVariables(): void;
  open: boolean;
  onToggle(): void;
}) {
  const selection: Selection = { kind: "view", id: view.id };
  const resource = dragResource(selection, view.name ?? view.id, undefined);
  const dragProps = useResourceDraggable(editing ? null : resource);
  const mainClassName = [
    "explorer__item",
    "explorer__view-main",
    active ? "explorer__item--active" : "",
    resource ? "explorer__item--draggable" : "",
  ].filter(Boolean).join(" ");
  const contentId = `explorer-view-${view.id}`;

  return <div className="explorer__view-resource" onContextMenu={onContextMenu}>
    <ExplorerTreeRow disclosure={{ label: open ? `Collapse ${view.name ?? view.id}` : `Expand ${view.name ?? view.id}`, expanded: open, controls: contentId, onToggle }}>
      {editing
        ? <div className={mainClassName} aria-current={active ? "page" : undefined}>
            <ResourceIcon selection={selection} title={view.name ?? view.id} />
            <input className="explorer__rename-input" aria-label={`Rename ${view.name ?? view.id}`} autoFocus value={renameValue} onFocus={(event) => event.currentTarget.select()} onChange={(event) => onRenameChange(event.target.value)} onBlur={onRenameFinish} onKeyDown={onRenameKeyDown} />
          </div>
        : <button
            type="button"
            aria-current={active ? "page" : undefined}
            className={mainClassName}
            onClick={onClick}
            onPointerDown={dragProps.onPointerDown}
            onClickCapture={dragProps.onClickCapture}
          >
            <ResourceIcon selection={selection} title={view.name ?? view.id} />
            <strong>{view.name ?? view.id}</strong>
          </button>}
    </ExplorerTreeRow>
    <ExplorerTreeGroup id={contentId} open={open}>
      <ExplorerTreeLeaf depth={1} icon={<FileText />} ariaLabel={`Open text editor for ${view.name ?? view.id}`} onClick={onOpenTextEditor}>Text editor</ExplorerTreeLeaf>
      <ExplorerTreeLeaf depth={1} icon={<Braces />} ariaLabel={`Open variables for ${view.name ?? view.id}`} onClick={onOpenVariables}>Variables</ExplorerTreeLeaf>
    </ExplorerTreeGroup>
  </div>;
}

function ResourceButton({ active, selection, title, editing, renameValue, resource, onRenameChange, onRenameFinish, onRenameKeyDown, onClick, onContextMenu }: { active: boolean; selection: Selection; title: string; editing: boolean; renameValue: string; resource: DraggableResource | null; onRenameChange(value: string): void; onRenameFinish(): void; onRenameKeyDown(event: KeyboardEvent<HTMLInputElement>): void; onClick(): void; onContextMenu(event: MouseEvent): void }) {
  const dragProps = useResourceDraggable(editing ? null : resource);
  const className = ["explorer__item", active ? "explorer__item--active" : "", resource ? "explorer__item--draggable" : ""].filter(Boolean).join(" ");
  if (editing) return <ExplorerTreeRow><div className={className} aria-current={active ? "page" : undefined} onContextMenu={onContextMenu}><ResourceIcon selection={selection} title={title} /><input className="explorer__rename-input" aria-label={`Rename ${title}`} autoFocus value={renameValue} onFocus={(event) => event.currentTarget.select()} onChange={(event) => onRenameChange(event.target.value)} onBlur={onRenameFinish} onKeyDown={onRenameKeyDown} /></div></ExplorerTreeRow>;
  return <ExplorerTreeRow><button type="button" aria-current={active ? "page" : undefined} className={className} onClick={onClick} onContextMenu={onContextMenu} onPointerDown={dragProps.onPointerDown} onClickCapture={dragProps.onClickCapture}><ResourceIcon selection={selection} title={title} /> <strong>{title}</strong></button></ExplorerTreeRow>;
}

function DraftResource({ kind, label }: ExplorerDraft) {
  const selection: Selection = kind === "command"
      ? { kind, name: label }
      : { kind, id: label };
  return <ExplorerTreeRow><div className="explorer__item explorer__item--active explorer__item--draft" aria-current="page"><ResourceIcon selection={selection} title={label} /><strong>{label}</strong><span className="explorer__draft-indicator">new</span></div></ExplorerTreeRow>;
}

function ChevronIcon() {
  return <ChevronDown aria-hidden="true" />;
}

function CategoryIcon({ category }: { category: ResourceSection }) {
  const icons = {
    views: LayoutGrid,
    flows: Workflow,
    handlers: Zap,
    commands: Terminal,
    schedules: CalendarDays,
  };
  const Icon = icons[category];
  return <span className={`explorer__category-icon explorer__category-icon--${category}`} aria-hidden="true"><Icon /></span>;
}

function draftSection(kind: CreatableResource): ResourceSection {
  if (kind === "command") return "commands";
  return kind === "schedule" ? "schedules" : `${kind}s` as ResourceSection;
}

function selectionSection(selection: Selection): ResourceSection {
  if (selection.kind === "command" || selection.kind === "commands") return "commands";
  if (selection.kind === "schedule") return "schedules";
  return `${selection.kind}s` as ResourceSection;
}

function dragResource(selection: Selection, label: string, handlerKind?: HandlerKind): DraggableResource | null {
  if (selection.kind === "commands" || selection.kind === "command") return null;
  return {
    kind: selection.kind,
    value: selection.id,
    label,
    selection,
    handlerKind,
  };
}

function isRenamable(selection: Selection | null): selection is Exclude<Selection, { kind: "commands" }> {
  return selection !== null && selection.kind !== "commands";
}

function resourceName(selection: Exclude<Selection, { kind: "commands" }>, workspace: Workspace): string {
  if (selection.kind === "command") return workspace.commands.items.find((item) => item.name === selection.name)?.display_name ?? defaultResourceName("Command", selection.name);
  if (selection.kind === "view") return workspace.views.find((item) => item.id === selection.id)?.name ?? selection.id;
  if (selection.kind === "flow") return workspace.flows.find((item) => item.id === selection.id)?.name ?? selection.id;
  if (selection.kind === "schedule") return workspace.schedules.find((item) => item.id === selection.id)?.name ?? selection.id;
  return workspace.handlers.find((item) => item.id === selection.id)?.name ?? selection.id;
}

function defaultResourceName(label: string, id: string): string {
  const match = new RegExp(`^${label.toLowerCase()}_(\\d+)$`).exec(id);
  return match ? `${label} ${match[1]}` : id;
}

function selectionKeyEquals(left: Selection | null, right: Selection): boolean {
  if (!left || left.kind !== right.kind) return false;
  if (left.kind === "commands" || right.kind === "commands") return left.kind === right.kind;
  if (left.kind === "command" && right.kind === "command") return left.name === right.name;
  return "id" in left && "id" in right && left.id === right.id;
}

function variableContextForSelection(selection: Selection): VariableResourceContext | null {
  if (selection.kind === "view") return { resourceType: "view", resourceId: selection.id };
  if (selection.kind === "flow") return { resourceType: "flow", resourceId: selection.id };
  if (selection.kind === "handler") return { resourceType: "handler", resourceId: selection.id };
  return null;
}
