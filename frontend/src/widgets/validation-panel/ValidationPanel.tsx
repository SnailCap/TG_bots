import type { Diagnostic } from "../../domain/project";

export function ValidationPanel({ issues, onRefresh, onSelect }: { issues: Diagnostic[]; onRefresh(): void; onSelect(issue: Diagnostic): void }) {
  const errors = issues.filter((issue) => issue.level === "error").length;
  const warnings = issues.length - errors;
  return (
    <section className="validation-panel" aria-label="Project validation">
      <header><div><p className="eyebrow">Project graph</p><h2>Validation</h2></div><button type="button" className="button--quiet" onClick={onRefresh}>Refresh</button></header>
      <p className="validation-summary">{errors} errors · {warnings} warnings</p>
      {issues.length === 0 && <p className="muted">No issues reported.</p>}
      {issues.map((issue, index) => (
        <button type="button" className={`diagnostic diagnostic--${issue.level}`} key={`${issue.code}-${issue.source_path}-${issue.field_path}-${index}`} onClick={() => onSelect(issue)}>
          <strong>{issue.message}</strong>
          <span>{issue.code}</span>
          {(issue.source_path || issue.entity_id || issue.field_path) && <small>{[issue.source_path, issue.entity_id, issue.field_path].filter(Boolean).join(" · ")}</small>}
        </button>
      ))}
    </section>
  );
}
