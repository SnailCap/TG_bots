import { SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument, TemplateNode } from "./model";
import { renderTelegramDateTime } from "./telegram-formatting";

export type PreviewValues = Record<string, unknown>;

export function defaultPreviewValues(
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): PreviewValues {
  return Object.fromEntries(catalog.map((field) => [field.path, field.example ?? ""]));
}

export function renderTemplatePreview(document: TemplateDocument, values: PreviewValues): string {
  return renderNodes(document.nodes, values);
}

function renderNodes(nodes: readonly TemplateNode[], values: PreviewValues): string {
  return nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "context-token") return String(values[node.path] ?? "");
    if (node.type === "format") {
      if (node.format === "custom-emoji") return node.fallback ?? renderNodes(node.children, values);
      if (node.format === "date-time") {
        return renderTelegramDateTime(
          node.unix ?? Number.NaN,
          node.dateTimeFormat ?? "",
          node.fallback ?? renderNodes(node.children, values),
        );
      }
      return renderNodes(node.children, values);
    }
    return node.source;
  }).join("");
}
