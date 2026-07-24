import { useEffect, useMemo, useRef, useState } from "react";

import type { Workspace } from "../domain/project";
import { StudioPage } from "../pages/studio/StudioPage";
import { useFieldHistory } from "../shared/lib/useFieldHistory";
import { Toast } from "../shared/ui/Toast";
import { StudioApi, type StudioApiClient } from "../studio/api";
import { BackendStatusCard } from "./BackendStatusCard";

export const LAST_PROJECT_STORAGE_KEY = "tg-bot-studio.dev.last-project";
export const RECENT_PROJECTS_STORAGE_KEY = "tg-bot-studio.dev.recent-projects";

type LauncherScreen = "projects" | "create" | "open";

function projectLabel(projectPath: string): string {
  return projectPath.split(/[\\/]/).filter(Boolean).at(-1) || projectPath;
}

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
  useFieldHistory();
  const api = useMemo(() => apiClient ?? new StudioApi(apiBaseUrl), [apiBaseUrl, apiClient]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [launcherScreen, setLauncherScreen] = useState<LauncherScreen>("projects");
  const [openPath, setOpenPath] = useState("");
  const [parentPath, setParentPath] = useState("");
  const [name, setName] = useState("my-bot");
  const [packageName] = useState("my_bot");
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

  const openProjectFromDisk = async () => {
    const selectDirectory = window.studioDesktop?.selectDirectory;
    if (!selectDirectory) {
      setLauncherScreen("open");
      return;
    }
    const selected = await selectDirectory();
    if (selected) await load(() => api.open(selected));
  };

  const createProject = async () => {
    const next = await api.create(parentPath, name);
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
      <header className="welcome__titlebar">
        <span className="welcome__brand">Telegram Bot Studio</span>
        <div className="welcome__backend"><BackendStatusCard apiBaseUrl={apiBaseUrl} /></div>
      </header>
      <section className="welcome__launcher" key={launcherScreen}>
        {launcherScreen === "projects" && <>
          <header className="welcome__launcher-header">
            <h1>Projects</h1>
            <div className="welcome__actions">
              <button type="button" className="button--secondary" onClick={() => void openProjectFromDisk()}>Open</button>
              <button type="button" onClick={() => setLauncherScreen("create")}>New project</button>
            </div>
          </header>
          {recentProjects.length > 0
            ? <div className="welcome__project-list" role="list">
              {recentProjects.map((projectPath) => <button type="button" className="welcome__project" role="listitem" key={projectPath} disabled={busy} onClick={() => void load(() => api.open(projectPath))}>
                <ProjectMark />
                <span><strong>{projectLabel(projectPath)}</strong><small>{projectPath}</small></span>
                <ChevronRight />
              </button>)}
            </div>
            : <div className="welcome__empty"><ProjectMark /><p>No recent projects</p></div>}
        </>}
        {launcherScreen === "open" && <section className="welcome__form-panel" aria-label="Open project">
          <LauncherHeader title="Open project" onBack={() => setLauncherScreen("projects")} />
          <label>Project folder<input autoFocus value={openPath} onChange={(event) => setOpenPath(event.target.value)} /></label>
          <div className="form-actions"><button type="button" className="button--secondary" onClick={() => void pick(setOpenPath)}>Choose folder…</button><button type="button" disabled={!openPath || busy} onClick={() => void load(() => api.open(openPath))}>{busy ? "Opening…" : "Open project"}</button></div>
        </section>}
        {launcherScreen === "create" && <section className="welcome__form-panel" aria-label="New project">
          <LauncherHeader title="New project" onBack={() => setLauncherScreen("projects")} />
          <label>Project name<input autoFocus value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>Location<input value={parentPath} onChange={(event) => setParentPath(event.target.value)} /></label>
          <div className="form-actions"><button type="button" className="button--secondary" onClick={() => void pick(setParentPath)}>Choose parent folder…</button><button type="button" disabled={!parentPath || !name || !packageName || busy} onClick={() => void load(createProject)}>{busy ? "Creating and configuring…" : "Create project"}</button></div>
        </section>}
      </section>
      {error && <Toast message={error} tone="error" onDismiss={() => setError("")} />}
    </main>
  );
}

function LauncherHeader({ title, onBack }: { title: string; onBack(): void }) {
  return <header className="welcome__launcher-header"><button type="button" className="welcome__back" aria-label="Back to projects" onClick={onBack}><ChevronLeft /></button><h1>{title}</h1></header>;
}

function ProjectMark() {
  return <span className="welcome__project-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3.5 7.5h6l1.8 2H20.5v8.8a2.2 2.2 0 0 1-2.2 2.2H5.7a2.2 2.2 0 0 1-2.2-2.2z" /><path d="M3.5 9.5h17" /></svg></span>;
}

function ChevronRight() {
  return <svg className="welcome__project-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>;
}

function ChevronLeft() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg>;
}

export { BackendStatusCard } from "./BackendStatusCard";
