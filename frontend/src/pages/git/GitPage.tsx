import { useCallback, useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { ConfirmationDialog } from "../../shared/ui/ConfirmationDialog";
import type {
  GitChange,
  GitChanges,
  GitCommit,
  GitPublishInput,
  GitStatus,
  StudioApiError,
} from "../../studio/api";
import {
  loadGitHubToken,
  openGitHubUrl,
  saveGitHubToken,
} from "../../studio/desktop";
import type { StudioPageContext } from "../studio/studio-page-context";


type Operation = "fetch" | "sync" | "push" | "publish" | "connect" | null;
type SetupMode = "existing" | "new";

const OPERATION_LABELS: Record<Exclude<Operation, null>, string> = {
  fetch: "Checking GitHub…",
  sync: "Getting the latest project…",
  push: "Validating and pushing…",
  publish: "Validating and publishing…",
  connect: "Connecting the project…",
};

export function GitPage() {
  const { api, workspace, tabs, saveAll } = useOutletContext<StudioPageContext>();
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [changes, setChanges] = useState<GitChanges>({ changes: [], suggested_message: "" });
  const [history, setHistory] = useState<GitCommit[]>([]);
  const [operation, setOperation] = useState<Operation>(null);
  const [error, setError] = useState("");
  const [errorDetails, setErrorDetails] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [showPush, setShowPush] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [showDisconnect, setShowDisconnect] = useState(false);
  const [commitMessage, setCommitMessage] = useState("");

  const loadConnectedData = useCallback(async (nextStatus?: GitStatus) => {
    const current = nextStatus ?? await api.gitStatus(workspace.project_id);
    setStatus(current);
    if (!current.connected) {
      setChanges({ changes: [], suggested_message: "" });
      setHistory([]);
      return;
    }
    const [nextChanges, nextHistory] = await Promise.all([
      api.gitChanges(workspace.project_id),
      api.gitHistory(workspace.project_id),
    ]);
    setChanges(nextChanges);
    setHistory(nextHistory);
    setCommitMessage((value) => value || nextChanges.suggested_message);
  }, [api, workspace.project_id]);

  useEffect(() => {
    let cancelled = false;
    void api.gitStatus(workspace.project_id).then(async (initial) => {
      if (cancelled) return;
      await loadConnectedData(initial);
      if (!initial.connected) return;
      try {
        const token = await loadGitHubToken();
        const fetched = await api.gitFetch(workspace.project_id, token);
        if (!cancelled) await loadConnectedData(fetched);
      } catch {
        // Background checks never interrupt editing; an explicit action surfaces the error.
      }
    }).catch((caught: unknown) => {
      if (!cancelled) setError(messageFor(caught));
    });
    return () => { cancelled = true; };
  }, [api, loadConnectedData, workspace.project_id]);

  const run = useCallback(async <T,>(
    kind: Exclude<Operation, null>,
    action: (token: string | undefined) => Promise<T>,
    success: string,
  ): Promise<T | undefined> => {
    setOperation(kind);
    setError("");
    setErrorDetails([]);
    setNotice("");
    try {
      if (tabs.some((tab) => tab.dirty)) await saveAll();
      const result = await action(await loadGitHubToken());
      await loadConnectedData();
      setNotice(success);
      return result;
    } catch (caught) {
      setError(messageFor(caught));
      setErrorDetails(detailsFor(caught));
      return undefined;
    } finally {
      setOperation(null);
    }
  }, [loadConnectedData, saveAll, tabs]);

  if (!status) {
    return <main className="git-page git-page--center">{error
      ? <EmptyState icon={<GitMark />} title="Git status is unavailable" text={error} action={<button type="button" onClick={() => { setError(""); void loadConnectedData().catch((caught: unknown) => setError(messageFor(caught))); }}>Try again</button>} />
      : <div className="git-loading" role="status"><Spinner />Loading project Git status…</div>}</main>;
  }

  if (!status.git_installed) {
    return <main className="git-page git-page--center"><EmptyState icon={<GitMark />} title="Git is required" text="Install Git for Windows, then restart Studio. Your project files have not been changed." action={<button type="button" onClick={() => void openGitHubUrl("https://github.com/git-for-windows/git/releases/latest")}>Open download page</button>} /></main>;
  }

  if (!status.connected) {
    return <main className="git-page git-page--setup"><GitSetup busy={operation === "connect"} onConnect={async (input, token) => {
      try {
        if (token) await saveGitHubToken(token);
      } catch (caught) {
        setError(messageFor(caught));
        return;
      }
      await run("connect", (savedToken) => input.mode === "existing"
        ? api.gitConnect(workspace.project_id, { repository: input.repository, development_branch: input.development, production_branch: input.production, token: savedToken })
        : api.gitCreateRepository(workspace.project_id, { repository: input.repository, visibility: input.visibility, development_branch: input.development, production_branch: input.production, token: savedToken }), "Project connected to GitHub.");
    }} error={error} /></main>;
  }

  const tone = status.sync_state ?? "changes";
  const localCount = status.local_changes ?? 0;
  const behind = status.behind ?? 0;
  const ahead = status.ahead ?? 0;
  const busy = operation !== null;

  return (
    <main className="git-page">
      <header className="git-hero">
        <div className="git-hero__identity">
          <div className={`git-repo-mark git-repo-mark--${tone}`}><GitMark /></div>
          <div>
            <div className="git-hero__eyebrow"><span className={`git-status-dot git-status-dot--${tone}`} />{syncLabel(status)}</div>
            <h1>{status.repository}</h1>
            <p>{status.account} on GitHub · local branch <code>{status.branch}</code></p>
          </div>
        </div>
        <button className="git-icon-button" type="button" aria-label="Refresh Git status" title="Check GitHub now" disabled={busy} onClick={() => void run("fetch", (token) => api.gitFetch(workspace.project_id, token), "GitHub status updated.")}><RefreshIcon /></button>
        <div className="git-branch-line" aria-label={`Development branch ${status.development_branch}, production branch ${status.production_branch}`}>
          <div><span className="git-branch-node git-branch-node--dev" /><small>Shared work</small><strong>{status.development_branch}</strong></div>
          <span className="git-branch-line__track"><i /></span>
          <div><span className="git-branch-node git-branch-node--production" /><small>Live release</small><strong>{status.production_branch}</strong></div>
        </div>
        <dl className="git-facts">
          <Fact label="Local work" value={localCount ? `${localCount} change${localCount === 1 ? "" : "s"}` : "Clean"} tone={localCount ? "warning" : "success"} />
          <Fact label="GitHub" value={behind ? `${behind} commit${behind === 1 ? "" : "s"} available` : "Up to date"} tone={behind ? "warning" : "success"} />
          <Fact label="Position" value={ahead || behind ? `${ahead} ahead · ${behind} behind` : "In sync"} />
          <Fact label="Last publish" value={publicationLabel(status)} />
        </dl>
      </header>

      {behind > 0 && <div className="git-update-banner"><span><DownloadIcon />A newer project version is available.</span><button type="button" disabled={busy || localCount > 0} onClick={() => void run("sync", (token) => api.gitSync(workspace.project_id, token), "Project synced with GitHub.")}>Sync now</button></div>}
      {error && <Message tone="error" title={error} details={errorDetails} />}
      {notice && <Message tone="success" title={notice} />}
      {operation && <div className="git-operation" role="status" aria-live="polite"><Spinner />{OPERATION_LABELS[operation]}</div>}

      <section className="git-actions" aria-label="Git workflow">
        <WorkflowAction icon={<DownloadIcon />} title="Sync" text="Get the latest changes from your shared development branch." disabled={busy || localCount > 0} onClick={() => void run("sync", (token) => api.gitSync(workspace.project_id, token), "Project synced with GitHub.")} />
        <WorkflowAction icon={<UploadIcon />} title="Push" text="Save your local changes for the team in the development branch." disabled={busy || behind > 0 || localCount === 0} onClick={() => { setCommitMessage(changes.suggested_message); setShowPush(true); }} />
        <WorkflowAction icon={<RocketIcon />} title="Publish" text="Release the tested development version to the production branch." primary disabled={busy || localCount > 0 || behind > 0 || ahead > 0} onClick={() => setShowPublish(true)} />
      </section>

      <div className="git-content-grid">
        <ChangesPanel changes={changes.changes} />
        <HistoryPanel commits={history} repository={status.repository ?? ""} />
      </div>

      <footer className="git-page__footer">
        <span>Remote <code>{status.remote_name}</code> · credentials stay in protected system storage</span>
        <button type="button" className="git-link-button" onClick={() => setShowDisconnect(true)}>Disconnect</button>
      </footer>

      <ConfirmationDialog open={showDisconnect} title="Disconnect this project from GitHub?" description="Studio will remove the configured remote from this project. Local files, commits, and your protected GitHub sign-in remain available." confirmLabel={operation === "connect" ? "Disconnecting…" : "Disconnect"} confirmDisabled={operation === "connect"} onCancel={() => setShowDisconnect(false)} onConfirm={() => void (async () => {
          setOperation("connect");
          try {
            await api.gitDisconnect(workspace.project_id);
            await loadConnectedData();
            setShowDisconnect(false);
          } catch (caught) {
            setError(messageFor(caught));
          } finally {
            setOperation(null);
          }
        })()} />

      {showPush && <PushDialog changes={changes.changes} message={commitMessage} busy={operation === "push"} onMessage={setCommitMessage} onCancel={() => setShowPush(false)} onPush={() => void run("push", (token) => api.gitPush(workspace.project_id, commitMessage, token), "Changes pushed for the team.").then((result) => { if (result) setShowPush(false); })} />}
      <PublishDialog open={showPublish} status={status} busy={operation === "publish"} onCancel={() => setShowPublish(false)} onPublish={(payload) => void run("publish", (token) => api.gitPublish(workspace.project_id, { ...payload, token }), "Production branch published.").then((result) => { if (result) setShowPublish(false); })} />
    </main>
  );
}

function GitSetup({ busy, error, onConnect }: { busy: boolean; error: string; onConnect(input: { mode: SetupMode; repository: string; visibility: "private" | "public"; development: string; production: string }, token: string): Promise<void> }) {
  const [mode, setMode] = useState<SetupMode>("existing");
  const [repository, setRepository] = useState("");
  const [visibility, setVisibility] = useState<"private" | "public">("private");
  const [development, setDevelopment] = useState("dev");
  const [production, setProduction] = useState("production");
  const [token, setToken] = useState("");
  const valid = repository.trim() && token.trim() && development.trim() && production.trim() && development !== production;
  return <section className="git-setup" aria-labelledby="git-setup-title">
    <div className="git-setup__intro"><div className="git-repo-mark"><GitMark /></div><p className="eyebrow">Team workflow</p><h1 id="git-setup-title">Connect this bot to GitHub</h1><p>Share project files, keep everyone up to date, and publish a tested production branch without using the terminal.</p></div>
    <div className="git-setup__card">
      <div className="git-segmented" role="tablist" aria-label="Repository setup">
        <button type="button" role="tab" aria-selected={mode === "existing"} onClick={() => setMode("existing")}>Existing repository</button>
        <button type="button" role="tab" aria-selected={mode === "new"} onClick={() => setMode("new")}>Create new</button>
      </div>
      {error && <Message tone="error" title={error} />}
      <label htmlFor="git-repository"><span>{mode === "existing" ? "Repository" : "Repository name"}</span><input id="git-repository" value={repository} onChange={(event) => setRepository(event.target.value)} placeholder={mode === "existing" ? "owner/my-family-bot" : "my-family-bot"} /></label>
      {mode === "new" && <fieldset className="git-radio-group"><legend>Visibility</legend><label><input type="radio" checked={visibility === "private"} onChange={() => setVisibility("private")} />Private</label><label><input type="radio" checked={visibility === "public"} onChange={() => setVisibility("public")} />Public</label></fieldset>}
      <div className="git-form-row"><label htmlFor="git-development"><span>Shared branch</span><input id="git-development" value={development} onChange={(event) => setDevelopment(event.target.value)} /></label><label htmlFor="git-production"><span>Production branch</span><input id="git-production" value={production} onChange={(event) => setProduction(event.target.value)} /></label></div>
      <label htmlFor="git-token"><span>GitHub personal access token</span><input id="git-token" aria-label="GitHub personal access token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Stored in protected system storage" /><small>Use a fine-grained token with access to this repository. It is never saved in the bot project.</small></label>
      <div className="git-setup__actions"><button type="button" className="button--secondary" onClick={() => void openGitHubUrl("https://github.com/settings/personal-access-tokens/new")}>Create token on GitHub</button><button type="button" disabled={!valid || busy} onClick={() => void onConnect({ mode, repository: repository.trim(), visibility, development: development.trim(), production: production.trim() }, token.trim())}>{busy ? "Connecting…" : mode === "existing" ? "Connect project" : "Create and connect"}</button></div>
    </div>
  </section>;
}

function ChangesPanel({ changes }: { changes: GitChange[] }) {
  return <section className="git-panel git-changes-panel"><header><div><p className="eyebrow">Working copy</p><h2>Changes <span>{changes.length}</span></h2></div></header>{changes.length ? <div className="git-change-list">{changes.map((change) => <details key={`${change.status}:${change.path}`} className="git-change"><summary><ChangeBadge status={change.status} /><span><strong>{change.summary}</strong><small>{change.path}</small></span><ChevronIcon /></summary>{change.binary ? <p className="git-diff-empty">Binary file preview is unavailable.</p> : change.diff ? <DiffPreview diff={change.diff} /> : <p className="git-diff-empty">{change.status === "untracked" ? "New file. It will be included in Push after the safety check." : "No text diff available."}</p>}</details>)}</div> : <EmptyPanel title="No local changes" text="This project matches your latest local commit." />}</section>;
}

function HistoryPanel({ commits, repository }: { commits: GitCommit[]; repository: string }) {
  return <section className="git-panel git-history-panel"><header><div><p className="eyebrow">Shared timeline</p><h2>History</h2></div></header>{commits.length ? <ol className="git-history">{commits.map((commit, index) => <li key={commit.hash} className={commit.published ? "git-history__item git-history__item--published" : "git-history__item"}><span className="git-history__node" /><div><strong>{commit.message}</strong><p>{commit.author} · {relativeDate(commit.authored_at)}</p><div><code>{commit.short_hash}</code><span>{commit.published ? "Published" : index === 0 ? "Latest development" : "Development"}</span>{repository && <button type="button" aria-label={`Open commit ${commit.short_hash} on GitHub`} onClick={() => void openGitHubUrl(commit.url ?? `https://github.com/${repository}/commit/${commit.hash}`)}><ExternalIcon /></button>}</div></div></li>)}</ol> : <EmptyPanel title="No commits yet" text="Your first Push will start the project history." />}</section>;
}

function PushDialog({ changes, message, busy, onMessage, onCancel, onPush }: { changes: GitChange[]; message: string; busy: boolean; onMessage(value: string): void; onCancel(): void; onPush(): void }) {
  return <div className="git-modal-layer" role="presentation"><section className="git-modal" role="dialog" aria-modal="true" aria-labelledby="git-push-title"><header><p className="eyebrow">Share with the team</p><h2 id="git-push-title">Push {changes.length} changed file{changes.length === 1 ? "" : "s"}</h2></header><div className="git-modal__body"><ul className="git-preview-list">{changes.slice(0, 8).map((change) => <li key={change.path}><ChangeBadge status={change.status} /><span>{change.path}</span></li>)}</ul><label><span>Commit message</span><input autoFocus value={message} maxLength={240} onChange={(event) => onMessage(event.target.value)} /></label><p className="git-modal__note">Studio will validate the project and check for credentials before creating the commit.</p></div><footer><button type="button" className="button--secondary" disabled={busy} onClick={onCancel}>Cancel</button><button type="button" disabled={busy || !message.trim()} onClick={onPush}>{busy ? "Pushing…" : "Push changes"}</button></footer></section></div>;
}

function PublishDialog({ open, status, busy, onCancel, onPublish }: { open: boolean; status: GitStatus; busy: boolean; onCancel(): void; onPublish(input: GitPublishInput): void }) {
  const [version, setVersion] = useState<GitPublishInput["version"]>("patch");
  const [customVersion, setCustomVersion] = useState("");
  return <ConfirmationDialog open={open} title="Publish current version?" confirmLabel={busy ? "Publishing…" : "Publish to production"} confirmDisabled={busy || (version === "custom" && !customVersion.trim())} tone="primary" onCancel={onCancel} onConfirm={() => onPublish({ version, custom_version: version === "custom" ? customVersion : undefined })}>
    <div className="git-publish-dialog"><p>This moves the validated <code>{status.development_branch}</code> commit <code>{status.last_commit?.short_hash}</code> to <code>{status.production_branch}</code>. No local work will be discarded.</p><fieldset className="git-version-options"><legend>Version tag</legend>{(["patch", "minor", "major", "none", "custom"] as const).map((item) => <label key={item}><input type="radio" checked={version === item} onChange={() => setVersion(item)} /><span>{item === "none" ? "Do not create a tag" : item === "custom" ? "Custom version" : item[0].toUpperCase() + item.slice(1)}</span></label>)}</fieldset>{version === "custom" && <label><span>Custom version</span><input value={customVersion} onChange={(event) => setCustomVersion(event.target.value)} placeholder="v1.4.0" /></label>}</div>
  </ConfirmationDialog>;
}

function WorkflowAction({ icon, title, text, disabled, primary = false, onClick }: { icon: React.ReactNode; title: string; text: string; disabled: boolean; primary?: boolean; onClick(): void }) {
  return <article className={primary ? "git-action git-action--primary" : "git-action"}><div className="git-action__icon">{icon}</div><div><h2>{title}</h2><p>{text}</p></div><button type="button" className={primary ? "" : "button--secondary"} disabled={disabled} onClick={onClick}>{title}<ArrowIcon /></button></article>;
}

function Fact({ label, value, tone }: { label: string; value: string; tone?: "success" | "warning" }) {
  return <div><dt>{label}</dt><dd className={tone ? `git-fact--${tone}` : undefined}>{value}</dd></div>;
}

function ChangeBadge({ status }: { status: GitChange["status"] }) {
  return <span className={`git-change-badge git-change-badge--${status}`} aria-label={status}>{status === "modified" ? "M" : status === "added" || status === "untracked" ? "A" : status === "deleted" ? "D" : "R"}</span>;
}

function DiffPreview({ diff }: { diff: string }) {
  return <pre className="git-diff" tabIndex={0}>{diff.split("\n").map((line, index) => <span key={index} className={line.startsWith("+") && !line.startsWith("+++") ? "git-diff__added" : line.startsWith("-") && !line.startsWith("---") ? "git-diff__removed" : line.startsWith("@@") ? "git-diff__hunk" : undefined}>{line || " "}</span>)}</pre>;
}

function Message({ tone, title, details = [] }: { tone: "error" | "success"; title: string; details?: string[] }) {
  return <div className={`git-message git-message--${tone}`} role={tone === "error" ? "alert" : "status"}><strong>{title}</strong>{details.length > 0 && <ul>{details.map((item) => <li key={item}>{item}</li>)}</ul>}</div>;
}

function EmptyState({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: React.ReactNode }) {
  return <section className="git-empty-state"><div>{icon}</div><h1>{title}</h1><p>{text}</p>{action}</section>;
}

function EmptyPanel({ title, text }: { title: string; text: string }) {
  return <div className="git-panel-empty"><CheckIcon /><strong>{title}</strong><p>{text}</p></div>;
}

function syncLabel(status: GitStatus): string {
  if (status.sync_state === "synced") return "Everything is in sync";
  if (status.sync_state === "conflict") return "Local and GitHub history diverged";
  return "Project has changes";
}

function publicationLabel(status: GitStatus): string {
  const publication = status.last_publication;
  if (!publication?.at) return "Not published yet";
  return `${publication.version ?? publication.commit?.slice(0, 7) ?? "Published"} · ${relativeDate(publication.at)}`;
}

function relativeDate(value: string): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value;
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(timestamp);
}

