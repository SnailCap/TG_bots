import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TemplateComposer } from "./TemplateComposer";

function Harness({ initial = "" }: { initial?: string }) {
  const [content, setContent] = useState(initial);
  return <><TemplateComposer content={content} onContentChange={setContent} /><output data-testid="source-value">{content}</output></>;
}

describe("floating Telegram formatting toolbar", () => {
  it("appears for a selection, applies a style, shows it as active, and removes it on repeat", () => {
    render(<Harness initial="hello" />);
    selectVisualText("hello");
    fireEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(source()).toBe("<b>hello</b>");

    selectVisualText("hello");
    expect(screen.getByRole("button", { name: "Bold" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(source()).toBe("hello");
  });

  it("removes a style from only the selected part", () => {
    render(<Harness initial="<b>hello world</b>" />);
    selectVisualText("world");
    fireEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(source()).toBe("<b>hello </b>world");
  });

  it("preserves selection while a link dialog is focused and can edit or remove the URL", () => {
    render(<Harness initial="website" />);
    selectVisualText("website");
    fireEvent.click(screen.getByRole("button", { name: "Text link" }));
    const url = screen.getByLabelText("Web URL");
    fireEvent.change(url, { target: { value: "https://example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(source()).toBe('<a href="https://example.com">website</a>');

    selectVisualText("website");
    fireEvent.click(screen.getByRole("button", { name: "Text link" }));
    expect(screen.getByLabelText("Web URL")).toHaveValue("https://example.com");
    fireEvent.click(screen.getByRole("button", { name: "Remove formatting" }));
    expect(source()).toBe("website");
  });

  it("offers distinct mention, code block, expandable quote, custom emoji, and date-time actions in More", () => {
    render(<Harness initial="selected" />);
    selectVisualText("selected");
    fireEvent.click(screen.getByRole("button", { name: "More formatting" }));
    for (const name of ["Mention user by ID", "Code block", "Expandable quote", "Custom emoji", "Dynamic date and time"]) {
      expect(screen.getByRole("menuitemcheckbox", { name })).toBeInTheDocument();
    }
  });

  it("creates a user mention through its separate dialog", () => {
    render(<Harness initial="Ada" />);
    selectVisualText("Ada");
    fireEvent.click(screen.getByRole("button", { name: "More formatting" }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Mention user by ID" }));
    fireEvent.change(screen.getByLabelText("Telegram user ID"), { target: { value: "123456789" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(source()).toBe('<a href="tg://user?id=123456789">Ada</a>');
  });

  it("creates a syntax-highlighted code block", () => {
    render(<Harness initial={"print('ok')"} />);
    selectVisualText("print('ok')");
    fireEvent.click(screen.getByRole("button", { name: "More formatting" }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Code block" }));
    fireEvent.change(screen.getByLabelText(/Syntax language/), { target: { value: "python" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(source()).toBe('<pre><code class="language-python">print(\'ok\')</code></pre>');
  });

  it("creates custom emoji and exposes the bot capability notice", () => {
    render(<Harness initial="🙂" />);
    selectVisualText("🙂");
    fireEvent.click(screen.getByRole("button", { name: "More formatting" }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Custom emoji" }));
    expect(screen.getByText(/Telegram Premium/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Custom emoji ID"), { target: { value: "5368324170671202286" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(source()).toBe('<tg-emoji emoji-id="5368324170671202286">🙂</tg-emoji>');
  });

  it("creates a dynamic date-time entity with a live preview and preserved fallback", () => {
    render(<Harness initial="Meeting time" />);
    selectVisualText("Meeting time");
    fireEvent.click(screen.getByRole("button", { name: "More formatting" }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Dynamic date and time" }));
    fireEvent.change(screen.getByLabelText("Date and time"), { target: { value: "2030-01-02T12:30" } });
    fireEvent.change(screen.getByLabelText("Display format"), { target: { value: "wDt" } });
    expect(screen.getAllByText("Preview")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(source()).toMatch(/^<tg-time unix="\d+" format="wDt">Meeting time<\/tg-time>$/);
    expect(screen.getByLabelText(/Dynamic date and time:/)).toBeInTheDocument();
  });

  it("renders expandable quotes distinctly and preserves their canonical attribute", () => {
    render(<Harness initial="Long details" />);
    selectVisualText("Long details");
    fireEvent.click(screen.getByRole("button", { name: "More formatting" }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Expandable quote" }));
    expect(source()).toBe("<blockquote expandable>Long details</blockquote>");
    expect(screen.getByLabelText("Expandable quote")).toBeInTheDocument();
  });

  it("normalizes Source aliases when returning to Visual", () => {
    render(<Harness initial="<strong>hello</strong>" />);
    fireEvent.click(screen.getByRole("tab", { name: "Source" }));
    fireEvent.click(screen.getByRole("tab", { name: "Visual" }));
    expect(source()).toBe("<b>hello</b>");
    expect(screen.getByRole("textbox", { name: "Visual message content" }).querySelector("b")).not.toBeNull();
  });
});

describe("Telegram Desktop hotkeys", () => {
  it.each([
    ["KeyB", false, "<b>hello</b>"],
    ["KeyI", false, "<i>hello</i>"],
    ["KeyU", false, "<u>hello</u>"],
    ["KeyX", true, "<s>hello</s>"],
    ["KeyM", true, "<code>hello</code>"],
    ["KeyP", true, "<tg-spoiler>hello</tg-spoiler>"],
    ["Period", true, "<blockquote>hello</blockquote>"],
  ])("handles %s only inside Visual mode", (code, shiftKey, expected) => {
    render(<Harness initial="hello" />);
    const editor = selectVisualText("hello");
    const event = createKeyEvent(code, shiftKey);
    fireEvent(editor, event);
    expect(event.defaultPrevented).toBe(true);
    expect(source()).toBe(expected);
  });

  it("opens the link dialog with Ctrl+K", () => {
    render(<Harness initial="hello" />);
    const editor = selectVisualText("hello");
    fireEvent(editor, createKeyEvent("KeyK", false));
    expect(screen.getByRole("dialog", { name: "Text link" })).toBeInTheDocument();
  });

  it("clears nested formatting with Ctrl+Shift+N", () => {
    render(<Harness initial="<b><i><u>hello</u></i></b>" />);
    const editor = selectVisualText("hello");
    fireEvent(editor, createKeyEvent("KeyN", true));
    expect(source()).toBe("hello");
  });
});

function selectVisualText(value: string): HTMLElement {
  const editor = screen.getByRole("textbox", { name: "Visual message content" });
  fireEvent.focus(editor);
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
  let textNode: Text | null = null;
  while (walker.nextNode()) {
    const candidate = walker.currentNode as Text;
    if (candidate.data.includes(value)) {
      textNode = candidate;
      break;
    }
  }
  if (!textNode) throw new Error(`Text not found in Visual editor: ${value}`);
  const start = textNode.data.indexOf(value);
  const range = document.createRange();
  range.setStart(textNode, start);
  range.setEnd(textNode, start + value.length);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
  fireEvent(document, new Event("selectionchange"));
  return editor;
}

function createKeyEvent(code: string, shiftKey: boolean): KeyboardEvent {
  return new KeyboardEvent("keydown", {
    bubbles: true,
    cancelable: true,
    code,
    key: code === "Period" ? "." : code.replace("Key", "").toLowerCase(),
    ctrlKey: true,
    shiftKey,
  });
}

function source(): string {
  return screen.getByTestId("source-value").textContent ?? "";
}
