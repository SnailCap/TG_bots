export type TelegramFormatKind =
  | "bold"
  | "italic"
  | "underline"
  | "strikethrough"
  | "spoiler"
  | "link"
  | "mention"
  | "inline-code"
  | "code-block"
  | "quote"
  | "expandable-quote"
  | "custom-emoji"
  | "date-time";

export type TelegramFormatGroup = "inline" | "block" | "special";

export type TelegramFormattingAction = {
  kind: TelegramFormatKind;
  label: string;
  shortLabel: string;
  tag: string;
  aliases: readonly string[];
  group: TelegramFormatGroup;
  toolbar: "primary" | "more";
  hotkey?: {
    code: string;
    shift?: boolean;
  };
  dialog?: "link" | "mention" | "code-block" | "custom-emoji" | "date-time";
};

export const TELEGRAM_FORMATTING_ACTIONS = [
  {
    kind: "bold",
    label: "Bold",
    shortLabel: "B",
    tag: "b",
    aliases: ["b", "strong"],
    group: "inline",
    toolbar: "primary",
    hotkey: { code: "KeyB" },
  },
  {
    kind: "italic",
    label: "Italic",
    shortLabel: "I",
    tag: "i",
    aliases: ["i", "em"],
    group: "inline",
    toolbar: "primary",
    hotkey: { code: "KeyI" },
  },
  {
    kind: "underline",
    label: "Underline",
    shortLabel: "U",
    tag: "u",
    aliases: ["u", "ins"],
    group: "inline",
    toolbar: "primary",
    hotkey: { code: "KeyU" },
  },
  {
    kind: "strikethrough",
    label: "Strikethrough",
    shortLabel: "S",
    tag: "s",
    aliases: ["s", "strike", "del"],
    group: "inline",
    toolbar: "primary",
    hotkey: { code: "KeyX", shift: true },
  },
  {
    kind: "spoiler",
    label: "Spoiler",
    shortLabel: "SP",
    tag: "tg-spoiler",
    aliases: ["tg-spoiler"],
    group: "inline",
    toolbar: "primary",
    hotkey: { code: "KeyP", shift: true },
  },
  {
    kind: "link",
    label: "Text link",
    shortLabel: "Link",
    tag: "a",
    aliases: ["a"],
    group: "special",
    toolbar: "primary",
    hotkey: { code: "KeyK" },
    dialog: "link",
  },
  {
    kind: "inline-code",
    label: "Inline code",
    shortLabel: "</>",
    tag: "code",
    aliases: ["code"],
    group: "inline",
    toolbar: "primary",
    hotkey: { code: "KeyM", shift: true },
  },
  {
    kind: "mention",
    label: "Mention user by ID",
    shortLabel: "Mention",
    tag: "a",
    aliases: [],
    group: "special",
    toolbar: "more",
    dialog: "mention",
  },
  {
    kind: "code-block",
    label: "Code block",
    shortLabel: "Code block",
    tag: "pre",
    aliases: ["pre"],
    group: "block",
    toolbar: "more",
    dialog: "code-block",
  },
  {
    kind: "quote",
    label: "Block quote",
    shortLabel: "Quote",
    tag: "blockquote",
    aliases: ["blockquote"],
    group: "block",
    toolbar: "more",
    hotkey: { code: "Period", shift: true },
  },
  {
    kind: "expandable-quote",
    label: "Expandable quote",
    shortLabel: "Expandable quote",
    tag: "blockquote",
    aliases: [],
    group: "block",
    toolbar: "more",
  },
  {
    kind: "custom-emoji",
    label: "Custom emoji",
    shortLabel: "Custom emoji",
    tag: "tg-emoji",
    aliases: ["tg-emoji"],
    group: "special",
    toolbar: "more",
    dialog: "custom-emoji",
  },
  {
    kind: "date-time",
    label: "Dynamic date and time",
    shortLabel: "Date & time",
    tag: "tg-time",
    aliases: ["tg-time"],
    group: "special",
    toolbar: "more",
    dialog: "date-time",
  },
] as const satisfies readonly TelegramFormattingAction[];

export const PRIMARY_FORMATTING_ACTIONS = TELEGRAM_FORMATTING_ACTIONS.filter((action) => action.toolbar === "primary");
export const MORE_FORMATTING_ACTIONS = TELEGRAM_FORMATTING_ACTIONS.filter((action) => action.toolbar === "more");

export const FORMAT_ACTION_BY_KIND = new Map<TelegramFormatKind, TelegramFormattingAction>(
  TELEGRAM_FORMATTING_ACTIONS.map((action) => [action.kind, action]),
);

