import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Braces,
  Check,
  CircleAlert,
  LockKeyhole,
  Plus,
  Save,
  Trash2,
  Variable,
} from "lucide-react";
import { useNavigate, useOutletContext, useSearchParams } from "react-router-dom";

import type {
  JsonValue,
  VariableCatalogDetail,
  VariableCatalogSpec,
  VariableDefinition,
  VariableOwnerType,
  VariablePersistence,
  VariableResourceContext,
  VariableType,
  Workspace,
} from "../../domain/project";
import type { StudioPageContext } from "../studio/studio-page-context";

const OWNER_TYPES: readonly VariableOwnerType[] = ["bot", "flow", "state", "view", "handler"];
const VARIABLE_TYPES: readonly VariableType[] = ["string", "number", "boolean", "date", "datetime", "object", "array"];
const PERSISTENCE_OPTIONS: readonly VariablePersistence[] = ["resource", "session", "user"];
const TYPE_LABELS: Record<VariableType, string> = {
  string: "Text",
  number: "Number",
  boolean: "Boolean",
  date: "Date",
  datetime: "Date and time",
  object: "Object",
  array: "Array",
};
const OWNER_LABELS: Record<VariableOwnerType, string> = {
  bot: "Bot",
  flow: "Flow",
  state: "State",
  view: "View",
  handler: "Handler",
};
const PERSISTENCE_LABELS: Record<VariablePersistence, string> = {
  resource: "Resource instance",
  session: "User session",
  user: "User profile",
};

type DraftState = {
  value: VariableDefinition;
  isNew: boolean;
  defaultText: string;
  exampleText: string;
};

