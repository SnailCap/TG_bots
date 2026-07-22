export type StudioActivity = "resources";

export function StudioActivityRail({ active, onSelect, settingsOpen, onOpenSettings }: { active: StudioActivity; onSelect(activity: StudioActivity): void; settingsOpen: boolean; onOpenSettings(): void }) {
  return (
    <nav className="studio-activity-rail" aria-label="Studio pages">
      <button
        type="button"
        className={active === "resources" ? "studio-activity-rail__button studio-activity-rail__button--active" : "studio-activity-rail__button"}
        aria-label="Resources"
        aria-current={active === "resources" ? "page" : undefined}
        title="Resources"
        data-tooltip="Resources"
        onClick={() => onSelect("resources")}
      >
        <ResourcesIcon />
      </button>
      <div className="studio-activity-rail__utility">
        <button
          type="button"
          className={settingsOpen ? "studio-activity-rail__button studio-activity-rail__button--active" : "studio-activity-rail__button"}
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

function SettingsIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m8.15 2.7.45-1.15h2.8l.45 1.15 1.08.45 1.13-.5 1.98 1.98-.5 1.13.45 1.08 1.15.45v2.8l-1.15.45-.45 1.08.5 1.13-1.98 1.98-1.13-.5-1.08.45-.45 1.15H8.6l-.45-1.15-1.08-.45-1.13.5-1.98-1.98.5-1.13-.45-1.08-1.15-.45v-2.8l1.15-.45.45-1.08-.5-1.13 1.98-1.98 1.13.5 1.08-.45Z" /><circle cx="10" cy="8.7" r="2.3" /></svg>;
}
