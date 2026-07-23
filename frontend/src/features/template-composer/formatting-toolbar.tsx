import { useState, type CSSProperties, type MouseEvent as ReactMouseEvent } from "react";

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
          <span aria-hidden="true">Tx</span>
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
  if (action.kind === "link") return <LinkIcon />;
  if (action.kind === "inline-code") return <span className="format-toolbar__code-glyph" aria-hidden="true">&lt;/&gt;</span>;
  if (action.kind === "mention") return <span className="format-more-menu__glyph" aria-hidden="true">@</span>;
  if (action.kind === "code-block") return <span className="format-more-menu__glyph" aria-hidden="true">{`{ }`}</span>;
  if (action.kind === "quote" || action.kind === "expandable-quote") return <QuoteIcon expandable={action.kind === "expandable-quote"} />;
  if (action.kind === "custom-emoji") return <EmojiIcon />;
  if (action.kind === "date-time") return <ClockIcon />;
  return <span className="format-toolbar__text-glyph" aria-hidden="true">{action.shortLabel}</span>;
}

function hotkeyLabel(action: TelegramFormattingAction): string {
  if (!action.hotkey) return "";
  const key = action.hotkey.code === "Period" ? "." : action.hotkey.code.replace("Key", "");
  return ` (${navigator.platform.toLowerCase().includes("mac") ? "Cmd" : "Ctrl"}+${action.hotkey.shift ? "Shift+" : ""}${key})`;
}

function MoreIcon() {
  return <svg viewBox="0 0 18 18" aria-hidden="true"><circle cx="4" cy="9" r="1" /><circle cx="9" cy="9" r="1" /><circle cx="14" cy="9" r="1" /></svg>;
}

function LinkIcon() {
  return <svg viewBox="0 0 18 18" aria-hidden="true"><path d="M7.1 11.4 5.7 12.8a2.5 2.5 0 0 1-3.5-3.6l2.2-2.1A2.5 2.5 0 0 1 8 7" /><path d="m10.9 6.6 1.4-1.4a2.5 2.5 0 1 1 3.5 3.6l-2.2 2.1A2.5 2.5 0 0 1 10 11" /><path d="m6.7 9.3 4.6-.6" /></svg>;
}

function QuoteIcon({ expandable }: { expandable: boolean }) {
  return <svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4.5 5.5h3v3h-3v-3Zm6 0h3v3h-3v-3ZM4.5 8.5c0 2.1-.7 3.3-2 4M10.5 8.5c0 2.1-.7 3.3-2 4" />{expandable ? <path d="m13 12 1.5 1.5L16 12" /> : null}</svg>;
}

function EmojiIcon() {
  return <svg viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="6.3" /><path d="M6.5 7h.1M11.4 7h.1M6.3 10.2c.8 1.4 1.7 2 2.7 2s1.9-.6 2.7-2" /></svg>;
}

function ClockIcon() {
  return <svg viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="6.2" /><path d="M9 5.5V9l2.6 1.5" /></svg>;
}

function CheckIcon() {
  return <svg className="format-more-menu__check" viewBox="0 0 18 18" aria-hidden="true"><path d="m4.5 9 3 3 6-6" /></svg>;
}
