import { contextBridge, ipcRenderer } from "electron";

import type { OpenCodeInput, ProjectProcessEvent, RunProjectInput, StudioDesktop } from "../contracts";

const desktop: StudioDesktop = {
  backendInfo: (): Promise<{ baseUrl: string }> => ipcRenderer.invoke("desktop:backend-info"),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke("desktop:select-directory"),
  openCode: (input: OpenCodeInput): Promise<void> => ipcRenderer.invoke("desktop:open-code", input),
  approveProjectRoot: (projectRoot: string): Promise<void> => ipcRenderer.invoke("desktop:approve-project-root", projectRoot),
  runProject: (input: RunProjectInput) => ipcRenderer.invoke("desktop:run-project", input),
  stopProject: (projectRoot: string): Promise<void> => ipcRenderer.invoke("desktop:stop-project", projectRoot),
  projectRunStatus: (projectRoot: string) => ipcRenderer.invoke("desktop:project-run-status", projectRoot),
  onProjectOutput: (listener: (event: ProjectProcessEvent) => void) => {
    const receive = (_event: Electron.IpcRendererEvent, value: ProjectProcessEvent) => listener(value);
    ipcRenderer.on("desktop:project-output", receive);
    return () => ipcRenderer.removeListener("desktop:project-output", receive);
  },
};

contextBridge.exposeInMainWorld("studioDesktop", desktop);
