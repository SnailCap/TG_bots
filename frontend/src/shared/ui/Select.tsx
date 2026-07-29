import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
  icon?: ReactNode;
  disabled?: boolean;
}

export function Select({ id, value, options, placeholder, disabled = false, readOnly = false, clickOnly = false, searchable = false, ariaLabel, "aria-describedby": ariaDescribedBy, "aria-invalid": ariaInvalid, onChange }: {
  id?: string;
  value: string;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  readOnly?: boolean;
  clickOnly?: boolean;
  searchable?: boolean;
  ariaLabel?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  onChange(value: string): void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId().replace(/:/g, "");
  const triggerId = id ?? `${listId}-trigger`;
  const selected = options.find((option) => option.value === value);
  const label = selected?.label ?? placeholder ?? value;
  const visibleOptions = searchable
    ? options.filter((option) => option.label.toLowerCase().includes(query.trim().toLowerCase()))
    : options;

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
    if (readOnly || next.disabled) return;
    setOpen(false);
    onChange(next.value);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled || readOnly) return;
    if (clickOnly) {
      if (event.key === " " || event.key === "Enter" || event.key === "ArrowDown" || event.key === "ArrowUp") event.preventDefault();
      return;
    }
    if (event.key === " " || event.key === "Enter" || event.key === "ArrowDown") {
      event.preventDefault();
      setQuery("");
      setOpen(true);
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setQuery("");
      setOpen(true);
    }
  };

  return <div ref={rootRef} className={["select-control", open ? "select-control--open" : "", readOnly ? "select-control--readonly" : ""].filter(Boolean).join(" ")}>
    <button id={triggerId} type="button" role="combobox" className="select-control__trigger" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-controls={listId} aria-describedby={ariaDescribedBy} aria-invalid={ariaInvalid || undefined} aria-readonly={readOnly || undefined} disabled={disabled} onClick={() => { if (readOnly) return; setOpen((current) => { if (!current) setQuery(""); return !current; }); }} onKeyDown={onKeyDown}>
      <span className="select-control__value">{selected?.icon && <span className="select-control__icon" aria-hidden="true">{selected.icon}</span>}<span>{label}</span></span><span className="select-control__chevron" aria-hidden="true"><ChevronIcon /></span>
    </button>
    {open && <div id={listId} className="select-control__menu" role="listbox" aria-labelledby={triggerId}>
      {searchable && <input className="select-control__search" aria-label={`Search ${ariaLabel ?? "options"}`} autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search…" />}
      {visibleOptions.length
        ? visibleOptions.map((option) => <button key={option.value} type="button" role="option" aria-selected={option.value === value} disabled={option.disabled} className={option.value === value ? "select-control__option select-control__option--selected" : "select-control__option"} onClick={(event) => { event.preventDefault(); event.stopPropagation(); choose(option); }}><span className="select-control__option-content">{option.icon && <span className="select-control__icon" aria-hidden="true">{option.icon}</span>}<span>{option.label}</span></span></button>)
        : <p className="select-control__empty">No matching options.</p>}
    </div>}
  </div>;
}

function ChevronIcon() {
  return <ChevronDown aria-hidden="true" />;
}
