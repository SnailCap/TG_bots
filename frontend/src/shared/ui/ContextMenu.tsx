import { useEffect, useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

export type ContextMenuItem = {
  id: string;
  label: string;
  icon?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
  onSelect(): void;
};

export function ContextMenu({ x, y, label, items, onClose }: {
  x: number;
  y: number;
  label: string;
  items: ContextMenuItem[];
  onClose(): void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null);

  useLayoutEffect(() => {
    const menu = menuRef.current;
    if (!menu) return;
    const margin = 8;
    const rect = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(margin, Math.min(x, window.innerWidth - rect.width - margin))}px`;
    menu.style.top = `${Math.max(margin, Math.min(y, window.innerHeight - rect.height - margin))}px`;
    menu.querySelector<HTMLButtonElement>('button[role="menuitem"]:not(:disabled)')?.focus();
  }, [x, y]);

  useEffect(() => {
    const close = () => onClose();
    window.addEventListener("pointerdown", close);
    window.addEventListener("blur", close);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("pointerdown", close);
      window.removeEventListener("blur", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
      if (returnFocusRef.current?.isConnected) returnFocusRef.current.focus();
    };
  }, [onClose]);

  const moveFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    const buttons = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>('button[role="menuitem"]:not(:disabled)') ?? []);
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "Tab") {
      onClose();
      return;
    }
    if (!buttons.length || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "Home") buttons[0].focus();
    else if (event.key === "End") buttons.at(-1)?.focus();
    else if (event.key === "ArrowDown") buttons[(current + 1 + buttons.length) % buttons.length].focus();
    else buttons[(current - 1 + buttons.length) % buttons.length].focus();
  };

  return createPortal(
    <div
      ref={menuRef}
      className="context-menu"
      role="menu"
      aria-label={label}
      style={{ left: x, top: y }}
      onContextMenu={(event) => event.preventDefault()}
      onPointerDown={(event) => event.stopPropagation()}
      onKeyDown={moveFocus}
    >
      {items.map((item) => <button
        type="button"
        role="menuitem"
        className={[
          "context-menu__item",
          item.danger ? "context-menu__item--danger" : "",
          item.icon ? "" : "context-menu__item--iconless",
        ].filter(Boolean).join(" ")}
        disabled={item.disabled}
        key={item.id}
        onClick={() => { item.onSelect(); onClose(); }}
      >
        {item.icon && <span className="context-menu__icon" aria-hidden="true">{item.icon}</span>}
        <span>{item.label}</span>
      </button>)}
    </div>,
    document.body,
  );
}
