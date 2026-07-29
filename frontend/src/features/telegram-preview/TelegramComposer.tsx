import { useState } from "react";
import { Send } from "lucide-react";

export function TelegramComposer({ onSend }: { onSend(text: string): void }) {
  const [value, setValue] = useState("");
  const send = () => {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue("");
  };
  return (
    <form className="telegram-composer" onSubmit={(event) => { event.preventDefault(); send(); }}>
      <input aria-label="Preview message" value={value} placeholder="Write a message…" onChange={(event) => setValue(event.target.value)} />
      <button type="submit" aria-label="Send preview message" disabled={!value.trim()}><SendIcon /></button>
    </form>
  );
}

function SendIcon() {
  return <Send aria-hidden="true" />;
}
