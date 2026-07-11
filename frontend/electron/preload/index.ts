import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("studioDesktop", {
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke("desktop:select-directory"),
  revealPath: (targetPath: string): Promise<void> => ipcRenderer.invoke("desktop:reveal-path", targetPath),
  backendInfo: (): Promise<{ baseUrl: string }> => ipcRenderer.invoke("desktop:backend-info"),
});
