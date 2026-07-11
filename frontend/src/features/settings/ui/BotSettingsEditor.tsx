import { useEffect, useMemo, useState } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import type { ProjectTreeNode } from "../../../entities/project/model/types";
import { toApiError } from "../../../shared/api/client";
import { studioApi } from "../../../shared/api/studioApi";
import type { BotSettings, TokenValidationResult } from "../../../shared/api/types";
import styles from "./BotSettingsEditor.module.css";

function collectFlows(nodes: ProjectTreeNode[]): ProjectTreeNode[] {
  return nodes.flatMap((node) => (node.kind === "flow" ? [node] : collectFlows(node.children)));
}

export function BotSettingsEditor() {
  const studio = useStudio();
  const projectId = studio.currentProject?.id;
  const [settings, setSettings] = useState<BotSettings | null>(null);
  const [projectName, setProjectName] = useState(studio.currentProject?.name ?? "");
  const [token, setToken] = useState("");
  const [tokenResult, setTokenResult] = useState<TokenValidationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const flows = useMemo(() => collectFlows(studio.tree), [studio.tree]);

  useEffect(() => {
    setProjectName(studio.currentProject?.name ?? "");
  }, [studio.currentProject?.name]);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    setLoading(true);
    void studioApi
      .getSettings(projectId)
      .then((loaded) => active && setSettings(loaded))
      .catch((reason) => active && setError(toApiError(reason).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [projectId]);

  async function saveSettings() {
    if (!projectId || !settings) return;
    setSaving(true);
    setError(null);
    try {
      const [saved] = await Promise.all([
        studioApi.saveSettings(projectId, settings),
        projectName.trim() && projectName.trim() !== studio.currentProject?.name
          ? studio.renameCurrentProject(projectName.trim())
          : Promise.resolve(),
      ]);
      setSettings(saved);
    } catch (reason) {
      setError(toApiError(reason).message);
    } finally {
      setSaving(false);
    }
  }

  async function saveToken() {
    if (!projectId || !token.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const result = await studioApi.saveToken(projectId, token.trim());
      setTokenResult(result);
      setToken("");
      setSettings((value) => (value ? { ...value, tokenConfigured: result.valid || value.tokenConfigured, bot: result.bot ?? value.bot } : value));
    } catch (reason) {
      setError(toApiError(reason).message);
    } finally {
      setSaving(false);
    }
  }

  async function validateToken() {
    if (!projectId) return;
    setSaving(true);
    setError(null);
    try {
      const result = await studioApi.validateToken(projectId);
      setTokenResult(result);
      setSettings((value) => (value ? { ...value, bot: result.bot ?? value.bot } : value));
    } catch (reason) {
      setError(toApiError(reason).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className={styles.message}>Loading bot settings…</div>;
  if (!settings) return <div className={styles.message}>Unable to load settings: {error ?? "Unknown error"}</div>;

  const bot = tokenResult?.bot ?? settings.bot;
  return (
    <section className={styles.page} aria-label="Bot settings">
      <header>
        <div>
          <span>Project configuration</span>
          <h1>Bot Settings</h1>
        </div>
        <button className={styles.save} disabled={saving} onClick={() => void saveSettings()}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </header>
      <div className={styles.content}>
        {error && <div className={styles.error}>{error}</div>}
        <section className={styles.card}>
          <div className={styles.cardTitle}>
            <span>01</span>
            <div><strong>Project</strong><small>Portable bot metadata</small></div>
          </div>
          <label>
            Project name
            <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
          </label>
          <label>
            Project folder
            <div className={styles.pathRow}>
              <input value={studio.currentProject?.path ?? ""} readOnly />
              <button type="button" onClick={() => studio.currentProject?.path && window.studioDesktop?.revealPath(studio.currentProject.path)}>
                Reveal
              </button>
            </div>
          </label>
        </section>

        <section className={styles.card}>
          <div className={styles.cardTitle}>
            <span>02</span>
            <div><strong>Telegram connection</strong><small>The token is stored in the operating system keyring</small></div>
          </div>
          <div className={styles.tokenStatus} data-valid={tokenResult?.valid ?? settings.tokenConfigured}>
            <span />
            {tokenResult
              ? tokenResult.valid ? "Token is valid" : tokenResult.error ?? "Token validation failed"
              : settings.tokenConfigured ? "A token is securely configured" : "No token configured"}
          </div>
          <label>
            Bot API token
            <div className={styles.pathRow}>
              <input
                type="password"
                value={token}
                autoComplete="new-password"
                placeholder={settings.tokenConfigured ? "Enter a replacement token" : "123456:ABC…"}
                onChange={(event) => setToken(event.target.value)}
              />
              <button type="button" disabled={!token.trim() || saving} onClick={() => void saveToken()}>
                Save securely
              </button>
              <button type="button" disabled={!settings.tokenConfigured || saving} onClick={() => void validateToken()}>
                Validate
              </button>
            </div>
          </label>
          {bot && (
            <div className={styles.botIdentity}>
              <div>{(bot.displayName || bot.username || "B").slice(0, 1).toUpperCase()}</div>
              <span><strong>{bot.displayName ?? "Telegram bot"}</strong><small>{bot.username ? `@${bot.username}` : `Bot ID ${bot.id}`}</small></span>
              <code>{bot.id}</code>
            </div>
          )}
        </section>

        <section className={styles.card}>
          <div className={styles.cardTitle}>
            <span>03</span>
            <div><strong>Conversation entry</strong><small>Controls `/start` and the initial flow</small></div>
          </div>
          <div className={styles.grid2}>
            <label>
              Start flow
              <select value={settings.startFlowId ?? ""} onChange={(event) => setSettings({ ...settings, startFlowId: event.target.value || null })}>
                <option value="">Select a start flow…</option>
                {flows.map((flow) => <option key={flow.id} value={flow.id}>{flow.name}</option>)}
              </select>
            </label>
            <label>
              `/start` behavior
              <select value={settings.startBehavior ?? "reset"} onChange={(event) => setSettings({ ...settings, startBehavior: event.target.value as BotSettings["startBehavior"] })}>
                <option value="reset">Reset current flow</option>
                <option value="resume">Resume the saved session</option>
              </select>
            </label>
          </div>
        </section>
      </div>
    </section>
  );
}
