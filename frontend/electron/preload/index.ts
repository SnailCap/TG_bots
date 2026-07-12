import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("studioDesktop", {
  backendInfo: (): Promise<{ baseUrl: string }> => ipcRenderer.invoke("desktop:backend-info"),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke("desktop:select-directory"),
});
