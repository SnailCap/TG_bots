import type { TelegramPreviewMessage } from "./preview-model";
import { TelegramKeyboard } from "./TelegramKeyboard";

export function TelegramMessageBubble({ message, onButtonClick }: { message: TelegramPreviewMessage; onButtonClick(label: string): void }) {
  const time = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date());
  return (
    <article className={`telegram-message telegram-message--${message.author}`}>
      <div className="telegram-message__bubble"><p>{message.text}</p><time>{time}</time></div>
      {message.buttons && <TelegramKeyboard rows={message.buttons} onSelect={onButtonClick} />}
    </article>
  );
}
