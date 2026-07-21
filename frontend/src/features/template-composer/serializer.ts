import type { TemplateDocument } from "./model";

export function serializeTemplate(document: TemplateDocument): string {
  return document.nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "context-token") return node.source ?? `{{ ${node.path} }}`;
    return node.source;
  }).join("");
}

