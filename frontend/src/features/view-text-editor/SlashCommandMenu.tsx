import type { Editor } from "@tiptap/core";
import { Braces, ListCollapse, Quote, Smile, UserRound, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

type SlashMatch = {
  from: number;
  to: number;
  query: string;
  left: number;
  top: number;
};

type SlashCommandId = "variable" | "emoji" | "quote" | "expandable-quote" | "code-block";

type SlashCommand = {
  id: SlashCommandId;
  label: string;
  description: string;
  keywords: string;
  icon: LucideIcon;
};

const SLASH_COMMANDS: readonly SlashCommand[] = [
  { id: "variable", label: "Variable", description: "Insert a BotStudio context value", keywords: "context field placeholder", icon: UserRound },
  { id: "emoji", label: "Emoji", description: "Insert Unicode or Telegram custom emoji", keywords: "smile custom", icon: Smile },
  { id: "quote", label: "Quote", description: "Turn this paragraph into a quote", keywords: "blockquote", icon: Quote },
  { id: "expandable-quote", label: "Expandable quote", description: "Create a collapsible Telegram quote", keywords: "collapse blockquote", icon: ListCollapse },
  { id: "code-block", label: "Code block", description: "Create a preformatted code block", keywords: "pre monospace", icon: Braces },
] as const;

export function SlashCommandMenu({
  editor,
  onOpenVariablePicker,
  onOpenEmojiPicker,
}: {
  editor: Editor;
  onOpenVariablePicker(): void;
  onOpenEmojiPicker(): void;
}) {
  const [match, setMatch] = useState<SlashMatch | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const matchRef = useRef<SlashMatch | null>(null);
  const dismissedRef = useRef<string | null>(null);

  const commands = useMemo(() => {
    const query = match?.query.toLocaleLowerCase() ?? "";
    if (!query) return SLASH_COMMANDS;
    return SLASH_COMMANDS.filter((command) => `${command.label} ${command.keywords}`.toLocaleLowerCase().includes(query));
  }, [match?.query]);
  const commandsRef = useRef(commands);
  commandsRef.current = commands;
  matchRef.current = match;

  const runCommand = (command: SlashCommand) => {
    const current = matchRef.current;
    if (!current) return;
    dismissedRef.current = null;
    setMatch(null);

    const chain = editor.chain().focus().deleteRange({ from: current.from, to: current.to });
    if (command.id === "variable") {
      chain.run();
      onOpenVariablePicker();
      return;
    }
    if (command.id === "emoji") {
      chain.run();
      onOpenEmojiPicker();
      return;
    }
    if (command.id === "quote") {
      chain.toggleWrap("blockquote").run();
      return;
    }
    if (command.id === "expandable-quote") {
      chain.toggleWrap("expandableBlockquote").run();
      return;
    }
    chain.toggleCodeBlock().run();
  };
  const runCommandRef = useRef(runCommand);
  runCommandRef.current = runCommand;

  useEffect(() => {
    const update = () => {
      const next = findSlashMatch(editor);
      const key = next ? slashMatchKey(next) : null;
      if (key && key === dismissedRef.current) {
        setMatch(null);
        return;
      }
      if (key !== dismissedRef.current) dismissedRef.current = null;
      setMatch(next);
      setActiveIndex(0);
    };
    editor.on("transaction", update);
    update();
    return () => {
      editor.off("transaction", update);
    };
  }, [editor]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      let editorDom: HTMLElement;
      try {
        editorDom = editor.view.dom;
      } catch {
        return;
      }
      if (target !== editorDom && !editorDom.contains(target)) return;
      const current = matchRef.current;
      if (!current) return;
      const available = commandsRef.current;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        dismissedRef.current = slashMatchKey(current);
        setMatch(null);
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        event.stopPropagation();
        if (available.length === 0) return;
        setActiveIndex((index) => (index + (event.key === "ArrowDown" ? 1 : -1) + available.length) % available.length);
        return;
      }
      if (event.key === "Enter" && available.length > 0) {
        event.preventDefault();
        event.stopPropagation();
        runCommandRef.current(available[Math.min(activeIndex, available.length - 1)]);
      }
    };
    let editorDom: HTMLElement | null = null;
    const attach = () => {
      let next: HTMLElement;
      try {
        next = editor.view.dom;
      } catch {
        return;
      }
      if (next === editorDom) return;
      editorDom?.removeEventListener("keydown", handleKeyDown);
      editorDom = next;
      editorDom.addEventListener("keydown", handleKeyDown);
    };
    attach();
    editor.on("transaction", attach);
    const animationFrame = window.requestAnimationFrame(attach);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      editor.off("transaction", attach);
      editorDom?.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeIndex, editor]);

  if (!match) return null;
  return (
    <div
      className="view-rich-slash-menu"
      role="listbox"
      aria-label="Slash commands"
      style={{ left: match.left, top: match.top }}
    >
      <span className="view-rich-slash-menu__eyebrow">Insert</span>
      {commands.length === 0 ? <p>No matching commands</p> : commands.map((command, index) => {
        const Icon = command.icon;
        return (
          <button
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            className={index === activeIndex ? "is-active" : undefined}
            key={command.id}
            onMouseEnter={() => setActiveIndex(index)}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => runCommand(command)}
          >
            <Icon aria-hidden="true" />
            <span><strong>{command.label}</strong><small>{command.description}</small></span>
          </button>
        );
      })}
    </div>
  );
}

function findSlashMatch(editor: Editor): SlashMatch | null {
  const { selection } = editor.state;
  if (!selection.empty || !selection.$from.parent.isTextblock) return null;
  const textBefore = selection.$from.parent.textBetween(0, selection.$from.parentOffset, undefined, " ");
  const match = /(?:^|\s)\/([^\s/]*)$/.exec(textBefore);
  if (!match) return null;
  const query = match[1] ?? "";
  const from = selection.from - query.length - 1;
  const position = menuPosition(editor, selection.from);
  return { from, to: selection.from, query, ...position };
}

function menuPosition(editor: Editor, position: number): { left: number; top: number } {
  try {
    const coordinates = editor.view.coordsAtPos(position);
    const menuWidth = 304;
    const estimatedHeight = 286;
    const left = Math.max(8, Math.min(coordinates.left, window.innerWidth - menuWidth - 8));
    const top = coordinates.bottom + estimatedHeight <= window.innerHeight
      ? coordinates.bottom + 6
      : Math.max(8, coordinates.top - estimatedHeight - 6);
    return { left, top };
  } catch {
    return { left: 24, top: 96 };
  }
}

function slashMatchKey(match: Pick<SlashMatch, "from" | "to" | "query">): string {
  return `${match.from}:${match.to}:${match.query}`;
}
