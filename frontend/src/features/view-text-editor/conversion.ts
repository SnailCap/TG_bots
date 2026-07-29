import type { JSONContent } from "@tiptap/core";

import {
  normalizeBotContentDocument,
  type BotContentBlock,
  type BotContentDocument,
  type BotContentInlineNode,
  type BotContentMark,
  type ExistingVariableReference,
} from "./model";

const TIPTAP_MARK_BY_CONTENT_MARK: Record<Exclude<BotContentMark["type"], "link">, string> = {
  bold: "bold",
  italic: "italic",
  underline: "underline",
  strikethrough: "strike",
  spoiler: "spoiler",
  code: "code",
};

export function documentToTiptapJson(document: BotContentDocument): JSONContent {
  const normalized = normalizeBotContentDocument(document);
  return {
    type: "doc",
    content: normalized.content.map(blockToTiptap),
  };
}

export function documentFromTiptapJson(
  content: JSONContent,
  base: BotContentDocument,
  updatedAt: string | Date = new Date(),
): BotContentDocument {
  const blocks = (content.content ?? []).flatMap(tiptapToBlocks);
  return normalizeBotContentDocument({
    ...base,
    content: blocks.length > 0 ? blocks : [{ type: "paragraph", content: [] }],
    metadata: {
      ...base.metadata,
      updatedAt: typeof updatedAt === "string" ? updatedAt : updatedAt.toISOString(),
    },
  });
}

/** Convenient aliases for adapters that use direction-first naming. */
export const botContentToTiptap = documentToTiptapJson;
export const botContentFromTiptap = documentFromTiptapJson;

function blockToTiptap(block: BotContentBlock): JSONContent {
  if (block.type === "paragraph") return paragraphToTiptap(block.content);
  if (block.type === "codeBlock") {
    return {
      type: "codeBlock",
      attrs: { language: block.language ?? null },
      content: block.text ? [{ type: "text", text: block.text }] : undefined,
    };
  }
  if (block.type === "legacyTemplate") {
    return { type: "legacyTemplate", attrs: { source: block.source } };
  }
  return {
    type: block.type === "blockquote" ? "blockquote" : "expandableBlockquote",
    content: [paragraphToTiptap(block.content)],
  };
}

function paragraphToTiptap(content: readonly BotContentInlineNode[]): JSONContent {
  const nodes = content.map(inlineToTiptap);
  return { type: "paragraph", content: nodes.length > 0 ? nodes : undefined };
}

function inlineToTiptap(node: BotContentInlineNode): JSONContent {
  if (node.type === "hardBreak") return { type: "hardBreak" };
  if (node.type === "customEmoji") {
    return {
      type: "customEmoji",
      attrs: {
        customEmojiId: node.customEmojiId,
        fallbackEmoji: node.fallbackEmoji,
      },
    };
  }
  if (node.type === "variable") {
    const source = node.variableReference.source ?? `{{ ${node.variableReference.path} }}`;
    return {
      type: "variable",
      attrs: {
        fieldId: node.variableReference.fieldId ?? null,
        path: node.variableReference.path,
        source,
      },
      marks: marksToTiptap(node.marks),
    };
  }
  return {
    type: "text",
    text: node.text,
    marks: marksToTiptap(node.marks),
  };
}

function marksToTiptap(marks: readonly BotContentMark[] | undefined): JSONContent["marks"] {
  if (!marks?.length) return undefined;
  return marks.map((mark) => mark.type === "link"
    ? { type: "link", attrs: { href: mark.href, target: null, rel: "noopener noreferrer" } }
    : { type: TIPTAP_MARK_BY_CONTENT_MARK[mark.type] });
}

function tiptapToBlocks(node: JSONContent): BotContentBlock[] {
  if (node.type === "paragraph") return [{ type: "paragraph", content: tiptapInlineNodes(node.content) }];
  if (node.type === "blockquote") {
    return [{ type: "blockquote", content: inlineFromBlockChildren(node.content) }];
  }
  if (node.type === "expandableBlockquote") {
    return [{ type: "expandableBlockquote", content: inlineFromBlockChildren(node.content) }];
  }
  if (node.type === "codeBlock") {
    const language = stringAttribute(node.attrs?.language);
    return [{ type: "codeBlock", text: tiptapText(node), ...(language ? { language } : {}) }];
  }
  if (node.type === "legacyTemplate") {
    return [{ type: "legacyTemplate", source: stringAttribute(node.attrs?.source) }];
  }

  const inline = inlineFromBlockChildren(node.content);
  return inline.length > 0 ? [{ type: "paragraph", content: inline }] : [];
}

function inlineFromBlockChildren(content: readonly JSONContent[] | undefined): BotContentInlineNode[] {
  const result: BotContentInlineNode[] = [];
  for (const child of content ?? []) {
    const next = child.type === "paragraph" ? tiptapInlineNodes(child.content) : tiptapInlineNodes([child]);
    if (result.length > 0 && next.length > 0) result.push({ type: "hardBreak" });
    result.push(...next);
  }
  return result;
}

function tiptapInlineNodes(content: readonly JSONContent[] | undefined): BotContentInlineNode[] {
  const result: BotContentInlineNode[] = [];
  for (const node of content ?? []) {
    if (node.type === "text") {
      const text = node.text ?? "";
      if (text) result.push({ type: "text", text, ...marksProperty(node.marks) });
      continue;
    }
    if (node.type === "hardBreak") {
      result.push({ type: "hardBreak" });
      continue;
    }
    if (node.type === "variable") {
      const path = stringAttribute(node.attrs?.path);
      const source = nullableStringAttribute(node.attrs?.source) ?? `{{ ${path} }}`;
      const reference: ExistingVariableReference = {
        path,
        source,
      };
      const fieldId = nullableStringAttribute(node.attrs?.fieldId);
      if (fieldId) reference.fieldId = fieldId;
      result.push({ type: "variable", variableReference: reference, ...marksProperty(node.marks) });
      continue;
    }
    if (node.type === "customEmoji") {
      result.push({
        type: "customEmoji",
        customEmojiId: stringAttribute(node.attrs?.customEmojiId),
        fallbackEmoji: stringAttribute(node.attrs?.fallbackEmoji),
      });
      continue;
    }
    result.push(...tiptapInlineNodes(node.content));
  }
  return result;
}

function marksProperty(marks: JSONContent["marks"]): { marks?: BotContentMark[] } {
  const converted = tiptapMarks(marks);
  return converted.length > 0 ? { marks: converted } : {};
}

function tiptapMarks(marks: JSONContent["marks"]): BotContentMark[] {
  const result: BotContentMark[] = [];
  for (const mark of marks ?? []) {
    if (mark.type === "strike") result.push({ type: "strikethrough" });
    else if (mark.type === "link") result.push({ type: "link", href: stringAttribute(mark.attrs?.href) });
    else if (["bold", "italic", "underline", "spoiler", "code"].includes(mark.type ?? "")) {
      result.push({ type: mark.type as Exclude<BotContentMark["type"], "strikethrough" | "link"> });
    }
  }
  return result;
}

function tiptapText(node: JSONContent): string {
  if (node.type === "text") return node.text ?? "";
  if (node.type === "hardBreak") return "\n";
  return (node.content ?? []).map(tiptapText).join("");
}

function stringAttribute(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function nullableStringAttribute(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}
