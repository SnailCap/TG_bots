import { useEffect, useRef, useState } from "react";

type MenuSection = "File" | "Edit" | "View" | "Navigate" | "Code" | "Refactor" | "Run" | "Tools" | "Git" | "Window" | "Help";

const sections: readonly MenuSection[] = ["File", "Edit", "View", "Navigate", "Code", "Refactor", "Run", "Tools", "Git", "Window", "Help"];

export function MainMenu({
  canSave,
  canCloseTab,
  canUndo = false,
  onOpenProject,
  onNewProject,
  onSave,
  onCloseTab,
  onUndo,
}: {
  canSave: boolean;
  canCloseTab: boolean;
  canUndo?: boolean;
  onOpenProject(): void;
  onNewProject(): void;
  onSave(): void;
  onCloseTab(): void;
  onUndo?(): void;
}) {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState<MenuSection>("File");
  const rootRef = useRef<HTMLDivElement>(null);

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

  const run = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <div ref={rootRef} className={open ? "main-menu main-menu--open" : "main-menu"}>
      <button
        type="button"
        className="main-menu__trigger"
        aria-label="Main menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <DotsIcon />
      </button>
      {open && (
        <div className="main-menu__panel" role="menu" aria-label="Main menu">
          <nav className="main-menu__sections" aria-label="Main menu sections">
            {sections.map((item) => (
              <button
                key={item}
                type="button"
                className={section === item ? "main-menu__section main-menu__section--active" : "main-menu__section"}
                aria-current={section === item ? "page" : undefined}
                onClick={() => setSection(item)}
              >
                {item}
              </button>
            ))}
          </nav>
          <div className="main-menu__items">
            {section === "File" && <>
              <MenuItem label="New project…" onSelect={() => run(onNewProject)} />
              <MenuItem label="Open project…" onSelect={() => run(onOpenProject)} />
              <MenuSeparator />
              <MenuItem label="Save" shortcut="Ctrl+S" disabled={!canSave} onSelect={() => run(onSave)} />
            </>}
            {section === "Edit" && <MenuItem label="Undo" shortcut="Ctrl+Z" disabled={!canUndo || !onUndo} onSelect={() => run(onUndo ?? (() => undefined))} />}
            {section === "View" && <MenuItem label="Close current tab" shortcut="Ctrl+W" disabled={!canCloseTab} onSelect={() => run(onCloseTab)} />}
            {section !== "File" && section !== "Edit" && section !== "View" && <p className="main-menu__empty">No actions here yet.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function MenuItem({ label, shortcut, disabled = false, onSelect }: { label: string; shortcut?: string; disabled?: boolean; onSelect(): void }) {
  return <button type="button" className="main-menu__item" role="menuitem" disabled={disabled} onClick={onSelect}><span>{label}</span>{shortcut && <kbd>{shortcut}</kbd>}</button>;
}

function MenuSeparator() {
  return <div className="main-menu__separator" role="separator" />;
}

function DotsIcon() {
  return <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="3.25" r="1.15" /><circle cx="8" cy="8" r="1.15" /><circle cx="8" cy="12.75" r="1.15" /></svg>;
}
