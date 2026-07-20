import type { Preview } from "../../domain/project";

export function TelegramPreview({ preview }: { preview: Preview | null }) {
  return (
    <section className="telegram-preview" aria-label="Telegram preview">
      <header><p className="eyebrow">Static preview</p><h2>Telegram</h2></header>
      {preview
        ? <><article className="telegram-message">{preview.text || <em>No text yet</em>}</article>{preview.keyboard.map((row, rowIndex) => <div className="telegram-row" key={rowIndex}>{row.map((button, buttonIndex) => <span key={button.id ?? buttonIndex}>{button.text}</span>)}</div>)}{preview.warnings.map((warning) => <p className="warning" key={warning}>{warning}</p>)}</>
        : <p className="muted">Select a view to preview it.</p>}
    </section>
  );
}
