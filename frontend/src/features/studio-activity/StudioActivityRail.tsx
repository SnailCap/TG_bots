export type StudioActivity = "resources" | "users";

export function StudioActivityRail({ active, onSelect, terminalOpen, onToggleTerminal, settingsOpen, onOpenSettings }: { active: StudioActivity; onSelect(activity: StudioActivity): void; terminalOpen: boolean; onToggleTerminal(): void; settingsOpen: boolean; onOpenSettings(): void }) {
  return (
    <nav className="studio-side-rail studio-activity-rail" aria-label="Studio pages">
      <button
        type="button"
        className={active === "resources" ? "studio-side-rail__button studio-side-rail__button--active studio-activity-rail__button" : "studio-side-rail__button studio-activity-rail__button"}
        aria-label="Resources"
        aria-current={active === "resources" ? "page" : undefined}
        title="Resources"
        data-tooltip="Resources"
        onClick={() => onSelect("resources")}
      >
        <ResourcesIcon />
      </button>
      <button
        type="button"
        className={active === "users" ? "studio-side-rail__button studio-side-rail__button--active studio-activity-rail__button" : "studio-side-rail__button studio-activity-rail__button"}
        aria-label="Users"
        aria-current={active === "users" ? "page" : undefined}
        title="Users"
        data-tooltip="Users"
        onClick={() => onSelect("users")}
      >
        <UsersIcon />
      </button>
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

function ResourcesIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="3.25" y="3.25" width="5.1" height="5.1" rx=".5" /><rect x="11.65" y="3.25" width="5.1" height="5.1" rx=".5" /><rect x="3.25" y="11.65" width="5.1" height="5.1" rx=".5" /><rect x="11.65" y="11.65" width="5.1" height="5.1" rx=".5" /></svg>;
}

function UsersIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="7.2" cy="7" r="2.7" /><path d="M2.4 16.7c.35-3.5 1.95-5.3 4.8-5.3s4.45 1.8 4.8 5.3M12 5.8a2.55 2.55 0 0 1 0 5m1.2 1.2c2.55.3 3.95 1.85 4.35 4.7" /></svg>;
}

function TerminalIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="2.8" y="4" width="14.4" height="12" rx="1" /><path d="m5.6 8 2.2 2-2.2 2m4.5.2h3.6" /></svg>;
}

function SettingsIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m8.15 2.7.45-1.15h2.8l.45 1.15 1.08.45 1.13-.5 1.98 1.98-.5 1.13.45 1.08 1.15.45v2.8l-1.15.45-.45 1.08.5 1.13-1.98 1.98-1.13-.5-1.08.45-.45 1.15H8.6l-.45-1.15-1.08-.45-1.13.5-1.98-1.98.5-1.13-.45-1.08-1.15-.45v-2.8l1.15-.45.45-1.08-.5-1.13 1.98-1.98 1.13.5 1.08-.45Z" /><circle cx="10" cy="8.7" r="2.3" /></svg>;
}