export function VariablesPage() {
  const { api, workspace } = useOutletContext<StudioPageContext>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const scope = useMemo(() => readScope(searchParams), [searchParams]);
  const [detail, setDetail] = useState<VariableCatalogDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | "custom" | "core">("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const creatingRef = useRef(false);

  const load = useCallback(async () => {
    if (!api.getVariables) {
      setError("This Studio backend does not support resource variables yet.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const next = await api.getVariables(workspace.project_id, scope);
      setDetail(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load project variables.");
    } finally {
      setLoading(false);
    }
  }, [api, scope, workspace.project_id]);

  useEffect(() => { void load(); }, [load]);

  const visibleDefinitions = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return (detail?.definitions ?? [])
      .filter((item) => sourceFilter === "all" || item.source === sourceFilter)
      .filter((item) => !normalized || `${item.path} ${item.id} ${item.description ?? ""}`.toLocaleLowerCase().includes(normalized))
      .slice()
      .sort((left, right) => Number(left.source !== "core") - Number(right.source !== "core") || left.path.localeCompare(right.path));
  }, [detail?.definitions, query, sourceFilter]);

  useEffect(() => {
    if (creatingRef.current || draft) return;
    if (!visibleDefinitions.length) {
      setSelectedId(null);
      setDraft(null);
      return;
    }
    if (selectedId && visibleDefinitions.some((item) => item.id === selectedId)) return;
    setSelectedId(visibleDefinitions[0].id);
  }, [draft, selectedId, visibleDefinitions]);

  useEffect(() => {
    if (creatingRef.current) return;
    const selected = selectedId ? detail?.definitions.find((item) => item.id === selectedId) : undefined;
    if (!selected) return;
    setDraft({ value: cloneDefinition(selected), isNew: false, defaultText: serializeValue(selected.defaultValue, selected.type), exampleText: serializeValue(selected.exampleValue, selected.type) });
  }, [detail?.definitions, selectedId]);

  const beginNew = () => {
    creatingRef.current = true;
    const owner = defaultOwner(scope, workspace);
    const value: VariableDefinition = {
      id: "",
      owner,
      path: "",
      type: "string",
      source: "custom",
      required: false,
      writable: true,
      persistence: "resource",
      exposedToTemplates: true,
      legacyPaths: [],
    };
    setSelectedId(null);
    setNotice("");
    setError("");
    setDraft({ value, isNew: true, defaultText: "", exampleText: "" });
  };

  const selectDefinition = (definition: VariableDefinition) => {
    creatingRef.current = false;
    setNotice("");
    setError("");
    setSelectedId(definition.id);
  };

  const updateDraft = (patch: Partial<VariableDefinition>) => {
    setDraft((current) => current ? { ...current, value: { ...current.value, ...patch } } : current);
  };

  const saveDraft = async () => {
    if (!draft || !detail || !api.saveVariables) return;
    const validationError = validateDraft(draft.value, draft.defaultText, draft.exampleText, detail.payload.variables, draft.isNew);
    if (validationError) {
      setError(validationError);
      return;
    }
    const value = normalizeDraft(draft);
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const nextPayload: VariableCatalogSpec = {
        schema_version: 3,
        variables: draft.isNew
          ? [...detail.payload.variables, value]
          : detail.payload.variables.map((item) => item.id === value.id ? value : item),
      };
      const next = await api.saveVariables(workspace.project_id, nextPayload, detail.revision);
      setDetail(next);
      creatingRef.current = false;
      setSelectedId(value.id);
      setDraft({ value: cloneDefinition(next.definitions.find((item) => item.id === value.id) ?? value), isNew: false, defaultText: serializeValue(value.defaultValue, value.type), exampleText: serializeValue(value.exampleValue, value.type) });
      setNotice(draft.isNew ? "Variable added." : "Variable saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save this variable.");
    } finally {
      setSaving(false);
    }
  };

  const deleteDraft = async () => {
    if (!draft || draft.isNew || !detail || !api.saveVariables) return;
    if (typeof window !== "undefined" && !window.confirm(`Delete variable “${draft.value.path}”?`)) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const next = await api.saveVariables(workspace.project_id, {
        schema_version: 3,
        variables: detail.payload.variables.filter((item) => item.id !== draft.value.id),
      }, detail.revision);
      setDetail(next);
      setDraft(null);
      setSelectedId(null);
      setNotice("Variable deleted.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete this variable.");
    } finally {
      setSaving(false);
    }
  };

  const scopeLabel = scope.resourceType && scope.resourceId ? resourceLabel(workspace, scope) : null;
  const customCount = detail?.payload.variables.length ?? 0;
  const coreCount = detail?.definitions.filter((item) => item.source === "core").length ?? 0;
  const cancelDraft = () => {
    if (!draft) return;
    if (draft.isNew) {
      creatingRef.current = false;
      setDraft(null);
      return;
    }
    const selected = detail?.definitions.find((item) => item.id === draft.value.id);
    if (selected) setDraft({ value: cloneDefinition(selected), isNew: false, defaultText: serializeValue(selected.defaultValue, selected.type), exampleText: serializeValue(selected.exampleValue, selected.type) });
  };

  return <main className="variables-page" aria-label="Resource variables">
    <header className="variables-page__header">
      <div className="variables-page__identity">
        <div className="variables-page__mark" aria-hidden="true"><Braces /></div>
        <div>
          <p className="eyebrow">Project schema</p>
          <h1>Variables</h1>
          <p>One catalog for values shared by your bot, flows, views and handlers.</p>
        </div>
      </div>
      <div className="variables-page__header-actions">
        <span className="variables-page__stats"><strong>{customCount}</strong> custom · <strong>{coreCount}</strong> built-in</span>
        <button type="button" onClick={beginNew}><Plus aria-hidden="true" />New variable</button>
      </div>
    </header>

    {scopeLabel && <div className="variables-scope-banner" role="status">
      <Variable aria-hidden="true" />
      <span>Showing variables available to <strong>{scopeLabel}</strong>.</span>
      <button type="button" className="button--link" onClick={() => navigate("/variables")}>View full catalog</button>
    </div>}
    {error && <div className="variables-message variables-message--error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <div className="variables-message variables-message--notice" role="status"><Check aria-hidden="true" /><span>{notice}</span></div>}

    <div className="variables-page__body">
      <aside className="variables-list-panel" aria-label="Variable catalog">
        <div className="variables-list-panel__toolbar">
          <label className="variables-search"><span className="sr-only">Search variables</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search path or description" /></label>
          <label className="variables-filter"><span className="sr-only">Filter variable source</span><select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)}><option value="all">All sources</option><option value="custom">Custom</option><option value="core">Built-in</option></select></label>
        </div>
        {loading ? <div className="variables-empty" role="status">Loading variables…</div> : visibleDefinitions.length === 0 ? <div className="variables-empty"><Variable aria-hidden="true" /><strong>No variables found</strong><span>Try another filter or add a custom variable.</span></div> : <div className="variables-list">{visibleDefinitions.map((definition) => <button key={definition.id} type="button" className={selectedId === definition.id ? "variables-list__item variables-list__item--active" : "variables-list__item"} onClick={() => selectDefinition(definition)}>
          <span className="variables-list__item-icon" aria-hidden="true"><Variable /></span>
          <span className="variables-list__item-copy"><strong>{definition.path}</strong><small>{definition.description || `${OWNER_LABELS[definition.owner.type]} · ${TYPE_LABELS[definition.type]}`}</small></span>
          <span className={`variables-badge variables-badge--${definition.source}`}>{definition.source === "core" ? "built-in" : TYPE_LABELS[definition.type]}</span>
        </button>)}</div>}
        <footer className="variables-list-panel__footer"><span>{visibleDefinitions.length} shown</span><code>variables.json</code></footer>
      </aside>

      <section className="variables-editor-panel" aria-label="Variable details">
        {!draft ? <div className="variables-editor-empty"><div className="variables-editor-empty__icon"><Braces /></div><h2>Choose a variable</h2><p>Select a catalog entry to inspect it, or create a custom variable for this project.</p><button type="button" className="button--secondary" onClick={beginNew}><Plus aria-hidden="true" />Add custom variable</button></div> : <VariableEditor draft={draft} workspace={workspace} saving={saving} onChange={updateDraft} onDefaultTextChange={(defaultText) => setDraft((current) => current ? { ...current, defaultText } : current)} onExampleTextChange={(exampleText) => setDraft((current) => current ? { ...current, exampleText } : current)} onSave={() => void saveDraft()} onCancel={cancelDraft} onDelete={() => void deleteDraft()} />}
      </section>
    </div>
  </main>;
}

