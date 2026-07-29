export const CONTENT_SCHEMA_VERSION = 1 as const;
const VARIABLE_PATH = /^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$/;
const VARIABLE_SOURCE = /^{{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*}}$/;

export type BotContentMark =
  | { type: "bold" }
  | { type: "italic" }
  | { type: "underline" }
  | { type: "strikethrough" }
  | { type: "spoiler" }
  | { type: "code" }
  | { type: "link"; href: string };

export type ExistingVariableReference = {
  /** Runtime-facing Jinja context path. */
  path: string;
  /** Stable catalog identifier when the variable is known to Studio. */
  fieldId?: string;
  /** Exact legacy spelling, retained for lossless source round-trips. */
  source?: string;
};

export type BotContentInlineNode =
  | { type: "text"; text: string; marks?: BotContentMark[] }
  | { type: "variable"; variableReference: ExistingVariableReference; marks?: BotContentMark[] }
  | { type: "customEmoji"; customEmojiId: string; fallbackEmoji: string }
  | { type: "hardBreak" };

export type BotContentBlock =
  | { type: "paragraph"; content: BotContentInlineNode[] }
  | { type: "blockquote"; content: BotContentInlineNode[] }
  | { type: "expandableBlockquote"; content: BotContentInlineNode[] }
  | { type: "codeBlock"; language?: string; text: string }
  | { type: "legacyTemplate"; source: string };

export type BotContentDocument = {
  schemaVersion: typeof CONTENT_SCHEMA_VERSION;
  id: string;
  content: BotContentBlock[];
  metadata: {
    createdAt: string;
    updatedAt: string;
    editorVersion: string;
    source?: "botstudio" | "telegram-import" | "legacy-content";
  };
};

export type ContentDiagnostic = {
  severity: "info" | "warning" | "error";
  code: string;
  message: string;
  path?: string;
  messageIndex?: number;
};

export type TelegramMessageEntity = {
  type:
    | "bold"
    | "italic"
    | "underline"
    | "strikethrough"
    | "spoiler"
    | "code"
    | "text_link"
    | "blockquote"
    | "expandable_blockquote"
    | "pre"
    | "custom_emoji";
  offset: number;
  length: number;
  url?: string;
  language?: string;
  custom_emoji_id?: string;
};

export type CompiledTelegramMessage = {
  text: string;
  entities: TelegramMessageEntity[];
};

export type TelegramCompileResult = {
  messages: CompiledTelegramMessage[];
  warnings: ContentDiagnostic[];
  errors: ContentDiagnostic[];
};

export const EMPTY_COMPILE_RESULT: TelegramCompileResult = {
  messages: [],
  warnings: [],
  errors: [],
};

export function emptyContentDocument(
  id: string,
  now: string | Date = new Date(),
): BotContentDocument {
  const timestamp = timestampFrom(now);
  return {
    schemaVersion: CONTENT_SCHEMA_VERSION,
    id,
    content: [{ type: "paragraph", content: [] }],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      editorVersion: "1.0.0",
      source: "botstudio",
    },
  };
}

export const createEmptyBotContentDocument = emptyContentDocument;

export function timestampFrom(value: string | Date): string {
  return typeof value === "string" ? value : value.toISOString();
}

export function normalizeBotContentDocument(document: BotContentDocument): BotContentDocument {
  const content = document.content.map(normalizeBlock);
  return {
    ...document,
    schemaVersion: CONTENT_SCHEMA_VERSION,
    content: content.length > 0 ? content : [{ type: "paragraph", content: [] }],
  };
}

export function documentPlainText(document: BotContentDocument): string {
  return document.content.map((block) => {
    if (block.type === "codeBlock") return block.text;
    if (block.type === "legacyTemplate") return block.source;
    return inlinePlainText(block.content);
  }).join("\n");
}

export function inlinePlainText(nodes: readonly BotContentInlineNode[]): string {
  return nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "variable") {
      return node.variableReference.source ?? `{{ ${node.variableReference.path} }}`;
    }
    if (node.type === "customEmoji") return node.fallbackEmoji;
    return "\n";
  }).join("");
}

