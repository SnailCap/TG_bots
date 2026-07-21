import { SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument } from "./model";

export type PreviewValues = Record<string, string | number>;

export function defaultPreviewValues(
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): PreviewValues {
  return Object.fromEntries(catalog.map((field) => [field.path, field.example ?? ""]));
}

export function renderTemplatePreview(document: TemplateDocument, values: PreviewValues): string {
  return document.nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "context-token") return String(values[node.path] ?? "");
    return node.source;
  }).join("");
}

