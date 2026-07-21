import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export function Select({ value, options, placeholder, disabled = false, clickOnly = false, ariaLabel, onChange }: {
  value: string;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  clickOnly?: boolean;
  ariaLabel: string;
  onChange(value: string): void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId().replace(/:/g, "");
  const selected = options.find((option) => option.value === value);
  const label = selected?.label ?? placeholder ?? value;

  useEffect(() => {
    if (!open) return;
    const closeOnOutsidePress = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("pointerdown", closeOnOutsidePress);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("pointerdown", closeOnOutsidePress);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const choose = (next: SelectOption) => {
    if (next.disabled) return;
    setOpen(false);
    onChange(next.value);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (clickOnly) {
      if (event.key === " " || event.key === "Enter" || event.key === "ArrowDown" || event.key === "ArrowUp") event.preventDefault();
      return;
    }
    if (event.key === " " || event.key === "Enter" || event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
    }
  };

  return <div ref={rootRef} className={open ? "select-control select-control--open" : "select-control"}>
    <button id={`${listId}-trigger`} type="button" className="select-control__trigger" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-controls={listId} disabled={disabled} onClick={() => setOpen((current) => !current)} onKeyDown={onKeyDown}>
      <span>{label}</span><span className="select-control__chevron" aria-hidden="true"><ChevronIcon /></span>
    </button>
    {open && <div id={listId} className="select-control__menu" role="listbox" aria-labelledby={`${listId}-trigger`}>
      {options.map((option) => <button key={option.value} type="button" role="option" aria-selected={option.value === value} disabled={option.disabled} className={option.value === value ? "select-control__option select-control__option--selected" : "select-control__option"} onClick={(event) => { event.preventDefault(); event.stopPropagation(); choose(option); }}>{option.label}</button>)}
    </div>}
  </div>;
}

function ChevronIcon() {
  return <svg viewBox="0 0 16 16" focusable="false"><path d="m4.5 6.25 3.5 3.5 3.5-3.5" /></svg>;
}
