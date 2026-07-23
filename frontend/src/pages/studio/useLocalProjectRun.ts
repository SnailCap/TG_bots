import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";

import type { ProjectProcessEvent } from "../../../electron/contracts";
import type { Workspace } from "../../domain/project";
import {
  approveProjectRoot,
  localProjectStatus,
  onLocalProjectOutput,
  runLocalProject,
  stopLocalProject,
} from "../../studio/desktop";

const MAX_TERMINAL_ENTRIES = 2000;

type LocalProjectRunOptions = {
  workspace: Workspace;
  dirty: boolean;
  busy: boolean;
  saving: boolean;
  setTerminalOpen: Dispatch<SetStateAction<boolean>>;
  setNotice: Dispatch<SetStateAction<string>>;
  setError: Dispatch<SetStateAction<string>>;
  report(caught: unknown): void;
};

export function useLocalProjectRun({
  workspace,
  dirty,
  busy,
  saving,
  setTerminalOpen,
  setNotice,
  setError,
  report,
}: LocalProjectRunOptions) {
  const [startingLocalRun, setStartingLocalRun] = useState(false);
  const [stoppingLocalRun, setStoppingLocalRun] = useState(false);
  const [localRunPid, setLocalRunPid] = useState<number | null>(null);
  const [terminalEntries, setTerminalEntries] = useState<ProjectProcessEvent[]>([]);
  const localRunCommandRevision = useRef(0);

  useEffect(() => onLocalProjectOutput((event) => {
    if (!sameProjectRoot(event.projectRoot, workspace.project_root)) return;
    setTerminalEntries((current) => [...current.slice(-(MAX_TERMINAL_ENTRIES - 1)), event]);
    if (event.running === true) {
      setLocalRunPid(event.pid ?? null);
      setStoppingLocalRun(false);
    } else if (event.running === false) {
      setLocalRunPid(null);
      setStoppingLocalRun(false);
    }
  }), [workspace.project_root]);

  useEffect(() => {
    let cancelled = false;
    if (!window.studioDesktop?.projectRunStatus) return undefined;
    const revision = localRunCommandRevision.current;
    void approveProjectRoot(workspace.project_root)
      .then(() => localProjectStatus(workspace.project_root))
      .then((runStatus) => {
        if (!cancelled && revision === localRunCommandRevision.current) {
          setLocalRunPid(runStatus.running ? runStatus.pid : null);
        }
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [workspace.project_root]);

  const runProject = useCallback(async () => {
    if (dirty || busy || saving || startingLocalRun) return;
    localRunCommandRevision.current += 1;
    setTerminalOpen(true);
    setStartingLocalRun(true);
    try {
      await approveProjectRoot(workspace.project_root);
      const result = await runLocalProject({ projectRoot: workspace.project_root, packageName: workspace.package });
      setLocalRunPid(result.pid || null);
      setNotice("");
      setError("");
    } catch (caught) {
      report(caught);
    } finally {
      setStartingLocalRun(false);
    }
  }, [busy, dirty, report, saving, setError, setNotice, setTerminalOpen, startingLocalRun, workspace.package, workspace.project_root]);

  const stopProject = useCallback(async () => {
    if (!localRunPid || stoppingLocalRun) return;
    localRunCommandRevision.current += 1;
    setTerminalOpen(true);
    setStoppingLocalRun(true);
    try {
      await stopLocalProject(workspace.project_root);
    } catch (caught) {
      setStoppingLocalRun(false);
      report(caught);
    }
  }, [localRunPid, report, setTerminalOpen, stoppingLocalRun, workspace.project_root]);

  return {
    startingLocalRun,
    stoppingLocalRun,
    localRunPid,
    terminalEntries,
    localRunActive: localRunPid !== null,
    canRunLocalProject: Boolean(window.studioDesktop?.runProject && window.studioDesktop?.stopProject),
    runProject,
    stopProject,
  };
}

function sameProjectRoot(left: string, right: string): boolean {
  const normalize = (value: string) => value.replaceAll("\\", "/").replace(/\/$/, "").toLowerCase();
  return normalize(left) === normalize(right);
}
