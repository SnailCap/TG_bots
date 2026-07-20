import { contextBridge, ipcRenderer } from "electron";

import type { OpenCodeInput, StudioDesktop } from "../contracts";

const desktop: StudioDesktop = {
  backendInfo: (): Promise<{ baseUrl: string }> => ipcRenderer.invoke("desktop:backend-info"),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke("desktop:select-directory"),
  openCode: (input: OpenCodeInput): Promise<void> => ipcRenderer.invoke("desktop:open-code", input),
};

contextBridge.exposeInMainWorld("studioDesktop", desktop);
