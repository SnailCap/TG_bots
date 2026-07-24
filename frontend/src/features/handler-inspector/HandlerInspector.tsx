import { useState } from "react";

import type { HandlerDetail, HandlerKind, HandlerUsage } from "../../domain/project";
import { FormField, FormGrid, FormSectionDivider } from "../../shared/ui/Form";
import { Select } from "../../shared/ui/Select";

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
      <FormGrid columns={2}>
        <FormField label="Handler name" layout="stacked" hint="Use dot-separated words. Studio derives the binding and Python file path from this name.">
          {(controlProps) => <input {...controlProps} value={id} onChange={(event) => setId(event.target.value)} placeholder="checkout.submit" />}
        </FormField>
        <FormField label="Context kind" layout="stacked">
          {(controlProps) => <Select {...controlProps} ariaLabel="Context kind" value={kind} options={[{ value: "button", label: "Button" }, { value: "message", label: "Message" }, { value: "command", label: "Command" }, { value: "lifecycle", label: "Lifecycle" }, { value: "task", label: "Task" }]} onChange={(next) => setKind(next as HandlerKind)} />}
        </FormField>
        <FormSectionDivider />
        <FormField label="Additional outcomes, comma-separated" layout="stacked" span="full">
          {(controlProps) => <input {...controlProps} value={outcomes} onChange={(event) => setOutcomes(event.target.value)} placeholder="invalid, access_denied" />}
        </FormField>
        <FormField label="Description" layout="stacked" span="full">
          {(controlProps) => <textarea {...controlProps} value={description} onChange={(event) => setDescription(event.target.value)} />}
        </FormField>
        <button type="button" disabled={!id.trim()} onClick={() => void onCreate(id.trim(), kind, outcomes.split(",").map((item) => item.trim()).filter(Boolean), description.trim() || undefined)}>Create handler and open code</button>
      </FormGrid>
    </section>
  );
}
