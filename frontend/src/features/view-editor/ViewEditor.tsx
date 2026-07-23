import { useLayoutEffect, useRef, useState } from "react";

import type { ActionOptions, TextSpec, ViewSpec } from "../../domain/project";
import { type HandlerActions } from "../action-editor/ActionEditor";
import { KeyboardComposer } from "../keyboard-composer/KeyboardComposer";
import { ResourceDropTarget } from "../resource-dnd";
import { FormControlGroup, FormField, FormGrid, type FormControlProps } from "../../shared/ui/Form";
import { OverlayDialog } from "../../shared/ui/OverlayDialog";
import { Select } from "../../shared/ui/Select";

export function ViewEditor({
  value,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
  onOpenTemplate,
  onCreateTemplate,
}: {
  value: ViewSpec;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ViewSpec): void;
  onOpenTemplate?(path: string): void;
  onCreateTemplate?(suggestedPath: string): void;
}) {
  const [accessMockup, setAccessMockup] = useState("everyone");
  return (
    <section className="editor" aria-label="View editor">
      <FormGrid columns={2} className="view-settings">
        <FormField label="Name:">
          {(controlProps) => (
            <input {...controlProps} value={value.id} onChange={(event) => onChange({ ...value, id: event.target.value })} />
          )}
        </FormField>
        <FormField label="Access:">
          {(controlProps) => (
            <Select
              {...controlProps}
              ariaLabel="Page access"
              value={accessMockup}
              options={[
                { value: "everyone", label: "Everyone", icon: <AccessIcon kind="everyone" /> },
                { value: "members", label: "Members", icon: <AccessIcon kind="members" /> },
                { value: "admins", label: "Administrators", icon: <AccessIcon kind="admins" /> },
              ]}
              onChange={setAccessMockup}
            />
          )}
        </FormField>
        <FormField label="Content:" span="full">
          {(controlProps) => (
            <TextSourceControl controlProps={controlProps} text={value.text} templates={options.templates ?? []} onChange={(text) => onChange({ ...value, text })} onOpenTemplate={onOpenTemplate} onCreateTemplate={onCreateTemplate} />
          )}
        </FormField>
        <KeyboardComposer
          viewId={value.id}
          keyboard={value.keyboard}
          options={options}
          handlerActions={handlerActions}
          createOptions={isNew ? undefined : {
            attachment: { type: "view_button", view_id: value.id, button_id: "" },
            target_revision: revision,
          }}
          onChange={(keyboard) => onChange({ ...value, keyboard })}
        />
      </FormGrid>
    </section>
  );
}

function AccessIcon({ kind }: { kind: "everyone" | "members" | "admins" }) {
  const paths = {
    everyone: <><circle cx="8" cy="8" r="5.5" /><path d="M2.5 8h11M8 2.5c1.45 1.5 2.2 3.35 2.2 5.5S9.45 12 8 13.5C6.55 12 5.8 10.15 5.8 8S6.55 4 8 2.5" /></>,
    members: <><circle cx="5.75" cy="5.5" r="2.25" /><circle cx="11.25" cy="6.25" r="1.75" /><path d="M1.9 13.2c.45-2.1 1.82-3.3 3.85-3.3s3.4 1.2 3.85 3.3M9.35 10.15c1.55.08 2.6 1.03 2.95 2.65" /></>,
    admins: <><path d="m8 1.9 4.7 1.9v3.55c0 3.05-1.88 5.18-4.7 6.75-2.82-1.57-4.7-3.7-4.7-6.75V3.8L8 1.9Z" /><path d="m5.75 8.05 1.45 1.45 3.05-3.05" /></>,
  };
  return <svg viewBox="0 0 16 16" focusable="false">{paths[kind]}</svg>;
}

