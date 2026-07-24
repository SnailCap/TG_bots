import { OverlayDialog } from "./OverlayDialog";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

/**
 * Use this dialog for every destructive or irreversible action in Studio.
 * Do not use window.confirm: it bypasses the app's focus handling and visual language.
 */
export function ConfirmationDialog({
  open,
  title,
  description,
  children,
  confirmLabel,
  confirmDisabled = false,
  tone = "danger",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  children?: ReactNode;
  confirmLabel: string;
  confirmDisabled?: boolean;
  tone?: "danger" | "primary";
  onConfirm(): void;
  onCancel(): void;
}) {
  if (!open) return null;
  return createPortal(<OverlayDialog open label={title} onClose={onCancel} className="confirmation-dialog">
    <header className="confirmation-dialog__header">
      <span className="confirmation-dialog__eyebrow">Confirmation required</span>
      <h2>{title}</h2>
    </header>
    {description && <p className="confirmation-dialog__description">{description}</p>}
    {children}
    <footer className="confirmation-dialog__actions">
      <button type="button" className="button--secondary" autoFocus onClick={onCancel}>Cancel</button>
      <button type="button" className={tone === "danger" ? "button--danger" : undefined} disabled={confirmDisabled} onClick={onConfirm}>{confirmLabel}</button>
    </footer>
  </OverlayDialog>, document.body);
}
