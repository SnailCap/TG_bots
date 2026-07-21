import { findContextField, SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument } from "./model";

export type TemplateDiagnostic = {
  code: "unknown-context-field" | "unsupported-expression";
  severity: "warning";
  message: string;
};

export function validateTemplate(
  document: TemplateDocument,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): TemplateDiagnostic[] {
  const diagnostics: TemplateDiagnostic[] = [];
  for (const node of document.nodes) {
    if (node.type === "unresolved-token" || (node.type === "context-token" && !findContextField(node.path, catalog))) {
      diagnostics.push({
        code: "unknown-context-field",
        severity: "warning",
        message: `Unknown context field: ${node.path}`,
      });
    } else if (node.type === "raw-fragment") {
      diagnostics.push({
        code: "unsupported-expression",
        severity: "warning",
        message: `Expression cannot be represented in Visual mode: ${node.source}`,
      });
    }
  }
  return diagnostics;
}

