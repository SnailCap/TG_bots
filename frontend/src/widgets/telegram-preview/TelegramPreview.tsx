import type { Preview } from "../../domain/project";

export function TelegramPreview({ preview }: { preview: Preview | null }) {
  return (
    <section className="telegram-preview" aria-label="Telegram preview">
      <header><p className="eyebrow">Static preview</p><h2>Telegram</h2></header>
      {preview
        ? <><article className="telegram-message">{preview.text || <em>No text yet</em>}</article>{preview.keyboard.map((row, rowIndex) => <div className="telegram-row" key={rowIndex}>{row.map((button, buttonIndex) => <span key={button.id ?? buttonIndex}>{button.text}</span>)}</div>)}{preview.warnings.map((warning) => <p className="callout callout--warning" key={warning}>{warning}</p>)}</>
        : <div className="panel-empty"><strong>No view selected</strong><p>Select a view to check its rendered text and inline keyboard.</p></div>}
    </section>
  );
}
