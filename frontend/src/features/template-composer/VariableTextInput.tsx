import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
  type InputHTMLAttributes,
  type KeyboardEvent,
} from "react";

import { ContextAutocomplete } from "./autocomplete";
import {
  searchContextFields,
  SYSTEM_CONTEXT_FIELDS,
  type ContextFieldDefinition,
} from "./context-catalog";

type Trigger = {
  start: number;
  end: number;
  query: string;
  activeIndex: number;
};

export const VariableTextInput = forwardRef<HTMLInputElement, {
  value: string;
  fields?: readonly ContextFieldDefinition[];
  onValueChange(value: string): void;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">>(
  function VariableTextInput(
    { value, fields = SYSTEM_CONTEXT_FIELDS, onValueChange, onKeyDown, onKeyUp, onBlur, ...props },
    forwardedRef,
  ) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [trigger, setTrigger] = useState<Trigger | null>(null);
    const suggestions = trigger ? searchContextFields(trigger.query, fields) : [];
    useImperativeHandle(forwardedRef, () => inputRef.current as HTMLInputElement);

    useEffect(() => {
      if (!trigger) return;
      setTrigger((current) => {
        if (!current) return null;
        const activeIndex = Math.min(current.activeIndex, Math.max(suggestions.length - 1, 0));
        return activeIndex === current.activeIndex ? current : { ...current, activeIndex };
      });
    }, [fields, trigger?.query, suggestions.length]);

    const updateTrigger = (nextValue = value, cursor = inputRef.current?.selectionStart) => {
      if (cursor === null || cursor === undefined) {
        setTrigger(null);
        return;
      }
      const match = nextValue.slice(0, cursor).match(/\$([^\s{}]*)$/u);
      if (!match || match.index === undefined) {
        setTrigger(null);
        return;
      }
      const start = match.index;
      setTrigger((current) => ({
        start,
        end: cursor,
        query: match[1],
        activeIndex: current && current.start === start ? current.activeIndex : 0,
      }));
    };

    const choose = (field: ContextFieldDefinition) => {
      if (!trigger) return;
      const token = `{{ ${field.path} }}`;
      const next = `${value.slice(0, trigger.start)}${token}${value.slice(trigger.end)}`;
      const cursor = trigger.start + token.length;
      onValueChange(next);
      setTrigger(null);
      queueMicrotask(() => {
        inputRef.current?.focus();
        inputRef.current?.setSelectionRange(cursor, cursor);
      });
    };

    const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
      const next = event.currentTarget.value;
      const cursor = event.currentTarget.selectionStart;
      onValueChange(next);
      updateTrigger(next, cursor);
    };

    const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
      onKeyDown?.(event);
      if (event.defaultPrevented || !trigger) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setTrigger(null);
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        setTrigger((current) => current ? {
          ...current,
          activeIndex: suggestions.length
            ? (current.activeIndex + direction + suggestions.length) % suggestions.length
            : 0,
        } : null);
        return;
      }
      if (event.key === "Enter" && suggestions.length) {
        event.preventDefault();
        choose(suggestions[trigger.activeIndex] ?? suggestions[0]);
      }
    };

    return (
      <span className="variable-text-input">
        <input
          {...props}
          ref={inputRef}
          value={value}
          onChange={handleChange}
          onClick={() => updateTrigger()}
          onKeyDown={handleKeyDown}
          onKeyUp={(event) => {
            onKeyUp?.(event);
            if (!event.defaultPrevented && !["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(event.key)) {
              updateTrigger();
            }
          }}
          onBlur={(event) => {
            onBlur?.(event);
            if (!event.defaultPrevented) setTrigger(null);
          }}
        />
        {trigger ? (
          <ContextAutocomplete
            fields={suggestions}
            activeIndex={trigger.activeIndex}
            position={{ left: 0, top: (inputRef.current?.offsetHeight ?? 32) + 4 }}
            onChoose={choose}
          />
        ) : null}
      </span>
    );
  },
);
