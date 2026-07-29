import { X } from "lucide-react";

export function TelegramChatHeader({ botName, contextLabel, onClose }: { botName: string; contextLabel: string; onClose(): void }) {
  return (
    <header className="telegram-chat__header">
      <span className="telegram-chat__avatar" aria-hidden="true">{botName.slice(0, 2).toUpperCase()}</span>
      <span className="telegram-chat__identity"><strong>{botName}</strong><small>bot · {contextLabel}</small></span>
      <button type="button" className="telegram-chat__close" aria-label="Close preview" title="Close preview" onClick={onClose}><CloseIcon /></button>
    </header>
  );
}

function CloseIcon() {
  return <X aria-hidden="true" />;
}
