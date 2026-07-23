import type { TelegramFormatKind } from "./telegram-formatting";

export type TemplateTextNode = {
  type: "text";
  text: string;
};

export type TemplateContextTokenNode = {
  type: "context-token";
  fieldId: string;
  path: string;
  /** Original Jinja spelling, retained when a template was parsed from source. */
  source?: string;
};

export type TemplateUnresolvedTokenNode = {
  type: "unresolved-token";
  path: string;
  source: string;
};

export type TemplateRawFragmentNode = {
  type: "raw-fragment";
  source: string;
  fragmentKind?: "jinja" | "html";
};

export type TemplateFormatNode = {
  type: "format";
  format: TelegramFormatKind;
  children: TemplateNode[];
  href?: string;
  userId?: string;
  language?: string;
  emojiId?: string;
  unix?: number;
  dateTimeFormat?: string;
  fallback?: string;
};

export type TemplateNode =
  | TemplateTextNode
  | TemplateContextTokenNode
  | TemplateUnresolvedTokenNode
  | TemplateRawFragmentNode
  | TemplateFormatNode;

export type TemplateDocument = {
  nodes: TemplateNode[];
};
