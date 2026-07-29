import { Editor, type JSONContent } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { sanitizePastedHtml } from "../template-composer/paste-sanitizer";
import {
  CustomEmojiNode,
  ExpandableBlockquote,
  INTERNAL_CONTENT_CLIPBOARD_MIME,
  InternalClipboard,
  LegacyTemplateNode,
  SpoilerMark,
  VariableNode,
} from "./extensions";
import { isValidCustomEmojiFallback } from "./model";

const editors: Editor[] = [];

function createEditor(content: JSONContent | string = "<p></p>") {
  const editor = new Editor({
    element: document.createElement("div"),
    extensions: [
      StarterKit.configure({ trailingNode: false }),
      SpoilerMark,
      VariableNode,
      CustomEmojiNode,
      ExpandableBlockquote,
      LegacyTemplateNode,
      InternalClipboard,
    ],
    content,
    editorProps: { transformPastedHTML: sanitizePastedHtml },
  });
  editors.push(editor);
  return editor;
}

afterEach(() => {
  act(() => editors.splice(0).forEach((editor) => editor.destroy()));
});

describe("rich editor plain-text clipboard", () => {
  it("atomizes only catalog variables and preserves pasted line breaks and unknown Jinja", () => {
    const editor = createEditor();
    const pasted = [
      "Hello {{user.first_name}}",
      "Unknown: {{ custom.value }}",
      "Complex: {{ user.username | upper }}",
    ].join("\n");

    const pasteEvent = createClipboardEvent("paste", clipboardStub());
    act(() => { editor.view.pasteText(pasted, pasteEvent); });

    const json = editor.getJSON();
    const inlineNodes = json.content?.flatMap((block) => block.content ?? []) ?? [];
    expect(inlineNodes.filter((node) => node.type === "variable")).toEqual([{
      type: "variable",
      attrs: {
        fieldId: "core.user.first_name",
        path: "user.first_name",
        source: "{{user.first_name}}",
      },
    }]);
    expect(editor.getText({ blockSeparator: "\n" })).toBe(pasted);
  });

  it("serializes atomic nodes to exact interoperable text and round-trips the private slice", () => {
    const source = createEditor({
      type: "doc",
      content: [
        {
          type: "paragraph",
          content: [
            { type: "text", text: "Hello " },
            {
              type: "variable",
              attrs: {
                fieldId: "core.user.first_name",
                path: "user.first_name",
                source: "{{user.first_name}}",
              },
            },
            { type: "text", text: " " },
            { type: "customEmoji", attrs: { customEmojiId: "123", fallbackEmoji: "🙂" } },
          ],
        },
        { type: "legacyTemplate", attrs: { source: "{% if user %}kept{% endif %}" } },
      ],
    });
    act(() => { source.commands.selectAll(); });
    const clipboard = clipboardStub();

    const copyEvent = dispatchClipboardEvent(source.view.dom, "copy", clipboard);

    expect(copyEvent.defaultPrevented).toBe(true);
    expect(clipboard.getData("text/plain")).toBe(
      "Hello {{user.first_name}} 🙂\n\n{% if user %}kept{% endif %}",
    );
    expect(clipboard.getData(INTERNAL_CONTENT_CLIPBOARD_MIME)).not.toBe("");

    const target = createEditor("<p>replace me</p>");
    act(() => { target.commands.selectAll(); });
    const pasteEvent = dispatchClipboardEvent(target.view.dom, "paste", clipboard);

    expect(pasteEvent.defaultPrevented).toBe(true);
    expect(target.getJSON()).toEqual(source.getJSON());
  });
});

describe("custom emoji paste safety", () => {
  it("accepts one real emoji and rejects text or multiple emoji", () => {
    expect(["🙂", "👩🏽‍💻", "🇪🇪", "#️⃣"].every(isValidCustomEmojiFallback)).toBe(true);
    expect(["A", "🙂🙂", "🏽", "🙂 text"].some(isValidCustomEmojiFallback)).toBe(false);
  });

  it("degrades an invalid tg-emoji fallback to plain text before document parsing", () => {
    expect(sanitizePastedHtml('<tg-emoji emoji-id="123"><b>not emoji</b></tg-emoji>')).toBe("not emoji");

    const editor = createEditor();
    const pasteEvent = createClipboardEvent("paste", clipboardStub());
    act(() => {
      editor.view.pasteHTML('<tg-emoji emoji-id="123">not emoji</tg-emoji>', pasteEvent);
    });

    const inlineNodes = editor.getJSON().content?.flatMap((block) => block.content ?? []) ?? [];
    expect(inlineNodes).not.toContainEqual(expect.objectContaining({ type: "customEmoji" }));
    expect(editor.getText()).toBe("not emoji");
  });
});

type ClipboardStub = Pick<DataTransfer, "clearData" | "getData" | "setData">;

function clipboardStub(): ClipboardStub {
  const values = new Map<string, string>();
  return {
    clearData: vi.fn(() => values.clear()),
    getData: vi.fn((type: string) => values.get(type) ?? ""),
    setData: vi.fn((type: string, value: string) => { values.set(type, value); }),
  };
}

function dispatchClipboardEvent(target: HTMLElement, type: "copy" | "paste", clipboardData: ClipboardStub): Event {
  const event = createClipboardEvent(type, clipboardData);
  act(() => { target.dispatchEvent(event); });
  return event;
}

function createClipboardEvent(type: "copy" | "paste", clipboardData: ClipboardStub): ClipboardEvent {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "clipboardData", { value: clipboardData });
  return event as ClipboardEvent;
}
