import { useMemo, useState } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import type { ValidationIssue } from "../../../entities/runtime/model/types";
import styles from "./ConsolePanel.module.css";

export function ConsolePanel() {
  const studio = useStudio();
  const [tab, setTab] = useState<"console" | "validation">("console");
  const counts = useMemo(
    () => ({
      errors: studio.issues.filter((issue) => issue.severity === "error").length,
      warnings: studio.issues.filter((issue) => issue.severity === "warning").length,
    }),
    [studio.issues],
  );

  function navigateFromLog(index: number) {
    const log = studio.logs[index];
    if (!log?.entity) return;
    studio.navigateToIssue({
      code: "RUNTIME_LOG",
      severity: log.level === "error" ? "error" : "info",
      message: log.message,
      entity: log.entity,
    } as ValidationIssue);
  }

  return (
    <section className={styles.panel} aria-label="Console and validation">
      <div className={styles.tabs}>
        <button className={tab === "console" ? styles.active : ""} onClick={() => setTab("console")}>
          Console <span>{studio.logs.length}</span>
        </button>
        <button className={tab === "validation" ? styles.active : ""} onClick={() => setTab("validation")}>
          Validation <span className={counts.errors ? styles.danger : ""}>{counts.errors}</span>
          <span className={counts.warnings ? styles.warning : ""}>{counts.warnings}</span>
        </button>
        <div className={styles.spacer} />
        {tab === "console" ? (
          <button onClick={studio.clearLogs}>Clear</button>
        ) : (
          <button onClick={() => void studio.validate()} disabled={!studio.currentProject || studio.validating}>
            {studio.validating ? "Checking…" : "Validate project"}
          </button>
        )}
      </div>
      <div className={styles.body}>
        {tab === "console" ? (
          studio.logs.length ? (
            <table className={styles.table}>
              <tbody>
                {studio.logs.map((log, index) => (
                  <tr key={log.id} data-level={log.level} onDoubleClick={() => navigateFromLog(index)}>
                    <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
                    <td>{log.level}</td>
                    <td>{log.source ?? "runtime"}</td>
                    <td title={log.message}>{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className={styles.empty}>Runtime logs will appear here. Double-click an error to navigate.</p>
          )
        ) : studio.issues.length ? (
          <div className={styles.issues}>
            {studio.issues.map((issue, index) => (
              <button key={`${issue.code}:${index}`} data-severity={issue.severity} onClick={() => studio.navigateToIssue(issue)}>
                <span>{issue.severity === "error" ? "●" : issue.severity === "warning" ? "▲" : "●"}</span>
                <strong>{issue.code}</strong>
                <span>{issue.message}</span>
                {issue.hint && <small>{issue.hint}</small>}
              </button>
            ))}
          </div>
        ) : (
          <p className={styles.empty}>No validation issues. Run validation before starting the bot.</p>
        )}
      </div>
    </section>
  );
}
