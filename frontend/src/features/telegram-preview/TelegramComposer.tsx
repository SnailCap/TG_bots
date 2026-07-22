import { useState } from "react";

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
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m17 3-6.35 13-1.7-5.3L3.6 9 17 3Z" /><path d="m8.95 10.7 3.2-3.15" /></svg>;
}
