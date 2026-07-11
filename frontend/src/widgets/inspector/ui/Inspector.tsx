import type { ActionDefinition } from "../../../shared/api/types";
import type { GraphSelection, StudioNodeData } from "../../../entities/flow/model/types";
import { useStudio } from "../../../app/providers/StudioProvider";
import { useEffect, useState } from "react";
import styles from "./Inspector.module.css";

interface NodeInspectorProps {
  data: StudioNodeData;
  actions: ActionDefinition[];
  onPatch(patch: Partial<StudioNodeData>): void;
  onOpenScript?(path: string): void;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className={styles.field}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function JsonField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Record<string, unknown>;
  onChange(value: Record<string, unknown>): void;
}) {
  const serialized = JSON.stringify(value, null, 2);
  const [source, setSource] = useState(() => serialized);
  const [invalid, setInvalid] = useState(false);
  useEffect(() => setSource(serialized), [serialized]);
  function commit() {
    try {
      const parsed = JSON.parse(source) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Expected object");
      setInvalid(false);
      onChange(parsed as Record<string, unknown>);
    } catch {
      setInvalid(true);
    }
  }
  return (
    <Field label={label}>
      <textarea
        rows={5}
        value={source}
        data-invalid={invalid || undefined}
        onChange={(event) => setSource(event.target.value)}
        onBlur={commit}
      />
      {invalid && <small className={styles.fieldError}>Enter a JSON object.</small>}
    </Field>
  );
}

function parseConditionValue(value: string): unknown {
  const source = value.trim();
  if (source === "") return "";
  if (source === "true") return true;
  if (source === "false") return false;
  if (source === "null") return null;
  if (!Number.isNaN(Number(source))) return Number(source);
  try {
    return JSON.parse(source);
  } catch {
    return value;
  }
}

