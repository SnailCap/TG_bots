import { Fragment, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { CircleAlert, CircleCheck, Eye, LoaderCircle, MessageSquareText, Send } from "lucide-react";

import { SYSTEM_CONTEXT_FIELDS } from "../template-composer/context-catalog";
import { CustomEmojiMedia } from "./custom-emoji-state";
import { isSafeContentLink, type TelegramCompileResult, type TelegramMessageEntity } from "./model";

export type RichEditorPreviewValues = Record<string, string | number>;
export type SendPreviewResult = { sentCount: number; totalCount: number };

type EntityTreeNode = {
  entity: TelegramMessageEntity;
  start: number;
  end: number;
  sourceIndex: number;
  children: EntityTreeNode[];
};

export function TelegramCompiledPreview({
  result,
  values,
  onValuesChange,
  onSendPreview,
}: {
  result: TelegramCompileResult | null;
  values: RichEditorPreviewValues;
  onValuesChange(values: RichEditorPreviewValues): void;
  onSendPreview?(chatId: string): Promise<SendPreviewResult>;
}) {
  const [chatId, setChatId] = useState("");
  const [sendState, setSendState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [sendMessage, setSendMessage] = useState("");
  const totalCharacters = useMemo(
    () => result?.messages.reduce((count, message) => count + message.text.length, 0) ?? 0,
    [result],
  );
  const canSend = Boolean(
    onSendPreview
    && chatId.trim()
    && chatId.trim().length <= 128
    && result
    && result.messages.length > 0
    && result.errors.length === 0
    && sendState !== "sending",
  );
  const sendPreview = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSend || !onSendPreview) return;
    setSendState("sending");
    setSendMessage("Sending a silent Telegram preview…");
    try {
      const sent = await onSendPreview(chatId.trim());
      setSendState("sent");
      setSendMessage(`${sent.sentCount} of ${sent.totalCount} ${sent.totalCount === 1 ? "message" : "messages"} sent.`);
    } catch (error) {
      setSendState("error");
      setSendMessage(error instanceof Error ? error.message : "Telegram preview could not be sent.");
    }
  };

  return (
    <aside className="view-rich-preview" aria-label="Telegram message preview">
      <header className="view-rich-preview__header">
        <div>
          <span>Telegram preview</span>
          <strong>{result && result.messages.length > 1 ? `${result.messages.length} messages` : "Bot message"}</strong>
        </div>
        <Eye aria-hidden="true" />
      </header>

      <div className="view-rich-preview__chat">
        {!result ? (
          <div className="view-rich-preview__empty" role="status">
            <MessageSquareText aria-hidden="true" />
            <span>Preview will appear after compilation.</span>
          </div>
        ) : result.messages.length === 0 ? (
          <div className="view-rich-preview__empty" role="status">
            <MessageSquareText aria-hidden="true" />
            <span>The compiled message is empty.</span>
          </div>
        ) : result.messages.map((message, index) => (
          <article className="view-rich-preview__message" key={`${index}-${message.text.length}`} data-testid="compiled-message">
            <div className="view-rich-preview__bubble">
              <div className="view-rich-preview__text">{renderCompiledEntityText(message.text, message.entities)}</div>
              <span className="view-rich-preview__time" aria-hidden="true">12:00</span>
            </div>
            {result.messages.length > 1 ? <span className="view-rich-preview__part">Part {index + 1}</span> : null}
          </article>
        ))}
      </div>

      <div className="view-rich-preview__summary" aria-label="Compiled character count">
        <span>{totalCharacters.toLocaleString()} UTF-16 units</span>
        <span className={totalCharacters > 4096 && (result?.messages.length ?? 0) <= 1 ? "is-warning" : undefined}>
          {result && result.messages.length > 1 ? "Split by compiler" : "4,096 per message"}
        </span>
      </div>

      {onSendPreview ? (
        <form className="view-rich-preview__send" onSubmit={(event) => void sendPreview(event)}>
          <div className="view-rich-preview__send-heading">
            <span>Send test</span>
            <small>Uses this project&apos;s bot token and sends silently.</small>
          </div>
          <div className="view-rich-preview__send-controls">
            <input
              aria-label="Telegram preview chat ID"
              value={chatId}
              maxLength={128}
              placeholder="Chat ID or @channel"
              onChange={(event) => {
                setChatId(event.target.value);
                setSendState("idle");
                setSendMessage("");
              }}
            />
            <button type="submit" disabled={!canSend} title="Send compiled preview to Telegram">
              {sendState === "sending" ? <LoaderCircle aria-hidden="true" /> : <Send aria-hidden="true" />}
              <span>Send</span>
            </button>
          </div>
          {sendMessage ? (
            <p className={`is-${sendState}`} role={sendState === "error" ? "alert" : "status"}>
              {sendState === "error" ? <CircleAlert aria-hidden="true" /> : sendState === "sent" ? <CircleCheck aria-hidden="true" /> : <LoaderCircle aria-hidden="true" />}
              <span>{sendMessage}</span>
            </p>
          ) : null}
        </form>
      ) : null}

      <details className="view-rich-preview__values">
        <summary>Test variable values</summary>
        <div>
          {SYSTEM_CONTEXT_FIELDS.map((field) => (
            <label key={field.id}>
              <span>{field.label}</span>
              <input
                aria-label={`Preview ${field.label}`}
                type={field.valueType === "integer" ? "number" : "text"}
                value={values[field.path] ?? ""}
                onChange={(event) => onValuesChange({
                  ...values,
                  [field.path]: field.valueType === "integer" ? Number(event.target.value) : event.target.value,
                })}
              />
            </label>
          ))}
        </div>
      </details>
    </aside>
  );
}

