import type { CSSProperties, MouseEvent } from "react";
import { UserRound } from "lucide-react";

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
  return <UserRound className="context-user-icon" aria-hidden="true" />;
}
