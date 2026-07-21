import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type { ActionOptions, ButtonSpec, TextSpec, ViewSpec } from "../../domain/project";
import { actionFor } from "../../domain/project";
import { ActionEditor, type HandlerActions } from "../action-editor/ActionEditor";
import { Select } from "../../shared/ui/Select";

export function ViewEditor({
  value,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
  onOpenTemplate,
}: {
  value: ViewSpec;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ViewSpec): void;
  onOpenTemplate?(path: string): void;
}) {
  const [accessMockup, setAccessMockup] = useState("everyone");
  const updateButton = (rowIndex: number, buttonIndex: number, button: ButtonSpec) => {
    onChange({
      ...value,
      keyboard: value.keyboard.map((row, currentRow) => currentRow === rowIndex
        ? row.map((item, currentButton) => currentButton === buttonIndex ? button : item)
        : row),
    });
  };
  const existingIds = value.keyboard.flat().map((button) => button.id);
  return (
    <section className="editor" aria-label="View editor">
      <div className="form-grid form-grid--view-settings">
        <div className="view-settings__primary">
          <label className="editor-field editor-field--name">
            <span>Name:</span>
            <input value={value.id} onChange={(event) => onChange({ ...value, id: event.target.value })} />
          </label>
          <label className="editor-field editor-field--access">
            <span>Access:</span>
            <Select
              ariaLabel="Page access"
              value={accessMockup}
              options={[
                { value: "everyone", label: "Everyone" },
                { value: "members", label: "Members" },
                { value: "admins", label: "Administrators" },
              ]}
              onChange={setAccessMockup}
            />
          </label>
        </div>
        <div className="text-source-field editor-field">
          <span>Content:</span>
          <TextSourceControl text={value.text} templates={options.templates ?? []} onChange={(text) => onChange({ ...value, text })} onOpenTemplate={onOpenTemplate} />
        </div>
        <fieldset className="keyboard-editor">
          <legend>Inline keyboard</legend>
          {value.keyboard.map((row, rowIndex) => (
            <div className="keyboard-row" key={rowIndex}>
              {row.map((button, buttonIndex) => (
                <section className="button-card" key={button.id || buttonIndex}>
                  <header><strong>Button {rowIndex + 1}.{buttonIndex + 1}</strong></header>
                  <label>
                    Stable action ID
                    <input value={button.id} onChange={(event) => updateButton(rowIndex, buttonIndex, { ...button, id: event.target.value })} />
                  </label>
                  <label>
                    Text
                    <input value={button.text} onChange={(event) => updateButton(rowIndex, buttonIndex, { ...button, text: event.target.value })} />
                  </label>
                  <ActionEditor
                    action={button.action}
                    onChange={(action) => updateButton(rowIndex, buttonIndex, { ...button, action })}
                    options={options}
                    scope={{ expectedKind: "button" }}
                    handlerActions={handlerActions}
                    createOptions={isNew ? undefined : {
                      attachment: { type: "view_button", view_id: value.id, button_id: button.id },
                      target_revision: revision,
                    }}
                  />
                  <button type="button" className="button--quiet" onClick={() => onChange({
                    ...value,
                    keyboard: value.keyboard.map((item, current) => current === rowIndex ? item.filter((_, index) => index !== buttonIndex) : item),
                  })}>Remove button</button>
                </section>
              ))}
              <div className="button-row">
                <button type="button" className="button--quiet" onClick={() => onChange({
                  ...value,
                  keyboard: value.keyboard.map((item, current) => current === rowIndex
                    ? [...item, { id: nextButtonId(value.id, existingIds), text: "Button", action: actionFor("noop") }]
                    : item),
                })}>Add button</button>
                <button type="button" className="button--quiet" onClick={() => onChange({ ...value, keyboard: value.keyboard.filter((_, index) => index !== rowIndex) })}>Remove row</button>
              </div>
            </div>
          ))}
          <button type="button" className="button--quiet" onClick={() => onChange({ ...value, keyboard: [...value.keyboard, []] })}>Add row</button>
        </fieldset>
      </div>
    </section>
  );
}

