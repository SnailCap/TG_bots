import { describe, expect, it } from "vitest";

import type { TemplateDocument, TemplateFormatNode } from "./model";
import { parseTemplate } from "./parser";
import { sanitizePastedHtml } from "./paste-sanitizer";
import { normalizeTelegramHtml, serializeTemplate } from "./serializer";
import {
  DATE_TIME_FORMAT_OPTIONS,
  TELEGRAM_DATE_TIME_FORMAT,
  TELEGRAM_FORMATTING_ACTIONS,
  formattingActionForHotkey,
} from "./telegram-formatting";
import { validateTemplate } from "./validation";

describe("Telegram HTML parser and canonical serializer", () => {
  it.each([
    ["<strong>bold</strong>", "<b>bold</b>", "bold"],
    ["<em>italic</em>", "<i>italic</i>", "italic"],
    ["<ins>underline</ins>", "<u>underline</u>", "underline"],
    ["<del>strike</del>", "<s>strike</s>", "strikethrough"],
    ['<span class="tg-spoiler">secret</span>', "<tg-spoiler>secret</tg-spoiler>", "spoiler"],
    ['<a href="https://example.com">site</a>', '<a href="https://example.com">site</a>', "link"],
    ['<a href="tg://user?id=123456789">Ada</a>', '<a href="tg://user?id=123456789">Ada</a>', "mention"],
    ["<code>value</code>", "<code>value</code>", "inline-code"],
    ["<pre>line 1\nline 2</pre>", "<pre>line 1\nline 2</pre>", "code-block"],
    ['<pre><code class="language-python">print(1)</code></pre>', '<pre><code class="language-python">print(1)</code></pre>', "code-block"],
    ["<blockquote>quote</blockquote>", "<blockquote>quote</blockquote>", "quote"],
    ["<blockquote expandable>quote</blockquote>", "<blockquote expandable>quote</blockquote>", "expandable-quote"],
    ['<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>', '<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>', "custom-emoji"],
    ['<tg-time unix="1893456000" format="wDT">New year</tg-time>', '<tg-time unix="1893456000" format="wDT">New year</tg-time>', "date-time"],
  ])("normalizes %s", (source, canonical, format) => {
    const parsed = parseTemplate(source);
    expect(parsed.nodes[0]).toMatchObject({ type: "format", format });
    expect(serializeTemplate(parsed)).toBe(canonical);
  });

  it("keeps all combinable inline formats nested without duplicates", () => {
    const source = "<b><i><u><s><tg-spoiler>text</tg-spoiler></s></u></i></b>";
    expect(serializeTemplate(parseTemplate(source))).toBe(source);
    expect(normalizeTelegramHtml("<strong><b>text</b></strong>")).toBe("<b>text</b>");
  });

  it("keeps Jinja tokens atomic inside Telegram formatting", () => {
    const source = "<b>Hello {{user.first_name}}</b>";
    const parsed = parseTemplate(source);
    const bold = parsed.nodes[0] as TemplateFormatNode;
    expect(bold.children).toEqual([
      { type: "text", text: "Hello " },
      expect.objectContaining({ type: "context-token", path: "user.first_name", source: "{{user.first_name}}" }),
    ]);
    expect(serializeTemplate(parsed)).toBe(source);
  });

  it("escapes ordinary text while retaining Jinja source", () => {
    const document: TemplateDocument = {
      nodes: [
        { type: "text", text: "5 < 8 & " },
        { type: "context-token", fieldId: "core.user.first_name", path: "user.first_name" },
      ],
    };
    expect(serializeTemplate(document)).toBe("5 &lt; 8 &amp; {{ user.first_name }}");
  });

  it("normalizes invalid code, quote, and exclusive nesting", () => {
    expect(normalizeTelegramHtml("<code><b>value</b></code>")).toBe("<code>value</code>");
    expect(normalizeTelegramHtml("<blockquote>a<blockquote>b</blockquote></blockquote>")).toBe("<blockquote>ab</blockquote>");
    const normalizedLinks = normalizeTelegramHtml('<a href="https://a.example"><a href="https://b.example">x</a></a>');
    expect(normalizedLinks.match(/<a /g)).toHaveLength(1);
  });

  it("preserves unsupported or unsafe source as a visible diagnostic instead of pretending it works", () => {
    const document = parseTemplate('<mark>text</mark><a href="javascript:alert(1)">bad</a>');
    expect(document.nodes).toEqual([
      expect.objectContaining({ type: "raw-fragment", fragmentKind: "html" }),
      expect.objectContaining({ type: "raw-fragment", fragmentKind: "html" }),
    ]);
    expect(validateTemplate(document).map((diagnostic) => diagnostic.code)).toEqual(["unsupported-html", "unsupported-html"]);
  });

  it("supports every allowed date-time format exposed by the UI", () => {
    for (const option of DATE_TIME_FORMAT_OPTIONS) expect(TELEGRAM_DATE_TIME_FORMAT.test(option.value)).toBe(true);
    expect(TELEGRAM_DATE_TIME_FORMAT.test("rr")).toBe(false);
    expect(TELEGRAM_DATE_TIME_FORMAT.test("rt")).toBe(false);
    expect(TELEGRAM_DATE_TIME_FORMAT.test("dd")).toBe(false);
  });

  it("round-trips a saved template after normalization and reopening", () => {
    const source = '<strong>Hi {{ user.first_name }}</strong>\n<blockquote expandable>Details</blockquote>';
    const saved = normalizeTelegramHtml(source);
    expect(saved).toBe("<b>Hi {{ user.first_name }}</b>\n<blockquote expandable>Details</blockquote>");
    expect(serializeTemplate(parseTemplate(saved))).toBe(saved);
  });
});

