/// <reference types="vite/client" />

interface StudioDesktopApi {
  selectDirectory(): Promise<string | null>;
  revealPath(path: string): Promise<void>;
  backendInfo(): Promise<{ baseUrl: string }>;
}

interface Window {
  studioDesktop?: StudioDesktopApi;
}
