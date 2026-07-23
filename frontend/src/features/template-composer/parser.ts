import { findContextField, SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";
import type { TemplateDocument, TemplateNode } from "./model";
import {
  FORMAT_KIND_BY_ALIAS,
  TELEGRAM_DATE_TIME_FORMAT,
  isSafeWebUrl,
  parseTelegramMentionHref,
} from "./telegram-formatting";

const JINJA_FRAGMENT = /({{[\s\S]*?}}|{%[\s\S]*?%}|{#[\s\S]*?#})/g;
const SIMPLE_CONTEXT_PATH = /^[A-Za-z_]\w*\.[A-Za-z_]\w*$/;
const PLACEHOLDER_PREFIX = "\uE000TGJINJA";
const PLACEHOLDER_SUFFIX = "\uE001";

export function parseTemplate(
  source: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): TemplateDocument {
  if (!source) return { nodes: [] };
  const fragments: string[] = [];
  const protectedSource = source.replace(JINJA_FRAGMENT, (fragment) => {
    const index = fragments.push(fragment) - 1;
    return `${PLACEHOLDER_PREFIX}${index}${PLACEHOLDER_SUFFIX}`;
  });
  const parsed = new DOMParser().parseFromString(`<body>${protectedSource}</body>`, "text/html");
  const nodes = parseDomChildren(parsed.body, catalog, fragments);
  return { nodes: mergeTextNodes(nodes) };
}

export function parseFragment(source: string, catalog: readonly ContextFieldDefinition[]): TemplateNode {
  if (!source.startsWith("{{")) return { type: "raw-fragment", source };

  const expression = source.slice(2, -2).trim();
  if (!SIMPLE_CONTEXT_PATH.test(expression)) return { type: "raw-fragment", source };

  const field = findContextField(expression, catalog);
  if (!field) return { type: "unresolved-token", path: expression, source };
  return { type: "context-token", fieldId: field.id, path: field.path, source };
}

function parseDomChildren(
  parent: ParentNode,
  catalog: readonly ContextFieldDefinition[],
  fragments: readonly string[],
): TemplateNode[] {
  const nodes: TemplateNode[] = [];
  for (const child of Array.from(parent.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      parseText(child.textContent ?? "", nodes, catalog, fragments);
    } else if (child instanceof HTMLElement) {
      nodes.push(parseElement(child, catalog, fragments));
    }
  }
  return mergeTextNodes(nodes);
}

function parseElement(
  element: HTMLElement,
  catalog: readonly ContextFieldDefinition[],
  fragments: readonly string[],
): TemplateNode {
  const tag = element.tagName.toLowerCase();
  const restoredSource = restoreFragments(element.outerHTML, fragments);

  if (tag === "span" && element.classList.length === 1 && element.classList.contains("tg-spoiler")) {
    return { type: "format", format: "spoiler", children: parseDomChildren(element, catalog, fragments) };
  }

  if (tag === "a") {
    const href = element.getAttribute("href") ?? "";
    const userId = parseTelegramMentionHref(href);
    if (userId) {
      return { type: "format", format: "mention", userId, href, children: parseDomChildren(element, catalog, fragments) };
    }
    if (!isSafeWebUrl(href)) return { type: "raw-fragment", source: restoredSource, fragmentKind: "html" };
    return { type: "format", format: "link", href, children: parseDomChildren(element, catalog, fragments) };
  }

  if (tag === "blockquote") {
    return {
      type: "format",
      format: element.hasAttribute("expandable") ? "expandable-quote" : "quote",
      children: parseDomChildren(element, catalog, fragments),
    };
  }

  if (tag === "pre") {
    const elementChildren = Array.from(element.children);
    const languageCode = elementChildren.length === 1 && elementChildren[0].tagName.toLowerCase() === "code"
      ? elementChildren[0] as HTMLElement
      : null;
    const language = languageCode?.className.match(/(?:^|\s)language-([A-Za-z0-9_+#.-]+)(?:\s|$)/)?.[1];
    return {
      type: "format",
      format: "code-block",
      language,
      children: parseDomChildren(languageCode ?? element, catalog, fragments),
    };
  }

  if (tag === "tg-emoji") {
    const emojiId = element.getAttribute("emoji-id") ?? "";
    const fallback = element.textContent ?? "";
    if (!/^\d+$/.test(emojiId) || !fallback) return { type: "raw-fragment", source: restoredSource, fragmentKind: "html" };
    return { type: "format", format: "custom-emoji", emojiId, fallback, children: [{ type: "text", text: fallback }] };
  }

  if (tag === "tg-time") {
    const unixValue = element.getAttribute("unix") ?? "";
    const dateTimeFormat = element.getAttribute("format") ?? "";
    const unix = Number(unixValue);
    const fallback = element.textContent ?? "";
    if (!/^\d+$/.test(unixValue) || !Number.isSafeInteger(unix) || !TELEGRAM_DATE_TIME_FORMAT.test(dateTimeFormat)) {
      return { type: "raw-fragment", source: restoredSource, fragmentKind: "html" };
    }
    return { type: "format", format: "date-time", unix, dateTimeFormat, fallback, children: [{ type: "text", text: fallback }] };
  }

  const format = FORMAT_KIND_BY_ALIAS.get(tag);
  if (format) return { type: "format", format, children: parseDomChildren(element, catalog, fragments) };

  return { type: "raw-fragment", source: restoredSource, fragmentKind: "html" };
}

function parseText(
  text: string,
  nodes: TemplateNode[],
  catalog: readonly ContextFieldDefinition[],
  fragments: readonly string[],
): void {
  const placeholder = new RegExp(`${PLACEHOLDER_PREFIX}(\\d+)${PLACEHOLDER_SUFFIX}`, "g");
  let cursor = 0;
  for (const match of text.matchAll(placeholder)) {
    const index = match.index ?? 0;
    pushText(nodes, text.slice(cursor, index));
    const source = fragments[Number(match[1])];
    if (source !== undefined) nodes.push(parseFragment(source, catalog));
    cursor = index + match[0].length;
  }
  pushText(nodes, text.slice(cursor));
}

function restoreFragments(source: string, fragments: readonly string[]): string {
  return source.replace(new RegExp(`${PLACEHOLDER_PREFIX}(\\d+)${PLACEHOLDER_SUFFIX}`, "g"), (_, index: string) => fragments[Number(index)] ?? "");
}

function pushText(nodes: TemplateNode[], text: string): void {
  if (!text) return;
  const previous = nodes.at(-1);
  if (previous?.type === "text") previous.text += text;
  else nodes.push({ type: "text", text });
}

function mergeTextNodes(nodes: TemplateNode[]): TemplateNode[] {
  const merged: TemplateNode[] = [];
  for (const node of nodes) {
    if (node.type === "text") pushText(merged, node.text);
    else merged.push(node);
  }
  return merged;
}