describe("Telegram paste sanitization", () => {
  it("keeps convertible formatting and removes external styles, classes, and unsupported wrappers", () => {
    const pasted = '<div class="foreign" style="color:red"><span style="font-weight:700;color:red">Bold</span> <mark><em>italic</em></mark></div>';
    expect(sanitizePastedHtml(pasted)).toBe("<b>Bold</b> <i>italic</i>");
  });

  it("drops unsafe links but keeps their text", () => {
    expect(sanitizePastedHtml('<a href="javascript:alert(1)">safe text</a>')).toBe("safe text");
  });

  it("retains only Telegram formatting inside pasted code", () => {
    expect(sanitizePastedHtml("<pre><b>literal</b></pre>")).toBe("<pre>literal</pre>");
  });

  it("preserves template variables in pasted text", () => {
    expect(sanitizePastedHtml("<b>Hello {{ user.first_name }}</b>")).toBe("<b>Hello {{ user.first_name }}</b>");
  });
});

describe("formatting action registry", () => {
  it("is the single complete catalog used by actions and aliases", () => {
    expect(TELEGRAM_FORMATTING_ACTIONS.map((action) => action.kind)).toEqual([
      "bold",
      "italic",
      "underline",
      "strikethrough",
      "spoiler",
      "link",
      "inline-code",
      "mention",
      "code-block",
      "quote",
      "expandable-quote",
      "custom-emoji",
      "date-time",
    ]);
  });

  it.each([
    ["KeyB", false, "bold"],
    ["KeyI", false, "italic"],
    ["KeyU", false, "underline"],
    ["KeyX", true, "strikethrough"],
    ["KeyM", true, "inline-code"],
    ["KeyP", true, "spoiler"],
    ["KeyK", false, "link"],
    ["Period", true, "quote"],
  ])("matches Telegram hotkey %s", (code, shiftKey, kind) => {
    expect(formattingActionForHotkey({ code, shiftKey, ctrlKey: true, metaKey: false, altKey: false })?.kind).toBe(kind);
  });
});
