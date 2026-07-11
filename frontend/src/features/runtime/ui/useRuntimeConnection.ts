import { useCallback, useEffect, useReducer, useState } from "react";
import { runtimeControlReducer, type RuntimeControlState } from "../../../entities/runtime/model/types";
import type { RuntimeLogEvent, ValidationIssue } from "../../../entities/runtime/model/types";
import { toApiError } from "../../../shared/api/client";
import { normalizeIssues, normalizeLog, normalizeRuntimeStatus } from "../../../shared/api/normalize";
import { studioApi } from "../../../shared/api/studioApi";

const initialState: RuntimeControlState = {
  status: { phase: "unknown", telegramConnected: false },
  pending: null,
  error: null,
};

export function useRuntimeConnection(projectId: string | undefined, onError: (message: string) => void) {
  const [control, dispatch] = useReducer(runtimeControlReducer, initialState);
  const [logs, setLogs] = useState<RuntimeLogEvent[]>([]);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [validating, setValidating] = useState(false);

  const refreshStatus = useCallback(async () => {
    if (!projectId) return;
    try {
      dispatch({ type: "status", status: await studioApi.runtimeStatus(projectId) });
    } catch (error) {
      const message = toApiError(error).message;
      dispatch({ type: "failed", message });
    }
  }, [projectId]);

  useEffect(() => {
    setLogs([]);
    setIssues([]);
    if (!projectId) return;
    void refreshStatus();
    void studioApi.logs(projectId).then(setLogs).catch(() => undefined);
    const timer = window.setInterval(() => void refreshStatus(), 5_000);
    let source: EventSource | undefined;
    if (typeof EventSource !== "undefined") {
      source = studioApi.connectRuntimeEvents(
        projectId,
        (event) => {
          if (event.type === "status" && event.status) {
            dispatch({ type: "status", status: normalizeRuntimeStatus(event.status) });
          } else if (event.type === "validation" && event.issues) {
            setIssues(normalizeIssues(event.issues));
          } else if (event.log) {
            setLogs((items) => [...items.slice(-999), normalizeLog(event.log)]);
          }
        },
        () => undefined,
      );
    }
    return () => {
      window.clearInterval(timer);
      source?.close();
    };
  }, [projectId, refreshStatus]);

  const run = useCallback(async () => {
    if (!projectId) return;
    dispatch({ type: "run_requested" });
    try {
      dispatch({ type: "status", status: await studioApi.run(projectId) });
    } catch (error) {
      const message = toApiError(error).message;
      dispatch({ type: "failed", message });
      onError(message);
    }
  }, [onError, projectId]);

  const stop = useCallback(async () => {
    if (!projectId) return;
    dispatch({ type: "stop_requested" });
    try {
      dispatch({ type: "status", status: await studioApi.stop(projectId) });
    } catch (error) {
      const message = toApiError(error).message;
      dispatch({ type: "failed", message });
      onError(message);
    }
  }, [onError, projectId]);

  const validate = useCallback(async () => {
    if (!projectId) return;
    setValidating(true);
    try {
      setIssues(await studioApi.validateProject(projectId));
    } catch (error) {
      onError(toApiError(error).message);
    } finally {
      setValidating(false);
    }
  }, [onError, projectId]);

  return {
    control,
    logs,
    issues,
    validating,
    run,
    stop,
    validate,
    refreshStatus,
    clearLogs: () => setLogs([]),
  };
}
