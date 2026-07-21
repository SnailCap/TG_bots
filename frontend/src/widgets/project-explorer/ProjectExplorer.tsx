import type { Selection, Workspace } from "../../domain/project";

export type CreatableResource = "view" | "template" | "flow" | "handler" | "schedule";

export function ProjectExplorer({
  workspace,
  selection,
  onSelect,
  onAdd,
}: {
  workspace: Workspace;
  selection: Selection | null;
  onSelect(selection: Selection): void;
  onAdd(kind: CreatableResource): void;
}) {
  return (
    <nav className="explorer" aria-label="Project resources">
      <div className="explorer__project"><p className="eyebrow">Current project</p><strong>{workspace.name}</strong><small title={workspace.project_root}>{workspace.project_root}</small><span>Schema v{workspace.schema_version}</span></div>
      <Section title="Views" onAdd={() => onAdd("view")}>
        {workspace.views.map((view) => <ResourceButton key={view.id} active={selection?.kind === "view" && selection.id === view.id} title={view.id} subtitle={view.source_path} onClick={() => onSelect({ kind: "view", id: view.id })} />)}
      </Section>
      <Section title="Templates" onAdd={() => onAdd("template") }>
        {workspace.templates.map((template) => <ResourceButton key={template.path} active={selection?.kind === "template" && selection.path === template.path} title={template.path} onClick={() => onSelect({ kind: "template", path: template.path })} />)}
      </Section>
      <Section title="Flows" onAdd={() => onAdd("flow") }>
        {workspace.flows.map((flow) => <ResourceButton key={flow.id} active={selection?.kind === "flow" && selection.id === flow.id} title={flow.id} subtitle={flow.source_path} onClick={() => onSelect({ kind: "flow", id: flow.id })} />)}
      </Section>
      <Section title="Handlers" onAdd={() => onAdd("handler") }>
        {workspace.handlers.map((handler) => <ResourceButton key={handler.id} active={selection?.kind === "handler" && selection.id === handler.id} title={handler.id} subtitle={`${handler.kind} · ${handler.status}${handler.usage_count === 0 ? " · unused" : ""}`} onClick={() => onSelect({ kind: "handler", id: handler.id })} />)}
      </Section>
      <Section title="Commands">
        <ResourceButton active={selection?.kind === "commands"} title="commands.json" subtitle={workspace.commands.source_path} onClick={() => onSelect({ kind: "commands" })} />
      </Section>
      <Section title="Schedules" onAdd={() => onAdd("schedule") }>
        {workspace.schedules.map((schedule) => <ResourceButton key={schedule.id} active={selection?.kind === "schedule" && selection.id === schedule.id} title={schedule.id} subtitle={schedule.source_path} onClick={() => onSelect({ kind: "schedule", id: schedule.id })} />)}
      </Section>
    </nav>
  );
}

function Section({ title, onAdd, children }: { title: string; onAdd?: () => void; children: React.ReactNode }) {
  return (
    <section className="explorer__section">
      <header><span>{title}</span>{onAdd && <button type="button" aria-label={`Add ${title.toLowerCase()}`} onClick={onAdd}>+</button>}</header>
      <div className="explorer__items">{children}</div>
    </section>
  );
}

function ResourceButton({ active, title, subtitle, onClick }: { active: boolean; title: string; subtitle?: string; onClick(): void }) {
  return <button type="button" aria-current={active ? "page" : undefined} className={active ? "explorer__item explorer__item--active" : "explorer__item"} onClick={onClick}><strong>{title}</strong>{subtitle && <small>{subtitle}</small>}</button>;
}
