import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./app/styles/global.css";
import { App } from "./app/App";
import { apiClient } from "./shared/api/client";

async function bootstrap(): Promise<void> {
  if (!import.meta.env.VITE_API_BASE_URL && window.studioDesktop) {
    try {
      const backend = await window.studioDesktop.backendInfo();
      apiClient.setBaseUrl(`${backend.baseUrl}/api/v1`);
    } catch {
      // The first API request will surface a normal connection error.
    }
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void bootstrap();
