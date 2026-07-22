import { useEffect, useRef, useState, type CSSProperties } from "react";

import type { Workspace } from "../../domain/project";

export function ProjectSwitcher({
  workspace,
  recentProjects,
  onOpenProject,
  onNewProject,
}: {
  workspace: Workspace;
  recentProjects: readonly string[];
  onOpenProject(path: string): void;
  onNewProject(): void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const currentPath = workspace.project_root;
  const recent = recentProjects.filter((path) => path !== currentPath).slice(0, 5);

  useEffect(() => {
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  const selectProject = (path: string) => {
    setOpen(false);
    onOpenProject(path);
  };

  return (
    <div ref={rootRef} className={open ? "project-switcher project-switcher--open" : "project-switcher"}>
      <button
        type="button"
        className="project-switcher__trigger"
        aria-label="Project menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <ProjectMark name={workspace.name} />
        <span className="project-switcher__name">{workspace.name}</span>
        <ChevronIcon />
      </button>
      {open && (
        <div className="project-switcher__menu" role="menu" aria-label="Project menu">
          <div className="project-switcher__actions">
            <button type="button" role="menuitem" onClick={() => { setOpen(false); onOpenProject(""); }}><FolderIcon />Open project…</button>
            <button type="button" role="menuitem" onClick={() => { setOpen(false); onNewProject(); }}><PlusIcon />New project…</button>
          </div>
          <div className="project-switcher__divider" />
          <section className="project-switcher__section">
            <span className="project-switcher__section-label">Current project</span>
            <button type="button" className="project-switcher__current" role="menuitem" onClick={() => setOpen(false)}>
              <ProjectMark name={workspace.name} />
              <span><strong>{workspace.name}</strong><small title={currentPath}>{currentPath}</small></span>
            </button>
          </section>
          <div className="project-switcher__divider" />
          <section className="project-switcher__section">
            <span className="project-switcher__section-label">Recent projects</span>
            {recent.length ? recent.map((path) => (
              <button type="button" className="project-switcher__recent" role="menuitem" key={path} onClick={() => selectProject(path)}>
                <FolderIcon /><span><strong>{projectName(path)}</strong><small title={path}>{path}</small></span>
              </button>
            )) : <span className="project-switcher__empty">No other recent projects</span>}
          </section>
        </div>
      )}
    </div>
  );
}

function ProjectMark({ name }: { name: string }) {
  return <span className="project-switcher__mark" style={{ "--project-mark": projectColor(name) } as CSSProperties}>{initials(name)}</span>;
}

function ChevronIcon() {
  return <svg className="project-switcher__chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4.5 6.25 3.5 3.5 3.5-3.5" /></svg>;
}

function FolderIcon() {
  return <svg className="project-switcher__action-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.3 4.7h4l1.1 1.4h6.3v5.7c0 .5-.4.9-.9.9H3.2c-.5 0-.9-.4-.9-.9V5.6c0-.5.4-.9.9-.9Z" /></svg>;
}

function PlusIcon() {
  return <svg className="project-switcher__action-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg>;
}

function initials(name: string): string {
  const words = name.split(/[\s_-]+/).filter(Boolean);
  return (words.length > 1 ? words.slice(0, 2).map((word) => word[0]).join("") : name.slice(0, 2)).toUpperCase();
}

function projectName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

function projectColor(name: string): string {
  const colors = ["#9a7529", "#367d87", "#695da1", "#9a5f4d", "#46785f"];
  const index = [...name].reduce((sum, character) => sum + character.codePointAt(0)!, 0) % colors.length;
  return colors[index];
}
