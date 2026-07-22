import { useEffect, useState } from "react";

import type { TelegramPreviewMessage, TelegramPreviewModel } from "./preview-model";
import { TelegramChatHeader } from "./TelegramChatHeader";
import { TelegramComposer } from "./TelegramComposer";
import { TelegramKeyboard } from "./TelegramKeyboard";
import { TelegramMessageBubble } from "./TelegramMessageBubble";

export function TelegramPreview({ open, model, onClose }: { open: boolean; model: TelegramPreviewModel; onClose(): void }) {
  const [draftMessages, setDraftMessages] = useState<TelegramPreviewMessage[]>([]);

  useEffect(() => { setDraftMessages([]); }, [model.key]);

  const appendUserMessage = (text: string) => setDraftMessages((current) => [...current, { id: `local-${Date.now()}-${current.length}`, author: "user", text }]);
  const messages = [...model.messages, ...draftMessages];

  return (
    <aside className={open ? "telegram-preview telegram-preview--open" : "telegram-preview"} aria-label="Telegram preview" aria-hidden={!open} inert={!open}>
      <div className="telegram-preview__content">
        <TelegramChatHeader botName={model.botName} contextLabel={model.contextLabel} onClose={onClose} />
        <div className="telegram-preview__messages">
          {messages.map((message) => <TelegramMessageBubble key={message.id} message={message} onButtonClick={appendUserMessage} />)}
        </div>
        {model.replyKeyboard && <TelegramKeyboard rows={model.replyKeyboard} reply onSelect={appendUserMessage} />}
        <TelegramComposer onSend={appendUserMessage} />
      </div>
    </aside>
  );
}
