import { useMemo, useState } from "react";

import type { Workspace } from "../domain/project";
import { StudioPage } from "../pages/studio/StudioPage";
import { StudioApi, type StudioApiClient } from "../studio/api";
import { BackendStatusCard } from "./BackendStatusCard";

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

  const load = async (operation: () => Promise<Workspace>) => {
    setBusy(true);
    try {
      setWorkspace(await operation());
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  };

  const pick = async (setValue: (value: string) => void) => {
    const value = await window.studioDesktop?.selectDirectory();
    if (value) setValue(value);
  };

  if (workspace) return <StudioPage key={workspace.project_id} api={api} apiBaseUrl={apiBaseUrl} initialWorkspace={workspace} />;
  return (
    <main className="welcome" aria-busy={busy}>
      <section className="welcome__content">
        <header className="welcome__intro">
          <p className="eyebrow">Declarative Project Studio</p>
          <h1>Build a Telegram bot with a visible project graph.</h1>
          <p>Open an existing schema v3 project or create an autonomous Python starter. Studio edits deployable files; it is not part of the bot runtime.</p>
          <BackendStatusCard apiBaseUrl={apiBaseUrl} />
        </header>
        {error && <p className="alert alert--error" role="alert">{error}</p>}
        <section className="welcome-card" aria-labelledby="open-project-title">
          <div className="section-heading"><div><p className="eyebrow">Continue working</p><h2 id="open-project-title">Open a project</h2></div><p>Load the folder that contains <code>resources/</code>.</p></div>
          <label>Existing schema v3 project<input value={openPath} onChange={(event) => setOpenPath(event.target.value)} placeholder="C:\projects\my-bot" /></label>
          <div className="form-actions"><button type="button" className="button--secondary" onClick={() => void pick(setOpenPath)}>Choose folder…</button><button type="button" disabled={!openPath || busy} onClick={() => void load(() => api.open(openPath))}>{busy ? "Opening…" : "Open project"}</button></div>
        </section>
        <section className="welcome-card" aria-labelledby="create-project-title">
          <div className="section-heading"><div><p className="eyebrow">Start from a safe baseline</p><h2 id="create-project-title">Create a new bot project</h2></div><p>Creates the schema, starter code, deployment files and an empty schedules directory.</p></div>
          <div className="form-grid form-grid--two"><label>New project name<input value={name} onChange={(event) => setName(event.target.value)} /></label><label>Python package<input value={packageName} onChange={(event) => setPackageName(event.target.value)} /></label></div>
          <label>Parent directory<input value={parentPath} onChange={(event) => setParentPath(event.target.value)} placeholder="C:\projects" /></label>
          <div className="form-actions"><button type="button" className="button--secondary" onClick={() => void pick(setParentPath)}>Choose parent folder…</button><button type="button" disabled={!parentPath || !name || !packageName || busy} onClick={() => void load(() => api.create(parentPath, name, packageName))}>{busy ? "Creating…" : "Create v3 starter"}</button></div>
        </section>
      </section>
    </main>
  );
}

export { BackendStatusCard } from "./BackendStatusCard";