function VariableEditor({ draft, workspace, saving, onChange, onDefaultTextChange, onExampleTextChange, onSave, onCancel, onDelete }: {
  draft: DraftState;
  workspace: Workspace;
  saving: boolean;
  onChange(patch: Partial<VariableDefinition>): void;
  onDefaultTextChange(value: string): void;
  onExampleTextChange(value: string): void;
  onSave(): void;
  onCancel(): void;
  onDelete(): void;
}) {
  const { value } = draft;
  const readOnly = value.source === "core";
  const ownerChoices = ownerOptions(workspace, value.owner.type);
  return <div className="variables-editor">
    <header className="variables-editor__header">
      <div><p className="eyebrow">{readOnly ? "Built-in context" : draft.isNew ? "New definition" : "Custom definition"}</p><h2>{value.path || "Untitled variable"}</h2></div>
      <span className={`variables-editor__status variables-editor__status--${readOnly ? "locked" : "editable"}`}>{readOnly ? <><LockKeyhole aria-hidden="true" />Read only</> : <><Check aria-hidden="true" />Editable</>}</span>
    </header>
    <div className="variables-editor__content">
      {readOnly && <div className="variables-readonly-note"><LockKeyhole aria-hidden="true" /><span>Built-in values are supplied by the Telegram runtime. Use them in templates, but do not overwrite their definition.</span></div>}
      <div className="variables-form-grid variables-form-grid--two">
        <label><span>Stable ID</span><input value={value.id} disabled={readOnly || !draft.isNew} onChange={(event) => onChange({ id: event.target.value })} placeholder="checkout.customer_name" /></label>
        <label><span>Template path</span><input value={value.path} disabled={readOnly} onChange={(event) => onChange({ path: event.target.value })} placeholder="customer.name" /></label>
      </div>
      <div className="variables-form-grid variables-form-grid--three">
        <label><span>Owner type</span><select value={value.owner.type} disabled={readOnly} onChange={(event) => { const type = event.target.value as VariableOwnerType; onChange({ owner: { type, id: ownerOptions(workspace, type)[0]?.id ?? "" } }); }}><option value="bot">Bot</option><option value="flow">Flow</option><option value="state">State</option><option value="view">View</option><option value="handler">Handler</option></select></label>
        <label className="variables-form-grid__wide"><span>Owner</span><select value={value.owner.id} disabled={readOnly} onChange={(event) => onChange({ owner: { ...value.owner, id: event.target.value } })}>{ownerChoices.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        <label><span>Value type</span><select value={value.type} disabled={readOnly} onChange={(event) => onChange({ type: event.target.value as VariableType })}>{VARIABLE_TYPES.map((type) => <option key={type} value={type}>{TYPE_LABELS[type]}</option>)}</select></label>
        <label><span>Persistence</span><select value={value.persistence} disabled={readOnly} onChange={(event) => onChange({ persistence: event.target.value as VariablePersistence })}>{PERSISTENCE_OPTIONS.map((persistence) => <option key={persistence} value={persistence}>{PERSISTENCE_LABELS[persistence]}</option>)}</select></label>
      </div>
      <div className="variables-form-grid variables-form-grid--two">
        <ValueField label="Default value" type={value.type} value={draft.defaultText} disabled={readOnly} onChange={onDefaultTextChange} />
        <ValueField label="Example value" type={value.type} value={draft.exampleText} disabled={readOnly} onChange={onExampleTextChange} />
      </div>
      <label><span>Description</span><textarea value={value.description ?? ""} disabled={readOnly} onChange={(event) => onChange({ description: event.target.value || undefined })} placeholder="What does this value represent?" /></label>
      <fieldset className="variables-toggles" disabled={readOnly}>
        <legend>Availability</legend>
        <label><input type="checkbox" checked={value.required} onChange={(event) => onChange({ required: event.target.checked })} /><span>Required at runtime</span></label>
        <label><input type="checkbox" checked={value.writable} onChange={(event) => onChange({ writable: event.target.checked })} /><span>Writable from handlers</span></label>
        <label><input type="checkbox" checked={value.exposedToTemplates} onChange={(event) => onChange({ exposedToTemplates: event.target.checked })} /><span>Expose in template autocomplete</span></label>
      </fieldset>
      {!readOnly && <footer className="variables-editor__footer"><button type="button" className="button--danger button--icon-text" disabled={saving || draft.isNew} onClick={onDelete}><Trash2 aria-hidden="true" />Delete</button><div><button type="button" className="button--secondary" disabled={saving} onClick={onCancel}>Cancel</button><button type="button" disabled={saving} onClick={onSave}>{saving ? "Saving…" : <><Save aria-hidden="true" />Save variable</>}</button></div></footer>}
    </div>
  </div>;
}

function ValueField({ label, type, value, disabled, onChange }: { label: string; type: VariableType; value: string; disabled: boolean; onChange(value: string): void }) {
  if (type === "boolean") return <label><span>{label}</span><select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}><option value="">Not set</option><option value="true">true</option><option value="false">false</option></select></label>;
  if (type === "object" || type === "array") return <label><span>{label} <small>(JSON)</small></span><textarea className="variables-value-json" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} placeholder={type === "array" ? "[\"example\"]" : "{\"key\": \"value\"}"} /></label>;
  return <label><span>{label}</span><input type={type === "number" ? "number" : type === "date" ? "date" : type === "datetime" ? "datetime-local" : "text"} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} /></label>;
}

