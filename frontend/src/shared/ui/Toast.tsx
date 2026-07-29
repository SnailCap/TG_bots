import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

export const DEFAULT_TOAST_TIMEOUT_MS = 5_000;

export function Toast({
  message,
  tone,
  onDismiss,
  action,
  timeoutMs = DEFAULT_TOAST_TIMEOUT_MS,
}: {
  message: string;
  tone: "error" | "notice";
  onDismiss(): void;
  action?: ReactNode;
  timeoutMs?: number;
}) {
  const dismissRef = useRef(onDismiss);

  useEffect(() => {
    dismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    const timeout = window.setTimeout(() => dismissRef.current(), timeoutMs);
    return () => window.clearTimeout(timeout);
  }, [message, timeoutMs]);

  const content = <section className={`toast toast--${tone}`} role={tone === "error" ? "alert" : "status"} aria-live={tone === "error" ? "assertive" : "polite"}>
    <span>{message}</span>
    {action}
    <button type="button" className="button--icon toast__dismiss" aria-label={`Dismiss ${tone === "error" ? "error" : "notice"}`} onClick={onDismiss}><X aria-hidden="true" /></button>
  </section>;
  return createPortal(content, document.body);
}
