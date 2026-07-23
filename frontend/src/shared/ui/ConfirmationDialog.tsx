import { OverlayDialog } from "./OverlayDialog";
import { createPortal } from "react-dom";

/**
 * Use this dialog for every destructive or irreversible action in Studio.
 * Do not use window.confirm: it bypasses the app's focus handling and visual language.
 */
export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm(): void;
  onCancel(): void;
}) {
  if (!open) return null;
  return createPortal(<OverlayDialog open label={title} onClose={onCancel} className="confirmation-dialog">
    <header className="confirmation-dialog__header">
      <span className="confirmation-dialog__eyebrow">Confirmation required</span>
      <h2>{title}</h2>
    </header>
    <p className="confirmation-dialog__description">{description}</p>
    <footer className="confirmation-dialog__actions">
      <button type="button" className="button--secondary" autoFocus onClick={onCancel}>Cancel</button>
      <button type="button" className="button--danger" onClick={onConfirm}>{confirmLabel}</button>
    </footer>
  </OverlayDialog>, document.body);
}