function readScope(params: URLSearchParams): VariableResourceContext {
  const resourceType = params.get("resourceType");
  const validType = OWNER_TYPES.includes(resourceType as VariableOwnerType) ? resourceType as VariableOwnerType : undefined;
  return {
    resourceType: validType,
    resourceId: params.get("resourceId") || undefined,
    flowId: params.get("flowId") || undefined,
    stateId: params.get("stateId") || undefined,
    handlerId: params.get("handlerId") || undefined,
  };
}

function defaultOwner(scope: VariableResourceContext, workspace: Workspace): { type: VariableOwnerType; id: string } {
  if (scope.resourceType && scope.resourceId) return { type: scope.resourceType, id: scope.resourceId };
  return { type: "bot", id: workspace.manifest.payload.id };
}

function ownerOptions(workspace: Workspace, type: VariableOwnerType): Array<{ id: string; label: string }> {
  if (type === "bot") return [{ id: workspace.manifest.payload.id, label: workspace.name }];
  if (type === "flow") return workspace.flows.map((item) => ({ id: item.id, label: item.name ?? item.id }));
  if (type === "view") return workspace.views.map((item) => ({ id: item.id, label: item.name ?? item.id }));
  if (type === "handler") return workspace.handlers.map((item) => ({ id: item.id, label: item.name ?? item.id }));
  return workspace.flows.flatMap((flow) => flow.states.map((id) => ({ id: `${flow.id}.${id}`, label: `${flow.name ?? flow.id} · ${id}` })));
}

