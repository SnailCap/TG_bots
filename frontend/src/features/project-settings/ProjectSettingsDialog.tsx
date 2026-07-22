import { useEffect, useId, useState, type FormEvent } from "react";

import { OverlayDialog } from "../../shared/ui/OverlayDialog";
import type { ProjectSettings } from "../../studio/api";

export function ProjectSettingsDialog({ open, settings, loading, saving, onClose, onSave, onClear }: {
  open: boolean;
  settings: ProjectSettings | null;
  loading: boolean;
  saving: boolean;
  onClose(): void;
  onSave(token: string): Promise<void>;
  onClear(): Promise<void>;
}) {
  const tokenId = useId();
  const [token, setToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (!open) return;
    setToken("");
    setShowToken(false);
    setFormError("");
  }, [open]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token.trim()) {
      setFormError("Enter a Telegram bot token before saving.");
      return;
    }
    try {
      setFormError("");
      await onSave(token);
      setToken("");
      setShowToken(false);
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not save the Telegram bot token.");
    }
  };

  const clear = async () => {
    try {
      setFormError("");
      await onClear();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not clear the Telegram bot token.");
    }
  };

  const configured = Boolean(settings?.telegram_bot_token_configured);
  return (
    <OverlayDialog open={open} label="Project settings" onClose={onClose} className="project-settings-dialog">
      <header className="project-settings-dialog__header">
        <h2>Settings</h2>
        <button type="button" className="project-settings-dialog__close" aria-label="Close settings" title="Close settings" onClick={onClose}><CloseIcon /></button>
      </header>
      <form className="project-settings-dialog__form" onSubmit={(event) => void submit(event)}>
            <div className="project-settings-field">
              <label htmlFor={tokenId}>Bot token:</label>
              <div className="project-settings-field__control">
                <input id={tokenId} type={showToken ? "text" : "password"} autoComplete="new-password" spellCheck={false} value={token} placeholder={configured ? "New token" : "123456:ABC…"} onChange={(event) => { setToken(event.target.value); setFormError(""); }} />
                <button type="button" className="project-settings-field__visibility" aria-label={showToken ? "Hide bot token" : "Show bot token"} title={showToken ? "Hide token" : "Show token"} onClick={() => setShowToken((visible) => !visible)}><VisibilityIcon visible={showToken} /></button>
              </div>
            </div>
            {formError && <p className="project-settings-dialog__error" role="alert">{formError}</p>}
            <footer className="project-settings-dialog__actions">
              <button type="button" className="button--secondary" disabled={loading || saving || !configured} onClick={() => void clear()}>Clear token</button>
              <button type="submit" disabled={loading || saving || !token.trim()}>{saving ? "Saving…" : "Save token"}</button>
            </footer>
          </form>
    </OverlayDialog>
  );
}

function CloseIcon() {
  return <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m5 5 6 6m0-6-6 6" /></svg>;
}

function VisibilityIcon({ visible }: { visible: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">{visible ? <><path d="M1.8 8S4.1 4.5 8 4.5 14.2 8 14.2 8 11.9 11.5 8 11.5 1.8 8 1.8 8Z" /><path d="m2.15 2.15 11.7 11.7" /></> : <><path d="M1.8 8S4.1 4.5 8 4.5 14.2 8 14.2 8 11.9 11.5 8 11.5 1.8 8 1.8 8Z" /><circle cx="8" cy="8" r="1.8" /></>}</svg>;
}