function TextSourceControl({ text, templates, onChange, onOpenTemplate }: { text: TextSpec; templates: string[]; onChange(text: TextSpec): void; onOpenTemplate?: (path: string) => void }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const [recentTemplates, setRecentTemplates] = useState<string[]>(readRecentTemplates);
  const isTemplate = "template" in text;
  const templateValue = isTemplate ? text.template ?? "" : "";
  const canOpenTemplate = templates.includes(templateValue.trim());
  const visibleTemplates = templates.filter((template) => template.toLowerCase().includes(filter.trim().toLowerCase()));
  const query = templateValue.trim().toLowerCase();
  const availableRecentTemplates = recentTemplates.filter((template) => templates.includes(template));
  const orderedTemplates = query
    ? templates.filter((template) => template.toLowerCase().includes(query) && template.toLowerCase() !== query)
    : [...availableRecentTemplates, ...templates.filter((template) => !availableRecentTemplates.includes(template))];
  const templateSuggestions = showAllSuggestions ? orderedTemplates : orderedTemplates.slice(0, 5);
  const hasMoreSuggestions = templateSuggestions.length < orderedTemplates.length;
  const chooseTemplateSuggestion = (template: string) => {
    onChange({ template });
    setRecentTemplates((current) => saveRecentTemplates([template, ...current.filter((item) => item !== template)]));
    setActiveSuggestionIndex(-1);
    setShowAllSuggestions(false);
    setSuggestionsOpen(false);
  };

  useEffect(() => {
    if (!pickerOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setPickerOpen(false); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [pickerOpen]);

  return <div className="text-source">
    <Select clickOnly ariaLabel="Text source" value={isTemplate ? "template" : "inline"} options={[{ value: "inline", label: "Text" }, { value: "template", label: "Template" }]} onChange={(mode) => onChange(mode === "template" ? { template: "" } : { inline: "" })} />
    {isTemplate
      ? <div className="text-source__template">
          <input
            aria-label="Template"
            aria-autocomplete="list"
            aria-controls="template-suggestions"
            aria-expanded={suggestionsOpen && templateSuggestions.length > 0}
            aria-activedescendant={activeSuggestionIndex >= 0 ? `template-suggestion-${activeSuggestionIndex}` : undefined}
            value={templateValue}
            placeholder="Template name"
            onFocus={() => { setShowAllSuggestions(false); setSuggestionsOpen(true); }}
            onBlur={() => { setActiveSuggestionIndex(-1); setShowAllSuggestions(false); setSuggestionsOpen(false); }}
            onKeyDown={(event) => {
              if (event.key === "Escape") { setActiveSuggestionIndex(-1); setSuggestionsOpen(false); return; }
              if (!templateSuggestions.length || (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Enter")) return;
              if (event.key === "Enter") {
                event.preventDefault();
                chooseTemplateSuggestion(templateSuggestions[Math.max(activeSuggestionIndex, 0)]);
                return;
              }
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                setSuggestionsOpen(true);
                setActiveSuggestionIndex((current) => event.key === "ArrowDown"
                  ? (current + 1) % templateSuggestions.length
                  : (current + templateSuggestions.length - 1) % templateSuggestions.length);
              }
            }}
            onChange={(event) => { onChange({ template: event.target.value }); setActiveSuggestionIndex(-1); setShowAllSuggestions(false); setSuggestionsOpen(true); }}
          />
          {suggestionsOpen && templateSuggestions.length > 0 && <div id="template-suggestions" className="template-suggestions" role="listbox" aria-label="Template suggestions">
            {templateSuggestions.map((template, index) => <button id={`template-suggestion-${index}`} key={template} type="button" role="option" aria-selected={index === activeSuggestionIndex} className={index === activeSuggestionIndex ? "template-suggestions__item template-suggestions__item--active" : "template-suggestions__item"} onMouseDown={(event) => { event.preventDefault(); chooseTemplateSuggestion(template); }}>{template}</button>)}
            {hasMoreSuggestions && <button type="button" className="template-suggestions__more" aria-label="Show more templates" onMouseDown={(event) => event.preventDefault()} onClick={() => { setActiveSuggestionIndex(-1); setShowAllSuggestions(true); }}><ChevronDownIcon /></button>}
          </div>}
          <button type="button" className="text-source__open" aria-label="Open current template" title={canOpenTemplate ? "Open template editor" : "Enter an existing template path to open it"} disabled={!canOpenTemplate} onClick={() => onOpenTemplate?.(templateValue.trim())}><OpenTemplateIcon /></button>
          <button type="button" className="text-source__browse" aria-label="Browse templates" title="Browse templates" onClick={() => { setSuggestionsOpen(false); setFilter(""); setPickerOpen(true); }}><FolderIcon /></button>
        </div>
      : <AutoGrowTextarea value={text.inline} onChange={(inline) => onChange({ inline })} />}
    {pickerOpen && <div className="template-picker-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setPickerOpen(false); }}>
      <section className="template-picker" role="dialog" aria-modal="true" aria-label="Choose template">
        <header><div><p className="eyebrow">Templates</p><h3>Choose a template</h3></div><button type="button" className="button--icon" aria-label="Close template picker" onClick={() => setPickerOpen(false)}>×</button></header>
        <input aria-label="Filter templates" autoFocus value={filter} placeholder="Filter templates" onChange={(event) => setFilter(event.target.value)} />
        <div className="template-picker__list">
          {visibleTemplates.length ? visibleTemplates.map((template) => <button key={template} type="button" className={template === text.template ? "template-picker__item template-picker__item--selected" : "template-picker__item"} onClick={() => { onChange({ template }); setPickerOpen(false); }}>{template}</button>) : <p className="muted">No matching templates.</p>}
        </div>
      </section>
    </div>}
  </div>;
}

const RECENT_TEMPLATES_KEY = "tg-bot-studio.recent-templates";
const MAX_RECENT_TEMPLATES = 20;

function readRecentTemplates(): string[] {
  try {
    const stored = window.localStorage.getItem(RECENT_TEMPLATES_KEY);
    const parsed: unknown = stored ? JSON.parse(stored) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string").slice(0, MAX_RECENT_TEMPLATES) : [];
  } catch {
    return [];
  }
}

function saveRecentTemplates(templates: string[]): string[] {
  const next = templates.slice(0, MAX_RECENT_TEMPLATES);
  try { window.localStorage.setItem(RECENT_TEMPLATES_KEY, JSON.stringify(next)); } catch { /* Local history is an optional UI enhancement. */ }
  return next;
}

function FolderIcon() {
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="M2.5 4.5h4l1.2 1.5h5.8v5.75c0 .42-.33.75-.75.75h-9.5a.75.75 0 0 1-.75-.75V5.25c0-.42.33-.75.75-.75Z" /></svg>;
}

function OpenTemplateIcon() {
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="M8.75 2.75h4.5v4.5M12.9 3.1 7 9M12.25 9.75v2.5c0 .41-.34.75-.75.75h-7a.75.75 0 0 1-.75-.75v-7c0-.41.34-.75.75-.75h2.5" /></svg>;
}

function ChevronDownIcon() {
  return <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="m4.5 6.25 3.5 3.5 3.5-3.5" /></svg>;
}

function AutoGrowTextarea({ value, onChange }: { value: string; onChange(value: string): void }) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const currentHeight = textarea.getBoundingClientRect().height;
    textarea.style.height = "auto";
    const nextHeight = Math.max(30, Math.min(textarea.scrollHeight, 180));
    textarea.style.height = `${currentHeight}px`;
    const frame = window.requestAnimationFrame(() => { textarea.style.height = `${nextHeight}px`; });
    return () => window.cancelAnimationFrame(frame);
  }, [value]);
  return <textarea ref={textareaRef} className="text-source__inline" aria-label="Inline text" value={value} rows={1} placeholder="Write the message text" onChange={(event) => onChange(event.target.value)} />;
}

function nextButtonId(viewId: string, existing: string[]): string {
  const prefix = `${viewId || "view"}.action`;
  let suffix = 1;
  while (existing.includes(`${prefix}_${suffix}`)) suffix += 1;
  return `${prefix}_${suffix}`;
}
