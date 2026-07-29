import { useState, type CSSProperties, type MouseEvent as ReactMouseEvent } from "react";
import {
  AtSign,
  Bold,
  Braces,
  Check,
  Clock3,
  CodeXml,
  Ellipsis,
  EyeOff,
  Italic,
  Link2,
  ListCollapse,
  Quote,
  RemoveFormatting,
  Smile,
  Strikethrough,
  Underline,
} from "lucide-react";

import {
  MORE_FORMATTING_ACTIONS,
  PRIMARY_FORMATTING_ACTIONS,
  type TelegramFormattingAction,
  type TelegramFormatKind,
} from "./telegram-formatting";

export type FormattingToolbarState = {
  position: { left: number; top: number };
  activeFormats: ReadonlySet<TelegramFormatKind>;
  multiline: boolean;
  codeLocked: boolean;
};

export function FormattingToolbar({
  state,
  onAction,
  onClear,
}: {
  state: FormattingToolbarState;
  onAction(action: TelegramFormattingAction): void;
  onClear(): void;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const style = {
    "--format-toolbar-left": `${state.position.left}px`,
    "--format-toolbar-top": `${state.position.top}px`,
  } as CSSProperties;

  const keepSelection = (event: ReactMouseEvent) => event.preventDefault();

  return (
    <div
      className="format-toolbar"
      role="toolbar"
      aria-label="Telegram text formatting"
      style={style}
      onMouseDown={keepSelection}
    >
      <div className="format-toolbar__primary">
        {PRIMARY_FORMATTING_ACTIONS.map((action) => (
          <FormatButton
            action={action}
            active={state.activeFormats.has(action.kind)}
            disabled={state.codeLocked && action.kind !== "inline-code"}
            key={action.kind}
            onClick={() => onAction(action)}
          />
        ))}
        <span className="format-toolbar__separator" aria-hidden="true" />
        <button
          type="button"
          className="format-toolbar__button format-toolbar__button--clear"
          aria-label="Clear formatting"
          title="Clear formatting (Ctrl+Shift+N)"
          onClick={onClear}
        >
          <RemoveFormatting aria-hidden="true" />
        </button>
        <div className="format-toolbar__more-wrap">
          <button
            type="button"
            className={moreOpen ? "format-toolbar__button format-toolbar__button--more is-active" : "format-toolbar__button format-toolbar__button--more"}
            aria-label="More formatting"
            aria-expanded={moreOpen}
            title="More formatting"
            onClick={() => setMoreOpen((open) => !open)}
          >
            <MoreIcon />
          </button>
          {moreOpen ? (
            <div className="format-more-menu" role="menu" aria-label="More Telegram formatting">
              {state.multiline ? <p className="format-more-menu__hint">Multiple lines selected — a code block may fit better than inline code.</p> : null}
              {MORE_FORMATTING_ACTIONS.map((action) => (
                <button
                  type="button"
                  role="menuitemcheckbox"
                  aria-checked={state.activeFormats.has(action.kind)}
                  className={state.activeFormats.has(action.kind) ? "format-more-menu__item is-active" : "format-more-menu__item"}
                  key={action.kind}
                  onClick={() => {
                    setMoreOpen(false);
                    onAction(action);
                  }}
                >
                  <FormattingGlyph action={action} />
                  <span>{action.label}</span>
                  {state.activeFormats.has(action.kind) ? <CheckIcon /> : null}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function FormatButton({
  action,
  active,
  disabled,
  onClick,
}: {
  action: TelegramFormattingAction;
  active: boolean;
  disabled: boolean;
  onClick(): void;
}) {
  return (
    <button
      type="button"
      className={active ? `format-toolbar__button format-toolbar__button--${action.kind} is-active` : `format-toolbar__button format-toolbar__button--${action.kind}`}
      aria-label={action.label}
      aria-pressed={active}
      disabled={disabled}
      title={`${action.label}${hotkeyLabel(action)}`}
      onClick={onClick}
    >
      <FormattingGlyph action={action} />
    </button>
  );
}

function FormattingGlyph({ action }: { action: TelegramFormattingAction }) {
  if (action.kind === "bold") return <Bold aria-hidden="true" />;
  if (action.kind === "italic") return <Italic aria-hidden="true" />;
  if (action.kind === "underline") return <Underline aria-hidden="true" />;
  if (action.kind === "strikethrough") return <Strikethrough aria-hidden="true" />;
  if (action.kind === "spoiler") return <EyeOff aria-hidden="true" />;
  if (action.kind === "link") return <LinkIcon />;
  if (action.kind === "inline-code") return <CodeXml aria-hidden="true" />;
  if (action.kind === "mention") return <AtSign aria-hidden="true" />;
  if (action.kind === "code-block") return <Braces aria-hidden="true" />;
  if (action.kind === "quote" || action.kind === "expandable-quote") return <QuoteIcon expandable={action.kind === "expandable-quote"} />;
  if (action.kind === "custom-emoji") return <EmojiIcon />;
  if (action.kind === "date-time") return <ClockIcon />;
  return null;
}

function hotkeyLabel(action: TelegramFormattingAction): string {
  if (!action.hotkey) return "";
  const key = action.hotkey.code === "Period" ? "." : action.hotkey.code.replace("Key", "");
  return ` (${navigator.platform.toLowerCase().includes("mac") ? "Cmd" : "Ctrl"}+${action.hotkey.shift ? "Shift+" : ""}${key})`;
}

function MoreIcon() {
  return <Ellipsis aria-hidden="true" />;
}

function LinkIcon() {
  return <Link2 aria-hidden="true" />;
}

function QuoteIcon({ expandable }: { expandable: boolean }) {
  return expandable ? <ListCollapse aria-hidden="true" /> : <Quote aria-hidden="true" />;
}

function EmojiIcon() {
  return <Smile aria-hidden="true" />;
}

function ClockIcon() {
  return <Clock3 aria-hidden="true" />;
}

function CheckIcon() {
  return <Check className="format-more-menu__check" aria-hidden="true" />;
}
