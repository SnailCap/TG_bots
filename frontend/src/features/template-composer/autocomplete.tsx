import type { CSSProperties, MouseEvent } from "react";

import type { ContextFieldDefinition } from "./context-catalog";

export function ContextAutocomplete({
  fields,
  activeIndex,
  position,
  onChoose,
}: {
  fields: readonly ContextFieldDefinition[];
  activeIndex: number;
  position: { left: number; top: number };
  onChoose(field: ContextFieldDefinition): void;
}) {
  const grouped = groupFields(fields);
  return (
    <div
      className="context-autocomplete"
      role="listbox"
      aria-label="Context fields"
      style={{ "--autocomplete-left": `${position.left}px`, "--autocomplete-top": `${position.top}px` } as CSSProperties}
    >
      {fields.length === 0 ? <div className="context-autocomplete__empty">No matching fields</div> : grouped.map(([group, groupFields]) => (
        <section className="context-autocomplete__group" key={group}>
          <div className="context-autocomplete__group-label">{group}</div>
          {groupFields.map(({ field, index }) => (
            <button
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              className={index === activeIndex ? "context-autocomplete__option context-autocomplete__option--active" : "context-autocomplete__option"}
              key={field.id}
              onMouseDown={(event: MouseEvent<HTMLButtonElement>) => {
                event.preventDefault();
                onChoose(field);
              }}
            >
              <UserIcon />
              <span><strong>{field.label}</strong><small>{field.path}</small></span>
            </button>
          ))}
        </section>
      ))}
    </div>
  );
}

function groupFields(fields: readonly ContextFieldDefinition[]): [string, { field: ContextFieldDefinition; index: number }[]][] {
  const groups = new Map<string, { field: ContextFieldDefinition; index: number }[]>();
  fields.forEach((field, index) => groups.set(field.group, [...(groups.get(field.group) ?? []), { field, index }]));
  return [...groups.entries()];
}

export function UserIcon() {
  return <svg className="context-user-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="5.25" r="2.45" /><path d="M3.5 13c.35-2.35 2.02-3.7 4.5-3.7s4.15 1.35 4.5 3.7" /></svg>;
}

