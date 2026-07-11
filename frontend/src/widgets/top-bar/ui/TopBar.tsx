import { useState } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import styles from "./TopBar.module.css";

export function TopBar() {
  const studio = useStudio();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("My Telegram Bot");
  const [directory, setDirectory] = useState("");
  const isRunning = studio.control.status.phase === "running" || studio.control.status.phase === "starting";

  function canReplaceWorkspace(): boolean {
    return (
      !studio.workspace.tabs.some((tab) => tab.dirty) ||
      window.confirm("Discard all unsaved changes and switch projects?")
    );
  }

  async function chooseDirectory() {
    const selected = await window.studioDesktop?.selectDirectory();
    if (selected) setDirectory(selected);
  }

  async function openProject() {
    const selected = await window.studioDesktop?.selectDirectory();
    if (selected && canReplaceWorkspace()) await studio.openProject(selected);
  }

  async function submitProject(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !directory.trim()) return;
    if (!canReplaceWorkspace()) return;
    const created = await studio.createProjectAndOpen({ name: name.trim(), directory: directory.trim() });
    if (created) setCreating(false);
  }

  return (
    <>
      <header className={styles.bar}>
        <div className={styles.brand} aria-label="Telegram Bot Studio">
          <span className={styles.logo}>B</span>
          <span>Bot Studio</span>
        </div>
        <select
          className={styles.projectSelect}
          aria-label="Current project"
          value={studio.currentProject?.id ?? ""}
          onChange={(event) => {
            if (event.target.value && canReplaceWorkspace()) {
              void studio.selectProject(event.target.value);
            }
          }}
          disabled={studio.loading}
        >
          <option value="">Select a project…</option>
          {studio.projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <button className={styles.secondary} onClick={() => setCreating(true)}>
          New
        </button>
        <button className={styles.secondary} onClick={() => void openProject()}>
          Open
        </button>
        <div className={styles.spacer} />
        <button
          className={styles.secondary}
          onClick={() => void studio.validate()}
          disabled={!studio.currentProject || studio.validating}
        >
          {studio.validating ? "Validating…" : "Validate"}
        </button>
        <button
          className={isRunning ? styles.stop : styles.run}
          onClick={() => void (isRunning ? studio.stop() : studio.run())}
          disabled={!studio.currentProject || studio.control.pending !== null}
        >
          {studio.control.pending ? "Please wait…" : isRunning ? "■ Stop" : "▶ Run"}
        </button>
        <div className={styles.status} data-phase={studio.control.status.phase}>
          <span className={styles.statusDot} />
          <div>
            <strong>{studio.control.status.phase}</strong>
            <small>
              {studio.control.status.bot?.username
                ? `@${studio.control.status.bot.username}`
                : studio.control.status.telegramConnected
                  ? "Telegram connected"
                  : "Telegram offline"}
            </small>
          </div>
        </div>
      </header>

      {creating && (
        <div className={styles.overlay} role="presentation" onMouseDown={() => setCreating(false)}>
          <form className={styles.dialog} onSubmit={submitProject} onMouseDown={(event) => event.stopPropagation()}>
            <h2>Create bot project</h2>
            <label>
              Project name
              <input value={name} onChange={(event) => setName(event.target.value)} autoFocus />
            </label>
            <label>
              Project directory
              <span className={styles.pathRow}>
                <input value={directory} onChange={(event) => setDirectory(event.target.value)} />
                <button type="button" onClick={() => void chooseDirectory()}>
                  Browse…
                </button>
              </span>
              <small>Choose or create an empty folder dedicated to this bot project.</small>
            </label>
            <div className={styles.dialogActions}>
              <button type="button" onClick={() => setCreating(false)}>
                Cancel
              </button>
              <button className={styles.run} type="submit" disabled={!name.trim() || !directory.trim()}>
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