/**
 * Renders already-compiled Telegram entities. JavaScript string indices are
 * UTF-16 code units, so slicing by compiler-provided offsets is intentional.
 */
export function renderCompiledEntityText(
  text: string,
  entities: readonly TelegramMessageEntity[],
): ReactNode {
  const tree = buildEntityTree(text, entities);
  return renderRange(text, 0, text.length, tree, "root");
}

export function sliceUtf16(value: string, offset: number, length: number): string {
  return value.slice(offset, offset + length);
}

function buildEntityTree(text: string, entities: readonly TelegramMessageEntity[]): EntityTreeNode[] {
  const ordered = entities.map((entity, sourceIndex) => ({
    entity,
    sourceIndex,
    start: entity.offset,
    end: entity.offset + entity.length,
    children: [] as EntityTreeNode[],
  })).filter((node) => Number.isInteger(node.start)
    && Number.isInteger(node.end)
    && node.start >= 0
    && node.end > node.start
    && node.end <= text.length)
    .sort((left, right) => left.start - right.start || right.end - left.end || left.sourceIndex - right.sourceIndex);

  const roots: EntityTreeNode[] = [];
  const stack: EntityTreeNode[] = [];
  for (const node of ordered) {
    while (stack.length > 0 && node.start >= stack.at(-1)!.end) stack.pop();
    const parent = stack.at(-1);
    if (parent) {
      // Crossing entities cannot be represented by nested DOM. The compiler is
      // responsible for reporting them; preview safely skips the crossing one.
      if (node.end > parent.end) continue;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
    stack.push(node);
  }
  return roots;
}

function renderRange(
  text: string,
  start: number,
  end: number,
  nodes: readonly EntityTreeNode[],
  keyPrefix: string,
): ReactNode[] {
  const output: ReactNode[] = [];
  let cursor = start;
  nodes.forEach((node, index) => {
    if (node.start > cursor) output.push(<Fragment key={`${keyPrefix}-text-${index}`}>{text.slice(cursor, node.start)}</Fragment>);
    const key = `${keyPrefix}-${node.sourceIndex}-${node.start}-${node.end}`;
    const children = renderRange(text, node.start, node.end, node.children, key);
    output.push(wrapEntity(node.entity, children, text.slice(node.start, node.end), key));
    cursor = node.end;
  });
  if (cursor < end) output.push(<Fragment key={`${keyPrefix}-tail`}>{text.slice(cursor, end)}</Fragment>);
  return output;
}

function wrapEntity(
  entity: TelegramMessageEntity,
  children: ReactNode,
  sourceText: string,
  key: string,
): ReactNode {
  const className = `view-rich-entity view-rich-entity--${entity.type.replaceAll("_", "-")}`;
  if (entity.type === "bold") return <strong className={className} key={key}>{children}</strong>;
  if (entity.type === "italic") return <em className={className} key={key}>{children}</em>;
  if (entity.type === "underline") return <u className={className} key={key}>{children}</u>;
  if (entity.type === "strikethrough") return <s className={className} key={key}>{children}</s>;
  if (entity.type === "code") return <code className={className} key={key}>{children}</code>;
  if (entity.type === "text_link" && entity.url && isSafeContentLink(entity.url)) {
    return <a className={className} href={entity.url} key={key} title={entity.url} onClick={(event) => event.preventDefault()}>{children}</a>;
  }
  if (entity.type === "custom_emoji") {
    const id = entity.custom_emoji_id;
    return <span className={className} key={key} data-custom-emoji-id={id}>{id ? <CustomEmojiMedia id={id} fallback={sourceText} /> : children}</span>;
  }
  if (entity.type === "pre") {
    return <span className={className} key={key} data-language={entity.language ?? ""}>{children}</span>;
  }
  if (entity.type === "expandable_blockquote") {
    return <span className={className} key={key} title="Expandable quote">{children}<span className="view-rich-entity__expandable-label" aria-hidden="true">Expandable</span></span>;
  }
  return <span className={className} key={key}>{children}</span>;
}