function resourceLabel(workspace: Workspace, scope: VariableResourceContext): string {
  if (!scope.resourceType || !scope.resourceId) return "this resource";
  if (scope.resourceType === "view") return workspace.views.find((item) => item.id === scope.resourceId)?.name ?? scope.resourceId;
  if (scope.resourceType === "flow") return workspace.flows.find((item) => item.id === scope.resourceId)?.name ?? scope.resourceId;
  if (scope.resourceType === "handler") return workspace.handlers.find((item) => item.id === scope.resourceId)?.name ?? scope.resourceId;
  return scope.resourceId;
}

function cloneDefinition(value: VariableDefinition): VariableDefinition {
  return { ...value, owner: { ...value.owner }, legacyPaths: [...value.legacyPaths] };
}

function normalizeDraft(draft: DraftState): VariableDefinition {
  const value = cloneDefinition(draft.value);
  const defaultValue = parseValue(draft.defaultText, value.type);
  const exampleValue = parseValue(draft.exampleText, value.type);
  if (defaultValue === undefined) delete value.defaultValue; else value.defaultValue = defaultValue;
  if (exampleValue === undefined) delete value.exampleValue; else value.exampleValue = exampleValue;
  return value;
}

function validateDraft(value: VariableDefinition, defaultText: string, exampleText: string, variables: VariableDefinition[], isNew: boolean): string {
  if (!value.id.trim()) return "Stable ID is required.";
  if (!value.path.trim()) return "Template path is required.";
  if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(value.id)) return "Stable ID may contain letters, numbers, dots, dashes and underscores.";
  if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(value.path)) return "Template path may contain letters, numbers, dots, dashes and underscores.";
  if (variables.some((item) => item.id === value.id && (isNew || item.path !== value.path || item.owner.id !== value.owner.id))) return `A different variable already uses ID “${value.id}”.`;
  if (variables.some((item) => item.path === value.path && item.id !== value.id)) return `A different variable already uses path “${value.path}”.`;
  for (const [label, text] of [["Default value", defaultText], ["Example value", exampleText]] as const) {
    if (!text.trim()) continue;
    try { parseValue(text, value.type); } catch (caught) { return `${label}: ${caught instanceof Error ? caught.message : "invalid value"}`; }
  }
  return "";
}

function parseValue(text: string, type: VariableType): JsonValue | undefined {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  if (type === "string" || type === "date" || type === "datetime") return text;
  if (type === "number") {
    const value = Number(trimmed);
    if (!Number.isFinite(value)) throw new Error("must be a finite number");
    return value;
  }
  if (type === "boolean") {
    if (trimmed !== "true" && trimmed !== "false") throw new Error("must be true or false");
    return trimmed === "true";
  }
  let value: unknown;
  try { value = JSON.parse(trimmed); } catch { throw new Error("must be valid JSON"); }
  if (type === "array" && !Array.isArray(value)) throw new Error("must be a JSON array");
  if (type === "object" && (!value || typeof value !== "object" || Array.isArray(value))) throw new Error("must be a JSON object");
  return value as JsonValue;
}

function serializeValue(value: JsonValue | undefined, type: VariableType): string {
  if (value === undefined) return "";
  if (type === "string" || type === "date" || type === "datetime") return String(value);
  return JSON.stringify(value);
}