export function isSafeContentLink(value: string): boolean {
  if (!value || /[\r\n\0]/.test(value)) return false;
  try {
    const url = new URL(value);
    return ["http:", "https:", "tg:", "mailto:"].includes(url.protocol.toLocaleLowerCase());
  } catch {
    return false;
  }
}

export function validateBotContentDocument(document: BotContentDocument): ContentDiagnostic[] {
  const diagnostics: ContentDiagnostic[] = [];
  if (document.schemaVersion !== CONTENT_SCHEMA_VERSION) {
    diagnostics.push({
      code: "unsupported-content-schema",
      severity: "error",
      message: `Content schema v${String(document.schemaVersion)} is not supported.`,
    });
  }

  for (const block of document.content) {
    if (block.type === "legacyTemplate") {
      diagnostics.push({
        code: "legacy-template-fragment",
        severity: "warning",
        message: "This source is preserved exactly, but it cannot be edited visually yet.",
      });
      continue;
    }
    if (block.type === "codeBlock") continue;
    for (const node of block.content) {
      if (node.type === "variable") {
        const { path, source } = node.variableReference;
        if (!VARIABLE_PATH.test(path)) {
          diagnostics.push({
            code: "invalid-variable-path",
            severity: "error",
            message: "Variable path must be a dotted Jinja identifier.",
          });
        }
        if (source !== undefined) {
          const match = VARIABLE_SOURCE.exec(source);
          if (!match || match[1] !== path) {
            diagnostics.push({
              code: "invalid-variable-source",
              severity: "error",
              message: "Variable source must be a simple Jinja reference to the same path.",
            });
          }
        }
      }
      if (node.type === "customEmoji" && !/^\d+$/.test(node.customEmojiId)) {
        diagnostics.push({
          code: "invalid-custom-emoji-id",
          severity: "error",
          message: "Custom emoji ID must contain digits only.",
        });
      }
      if (node.type === "customEmoji" && !isValidCustomEmojiFallback(node.fallbackEmoji)) {
        diagnostics.push({
          code: "invalid-custom-emoji-fallback",
          severity: "error",
          message: "Custom emoji fallback must contain exactly one supported Unicode emoji.",
        });
      }
      if (node.type === "text" || node.type === "variable") {
        for (const mark of node.marks ?? []) {
          if (mark.type === "link" && !isSafeContentLink(mark.href)) {
            diagnostics.push({
              code: "invalid-link",
              severity: "error",
              message: "Text links must use http://, https://, tg://, or mailto:.",
            });
          }
        }
      }
    }
  }
  return diagnostics;
}

/** Mirrors tg_bot_core.content.validation.is_valid_custom_emoji_fallback. */
export function isValidCustomEmojiFallback(value: string): boolean {
  if (!value || value.length > 32) return false;

  const codepoints = Array.from(value, (character) => character.codePointAt(0)!);
  if (codepoints.some((codepoint) => {
    if (codepoint === 0x200d || (codepoint >= 0xe0020 && codepoint <= 0xe007f)) return false;
    return /\p{C}/u.test(String.fromCodePoint(codepoint));
  })) return false;

  if (codepoints.every((codepoint) => codepoint >= 0x1f1e6 && codepoint <= 0x1f1ff)) {
    return codepoints.length === 2;
  }
  if (
    (codepoints.length === 2 || codepoints.length === 3)
    && "#*0123456789".includes(String.fromCodePoint(codepoints[0]))
    && codepoints.at(-1) === 0x20e3
  ) {
    return codepoints.length === 2 || codepoints[1] === 0xfe0f;
  }
  if (
    codepoints.length >= 3
    && codepoints[0] === 0x1f3f4
    && codepoints.at(-1) === 0xe007f
  ) {
    return codepoints.slice(1, -1).every((codepoint) => codepoint >= 0xe0020 && codepoint <= 0xe007e);
  }

  let index = consumeEmojiComponent(codepoints, 0);
  if (index === null) return false;
  while (index < codepoints.length) {
    if (codepoints[index] !== 0x200d) return false;
    index = consumeEmojiComponent(codepoints, index + 1);
    if (index === null) return false;
  }
  return true;
}

