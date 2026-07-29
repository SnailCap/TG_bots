import { describe, expect, it } from "vitest";

import type { BotContentDocument } from "../../domain/content";
import { documentFromTiptapJson, documentToTiptapJson } from "./conversion";
import { documentFromLegacyTemplate, legacyTemplateFromDocument } from "./legacy-adapter";
import { documentPlainText, isSafeContentLink, normalizeBotContentDocument } from "./model";

const TIMESTAMP = "2026-07-29T10:00:00.000Z";

function documentWith(content: BotContentDocument["content"]): BotContentDocument {
  return {
    schemaVersion: 1,
    id: "welcome",
    content,
    metadata: {
      createdAt: TIMESTAMP,
      updatedAt: TIMESTAMP,
      editorVersion: "1.0.0",
      source: "botstudio",
    },
  };
}

describe("BotContentDocument ↔ Tiptap conversion", () => {
  it("round-trips marks, atomic inline nodes, and Telegram blocks", () => {
    const source = documentWith([
      {
        type: "paragraph",
        content: [
          { type: "text", text: "Hello ", marks: [{ type: "bold" }, { type: "italic" }] },
          {
            type: "variable",
            variableReference: {
              fieldId: "core.user.first_name",
              path: "user.first_name",
              source: "{{user.first_name}}",
            },
            marks: [{ type: "underline" }],
          },
          { type: "hardBreak" },
          { type: "customEmoji", customEmojiId: "5368324170671202286", fallbackEmoji: "🙂" },
        ],
      },
      { type: "blockquote", content: [{ type: "text", text: "Quote", marks: [{ type: "spoiler" }] }] },
      { type: "expandableBlockquote", content: [{ type: "text", text: "More" }] },
      { type: "codeBlock", language: "python", text: "print('ok')" },
      { type: "legacyTemplate", source: "{% if user %}kept{% endif %}" },
    ]);

    const restored = documentFromTiptapJson(documentToTiptapJson(source), source, TIMESTAMP);

    expect(restored).toEqual(source);
  });

  it("normalizes empty documents and adjacent equivalent text runs", () => {
    const normalized = normalizeBotContentDocument(documentWith([
      {
        type: "paragraph",
        content: [
          { type: "text", text: "A", marks: [{ type: "bold" }, { type: "bold" }] },
          { type: "text", text: "B", marks: [{ type: "bold" }] },
          { type: "text", text: "" },
        ],
      },
    ]));

    expect(normalized.content).toEqual([{
      type: "paragraph",
      content: [{ type: "text", text: "AB", marks: [{ type: "bold" }] }],
    }]);
    expect(normalizeBotContentDocument(documentWith([])).content).toEqual([{ type: "paragraph", content: [] }]);
  });

  it("matches runtime plain-text block and safe-link semantics", () => {
    const document = documentWith([
      {
        type: "paragraph",
        content: [{ type: "variable", variableReference: { path: "user.first_name" } }],
      },
      { type: "paragraph", content: [{ type: "text", text: "next" }] },
    ]);
    expect(documentPlainText(document)).toBe("{{ user.first_name }}\nnext");
    expect(["https://example.com", "http://example.com", "tg://user?id=42", "mailto:bot@example.com"].every(isSafeContentLink)).toBe(true);
    expect(isSafeContentLink("javascript:alert(1)")).toBe(false);
    expect(isSafeContentLink("https://example.com\njavascript:alert(1)")).toBe(false);

    const restored = documentFromTiptapJson(documentToTiptapJson(document), document, TIMESTAMP);
    expect(restored.content[0]).toEqual({
      type: "paragraph",
      content: [{
        type: "variable",
        variableReference: { path: "user.first_name", source: "{{ user.first_name }}" },
      }],
    });
  });
});

describe("legacy view template adapter", () => {
  it("keeps known and unknown variable identity and exact source spelling", () => {
    const source = "<b>Hello {{user.first_name}}</b> / {{ custom.value }}";
    const imported = documentFromLegacyTemplate("welcome", source, TIMESTAMP);
    const paragraph = imported.content[0];

    expect(paragraph.type).toBe("paragraph");
    if (paragraph.type !== "paragraph") throw new Error("Expected paragraph");
    expect(paragraph.content).toEqual([
      { type: "text", text: "Hello ", marks: [{ type: "bold" }] },
      {
        type: "variable",
        variableReference: {
          fieldId: "core.user.first_name",
          path: "user.first_name",
          source: "{{user.first_name}}",
        },
        marks: [{ type: "bold" }],
      },
      { type: "text", text: " / " },
      {
        type: "variable",
        variableReference: { path: "custom.value", source: "{{ custom.value }}" },
      },
    ]);
    expect(legacyTemplateFromDocument(imported)).toBe(source);
  });

  it.each([
    "{% if user %}Hello{% endif %}",
    "<section data-x=\"1\">Unknown HTML</section>",
    "{{ user.first_name | upper }}",
  ])("preserves unsupported source losslessly: %s", (source) => {
    const imported = documentFromLegacyTemplate("welcome", source, TIMESTAMP);
    expect(imported.content).toEqual([{ type: "legacyTemplate", source }]);
    expect(legacyTemplateFromDocument(imported)).toBe(source);
  });

  it("uses the lossless block when structured block boundaries would add whitespace", () => {
    const source = "<blockquote>quote</blockquote>tail";
    const imported = documentFromLegacyTemplate("welcome", source, TIMESTAMP);
    expect(imported.content).toEqual([{ type: "legacyTemplate", source }]);
    expect(legacyTemplateFromDocument(imported)).toBe(source);
  });
});
