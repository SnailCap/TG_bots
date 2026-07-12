import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import "./app/styles.css";

async function resolveApiBaseUrl(): Promise<string | undefined> {
  if (import.meta.env.VITE_API_BASE_URL || !window.studioDesktop) return undefined;

  try {
    return (await window.studioDesktop.backendInfo()).baseUrl;
  } catch {
    return undefined;
  }
}

async function bootstrap(): Promise<void> {
  const apiBaseUrl = await resolveApiBaseUrl();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App apiBaseUrl={apiBaseUrl} />
    </StrictMode>,
  );
}

void bootstrap();
