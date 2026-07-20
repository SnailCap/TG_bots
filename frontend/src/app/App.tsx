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
    <main className="welcome">
      <section>
        <p className="eyebrow">Declarative Project Studio</p>
        <h1>Telegram Bot Studio</h1>
        <p>Edit a complete schema v3 application graph and generate an autonomous Python bot.</p>
        <BackendStatusCard apiBaseUrl={apiBaseUrl} />
        {error && <p className="error">{error}</p>}
        <div className="welcome__actions">
          <label>Existing schema v3 project<input value={openPath} onChange={(event) => setOpenPath(event.target.value)} placeholder="C:\projects\my-bot" /></label>
          <div><button type="button" className="button--quiet" onClick={() => void pick(setOpenPath)}>Choose…</button><button type="button" disabled={!openPath || busy} onClick={() => void load(() => api.open(openPath))}>Open project</button></div>
        </div>
        <div className="welcome__actions">
          <label>New project name<input value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>Python package<input value={packageName} onChange={(event) => setPackageName(event.target.value)} /></label>
          <label>Parent directory<input value={parentPath} onChange={(event) => setParentPath(event.target.value)} /></label>
          <div><button type="button" className="button--quiet" onClick={() => void pick(setParentPath)}>Choose parent…</button><button type="button" disabled={!parentPath || !name || !packageName || busy} onClick={() => void load(() => api.create(parentPath, name, packageName))}>Create v3 starter</button></div>
        </div>
      </section>
    </main>
  );
}

export { BackendStatusCard } from "./BackendStatusCard";
