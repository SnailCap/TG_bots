import { useEffect, useMemo, useRef, useState } from "react";

import type { Workspace } from "../domain/project";
import { StudioPage } from "../pages/studio/StudioPage";
import { Toast } from "../shared/ui/Toast";
import { StudioApi, type StudioApiClient } from "../studio/api";
import { BackendStatusCard } from "./BackendStatusCard";

export const LAST_PROJECT_STORAGE_KEY = "tg-bot-studio.dev.last-project";
export const RECENT_PROJECTS_STORAGE_KEY = "tg-bot-studio.dev.recent-projects";

function loadLastProjectPath(): string | null {
  if (!import.meta.env.DEV) return null;
  try {
    return window.localStorage.getItem(LAST_PROJECT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function saveLastProjectPath(path: string): void {
  if (!import.meta.env.DEV) return;
  try {
    window.localStorage.setItem(LAST_PROJECT_STORAGE_KEY, path);
  } catch {
    // Local persistence is a development convenience and must not block Studio.
  }
}

function loadRecentProjectPaths(): string[] {
  try {
    const value = window.localStorage.getItem(RECENT_PROJECTS_STORAGE_KEY);
    const parsed: unknown = value ? JSON.parse(value) : [];
    return Array.isArray(parsed) ? parsed.filter((path): path is string => typeof path === "string") : [];
  } catch {
    return [];
  }
}

function saveRecentProjectPath(path: string): string[] {
  const recent = [path, ...loadRecentProjectPaths().filter((item) => item !== path)].slice(0, 6);
  try {
    window.localStorage.setItem(RECENT_PROJECTS_STORAGE_KEY, JSON.stringify(recent));
  } catch {
    // Recent project links are a development convenience and must not block Studio.
  }
  return recent;
}

export function defaultApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
}

export function App({ apiBaseUrl = defaultApiBaseUrl(), apiClient }: { apiBaseUrl?: string; apiClient?: StudioApiClient }) {
  const api = useMemo(() => apiClient ?? new StudioApi(apiBaseUrl), [apiBaseUrl, apiClient]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [openPath, setOpenPath] = useState("");
  const [parentPath, setParentPath] = useState("");
  const [name, setName] = useState("my-bot");
  const [packageName, setPackageName] = useState("my_bot");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recentProjects, setRecentProjects] = useState(loadRecentProjectPaths);
  const autoOpenAttempted = useRef(false);
  const autoOpenCancelled = useRef(false);

  const load = async (operation: () => Promise<Workspace>) => {
    autoOpenCancelled.current = true;
    setBusy(true);
    try {
      const next = await operation();
      saveLastProjectPath(next.project_root);
      setRecentProjects(saveRecentProjectPath(next.project_root));
      setWorkspace(next);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (autoOpenAttempted.current) return;
    autoOpenAttempted.current = true;
    const path = loadLastProjectPath();
    if (!path) return;
    void api.open(path)
      .then((next) => {
        if (autoOpenCancelled.current) return;
        saveLastProjectPath(next.project_root);
        setRecentProjects(saveRecentProjectPath(next.project_root));
        setWorkspace(next);
      })
      .catch(() => {
        // Keep the development convenience through transient backend restarts.
      });
  }, [api]);

  const pick = async (setValue: (value: string) => void) => {
    const value = await window.studioDesktop?.selectDirectory();
    if (value) setValue(value);
  };

  const openProjectFromSwitcher = async (path: string) => {
    if (!path) {
      const selected = await window.studioDesktop?.selectDirectory();
      if (selected) await load(() => api.open(selected));
      return;
    }
    await load(() => api.open(path));
  };

  const createProject = async () => {
    const next = await api.create(parentPath, name, packageName);
    try {
      if (window.studioDesktop?.prepareProject) {
        await window.studioDesktop.approveProjectRoot?.(next.project_root);
        await window.studioDesktop.prepareProject({
          projectRoot: next.project_root,
          packageName: next.package,
        });
      }
    } catch (caught) {
      const reason = caught instanceof Error ? caught.message : "unexpected environment error";
      throw new Error(
        `Project files were created at ${next.project_root}, but Python setup failed: ${reason}. `
          + "Open that project to retry setup automatically on Run.",
      );
    }
    return next;
  };

  if (workspace) return <StudioPage key={workspace.project_id} api={api} apiBaseUrl={apiBaseUrl} initialWorkspace={workspace} recentProjects={recentProjects} onOpenProject={(path) => void openProjectFromSwitcher(path)} onNewProject={() => { autoOpenCancelled.current = true; setWorkspace(null); }} />;
  return (
    <main className="welcome" aria-busy={busy}>
      <section className="welcome__content">
        <header className="welcome__intro">
          <p className="eyebrow">Declarative Project Studio</p>
          <h1>Build a Telegram bot with a visible project graph.</h1>
          <p>Open an existing project or create an autonomous Python starter. Studio edits deployable files; it is not part of the bot runtime.</p>
          <BackendStatusCard apiBaseUrl={apiBaseUrl} />
        </header>
        {error && <Toast message={error} tone="error" onDismiss={() => setError("")} />}
        <section className="welcome-card" aria-labelledby="open-project-title">
          <div className="section-heading"><div><p className="eyebrow">Continue working</p><h2 id="open-project-title">Open a project</h2></div><p>Load the folder that contains <code>resources/</code>.</p></div>
          <label>Existing project<input value={openPath} onChange={(event) => setOpenPath(event.target.value)} placeholder="C:\projects\my-bot" /></label>
          <div className="form-actions"><button type="button" className="button--secondary" onClick={() => void pick(setOpenPath)}>Choose folder…</button><button type="button" disabled={!openPath || busy} onClick={() => void load(() => api.open(openPath))}>{busy ? "Opening…" : "Open project"}</button></div>
        </section>
        <section className="welcome-card" aria-labelledby="create-project-title">
          <div className="section-heading"><div><p className="eyebrow">Start from a safe baseline</p><h2 id="create-project-title">Create a new bot project</h2></div><p>Creates the project, selects a compatible Python and installs its local environment automatically.</p></div>
          <div className="form-grid form-grid--two"><label>New project name<input value={name} onChange={(event) => setName(event.target.value)} /></label><label>Python package<input value={packageName} onChange={(event) => setPackageName(event.target.value)} /></label></div>
          <label>Parent directory<input value={parentPath} onChange={(event) => setParentPath(event.target.value)} placeholder="C:\projects" /></label>
          <div className="form-actions"><button type="button" className="button--secondary" onClick={() => void pick(setParentPath)}>Choose parent folder…</button><button type="button" disabled={!parentPath || !name || !packageName || busy} onClick={() => void load(createProject)}>{busy ? "Creating and configuring…" : "Create project"}</button></div>
        </section>
      </section>
    </main>
  );
}

export { BackendStatusCard } from "./BackendStatusCard";
