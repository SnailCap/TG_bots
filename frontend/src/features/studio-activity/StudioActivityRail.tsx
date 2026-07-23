import type { ComponentType } from "react";
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
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="2.8" y="4" width="14.4" height="12" rx="1" /><path d="m5.6 8 2.2 2-2.2 2m4.5.2h3.6" /></svg>;
}

function SettingsIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m8.15 2.7.45-1.15h2.8l.45 1.15 1.08.45 1.13-.5 1.98 1.98-.5 1.13.45 1.08 1.15.45v2.8l-1.15.45-.45 1.08.5 1.13-1.98 1.98-1.13-.5-1.08.45-.45 1.15H8.6l-.45-1.15-1.08-.45-1.13.5-1.98-1.98.5-1.13-.45-1.08-1.15-.45v-2.8l1.15-.45.45-1.08-.5-1.13 1.98-1.98 1.13.5 1.08-.45Z" /><circle cx="10" cy="8.7" r="2.3" /></svg>;
}
