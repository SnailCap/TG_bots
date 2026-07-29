import { findContextField, SYSTEM_CONTEXT_FIELDS } from "../template-composer/context-catalog";
import type { TemplateDocument, TemplateFormatNode, TemplateNode } from "../template-composer/model";
import { parseFragment, parseTemplate } from "../template-composer/parser";
import { serializeTemplate } from "../template-composer/serializer";
import type { TelegramFormatKind } from "../template-composer/telegram-formatting";
import {
  BOT_CONTENT_SCHEMA_VERSION,
  normalizeBotContentDocument,
  timestampFrom,
  type BotContentBlock,
  type BotContentDocument,
  type BotContentInlineNode,
  type BotContentMark,
} from "./model";

const MARK_BY_LEGACY_FORMAT: Partial<Record<TelegramFormatKind, BotContentMark["type"]>> = {
  bold: "bold",
  italic: "italic",
  underline: "underline",
  strikethrough: "strikethrough",
  spoiler: "spoiler",
  "inline-code": "code",
  link: "link",
};

const LEGACY_FORMAT_BY_MARK: Record<BotContentMark["type"], TelegramFormatKind> = {
  bold: "bold",
  italic: "italic",
  underline: "underline",
  strikethrough: "strikethrough",
  spoiler: "spoiler",
  code: "inline-code",
  link: "link",
};

const JINJA_FRAGMENT = /{{[\s\S]*?}}/g;

export type SupportedVariableTokenMatch = {
  index: number;
  source: string;
  fieldId: string;
  path: string;
};

/**
 * Finds only simple variables present in Studio's shared context catalog.
 * Unknown or complex Jinja is intentionally omitted so paste keeps it visible
 * as ordinary text instead of creating an unresolved atomic node.
 */
export function findSupportedVariableTokens(source: string): SupportedVariableTokenMatch[] {
  const matches: SupportedVariableTokenMatch[] = [];
  for (const match of source.matchAll(JINJA_FRAGMENT)) {
    const tokenSource = match[0];
    const parsed = parseFragment(tokenSource, SYSTEM_CONTEXT_FIELDS);
    if (parsed.type !== "context-token") continue;
    matches.push({
      index: match.index,
      source: tokenSource,
      fieldId: parsed.fieldId,
      path: parsed.path,
    });
  }
  return matches;
}

/**
 * Imports the current schema-v3 template string. Unsupported source is retained
 * as one atomic block so opening the richer editor can never silently rewrite
 * complex Jinja or unknown Telegram HTML.
 */
export function documentFromLegacyTemplate(
  viewId: string,
  source: string,
  now: string | Date = new Date(),
): BotContentDocument {
  const timestamp = timestampFrom(now);
  const parsed = parseTemplate(source);
  const structured = containsUnsupportedLegacyNode(parsed.nodes) ? null : legacyNodesToBlocks(parsed.nodes);
  // The old parser accepts a few equivalent HTML spellings. Only expose a
  // structured document when exporting it reproduces the original bytes;
  // otherwise retain the whole source atomically.
  const content = structured && structured.map(blockToLegacyTemplate).join("\n") === source
    ? structured
    : [{ type: "legacyTemplate" as const, source }];
  return normalizeBotContentDocument({
    schemaVersion: BOT_CONTENT_SCHEMA_VERSION,
    id: viewId,
    content: content.length > 0 ? content : [{ type: "paragraph", content: [] }],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      editorVersion: "1",
      source: "legacy-content",
    },
  });
}

/** Exports a structured document through the existing canonical template serializer. */
export function legacyTemplateFromDocument(document: BotContentDocument): string {
  return document.content.map(blockToLegacyTemplate).join("\n");
}

function containsUnsupportedLegacyNode(nodes: readonly TemplateNode[], ancestors: readonly TelegramFormatKind[] = []): boolean {
  for (const node of nodes) {
    if (node.type === "raw-fragment") return true;
    if (node.type !== "format") continue;
    if (node.format === "mention" || node.format === "date-time") return true;
    if (node.format === "code-block" && node.children.some((child) => child.type !== "text")) return true;
    if (node.format === "custom-emoji" && ancestors.some((format) => MARK_BY_LEGACY_FORMAT[format])) return true;
    if (containsUnsupportedLegacyNode(node.children, [...ancestors, node.format])) return true;
  }
  return false;
}

function legacyNodesToBlocks(nodes: readonly TemplateNode[]): BotContentBlock[] {
  const blocks: BotContentBlock[] = [];
  let paragraph: BotContentInlineNode[] = [];
  const flushParagraph = () => {
    if (paragraph.length === 0 && blocks.length > 0) return;
    blocks.push({ type: "paragraph", content: paragraph });
    paragraph = [];
  };

  for (const node of nodes) {
    if (node.type === "format" && node.format === "code-block") {
      if (paragraph.length > 0) flushParagraph();
      blocks.push({
        type: "codeBlock",
        text: templateNodesPlainText(node.children),
        ...(node.language ? { language: node.language } : {}),
      });
      continue;
    }
    if (node.type === "format" && (node.format === "quote" || node.format === "expandable-quote")) {
      if (paragraph.length > 0) flushParagraph();
      blocks.push({
        type: node.format === "quote" ? "blockquote" : "expandableBlockquote",
        content: legacyInlineNodes(node.children),
      });
      continue;
    }
    paragraph.push(...legacyInlineNodes([node]));
  }
  if (paragraph.length > 0 || blocks.length === 0) flushParagraph();
  return blocks;
}