function TextSourceControl({ controlProps, text, templates, onChange, onOpenTemplate, onCreateTemplate }: { controlProps: FormControlProps; text: TextSpec; templates: string[]; onChange(text: TextSpec): void; onOpenTemplate?: (path: string) => void; onCreateTemplate?(suggestedPath: string): void }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const [hasTypedSinceFocus, setHasTypedSinceFocus] = useState(false);
  const [recentTemplates, setRecentTemplates] = useState<string[]>(readRecentTemplates);
  const isTemplate = "template" in text;
  const templateValue = isTemplate ? text.template ?? "" : "";
  const canOpenTemplate = templates.includes(templateValue.trim());
  const visibleTemplates = templates.filter((template) => template.toLowerCase().includes(filter.trim().toLowerCase()));
  const normalizedTemplateValue = templateValue.trim().toLowerCase();
  const query = hasTypedSinceFocus ? templateValue.trim().toLowerCase() : "";
  const availableRecentTemplates = recentTemplates.filter((template) => templates.includes(template));
  const orderedTemplates = query
    ? templates.filter((template) => template.toLowerCase().includes(query) && template.toLowerCase() !== query)
    : [...availableRecentTemplates, ...templates.filter((template) => !availableRecentTemplates.includes(template))]
      .filter((template) => template.toLowerCase() !== normalizedTemplateValue);
  const templateSuggestions = showAllSuggestions ? orderedTemplates : orderedTemplates.slice(0, 5);
  const hasMoreSuggestions = templateSuggestions.length < orderedTemplates.length;
  const chooseTemplateSuggestion = (template: string) => {
    onChange({ template });
    setRecentTemplates((current) => saveRecentTemplates([template, ...current.filter((item) => item !== template)]));
    setActiveSuggestionIndex(-1);
    setShowAllSuggestions(false);
    setSuggestionsOpen(false);
  };

  return <FormControlGroup layout="split" className="text-source">
    <Select {...controlProps} clickOnly ariaLabel="Text source" value={isTemplate ? "template" : "inline"} options={[{ value: "inline", label: "Text" }, { value: "template", label: "Template" }]} onChange={(mode) => onChange(mode === "template" ? { template: "" } : { inline: "" })} />
    {isTemplate
      ? <ResourceDropTarget target={{ type: "template-reference" }} label="Drop template here" className="form-control-group form-control-group--attached text-source__template" onDrop={(resource) => chooseTemplateSuggestion(resource.value)}>
          <input
            aria-label="Template"
            aria-autocomplete="list"
            aria-controls="template-suggestions"
            aria-expanded={suggestionsOpen && templateSuggestions.length > 0}
            aria-activedescendant={activeSuggestionIndex >= 0 ? `template-suggestion-${activeSuggestionIndex}` : undefined}
            value={templateValue}
            placeholder="Template name"
            onFocus={() => { setHasTypedSinceFocus(false); setShowAllSuggestions(false); setSuggestionsOpen(true); }}
            onBlur={() => { setHasTypedSinceFocus(false); setActiveSuggestionIndex(-1); setShowAllSuggestions(false); setSuggestionsOpen(false); }}
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
            onChange={(event) => { onChange({ template: event.target.value }); setHasTypedSinceFocus(true); setActiveSuggestionIndex(-1); setShowAllSuggestions(false); setSuggestionsOpen(true); }}
          />
          {suggestionsOpen && <div id="template-suggestions" className="template-suggestions" role="listbox" aria-label="Template suggestions">
            {templateSuggestions.map((template, index) => <button id={`template-suggestion-${index}`} key={template} type="button" role="option" aria-selected={index === activeSuggestionIndex} className={index === activeSuggestionIndex ? "template-suggestions__item template-suggestions__item--active" : "template-suggestions__item"} onMouseDown={(event) => { event.preventDefault(); chooseTemplateSuggestion(template); }}>{template}</button>)}
            {hasMoreSuggestions && <button type="button" className="template-suggestions__more" aria-label="Show more templates" onMouseDown={(event) => event.preventDefault()} onClick={() => { setActiveSuggestionIndex(-1); setShowAllSuggestions(true); }}><ChevronDownIcon /></button>}
            <button type="button" className="template-suggestions__create" onMouseDown={(event) => event.preventDefault()} onClick={() => { onCreateTemplate?.(canOpenTemplate ? "" : templateValue.trim()); setSuggestionsOpen(false); }}>Create template</button>
          </div>}
          <div className="form-control-group__actions">
            <button type="button" className="text-source__open" aria-label="Open current template" title={canOpenTemplate ? "Open template editor" : "Enter an existing template path to open it"} disabled={!canOpenTemplate} onClick={() => onOpenTemplate?.(templateValue.trim())}><OpenTemplateIcon /></button>
            <button type="button" className="text-source__browse" aria-label="Browse templates" title="Browse templates" onClick={() => { setSuggestionsOpen(false); setFilter(""); setPickerOpen(true); }}><FolderIcon /></button>
          </div>
        </ResourceDropTarget>
      : <AutoGrowTextarea value={text.inline} onChange={(inline) => onChange({ inline })} />}
    <OverlayDialog open={pickerOpen} label="Choose template" onClose={() => setPickerOpen(false)} className="template-picker">
        <header><div><p className="eyebrow">Templates</p><h3>Choose a template</h3></div><button type="button" className="button--icon" aria-label="Close template picker" onClick={() => setPickerOpen(false)}>×</button></header>
        <input aria-label="Filter templates" autoFocus value={filter} placeholder="Filter templates" onChange={(event) => setFilter(event.target.value)} />
        <div className="template-picker__list">
          {visibleTemplates.length ? visibleTemplates.map((template) => <button key={template} type="button" className={template === text.template ? "template-picker__item template-picker__item--selected" : "template-picker__item"} onClick={() => { onChange({ template }); setPickerOpen(false); }}>{template}</button>) : <p className="muted">No matching templates.</p>}
        </div>
    </OverlayDialog>
  </FormControlGroup>;
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
    const minimumHeight = Number.parseFloat(window.getComputedStyle(textarea).minHeight) || 32;
    textarea.style.height = "auto";
    const nextHeight = Math.max(minimumHeight, Math.min(textarea.scrollHeight, 180));
    textarea.style.height = `${currentHeight}px`;
    const frame = window.requestAnimationFrame(() => { textarea.style.height = `${nextHeight}px`; });
    return () => window.cancelAnimationFrame(frame);
  }, [value]);
  return <textarea ref={textareaRef} className="text-source__inline" aria-label="Inline text" value={value} rows={1} placeholder="Write the message text" onChange={(event) => onChange(event.target.value)} />;
}
