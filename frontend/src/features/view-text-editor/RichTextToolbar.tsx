import type { Editor } from "@tiptap/core";
import { useEditorState } from "@tiptap/react";
import {
  Bold,
  Braces,
  Code2,
  EyeOff,
  Italic,
  Link2,
  ListCollapse,
  Quote,
  Redo2,
  RemoveFormatting,
  Smile,
  Strikethrough,
  Underline,
  Undo2,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import { clearInlineFormatting, isInlineMarkActive, toggleInlineMark } from "./inline-atom-marks";

type ToolbarButton = {
  id: string;
  label: string;
  shortcut?: string;
  icon: LucideIcon;
  active?: boolean;
  disabled?: boolean;
  separatorBefore?: boolean;
  run(): void;
};

const INACTIVE_TOOLBAR_STATE = {
  canUndo: false,
  canRedo: false,
  bold: false,
  italic: false,
  underline: false,
  strike: false,
  spoiler: false,
  code: false,
  link: false,
  quote: false,
  expandableQuote: false,
  codeBlock: false,
};

export function RichTextToolbar({
  editor,
  variablePickerOpen,
  emojiPickerOpen,
  linkEditorOpen,
  onToggleVariablePicker,
  onToggleEmojiPicker,
  onToggleLinkEditor,
}: {
  editor: Editor;
  variablePickerOpen: boolean;
  emojiPickerOpen: boolean;
  linkEditorOpen: boolean;
  onToggleVariablePicker(): void;
  onToggleEmojiPicker(): void;
  onToggleLinkEditor(): void;
}) {
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => {
      if (current.isDestroyed) return INACTIVE_TOOLBAR_STATE;
      try {
        return {
          canUndo: current.can().chain().undo().run(),
          canRedo: current.can().chain().redo().run(),
          bold: isInlineMarkActive(current, "bold"),
          italic: isInlineMarkActive(current, "italic"),
          underline: isInlineMarkActive(current, "underline"),
          strike: isInlineMarkActive(current, "strike"),
          spoiler: isInlineMarkActive(current, "spoiler"),
          code: isInlineMarkActive(current, "code"),
          link: isInlineMarkActive(current, "link"),
          quote: current.isActive("blockquote"),
          expandableQuote: current.isActive("expandableBlockquote"),
          codeBlock: current.isActive("codeBlock"),
        };
      } catch {
        // Tiptap can notify one final time while its React node view is tearing down.
        return INACTIVE_TOOLBAR_STATE;
      }
    },
  });

  const buttons: ToolbarButton[] = [
    { id: "undo", label: "Undo", shortcut: "Ctrl+Z", icon: Undo2, disabled: !state.canUndo, run: () => { editor.chain().focus().undo().run(); } },
    { id: "redo", label: "Redo", shortcut: "Ctrl+Shift+Z", icon: Redo2, disabled: !state.canRedo, run: () => { editor.chain().focus().redo().run(); } },
    { id: "bold", label: "Bold", shortcut: "Ctrl+B", icon: Bold, active: state.bold, separatorBefore: true, run: () => { toggleInlineMark(editor, "bold"); } },
    { id: "italic", label: "Italic", shortcut: "Ctrl+I", icon: Italic, active: state.italic, run: () => { toggleInlineMark(editor, "italic"); } },
    { id: "underline", label: "Underline", shortcut: "Ctrl+U", icon: Underline, active: state.underline, run: () => { toggleInlineMark(editor, "underline"); } },
    { id: "strike", label: "Strikethrough", icon: Strikethrough, active: state.strike, run: () => { toggleInlineMark(editor, "strike"); } },
    { id: "spoiler", label: "Spoiler", shortcut: "Ctrl+Shift+P", icon: EyeOff, active: state.spoiler, run: () => { toggleInlineMark(editor, "spoiler"); } },
    { id: "code", label: "Inline code", icon: Code2, active: state.code, run: () => { toggleInlineMark(editor, "code"); } },
    { id: "link", label: "Text link", shortcut: "Ctrl+K", icon: Link2, active: state.link || linkEditorOpen, run: onToggleLinkEditor },
    { id: "quote", label: "Quote", icon: Quote, active: state.quote, separatorBefore: true, run: () => toggleQuote(editor, "blockquote") },
    { id: "expandable-quote", label: "Expandable quote", icon: ListCollapse, active: state.expandableQuote, run: () => toggleQuote(editor, "expandableBlockquote") },
    { id: "code-block", label: "Code block", icon: Braces, active: state.codeBlock, run: () => { editor.chain().focus().toggleCodeBlock().run(); } },
    { id: "variable", label: "Insert variable", icon: UserRound, active: variablePickerOpen, separatorBefore: true, run: onToggleVariablePicker },
    { id: "emoji", label: "Insert emoji", icon: Smile, active: emojiPickerOpen, run: onToggleEmojiPicker },
    { id: "clear", label: "Clear formatting", icon: RemoveFormatting, separatorBefore: true, run: () => { clearInlineFormatting(editor); } },
  ];

  return (
    <div className="view-rich-toolbar" role="toolbar" aria-label="Message formatting">
      {buttons.map(({ id, label, shortcut, icon: Icon, active, disabled, separatorBefore, run }) => (
        <span className={separatorBefore ? "view-rich-toolbar__slot view-rich-toolbar__slot--separated" : "view-rich-toolbar__slot"} key={id}>
          <button
            type="button"
            className={active ? "view-rich-toolbar__button is-active" : "view-rich-toolbar__button"}
            aria-label={label}
            aria-pressed={active ?? undefined}
            disabled={disabled}
            title={`${label}${shortcut ? ` (${shortcut})` : ""}`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={run}
          >
            <Icon aria-hidden="true" />
          </button>
        </span>
      ))}
    </div>
  );
}

function toggleQuote(editor: Editor, target: "blockquote" | "expandableBlockquote") {
  const other = target === "blockquote" ? "expandableBlockquote" : "blockquote";
  if (editor.isActive(other)) {
    editor.chain().focus().lift(other).toggleWrap(target).run();
    return;
  }
  editor.chain().focus().toggleWrap(target).run();
}
