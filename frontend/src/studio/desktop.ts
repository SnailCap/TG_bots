import type { IdeAdapter, LocalRunResult, LocalRunStatus, OpenCodeInput, ProjectProcessEvent, RunProjectInput } from "../../electron/contracts";
import type { OpenCodeTarget } from "../domain/project";

export async function openCode(target: OpenCodeTarget, adapter?: IdeAdapter): Promise<void> {
  if (!window.studioDesktop) throw new Error("Open code is available in the desktop Studio application.");
  const input: OpenCodeInput = { ...target, adapter };
  await window.studioDesktop.openCode(input);
}

export async function approveProjectRoot(projectRoot: string): Promise<void> {
  if (!window.studioDesktop?.approveProjectRoot) return;
  await window.studioDesktop.approveProjectRoot(projectRoot);
}

export async function runLocalProject(input: RunProjectInput): Promise<LocalRunResult> {
  if (!window.studioDesktop?.runProject) throw new Error("Local run is available in the desktop Studio application.");
  return window.studioDesktop.runProject(input);
}

export async function stopLocalProject(projectRoot: string): Promise<void> {
  if (!window.studioDesktop?.stopProject) throw new Error("Local stop is available in the desktop Studio application.");
  await window.studioDesktop.stopProject(projectRoot);
}

export async function localProjectStatus(projectRoot: string): Promise<LocalRunStatus> {
  if (!window.studioDesktop?.projectRunStatus) return { running: false, pid: null };
  return window.studioDesktop.projectRunStatus(projectRoot);
}

export function onLocalProjectOutput(listener: (event: ProjectProcessEvent) => void): () => void {
  return window.studioDesktop?.onProjectOutput?.(listener) ?? (() => undefined);
}

export async function saveGitHubToken(token: string): Promise<void> {
  if (!window.studioDesktop?.saveGitHubToken) throw new Error("Secure GitHub sign-in is available in the desktop Studio application.");
  await window.studioDesktop.saveGitHubToken(token);
}

export async function loadGitHubToken(): Promise<string | undefined> {
  return (await window.studioDesktop?.loadGitHubToken?.()) ?? undefined;
}

export async function clearGitHubToken(): Promise<void> {
  await window.studioDesktop?.clearGitHubToken?.();
}

export async function openGitHubUrl(url: string): Promise<void> {
  if (window.studioDesktop?.openExternal) {
    await window.studioDesktop.openExternal(url);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
