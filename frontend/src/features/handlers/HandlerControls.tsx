import type { HandlerCreateOptions, HandlerKind, HandlerSummary, HandlerUsage } from "../../domain/project";

export function HandlerStatusBadge({ handler }: { handler: HandlerSummary }) {
  const label = {
    ready: "Ready",
    missing_file: "Missing file",
    missing_symbol: "Missing symbol",
    invalid_signature: "Invalid signature",
    invalid_module: "Invalid module",
  }[handler.status];
  return (
    <span className={`status status--${handler.status}`}>
      {label}{handler.usage_count === 0 ? " · Unused" : ""}
    </span>
  );
}

export function HandlerControls({
  handlerId,
  kind,
  handlers,
  disabled,
  onCreate,
  onRepair,
  onOpen,
  onFindUsages,
  createOptions,
}: {
  handlerId: string;
  kind: HandlerKind;
  handlers: HandlerSummary[];
  disabled?: boolean;
  onCreate(handlerId: string, kind: HandlerKind, options?: HandlerCreateOptions): Promise<void>;
  onRepair(handlerId: string): Promise<void>;
  onOpen(handlerId: string): Promise<void>;
  onFindUsages(handlerId: string): Promise<HandlerUsage[]>;
  createOptions?: HandlerCreateOptions;
}) {
  const handler = handlers.find((candidate) => candidate.id === handlerId);
  const canOpen = Boolean(
    handler
    && handler.status !== "missing_file"
    && (handler.source_file || handler.inspection?.source?.path),
  );
  return (
    <div className="handler-controls">
      {handler && <HandlerStatusBadge handler={handler} />}
      {!handler && handlerId && <span className="status status--missing_file">Binding missing</span>}
      <div className="button-row">
        {!handler && (
          <button type="button" disabled={disabled || !handlerId} onClick={() => void onCreate(handlerId, kind, createOptions)}>
            Create handler
          </button>
        )}
        {handler?.status === "missing_file" && (
          <button type="button" disabled={disabled} onClick={() => void onRepair(handler.id)}>
            Create missing source
          </button>
        )}
        {handler && canOpen && (
          <button type="button" disabled={disabled} onClick={() => void onOpen(handler.id)}>
            Open code
          </button>
        )}
        {handler && (
          <button
            type="button"
            className="button--quiet"
            disabled={disabled}
            onClick={() => void onFindUsages(handler.id).then((items) => {
              const message = items.length
                ? items.map((item) => `${item.source_path}: ${item.field_path}`).join("\n")
                : "No usages found.";
              window.alert(message);
            })}
          >
            Find usages
          </button>
        )}
      </div>
    </div>
  );
}
