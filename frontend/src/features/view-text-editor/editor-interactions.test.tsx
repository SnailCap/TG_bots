import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CustomEmojiNode, ExpandableBlockquote, LegacyTemplateNode, SpoilerMark, VariableNode } from "./extensions";
import { LinkEditorPopover } from "./EditorPopovers";
import { RichTextToolbar } from "./RichTextToolbar";
import { SlashCommandMenu } from "./SlashCommandMenu";

const editors: Editor[] = [];

function createEditor(content = "<p>Hello</p>") {
  const editor = new Editor({
    element: document.createElement("div"),
    extensions: [StarterKit, SpoilerMark, VariableNode, CustomEmojiNode, ExpandableBlockquote, LegacyTemplateNode],
    content,
  });
  editors.push(editor);
  return editor;
}

afterEach(() => {
  act(() => editors.splice(0).forEach((editor) => editor.destroy()));
});

describe("rich editor toolbar", () => {
  it("applies formatting to the selected document range", () => {
    const editor = createEditor();
    render(
      <RichTextToolbar
        editor={editor}
        variablePickerOpen={false}
        emojiPickerOpen={false}
        linkEditorOpen={false}
        onToggleVariablePicker={() => undefined}
        onToggleEmojiPicker={() => undefined}
        onToggleLinkEditor={() => undefined}
      />,
    );

    act(() => editor.commands.setTextSelection({ from: 1, to: 6 }));
    fireEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(editor.getJSON().content?.[0].content?.[0].marks).toEqual([{ type: "bold" }]);
  });

  it("applies and clears formatting on an atomic variable selection", () => {
    const editor = createEditor({
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "variable", attrs: { fieldId: "core.user.first_name", path: "user.first_name", source: "{{ user.first_name }}" } }] }],
    } as never);
    render(
      <RichTextToolbar
        editor={editor}
        variablePickerOpen={false}
        emojiPickerOpen={false}
        linkEditorOpen={false}
        onToggleVariablePicker={() => undefined}
        onToggleEmojiPicker={() => undefined}
        onToggleLinkEditor={() => undefined}
      />,
    );

    act(() => editor.commands.setNodeSelection(1));
    fireEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(editor.getJSON().content?.[0].content?.[0].marks).toEqual([{ type: "bold" }]);

    fireEvent.click(screen.getByRole("button", { name: "Clear formatting" }));
    expect(editor.getJSON().content?.[0].content?.[0].marks).toBeUndefined();

    fireEvent.keyDown(editor.view.dom, { key: "i", code: "KeyI", ctrlKey: true });
    expect(editor.getJSON().content?.[0].content?.[0].marks).toEqual([{ type: "italic" }]);
  });

  it("applies a validated text link to an atomic variable", () => {
    const editor = createEditor({
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "variable", attrs: { fieldId: "core.user.first_name", path: "user.first_name", source: "{{ user.first_name }}" } }] }],
    } as never);
    const onClose = vi.fn();
    act(() => editor.commands.setNodeSelection(1));
    render(<LinkEditorPopover editor={editor} open onClose={onClose} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Web address" }), { target: { value: "https://example.com/user" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(editor.getJSON().content?.[0].content?.[0].marks).toEqual([
      expect.objectContaining({ type: "link", attrs: expect.objectContaining({ href: "https://example.com/user" }) }),
    ]);
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("slash commands", () => {
  it("offers the five MVP commands and opens the existing variable picker", () => {
    const editor = createEditor("<p></p>");
    const onOpenVariablePicker = vi.fn();
    render(<SlashCommandMenu editor={editor} onOpenVariablePicker={onOpenVariablePicker} onOpenEmojiPicker={() => undefined} />);

    act(() => { editor.commands.insertContent("/var"); });
    expect(screen.getByRole("listbox", { name: "Slash commands" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /Variable/ }));
    expect(onOpenVariablePicker).toHaveBeenCalledOnce();
    expect(editor.getText()).toBe("");

    act(() => { editor.commands.insertContent("/"); });
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      expect.stringContaining("Variable"),
      expect.stringContaining("Emoji"),
      expect.stringContaining("Quote"),
      expect.stringContaining("Expandable quote"),
      expect.stringContaining("Code block"),
    ]);
  });

  it("executes the active command from the keyboard", () => {
    const editor = createEditor("<p></p>");
    render(<SlashCommandMenu editor={editor} onOpenVariablePicker={() => undefined} onOpenEmojiPicker={() => undefined} />);

    act(() => { editor.commands.insertContent("/quo"); });
    fireEvent.keyDown(editor.view.dom, { key: "Enter" });

    expect(editor.isActive("blockquote")).toBe(true);
    expect(editor.getText()).not.toContain("/quo");
  });
});
