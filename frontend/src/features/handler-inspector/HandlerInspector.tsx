import { useState } from "react";

import type { HandlerDetail, HandlerKind, HandlerUsage } from "../../domain/project";
import { HandlerStatusBadge } from "../handlers/HandlerControls";

export function HandlerInspector({
  handler,
  onRepair,
  onOpen,
  onFindUsages,
}: {
  handler: HandlerDetail;
  onRepair(id: string): Promise<void>;
  onOpen(id: string): Promise<void>;
  onFindUsages(id: string): Promise<HandlerUsage[]>;
}) {
  const [usages, setUsages] = useState<HandlerUsage[] | null>(null);
  const canOpen = handler.status !== "missing_file" && Boolean(handler.source_file || handler.inspection?.source?.path);
  return (
    <section className="editor" aria-label="Handler inspector">
      <header className="editor__header"><div><p className="eyebrow">Custom code</p><h2>{handler.id}</h2><small>{handler.source_file ?? handler.source_path}</small></div><HandlerStatusBadge handler={handler} /></header>
      <dl className="details">
        <dt>Kind</dt><dd>{handler.kind}</dd>
        <dt>Module</dt><dd><code>{handler.module}</code></dd>
        <dt>Symbol</dt><dd><code>{handler.symbol}</code></dd>
        <dt>Declared outcomes</dt><dd>{handler.outcomes.length ? handler.outcomes.join(", ") : "success only"}</dd>
        <dt>Description</dt><dd>{handler.description || "—"}</dd>
      </dl>
      <div className="button-row">
        {handler.status === "missing_file" && <button type="button" onClick={() => void onRepair(handler.id)}>Create missing source</button>}
        {canOpen && <button type="button" onClick={() => void onOpen(handler.id)}>Open code</button>}
        <button type="button" className="button--quiet" onClick={() => void onFindUsages(handler.id).then(setUsages)}>Find usages</button>
      </div>
      {usages && <section className="usages"><h3>Usages</h3>{usages.length ? usages.map((usage, index) => <p key={`${usage.source_path}-${usage.field_path}-${index}`}><strong>{usage.entity_id ?? usage.source_path}</strong><small>{usage.source_path} · {usage.field_path}</small></p>) : <p className="muted">No usages found.</p>}</section>}
      {handler.diagnostics?.length ? <section className="usages"><h3>Handler diagnostics</h3>{handler.diagnostics.map((item, index) => <p className={item.level} key={`${item.code}-${index}`}>{item.message}<small>{item.field_path}</small></p>)}</section> : null}
    </section>
  );
}

export function NewHandlerEditor({ onCreate }: { onCreate(id: string, kind: HandlerKind, outcomes: string[], description?: string): Promise<void> }) {
  const [id, setId] = useState("custom.handler");
  const [kind, setKind] = useState<HandlerKind>("button");
  const [outcomes, setOutcomes] = useState("");
  const [description, setDescription] = useState("");
  return (
    <section className="editor" aria-label="New handler editor">
      <header className="editor__header"><div><p className="eyebrow">Custom code scaffold</p><h2>New handler</h2></div></header>
      <div className="form-grid">
        <label>Stable handler ID<input value={id} onChange={(event) => setId(event.target.value)} /></label>
        <label>Context kind<select value={kind} onChange={(event) => setKind(event.target.value as HandlerKind)}><option value="button">Button</option><option value="message">Message</option><option value="command">Command</option><option value="lifecycle">Lifecycle</option><option value="task">Task</option></select></label>
        <label>Additional outcomes, comma-separated<input value={outcomes} onChange={(event) => setOutcomes(event.target.value)} placeholder="invalid, access_denied" /></label>
        <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <button type="button" disabled={!id.trim()} onClick={() => void onCreate(id.trim(), kind, outcomes.split(",").map((item) => item.trim()).filter(Boolean), description.trim() || undefined)}>Create handler and open code</button>
      </div>
    </section>
  );
}