export function NodeInspector({ data, actions, onPatch, onOpenScript }: NodeInspectorProps) {
  const choicesText = (data.choices ?? []).map((choice) => `${choice.label} | ${choice.value}`).join("\n");
  const selectedAction = actions.find((action) => action.name === data.actionName);

  return (
    <div className={styles.form}>
      <div className={styles.kind}>{data.kind.replace("_", " ")}</div>
      <Field label="Title">
        <input value={data.title} onChange={(event) => onPatch({ title: event.target.value })} />
      </Field>

      {["send_message", "ask_input", "choice"].includes(data.kind) && (
        <Field label={data.kind === "ask_input" ? "Question" : "Message text"}>
          <textarea rows={4} value={data.text ?? ""} onChange={(event) => onPatch({ text: event.target.value })} />
        </Field>
      )}

      {data.kind === "send_message" && (
        <>
          <Field label="Media type">
            <select
              value={data.mediaKind ?? "photo"}
              onChange={(event) => onPatch({ mediaKind: event.target.value as StudioNodeData["mediaKind"] })}
            >
              <option value="photo">Photo</option>
              <option value="document">Document</option>
            </select>
          </Field>
          <Field label="Media / file path">
            <input value={data.mediaPath ?? ""} onChange={(event) => onPatch({ mediaPath: event.target.value })} />
          </Field>
          <Field label="Keyboard">
            <select value={data.keyboard ?? "none"} onChange={(event) => onPatch({ keyboard: event.target.value as StudioNodeData["keyboard"] })}>
              <option value="none">None</option>
              <option value="inline">Inline</option>
              <option value="reply">Reply</option>
            </select>
          </Field>
        </>
      )}

      {data.kind === "ask_input" && (
        <>
          <Field label="Variable name">
            <input value={data.variableName ?? ""} onChange={(event) => onPatch({ variableName: event.target.value })} />
          </Field>
          <Field label="Expected type">
            <select value={data.valueType ?? "string"} onChange={(event) => onPatch({ valueType: event.target.value as StudioNodeData["valueType"] })}>
              <option value="string">String</option>
              <option value="integer">Integer</option>
              <option value="number">Number</option>
              <option value="boolean">Boolean</option>
            </select>
          </Field>
          <label className={styles.checkbox}>
            <input type="checkbox" checked={data.required ?? false} onChange={(event) => onPatch({ required: event.target.checked })} />
            Required input
          </label>
          <Field label="Validation regex">
            <input
              value={data.validationRegex ?? ""}
              placeholder="^[A-Za-z]+$"
              onChange={(event) => onPatch({ validationRegex: event.target.value })}
            />
          </Field>
          {(data.valueType === "number" || data.valueType === "integer") && (
            <div className={styles.fieldGrid}>
              <Field label="Minimum">
                <input
                  type="number"
                  value={data.minValue ?? ""}
                  onChange={(event) => onPatch({ minValue: event.target.value === "" ? undefined : Number(event.target.value) })}
                />
              </Field>
              <Field label="Maximum">
                <input
                  type="number"
                  value={data.maxValue ?? ""}
                  onChange={(event) => onPatch({ maxValue: event.target.value === "" ? undefined : Number(event.target.value) })}
                />
              </Field>
            </div>
          )}
          <Field label="Validation error message">
            <textarea rows={2} value={data.errorMessage ?? ""} onChange={(event) => onPatch({ errorMessage: event.target.value })} />
          </Field>
          <Field label="Maximum attempts">
            <input
              type="number"
              min={1}
              max={100}
              value={data.maxAttempts ?? 3}
              onChange={(event) => onPatch({ maxAttempts: Number(event.target.value) || 1 })}
            />
          </Field>
        </>
      )}

      {data.kind === "choice" && (
        <Field label="Options (label | value)">
          <textarea
            rows={6}
            value={choicesText}
            onChange={(event) =>
              onPatch({
                choices: event.target.value
                  .split("\n")
                  .map((line, index) => {
                    const [label, value] = line.split("|").map((part) => part.trim());
                    return { id: `option-${index + 1}`, label: label || `Option ${index + 1}`, value: value || label || "" };
                  })
                  .filter((choice) => choice.label),
              })
            }
          />
        </Field>
      )}

      {data.kind === "action" && (
        <>
          <Field label="Registered action">
            <select value={data.actionName ?? ""} onChange={(event) => onPatch({ actionName: event.target.value })}>
              <option value="">Select an action…</option>
              {actions.map((action) => (
                <option key={action.name} value={action.name} disabled={!action.valid}>
                  {action.name}{action.valid ? "" : " (invalid)"}
                </option>
              ))}
            </select>
          </Field>
          {selectedAction && (
            <div className={styles.actionCard}>
              <code>{selectedAction.signature ?? selectedAction.name}</code>
              <small>{selectedAction.scriptPath}{selectedAction.line ? `:${selectedAction.line}` : ""}</small>
              <button type="button" onClick={() => onOpenScript?.(selectedAction.scriptPath)}>
                Open script
              </button>
            </div>
          )}
          <Field label="Timeout (seconds)">
            <input
              type="number"
              min={1}
              value={data.actionTimeoutSeconds ?? 30}
              onChange={(event) => onPatch({ actionTimeoutSeconds: Number(event.target.value) || 1 })}
            />
          </Field>
          <JsonField
            label="Input parameters (JSON)"
            value={data.actionInputParameters ?? {}}
            onChange={(value) => onPatch({ actionInputParameters: value })}
          />
          <JsonField
            label="Output mapping (JSON)"
            value={data.actionOutputMapping ?? {}}
            onChange={(value) => onPatch({ actionOutputMapping: value as Record<string, string> })}
          />
        </>
      )}

      {data.kind === "condition" && (
        <>
          <Field label="Session variable">
            <input
              value={data.conditionVariable ?? ""}
              placeholder="request.status"
              onChange={(event) => onPatch({ conditionVariable: event.target.value })}
            />
          </Field>
          <Field label="Operator">
            <select
              value={data.conditionOperator ?? "truthy"}
              onChange={(event) => onPatch({ conditionOperator: event.target.value as StudioNodeData["conditionOperator"] })}
            >
              <option value="eq">Equals</option>
              <option value="ne">Not equal</option>
              <option value="gt">Greater than</option>
              <option value="gte">Greater or equal</option>
              <option value="lt">Less than</option>
              <option value="lte">Less or equal</option>
              <option value="contains">Contains</option>
              <option value="in">In</option>
              <option value="exists">Exists</option>
              <option value="truthy">Truthy</option>
            </select>
          </Field>
          {!(["exists", "truthy"] as string[]).includes(data.conditionOperator ?? "truthy") && (
            <Field label="Comparison value">
              <input
                value={typeof data.conditionValue === "string" ? data.conditionValue : JSON.stringify(data.conditionValue ?? "")}
                onChange={(event) => onPatch({ conditionValue: parseConditionValue(event.target.value) })}
              />
            </Field>
          )}
        </>
      )}
    </div>
  );
}

function InspectorContent({ selection }: { selection: GraphSelection }) {
  const studio = useStudio();
  if (!selection) {
    return (
      <div className={styles.empty}>
        <strong>{studio.currentProject?.name ?? "Nothing selected"}</strong>
        <p>Select a node or transition to edit its properties.</p>
      </div>
    );
  }
  if (selection.kind === "edge") {
    return (
      <div className={styles.form}>
        <div className={styles.kind}>Transition</div>
        <Field label="From">
          <input value={selection.edge.source} readOnly />
        </Field>
        <Field label="To">
          <input value={selection.edge.target} readOnly />
        </Field>
        <Field label="Kind">
          <input value={selection.edge.data?.transitionKind ?? "automatic"} readOnly />
        </Field>
        <p className={styles.hint}>Reconnect the edge or use source handles to change its outcome.</p>
      </div>
    );
  }
  return (
    <NodeInspector
      data={selection.node.data}
      actions={studio.actions}
      onPatch={studio.patchSelectedNode}
      onOpenScript={studio.navigateToScript}
    />
  );
}

export function Inspector() {
  const studio = useStudio();
  return (
    <aside className={styles.panel} aria-label="Inspector">
      <header>Inspector</header>
      <div className={styles.content}>
        <InspectorContent selection={studio.graphSelection} />
      </div>
    </aside>
  );
}
