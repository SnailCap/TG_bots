import type { TemplateDocument, TemplateFormatNode, TemplateNode } from "./model";
import { parseTemplate } from "./parser";
import {
  CODE_FORMATS,
  FORMAT_ACTION_BY_KIND,
  INLINE_COMBINABLE_FORMATS,
  QUOTE_FORMATS,
  TELEGRAM_DATE_TIME_FORMAT,
  isSafeWebUrl,
  telegramMentionHref,
} from "./telegram-formatting";

export function serializeTemplate(document: TemplateDocument): string {
  return serializeNodes(normalizeNodes(document.nodes));
}

export function normalizeTelegramHtml(source: string): string {
  return serializeTemplate(parseTemplate(source));
}

export function escapeTelegramText(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function serializeNodes(nodes: readonly TemplateNode[]): string {
  return nodes.map(serializeNode).join("");
}

function serializeNode(node: TemplateNode): string {
  if (node.type === "text") return escapeTelegramText(node.text);
  if (node.type === "context-token") return node.source ?? `{{ ${node.path} }}`;
  if (node.type === "unresolved-token" || node.type === "raw-fragment") return node.source;
  return serializeFormat(node);
}

function serializeFormat(node: TemplateFormatNode): string {
  const action = FORMAT_ACTION_BY_KIND.get(node.format);
  if (!action) return serializeNodes(node.children);
  const content = serializeNodes(node.children);
  switch (node.format) {
    case "link":
      return isSafeWebUrl(node.href ?? "") ? `<a href="${escapeAttribute(node.href!)}">${content}</a>` : content;
    case "mention":
      return node.userId && /^\d+$/.test(node.userId)
        ? `<a href="${telegramMentionHref(node.userId)}">${content}</a>`
        : content;
    case "code-block":
      return node.language
        ? `<pre><code class="language-${escapeAttribute(node.language)}">${content}</code></pre>`
        : `<pre>${content}</pre>`;
    case "expandable-quote":
      return `<blockquote expandable>${content}</blockquote>`;
    case "custom-emoji": {
      const fallback = escapeTelegramText(node.fallback ?? plainText(node.children));
      return node.emojiId && /^\d+$/.test(node.emojiId)
        ? `<tg-emoji emoji-id="${node.emojiId}">${fallback}</tg-emoji>`
        : fallback;
    }
    case "date-time": {
      const fallback = escapeTelegramText(node.fallback ?? plainText(node.children));
      if (!Number.isSafeInteger(node.unix) || node.unix! < 0 || !TELEGRAM_DATE_TIME_FORMAT.test(node.dateTimeFormat ?? "")) return fallback;
      const format = node.dateTimeFormat ? ` format="${node.dateTimeFormat}"` : "";
      return `<tg-time unix="${node.unix}"${format}>${fallback}</tg-time>`;
    }
    default:
      return `<${action.tag}>${content}</${action.tag}>`;
  }
}

function normalizeNodes(nodes: readonly TemplateNode[], ancestors: readonly TemplateFormatNode[] = []): TemplateNode[] {
  const normalized: TemplateNode[] = [];
  for (const node of nodes) {
    if (node.type !== "format") {
      pushNode(normalized, node);
      continue;
    }

    const parent = ancestors.at(-1);
    const forbiddenByCode = parent && CODE_FORMATS.has(parent.format);
    const nestedQuote = parent && QUOTE_FORMATS.has(parent.format) && QUOTE_FORMATS.has(node.format);
    const nestedExclusive = parent && ["link", "mention", "custom-emoji", "date-time"].includes(parent.format)
      && ["link", "mention", "custom-emoji", "date-time"].includes(node.format);
    if (forbiddenByCode || nestedQuote || nestedExclusive) {
      for (const child of normalizeNodes(node.children, ancestors)) pushNode(normalized, child);
      continue;
    }

    const children = normalizeNodes(node.children, [...ancestors, node]);
    if (!children.length && node.format !== "date-time" && node.format !== "custom-emoji") continue;
    if (parent?.format === node.format && INLINE_COMBINABLE_FORMATS.has(node.format)) {
      for (const child of children) pushNode(normalized, child);
      continue;
    }
    pushNode(normalized, { ...node, children });
  }
  return normalized;
}

function pushNode(nodes: TemplateNode[], node: TemplateNode): void {
  const previous = nodes.at(-1);
  if (node.type === "text" && previous?.type === "text") {
    previous.text += node.text;
    return;
  }
  if (
    node.type === "format"
    && previous?.type === "format"
    && previous.format === node.format
    && sameAttributes(previous, node)
    && INLINE_COMBINABLE_FORMATS.has(node.format)
  ) {
    previous.children.push(...node.children);
    return;
  }
  nodes.push(node);
}

function sameAttributes(left: TemplateFormatNode, right: TemplateFormatNode): boolean {
  return left.href === right.href
    && left.userId === right.userId
    && left.language === right.language
    && left.emojiId === right.emojiId
    && left.unix === right.unix
    && left.dateTimeFormat === right.dateTimeFormat;
}

function plainText(nodes: readonly TemplateNode[]): string {
  return nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "context-token") return node.source ?? `{{ ${node.path} }}`;
    if (node.type === "format") return plainText(node.children);
    return node.source;
  }).join("");
}

function escapeAttribute(value: string): string {
  return escapeTelegramText(value).replaceAll('"', "&quot;");
}
