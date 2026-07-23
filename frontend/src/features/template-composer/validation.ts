import { findContextField, SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument, TemplateFormatNode, TemplateNode } from "./model";
import {
  CODE_FORMATS,
  QUOTE_FORMATS,
  TELEGRAM_DATE_TIME_FORMAT,
  isSafeWebUrl,
  isValidCustomEmojiFallback,
} from "./telegram-formatting";

export type TemplateDiagnostic = {
  code:
    | "unknown-context-field"
    | "unsupported-expression"
    | "unsupported-html"
    | "invalid-format-attributes"
    | "invalid-format-nesting";
  severity: "warning";
  message: string;
};

export function validateTemplate(
  document: TemplateDocument,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): TemplateDiagnostic[] {
  const diagnostics: TemplateDiagnostic[] = [];
  visitNodes(document.nodes, [], (node, ancestors) => {
    if (node.type === "unresolved-token" || (node.type === "context-token" && !findContextField(node.path, catalog))) {
      diagnostics.push({
        code: "unknown-context-field",
        severity: "warning",
        message: `Unknown context field: ${node.path}`,
      });
    } else if (node.type === "raw-fragment") {
      diagnostics.push({
        code: node.fragmentKind === "html" ? "unsupported-html" : "unsupported-expression",
        severity: "warning",
        message: node.fragmentKind === "html"
          ? `Unsupported or unsafe Telegram HTML is preserved as source: ${node.source}`
          : `Expression cannot be represented in Visual mode: ${node.source}`,
      });
    } else if (node.type === "format") {
      const attributeIssue = validateAttributes(node);
      if (attributeIssue) diagnostics.push({ code: "invalid-format-attributes", severity: "warning", message: attributeIssue });
      const parent = ancestors.at(-1);
      if (
        (parent && CODE_FORMATS.has(parent.format))
        || (parent && QUOTE_FORMATS.has(parent.format) && QUOTE_FORMATS.has(node.format))
        || (parent && isExclusive(parent) && isExclusive(node))
      ) {
        diagnostics.push({
          code: "invalid-format-nesting",
          severity: "warning",
          message: `${node.format} cannot be nested inside ${parent?.format}.`,
        });
      }
    }
  });
  return diagnostics;
}

function visitNodes(
  nodes: readonly TemplateNode[],
  ancestors: readonly TemplateFormatNode[],
  visitor: (node: TemplateNode, ancestors: readonly TemplateFormatNode[]) => void,
): void {
  for (const node of nodes) {
    visitor(node, ancestors);
    if (node.type === "format") visitNodes(node.children, [...ancestors, node], visitor);
  }
}

function validateAttributes(node: TemplateFormatNode): string | null {
  if (node.format === "link" && !isSafeWebUrl(node.href ?? "")) return "Text link must use an http:// or https:// URL.";
  if (node.format === "mention" && !/^\d+$/.test(node.userId ?? "")) return "Telegram mention requires a numeric user ID.";
  if (node.format === "custom-emoji") {
    if (!/^\d+$/.test(node.emojiId ?? "")) return "Custom emoji requires a numeric emoji ID.";
    if (!isValidCustomEmojiFallback(node.fallback ?? "")) return "Custom emoji fallback must contain exactly one emoji.";
  }
  if (node.format === "date-time") {
    if (!Number.isSafeInteger(node.unix) || node.unix! < 0) return "Dynamic date and time requires a valid Unix timestamp.";
    if (!TELEGRAM_DATE_TIME_FORMAT.test(node.dateTimeFormat ?? "")) return "Dynamic date and time has an unsupported format.";
  }
  return null;
}

function isExclusive(node: TemplateFormatNode): boolean {
  return ["link", "mention", "custom-emoji", "date-time"].includes(node.format);
}