export const FORMAT_KIND_BY_ALIAS = new Map<string, TelegramFormatKind>(
  TELEGRAM_FORMATTING_ACTIONS.flatMap((action) => action.aliases.map((alias) => [alias, action.kind] as const)),
);

export const INLINE_COMBINABLE_FORMATS = new Set<TelegramFormatKind>([
  "bold",
  "italic",
  "underline",
  "strikethrough",
  "spoiler",
]);

export const EXCLUSIVE_INLINE_FORMATS = new Set<TelegramFormatKind>([
  "link",
  "mention",
  "custom-emoji",
  "date-time",
]);

export const CODE_FORMATS = new Set<TelegramFormatKind>(["inline-code", "code-block"]);
export const QUOTE_FORMATS = new Set<TelegramFormatKind>(["quote", "expandable-quote"]);

export const TELEGRAM_DATE_TIME_FORMAT = /^(?:r|w?[dD]?[tT]?)$/;

export const DATE_TIME_FORMAT_OPTIONS = [
  { value: "", label: "Fallback text only" },
  { value: "r", label: "Relative time" },
  { value: "t", label: "Short time" },
  { value: "T", label: "Long time" },
  { value: "d", label: "Short date" },
  { value: "D", label: "Long date" },
  { value: "wd", label: "Weekday + short date" },
  { value: "wD", label: "Weekday + long date" },
  { value: "dt", label: "Short date + short time" },
  { value: "dT", label: "Short date + long time" },
  { value: "Dt", label: "Long date + short time" },
  { value: "DT", label: "Long date + long time" },
  { value: "wdt", label: "Weekday + short date + short time" },
  { value: "wdT", label: "Weekday + short date + long time" },
  { value: "wDt", label: "Weekday + long date + short time" },
  { value: "wDT", label: "Weekday + long date + long time" },
] as const;

export function formattingActionForHotkey(event: Pick<KeyboardEvent, "altKey" | "code" | "ctrlKey" | "metaKey" | "shiftKey">): TelegramFormattingAction | null {
  if (!(event.ctrlKey || event.metaKey) || event.altKey) return null;
  return TELEGRAM_FORMATTING_ACTIONS.find((candidate) => {
    const action: TelegramFormattingAction = candidate;
    return action.hotkey?.code === event.code && Boolean(action.hotkey.shift) === event.shiftKey;
  }) ?? null;
}

export function isSafeWebUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function telegramMentionHref(userId: string): string {
  return `tg://user?id=${userId}`;
}

export function parseTelegramMentionHref(value: string): string | null {
  const match = value.match(/^tg:\/\/user\?id=(\d+)$/);
  return match?.[1] ?? null;
}

export function isValidTelegramUserId(value: string): boolean {
  return /^\d+$/.test(value.trim());
}

export function isValidCustomEmojiFallback(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  if (typeof Intl.Segmenter !== "function") return Array.from(text).length <= 2;
  return Array.from(new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)).length === 1;
}

export function renderTelegramDateTime(unix: number, format: string, fallback: string, now = Date.now()): string {
  if (!TELEGRAM_DATE_TIME_FORMAT.test(format) || !format) return fallback;
  const date = new Date(unix * 1000);
  if (Number.isNaN(date.getTime())) return fallback;
  if (format === "r") return formatRelativeTime(date.getTime() - now);

  const options: Intl.DateTimeFormatOptions = {};
  if (format.includes("w")) options.weekday = "short";
  if (format.includes("d")) {
    options.year = "2-digit";
    options.month = "2-digit";
    options.day = "2-digit";
  }
  if (format.includes("D")) {
    options.year = "numeric";
    options.month = "long";
    options.day = "numeric";
  }
  if (format.includes("t")) {
    options.hour = "2-digit";
    options.minute = "2-digit";
  }
  if (format.includes("T")) {
    options.hour = "2-digit";
    options.minute = "2-digit";
    options.second = "2-digit";
  }
  return new Intl.DateTimeFormat(undefined, options).format(date);
}

function formatRelativeTime(deltaMilliseconds: number): string {
  const absoluteSeconds = Math.abs(deltaMilliseconds) / 1000;
  const units: readonly [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 365 * 86400],
    ["month", 31 * 86400],
    ["week", 7 * 86400],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
    ["second", 1],
  ];
  const [unit, seconds] = units.find(([, unitSeconds]) => absoluteSeconds >= unitSeconds) ?? units.at(-1)!;
  const value = Math.trunc(deltaMilliseconds / 1000 / seconds);
  return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(value, unit);
}