function consumeEmojiComponent(codepoints: readonly number[], start: number): number | null {
  if (start >= codepoints.length) return null;
  const base = codepoints[start];
  if ((base >= 0x1f3fb && base <= 0x1f3ff) || !isEmojiBase(base)) return null;

  let index = start + 1;
  if (codepoints[index] === 0xfe0e || codepoints[index] === 0xfe0f) index += 1;
  if (codepoints[index] >= 0x1f3fb && codepoints[index] <= 0x1f3ff) index += 1;
  return index;
}

function isEmojiBase(codepoint: number): boolean {
  return [
    0x00a9, 0x00ae, 0x203c, 0x2049, 0x2122, 0x2139, 0x2328, 0x23cf,
    0x24c2, 0x3030, 0x303d, 0x3297, 0x3299, 0x25b6, 0x25c0, 0x2b50, 0x2b55,
  ].includes(codepoint)
    || (codepoint >= 0x2194 && codepoint <= 0x2199)
    || (codepoint >= 0x21a9 && codepoint <= 0x21aa)
    || (codepoint >= 0x231a && codepoint <= 0x231b)
    || (codepoint >= 0x23e9 && codepoint <= 0x23f3)
    || (codepoint >= 0x23f8 && codepoint <= 0x23fa)
    || (codepoint >= 0x25aa && codepoint <= 0x25ab)
    || (codepoint >= 0x25fb && codepoint <= 0x25fe)
    || (codepoint >= 0x2600 && codepoint <= 0x27bf)
    || (codepoint >= 0x2934 && codepoint <= 0x2935)
    || (codepoint >= 0x2b05 && codepoint <= 0x2b07)
    || (codepoint >= 0x2b1b && codepoint <= 0x2b1c)
    || (codepoint >= 0x1f000 && codepoint <= 0x1faff);
}

function normalizeBlock(block: BotContentBlock): BotContentBlock {
  if (block.type === "codeBlock") {
    const language = block.language?.trim();
    return { type: "codeBlock", text: block.text, ...(language ? { language } : {}) };
  }
  if (block.type === "legacyTemplate") return { type: "legacyTemplate", source: block.source };
  return { ...block, content: normalizeInlineNodes(block.content) };
}

function normalizeInlineNodes(nodes: readonly BotContentInlineNode[]): BotContentInlineNode[] {
  const normalized: BotContentInlineNode[] = [];
  for (const node of nodes) {
    if (node.type === "text") {
      if (!node.text) continue;
      const marks = normalizeMarks(node.marks);
      const previous = normalized.at(-1);
      if (previous?.type === "text" && marksEqual(previous.marks, marks)) {
        previous.text += node.text;
      } else {
        normalized.push({ type: "text", text: node.text, ...(marks.length ? { marks } : {}) });
      }
      continue;
    }
    if (node.type === "variable") {
      const marks = normalizeMarks(node.marks);
      normalized.push({
        type: "variable",
        variableReference: { ...node.variableReference },
        ...(marks.length ? { marks } : {}),
      });
      continue;
    }
    if (node.type === "customEmoji") {
      normalized.push({ ...node });
      continue;
    }
    normalized.push({ type: "hardBreak" });
  }
  return normalized;
}

function normalizeMarks(marks: readonly BotContentMark[] | undefined): BotContentMark[] {
  if (!marks?.length) return [];
  const result: BotContentMark[] = [];
  const seen = new Set<string>();
  for (const mark of marks) {
    const key = mark.type === "link" ? `${mark.type}:${mark.href}` : mark.type;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push({ ...mark });
  }
  if (result.some((mark) => mark.type === "code")) return [{ type: "code" }];
  return result;
}

function marksEqual(left: readonly BotContentMark[] | undefined, right: readonly BotContentMark[]): boolean {
  return JSON.stringify(left ?? []) === JSON.stringify(right);
}