function legacyInlineNodes(
  nodes: readonly TemplateNode[],
  inheritedMarks: readonly BotContentMark[] = [],
): BotContentInlineNode[] {
  const result: BotContentInlineNode[] = [];
  for (const node of nodes) {
    if (node.type === "text") {
      result.push(...textWithHardBreaks(node.text, inheritedMarks));
      continue;
    }
    if (node.type === "context-token" || node.type === "unresolved-token") {
      const field = findContextField(node.path);
      const fieldId = node.type === "context-token" ? node.fieldId : field?.id;
      result.push({
        type: "variable",
        variableReference: {
          ...(fieldId ? { fieldId } : {}),
          path: node.path,
          source: node.source ?? `{{ ${node.path} }}`,
        },
        ...(inheritedMarks.length ? { marks: inheritedMarks.map((mark) => ({ ...mark })) } : {}),
      });
      continue;
    }
    if (node.type === "raw-fragment") continue;
    if (node.format === "custom-emoji") {
      result.push({
        type: "customEmoji",
        customEmojiId: node.emojiId ?? "",
        fallbackEmoji: node.fallback ?? templateNodesPlainText(node.children),
      });
      continue;
    }
    const markType = MARK_BY_LEGACY_FORMAT[node.format];
    if (!markType) {
      result.push(...legacyInlineNodes(node.children, inheritedMarks));
      continue;
    }
    const mark: BotContentMark = markType === "link"
      ? { type: "link", href: node.href ?? "" }
      : { type: markType };
    result.push(...legacyInlineNodes(node.children, [...inheritedMarks, mark]));
  }
  return result;
}

function textWithHardBreaks(text: string, marks: readonly BotContentMark[]): BotContentInlineNode[] {
  const pieces = text.split("\n");
  const result: BotContentInlineNode[] = [];
  pieces.forEach((piece, index) => {
    if (piece) result.push({ type: "text", text: piece, ...(marks.length ? { marks: marks.map((mark) => ({ ...mark })) } : {}) });
    if (index < pieces.length - 1) result.push({ type: "hardBreak" });
  });
  return result;
}

function blockToLegacyTemplate(block: BotContentBlock): string {
  if (block.type === "legacyTemplate") return block.source;
  if (block.type === "codeBlock") {
    return serializeTemplate({ nodes: [{
      type: "format",
      format: "code-block",
      children: block.text ? [{ type: "text", text: block.text }] : [],
      ...(block.language ? { language: block.language } : {}),
    }] });
  }
  const nodes = contentInlineToLegacyNodes(block.content);
  if (block.type === "paragraph") return serializeTemplate({ nodes });
  return serializeTemplate({ nodes: [{
    type: "format",
    format: block.type === "blockquote" ? "quote" : "expandable-quote",
    children: nodes,
  }] });
}

function contentInlineToLegacyNodes(nodes: readonly BotContentInlineNode[]): TemplateNode[] {
  return nodes.map((node): TemplateNode => {
    if (node.type === "hardBreak") return { type: "text", text: "\n" };
    if (node.type === "customEmoji") {
      return {
        type: "format",
        format: "custom-emoji",
        emojiId: node.customEmojiId,
        fallback: node.fallbackEmoji,
        children: [{ type: "text", text: node.fallbackEmoji }],
      };
    }
    const leaf: TemplateNode = node.type === "variable"
      ? variableToLegacyNode(node)
      : { type: "text", text: node.text };
    return wrapLegacyMarks(leaf, node.marks ?? []);
  });
}

function variableToLegacyNode(node: Extract<BotContentInlineNode, { type: "variable" }>): TemplateNode {
  const { fieldId, path, source } = node.variableReference;
  const effectiveSource = source ?? `{{ ${path} }}`;
  return fieldId
    ? { type: "context-token", fieldId, path, source: effectiveSource }
    : { type: "unresolved-token", path, source: effectiveSource };
}

function wrapLegacyMarks(leaf: TemplateNode, marks: readonly BotContentMark[]): TemplateNode {
  return marks.reduceRight<TemplateNode>((child, mark) => {
    const format = LEGACY_FORMAT_BY_MARK[mark.type];
    const wrapped: TemplateFormatNode = {
      type: "format",
      format,
      children: [child],
      ...(mark.type === "link" ? { href: mark.href } : {}),
    };
    return wrapped;
  }, leaf);
}

function templateNodesPlainText(nodes: readonly TemplateNode[]): string {
  return nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "format") return templateNodesPlainText(node.children);
    if (node.type === "raw-fragment") return node.source;
    return node.source ?? `{{ ${node.path} }}`;
  }).join("");
}

/** Useful for tests and adapters that already hold the legacy transient tree. */
export function legacyTemplateDocumentFromSource(source: string): TemplateDocument {
  return parseTemplate(source);
}
