export function TelegramKeyboard({ rows, onSelect, reply = false }: { rows: string[][]; onSelect(label: string): void; reply?: boolean }) {
  return (
    <div className={reply ? "telegram-keyboard telegram-keyboard--reply" : "telegram-keyboard"}>
      {rows.map((row, rowIndex) => <div className="telegram-keyboard__row" key={rowIndex}>
        {row.map((label, buttonIndex) => <button type="button" key={`${label}-${buttonIndex}`} onClick={() => onSelect(label)}>{label}</button>)}
      </div>)}
    </div>
  );
}
