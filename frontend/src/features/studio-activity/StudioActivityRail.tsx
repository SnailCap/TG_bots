import type { ComponentType } from "react";
import { Settings, SquareTerminal } from "lucide-react";
import { NavLink } from "react-router-dom";

type StudioRailRoute = {
  id: string;
  path: string;
  label: string;
  icon: ComponentType;
};

export function StudioActivityRail({ routes, terminalOpen, onToggleTerminal, settingsOpen, onOpenSettings }: { routes: readonly StudioRailRoute[]; terminalOpen: boolean; onToggleTerminal(): void; settingsOpen: boolean; onOpenSettings(): void }) {
  return (
    <nav className="studio-side-rail studio-activity-rail" aria-label="Studio pages">
      {routes.map(({ id, path, label, icon: Icon }) => (
        <NavLink
          key={id}
          to={path}
          className={({ isActive }) => isActive
            ? "studio-side-rail__button studio-side-rail__button--active studio-activity-rail__button"
            : "studio-side-rail__button studio-activity-rail__button"}
          aria-label={label}
          title={label}
          data-tooltip={label}
        >
          <Icon />
        </NavLink>
      ))}
      <div className="studio-activity-rail__utility">
        <button
          type="button"
          className={terminalOpen ? "studio-side-rail__button studio-side-rail__button--active studio-activity-rail__button" : "studio-side-rail__button studio-activity-rail__button"}
          aria-label="Terminal"
          aria-pressed={terminalOpen}
          title="Terminal"
          data-tooltip="Terminal"
          onClick={onToggleTerminal}
        >
          <TerminalIcon />
        </button>
        <button
          type="button"
          className={settingsOpen ? "studio-side-rail__button studio-side-rail__button--active studio-activity-rail__button" : "studio-side-rail__button studio-activity-rail__button"}
          aria-label="Settings"
          aria-pressed={settingsOpen}
          title="Settings"
          data-tooltip="Settings"
          onClick={onOpenSettings}
        >
          <SettingsIcon />
        </button>
      </div>
    </nav>
  );
}

function TerminalIcon() {
  return <SquareTerminal aria-hidden="true" />;
}

function SettingsIcon() {
  return <Settings aria-hidden="true" />;
}
