import { useId, useState } from "react";

import { OverlayDialog } from "./OverlayDialog";

const MAX_RECENT_ITEMS = 20;

export function SuggestionInput({
  id,
  value,
  items,
  ariaLabel,
  placeholder,
  browseLabel,
  pickerLabel,
  pickerEyebrow = "Resources",
  emptyText = "No matching resources.",
  createLabel = "Create resource",
  recentStorageKey,
  disabled = false,
  showBrowse = true,
  onChange,
  onOpen,
  onCreate,
}: {
  id?: string;
  value: string;
  items: string[];
  ariaLabel: string;
  placeholder?: string;
  browseLabel: string;
  pickerLabel: string;
  pickerEyebrow?: string;
  emptyText?: string;
  createLabel?: string;
  recentStorageKey?: string;
  disabled?: boolean;
  showBrowse?: boolean;
  onChange(value: string): void;
  onOpen?(): void;
  onCreate?(suggestedValue: string): void;
}) {
  const generatedId = useId().replace(/:/g, "");
  const inputId = id ?? `suggestion-input-${generatedId}`;
  const listId = `${inputId}-suggestions`;
  const [pickerOpen, setPickerOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const [hasTypedSinceFocus, setHasTypedSinceFocus] = useState(false);
  const [recentItems, setRecentItems] = useState<string[]>(() => readRecentItems(recentStorageKey));
  const normalizedValue = value.trim().toLowerCase();
  const query = hasTypedSinceFocus ? normalizedValue : "";
  const availableRecentItems = recentItems.filter((item) => items.includes(item));
  const orderedItems = (query
    ? items.filter((item) => item.toLowerCase().includes(query))
    : [...availableRecentItems, ...items.filter((item) => !availableRecentItems.includes(item))])
    .filter((item) => item.toLowerCase() !== normalizedValue);
  const suggestions = showAllSuggestions ? orderedItems : orderedItems.slice(0, 5);
  const visibleItems = items.filter((item) => item.toLowerCase().includes(filter.trim().toLowerCase()));
  const canOpen = items.includes(value.trim()) && Boolean(onOpen);

  const choose = (item: string) => {
    onChange(item);
    if (recentStorageKey) {
      setRecentItems((current) => saveRecentItems(recentStorageKey, [item, ...current.filter((entry) => entry !== item)]));
    }
    setActiveSuggestionIndex(-1);
    setShowAllSuggestions(false);
    setSuggestionsOpen(false);
  };

  return (
    <div className="form-control-group form-control-group--attached suggestion-input">
      <input
        id={inputId}
        aria-label={ariaLabel}
        aria-autocomplete="list"
        aria-controls={listId}
        aria-expanded={suggestionsOpen && suggestions.length > 0}
        aria-activedescendant={activeSuggestionIndex >= 0 ? `${listId}-${activeSuggestionIndex}` : undefined}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onFocus={() => {
          setHasTypedSinceFocus(false);
          setShowAllSuggestions(false);
          setSuggestionsOpen(true);
        }}
        onBlur={() => {
          setHasTypedSinceFocus(false);
          setActiveSuggestionIndex(-1);
          setShowAllSuggestions(false);
          setSuggestionsOpen(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setActiveSuggestionIndex(-1);
            setSuggestionsOpen(false);
            return;
          }
          if (!suggestions.length || !["ArrowDown", "ArrowUp", "Enter"].includes(event.key)) return;
          event.preventDefault();
          if (event.key === "Enter") {
            choose(suggestions[Math.max(activeSuggestionIndex, 0)]);
            return;
          }
          setSuggestionsOpen(true);
          setActiveSuggestionIndex((current) => event.key === "ArrowDown"
            ? (current + 1) % suggestions.length
            : (current + suggestions.length - 1) % suggestions.length);
        }}
        onChange={(event) => {
          onChange(event.target.value);
          setHasTypedSinceFocus(true);
          setActiveSuggestionIndex(-1);
          setShowAllSuggestions(false);
          setSuggestionsOpen(true);
        }}
      />
      {suggestionsOpen && (suggestions.length > 0 || onCreate) && (
        <div id={listId} className="suggestion-input__suggestions" role="listbox" aria-label={`${ariaLabel} suggestions`}>
          {suggestions.map((item, index) => (
            <button
              id={`${listId}-${index}`}
              key={item}
              type="button"
              role="option"
              aria-selected={index === activeSuggestionIndex}
              className={index === activeSuggestionIndex ? "suggestion-input__item suggestion-input__item--active" : "suggestion-input__item"}
              onMouseDown={(event) => {
                event.preventDefault();
                choose(item);
              }}
              onClick={() => choose(item)}
            >
              {item}
            </button>
          ))}
          {suggestions.length < orderedItems.length && (
            <button type="button" className="suggestion-input__more" aria-label={`Show more ${ariaLabel} suggestions`} onMouseDown={(event) => event.preventDefault()} onClick={() => { setActiveSuggestionIndex(-1); setShowAllSuggestions(true); }}>
              <ChevronDownIcon />
            </button>
          )}
          {onCreate && (
            <button
              type="button"
              className="suggestion-input__create"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onCreate(items.includes(value.trim()) ? "" : value.trim());
                setSuggestionsOpen(false);
              }}
            >
              {createLabel}
            </button>
          )}
        </div>
      )}
      <div className="form-control-group__actions">
        {onOpen && <button type="button" className="suggestion-input__open" aria-label={`Open current ${ariaLabel.toLowerCase()}`} title={canOpen ? "Open selected resource" : "Choose an existing resource to open it"} disabled={!canOpen} onClick={onOpen}><OpenIcon /></button>}
        {showBrowse && <button type="button" className="suggestion-input__browse" aria-label={browseLabel} title={browseLabel} disabled={disabled} onClick={() => { setSuggestionsOpen(false); setFilter(""); setPickerOpen(true); }}><FolderIcon /></button>}
      </div>
      <OverlayDialog open={pickerOpen} label={pickerLabel} onClose={() => setPickerOpen(false)} className="suggestion-picker">
        <header><div><p className="eyebrow">{pickerEyebrow}</p><h3>{pickerLabel}</h3></div><button type="button" className="button--icon" aria-label={`Close ${pickerLabel.toLowerCase()}`} onClick={() => setPickerOpen(false)}>×</button></header>
        <input aria-label={`Filter ${ariaLabel.toLowerCase()}`} autoFocus value={filter} placeholder="Filter…" onChange={(event) => setFilter(event.target.value)} />
        <div className="suggestion-picker__list">
          {visibleItems.length
            ? visibleItems.map((item) => <button key={item} type="button" className={item === value ? "suggestion-picker__item suggestion-picker__item--selected" : "suggestion-picker__item"} onClick={() => { choose(item); setPickerOpen(false); }}>{item}</button>)
            : <p className="muted">{emptyText}</p>}
        </div>
      </OverlayDialog>
    </div>
  );
}

function readRecentItems(storageKey?: string): string[] {
  if (!storageKey) return [];
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(storageKey) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string").slice(0, MAX_RECENT_ITEMS) : [];
  } catch {
    return [];
  }
}

function saveRecentItems(storageKey: string, items: string[]): string[] {
  const next = items.slice(0, MAX_RECENT_ITEMS);
  try { window.localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Recents are optional. */ }
  return next;
}

function FolderIcon() {
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="M2.5 4.5h4l1.2 1.5h5.8v5.75c0 .42-.33.75-.75.75h-9.5a.75.75 0 0 1-.75-.75V5.25c0-.42.33-.75.75-.75Z" /></svg>;
}

function OpenIcon() {
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="M8.75 2.75h4.5v4.5M12.9 3.1 7 9M12.25 9.75v2.5c0 .41-.34.75-.75.75h-7a.75.75 0 0 1-.75-.75v-7c0-.41.34-.75.75-.75h2.5" /></svg>;
}

function ChevronDownIcon() {
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="m4.5 6.25 3.5 3.5 3.5-3.5" /></svg>;
}
