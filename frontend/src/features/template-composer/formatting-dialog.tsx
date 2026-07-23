import { useEffect, useId, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent, type RefObject } from "react";

import {
  DATE_TIME_FORMAT_OPTIONS,
  isSafeWebUrl,
  isValidCustomEmojiFallback,
  isValidTelegramUserId,
  renderTelegramDateTime,
  type TelegramFormatKind,
} from "./telegram-formatting";

export type FormattingDialogState = {
  kind: Extract<TelegramFormatKind, "link" | "mention" | "code-block" | "custom-emoji" | "date-time">;
  selectedText: string;
  existing?: {
    href?: string;
    userId?: string;
    language?: string;
    emojiId?: string;
    unix?: number;
    dateTimeFormat?: string;
    fallback?: string;
  };
};

export type FormattingDialogResult =
  | { kind: "link"; href: string }
  | { kind: "mention"; userId: string }
  | { kind: "code-block"; language?: string }
  | { kind: "custom-emoji"; emojiId: string; fallback: string }
  | { kind: "date-time"; unix: number; dateTimeFormat: string; fallback: string };

export function FormattingDialog({
  dialog,
  onApply,
  onRemove,
  onCancel,
  position,
}: {
  dialog: FormattingDialogState;
  onApply(result: FormattingDialogResult): void;
  onRemove(): void;
  onCancel(): void;
  position: { left: number; top: number };
}) {
  const titleId = useId();
  const initial = initialValues(dialog);
  const [primary, setPrimary] = useState(initial.primary);
  const [secondary, setSecondary] = useState(initial.secondary);
  const [tertiary, setTertiary] = useState(initial.tertiary);
  const [error, setError] = useState("");
  const firstFieldRef = useRef<HTMLInputElement | HTMLSelectElement>(null);

  useEffect(() => {
    firstFieldRef.current?.focus();
    if (firstFieldRef.current instanceof HTMLInputElement) firstFieldRef.current.select();
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    onCancel();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const issue = validate(dialog.kind, primary, secondary, tertiary);
    if (issue) {
      setError(issue);
      return;
    }
    if (dialog.kind === "link") onApply({ kind: "link", href: primary.trim() });
    if (dialog.kind === "mention") onApply({ kind: "mention", userId: primary.trim() });
    if (dialog.kind === "code-block") onApply({ kind: "code-block", language: primary.trim() || undefined });
    if (dialog.kind === "custom-emoji") onApply({ kind: "custom-emoji", emojiId: primary.trim(), fallback: secondary.trim() });
    if (dialog.kind === "date-time") {
      onApply({
        kind: "date-time",
        unix: Math.floor(new Date(primary).getTime() / 1000),
        dateTimeFormat: secondary,
        fallback: tertiary.trim(),
      });
    }
  };

  const title = dialogTitle(dialog.kind);
  const style = {
    "--format-dialog-left": `${position.left}px`,
    "--format-dialog-top": `${position.top}px`,
  } as CSSProperties;

  return (
    <div className="format-dialog" role="dialog" aria-modal="false" aria-labelledby={titleId} style={style} onKeyDown={handleKeyDown}>
      <header>
        <div>
          <span className="format-dialog__kicker">Telegram HTML</span>
          <h3 id={titleId}>{title}</h3>
        </div>
        <button type="button" className="format-dialog__close" aria-label={`Close ${title.toLowerCase()}`} onClick={onCancel}>×</button>
      </header>
      <form onSubmit={submit}>
        {dialog.kind === "link" ? (
          <label>
            <span>Web URL</span>
            <input ref={firstFieldRef as RefObject<HTMLInputElement>} aria-label="Web URL" type="url" value={primary} placeholder="https://example.com" onChange={(event) => setPrimary(event.target.value)} />
            <small>Only http:// and https:// links are allowed.</small>
          </label>
        ) : null}
        {dialog.kind === "mention" ? (
          <label>
            <span>Telegram user ID</span>
            <input ref={firstFieldRef as RefObject<HTMLInputElement>} aria-label="Telegram user ID" inputMode="numeric" value={primary} placeholder="123456789" onChange={(event) => setPrimary(event.target.value)} />
            <small>Creates a <code>tg://user</code> mention, not a web link.</small>
          </label>
        ) : null}
        {dialog.kind === "code-block" ? (
          <label>
            <span>Syntax language <em>optional</em></span>
            <input ref={firstFieldRef as RefObject<HTMLInputElement>} aria-label="Syntax language" list="telegram-code-languages" value={primary} placeholder="python" onChange={(event) => setPrimary(event.target.value)} />
            <datalist id="telegram-code-languages">
              {["bash", "c", "cpp", "css", "go", "html", "javascript", "json", "python", "rust", "sql", "typescript", "xml", "yaml"].map((language) => <option value={language} key={language} />)}
            </datalist>
            <small>Telegram uses this value for syntax highlighting.</small>
          </label>
        ) : null}
        {dialog.kind === "custom-emoji" ? (
          <>
            <label>
              <span>Custom emoji ID</span>
              <input ref={firstFieldRef as RefObject<HTMLInputElement>} aria-label="Custom emoji ID" inputMode="numeric" value={primary} placeholder="5368324170671202286" onChange={(event) => setPrimary(event.target.value)} />
            </label>
            <label>
              <span>Fallback emoji</span>
              <input aria-label="Fallback emoji" value={secondary} placeholder="🙂" onChange={(event) => setSecondary(event.target.value)} />
            </label>
            <p className="format-dialog__notice">Availability depends on the bot owner’s Telegram Premium status or purchased Fragment usernames. The fallback is always kept.</p>
          </>
        ) : null}
        {dialog.kind === "date-time" ? (
          <>
            <label>
              <span>Date and time</span>
              <input ref={firstFieldRef as RefObject<HTMLInputElement>} aria-label="Date and time" type="datetime-local" value={primary} onChange={(event) => setPrimary(event.target.value)} />
            </label>
            <label>
              <span>Display format</span>
              <select aria-label="Display format" value={secondary} onChange={(event) => setSecondary(event.target.value)}>
                {DATE_TIME_FORMAT_OPTIONS.map((option) => <option value={option.value} key={option.value || "fallback"}>{option.label}</option>)}
              </select>
            </label>
            <label>
              <span>Fallback text</span>
              <input aria-label="Fallback text" value={tertiary} placeholder="Tomorrow at 22:45" onChange={(event) => setTertiary(event.target.value)} />
            </label>
            <div className="format-dialog__preview">
              <span>Preview</span>
              <strong>{datePreview(primary, secondary, tertiary)}</strong>
            </div>
          </>
        ) : null}
        {error ? <p className="format-dialog__error" role="alert">{error}</p> : null}
        <footer>
          {dialog.existing ? <button type="button" className="format-dialog__remove" onClick={onRemove}>Remove formatting</button> : <span />}
          <div>
            <button type="button" className="button--quiet" onClick={onCancel}>Cancel</button>
            <button type="submit">Apply</button>
          </div>
        </footer>
      </form>
    </div>
  );
}

function initialValues(dialog: FormattingDialogState): { primary: string; secondary: string; tertiary: string } {
  if (dialog.kind === "link") return { primary: dialog.existing?.href ?? "https://", secondary: "", tertiary: "" };
  if (dialog.kind === "mention") return { primary: dialog.existing?.userId ?? "", secondary: "", tertiary: "" };
  if (dialog.kind === "code-block") return { primary: dialog.existing?.language ?? "", secondary: "", tertiary: "" };
  if (dialog.kind === "custom-emoji") {
    return {
      primary: dialog.existing?.emojiId ?? "",
      secondary: dialog.existing?.fallback ?? dialog.selectedText.trim(),
      tertiary: "",
    };
  }
  const unix = dialog.existing?.unix ?? Math.floor(Date.now() / 1000) + 3600;
  return {
    primary: toLocalDateTimeValue(unix),
    secondary: dialog.existing?.dateTimeFormat ?? "wDt",
    tertiary: dialog.existing?.fallback ?? dialog.selectedText.trim(),
  };
}

function validate(kind: FormattingDialogState["kind"], primary: string, secondary: string, tertiary: string): string {
  if (kind === "link" && !isSafeWebUrl(primary.trim())) return "Enter a valid http:// or https:// URL.";
  if (kind === "mention" && !isValidTelegramUserId(primary)) return "Enter a numeric Telegram user ID.";
  if (kind === "code-block" && primary && !/^[A-Za-z0-9_+#.-]+$/.test(primary.trim())) return "Use a language identifier such as python, cpp, or typescript.";
  if (kind === "custom-emoji" && !/^\d+$/.test(primary.trim())) return "Enter a numeric custom emoji ID.";
  if (kind === "custom-emoji" && !isValidCustomEmojiFallback(secondary)) return "Fallback must contain exactly one emoji.";
  if (kind === "date-time" && Number.isNaN(new Date(primary).getTime())) return "Choose a valid date and time.";
  if (kind === "date-time" && !tertiary.trim()) return "Add fallback text for clients that cannot render the entity.";
  return "";
}

function dialogTitle(kind: FormattingDialogState["kind"]): string {
  if (kind === "link") return "Text link";
  if (kind === "mention") return "Mention user";
  if (kind === "code-block") return "Code block";
  if (kind === "custom-emoji") return "Custom emoji";
  return "Dynamic date and time";
}

function datePreview(value: string, format: string, fallback: string): string {
  const unix = Math.floor(new Date(value).getTime() / 1000);
  return renderTelegramDateTime(unix, format, fallback || "Fallback text");
}

function toLocalDateTimeValue(unix: number): string {
  const date = new Date(unix * 1000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
