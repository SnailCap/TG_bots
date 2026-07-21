import { findContextField, SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument, TemplateNode } from "./model";

const JINJA_FRAGMENT = /({{[\s\S]*?}}|{%[\s\S]*?%}|{#[\s\S]*?#})/g;
const SIMPLE_CONTEXT_PATH = /^[A-Za-z_]\w*\.[A-Za-z_]\w*$/;

export function parseTemplate(
  source: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): TemplateDocument {
  const nodes: TemplateNode[] = [];
  let cursor = 0;

  for (const match of source.matchAll(JINJA_FRAGMENT)) {
    const index = match.index ?? 0;
    pushText(nodes, source.slice(cursor, index));
    nodes.push(parseFragment(match[0], catalog));
    cursor = index + match[0].length;
  }

  pushText(nodes, source.slice(cursor));
  return { nodes };
}

function parseFragment(source: string, catalog: readonly ContextFieldDefinition[]): TemplateNode {
  if (!source.startsWith("{{")) return { type: "raw-fragment", source };

  const expression = source.slice(2, -2).trim();
  if (!SIMPLE_CONTEXT_PATH.test(expression)) return { type: "raw-fragment", source };

  const field = findContextField(expression, catalog);
  if (!field) return { type: "unresolved-token", path: expression, source };
  return { type: "context-token", fieldId: field.id, path: field.path, source };
}

function pushText(nodes: TemplateNode[], text: string): void {
  if (!text) return;
  const previous = nodes.at(-1);
  if (previous?.type === "text") previous.text += text;
  else nodes.push({ type: "text", text });
}

