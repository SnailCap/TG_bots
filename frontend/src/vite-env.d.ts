/// <reference types="vite/client" />

interface Window {
  studioDesktop?: {
    backendInfo(): Promise<{ baseUrl: string }>;
    selectDirectory(): Promise<string | null>;
  };
}