function messageFor(caught: unknown): string {
  const error = caught as StudioApiError | Error;
  return error?.message || "Git could not complete the operation.";
}

function detailsFor(caught: unknown): string[] {
  const apiError = caught as StudioApiError;
  const envelope = apiError?.details as { detail?: { details?: { files?: string[]; issues?: Array<{ message?: string; source_path?: string }> } } } | undefined;
  const details = envelope?.detail?.details;
  if (details?.files) return details.files;
  if (details?.issues) return details.issues.slice(0, 8).map((issue) => `${issue.source_path ? `${issue.source_path}: ` : ""}${issue.message ?? "Validation error"}`);
  return [];
}

function GitMark() { return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="7" cy="5" r="2.2" /><circle cx="17" cy="8" r="2.2" /><circle cx="7" cy="19" r="2.2" /><path d="M7 7.2v9.6M9.2 8h4.2A3.6 3.6 0 0 0 17 4.4V5.8" /></svg>; }
function RefreshIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M15.7 7.4A6.2 6.2 0 1 0 16 11M15.7 3.8v3.6h-3.6" /></svg>; }
function DownloadIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.8v9.1m-3.4-3.4 3.4 3.4 3.4-3.4M3.3 14v2.7h13.4V14" /></svg>; }
function UploadIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 13V3.9M6.6 7.3 10 3.9l3.4 3.4M3.3 14v2.7h13.4V14" /></svg>; }
function RocketIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M11.4 3.2c2.1-1 4-1 5.4-.6.4 1.4.4 3.3-.6 5.4l-3.8 3.8-4.8-4.8 3.8-3.8Z" /><circle cx="13.2" cy="5.8" r="1.2" /><path d="m7.7 7-3.3.6-2 2 4.3.7m5.7 1.3-.6 3.3-2 2-.7-4.3M5.2 13.1l-1.8 3.5 3.5-1.8" /></svg>; }
function ArrowIcon() { return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m5.5 3.5 4.5 4.5-4.5 4.5" /></svg>; }
function ChevronIcon() { return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>; }
function ExternalIcon() { return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9 3h4v4M13 3 7.5 8.5M11 8.5V13H3V5h4.5" /></svg>; }
function CheckIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4 10.5 3.5 3.5L16 5.5" /></svg>; }
function Spinner() { return <span className="git-spinner" aria-hidden="true" />; }
