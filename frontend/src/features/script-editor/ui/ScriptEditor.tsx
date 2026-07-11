import Editor, { loader, type OnMount } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import type { ValidationIssue } from "../../../entities/runtime/model/types";
import { toApiError } from "../../../shared/api/client";
import { studioApi } from "../../../shared/api/studioApi";
import type { ActionDefinition, ActionUsage, ScriptFile, ScriptSearchMatch } from "../../../shared/api/types";
import styles from "./ScriptEditor.module.css";

loader.config({ monaco });

type SideTab = "actions" | "search" | "problems";

export function ScriptEditor({ path, tabId }: { path: string; tabId: string }) {
  const studio = useStudio();
  const projectId = studio.currentProject?.id;
  const [script, setScript] = useState<ScriptFile | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sideTab, setSideTab] = useState<SideTab>("actions");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ScriptSearchMatch[]>([]);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [selectedAction, setSelectedAction] = useState<ActionDefinition | null>(null);
  const [usages, setUsages] = useState<ActionUsage[]>([]);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const saveRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    setLoading(true);
    setError(null);
    void studioApi
      .getScript(projectId, path)
      .then((loaded) => {
        if (!active) return;
        setScript(loaded);
        setContent(loaded.content);
        studio.markTabDirty(tabId, false);
      })
      .catch((reason) => active && setError(toApiError(reason).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [path, projectId, studio.markTabDirty, tabId]);

  const revealLine = useCallback((line = 1) => {
    editorRef.current?.revealLineInCenter(line);
    editorRef.current?.setPosition({ lineNumber: line, column: 1 });
    editorRef.current?.focus();
  }, []);

  useEffect(() => {
    const target = studio.scriptNavigation;
    if (target?.path === path && target.line) revealLine(target.line);
  }, [path, revealLine, studio.scriptNavigation]);

  const validate = useCallback(async () => {
    if (!projectId) return [];
    try {
      const nextIssues = await studioApi.validateScript(projectId, path, content);
      setIssues(nextIssues);
      if (nextIssues.length) setSideTab("problems");
      return nextIssues;
    } catch (reason) {
      const message = toApiError(reason).message;
      setError(message);
      return [];
    }
  }, [content, path, projectId]);

  const save = useCallback(async () => {
    if (!projectId || !script) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await studioApi.saveScript(projectId, { ...script, content });
      setScript({ ...saved, path: saved.path || script.path, content: saved.content || content });
      studio.markTabDirty(tabId, false);
      await Promise.all([validate(), studio.refreshProjectResources()]);
    } catch (reason) {
      setError(toApiError(reason).message);
    } finally {
      setSaving(false);
    }
  }, [content, projectId, script, studio.markTabDirty, studio.refreshProjectResources, tabId, validate]);
  saveRef.current = () => void save();

  const onMount: OnMount = (editor, monacoInstance) => {
    editorRef.current = editor;
    editor.addCommand(monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS, () => saveRef.current());
    editor.addCommand(monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyF, () => {
      editor.getAction("actions.find")?.run();
    });
    const target = studio.scriptNavigation;
    if (target?.path === path && target.line) revealLine(target.line);
  };

  async function searchProject() {
    if (!projectId || !query.trim()) return;
    try {
      setMatches(await studioApi.searchScripts(projectId, query.trim()));
      setSideTab("search");
    } catch (reason) {
      setError(toApiError(reason).message);
    }
  }

  async function chooseAction(action: ActionDefinition) {
    setSelectedAction(action);
    setSideTab("actions");
    if (action.scriptPath === path && action.line) revealLine(action.line);
    try {
      setUsages(projectId ? await studioApi.actionUsages(projectId, action.name) : []);
    } catch {
      setUsages([]);
    }
  }

  async function createScript() {
    const name = window.prompt("New script name", "action.py")?.trim();
    if (name) await studio.createExplorerResource("script", name);
  }

  async function renameScript() {
    const next = window.prompt("New script path", path)?.trim();
    if (!next || next === path) return;
    const nextPath = next.startsWith("scripts/") ? next : `scripts/${next}`;
    await studio.renameResource({ id: path, path, name: script?.name ?? path, kind: "script", children: [] }, nextPath);
    studio.closeTab(tabId);
    studio.navigateToScript(nextPath);
  }

  async function deleteScript() {
    if (!window.confirm(`Delete ${path}?`)) return;
    await studio.deleteResource({ id: path, path, name: script?.name ?? path, kind: "script", children: [] });
  }

  const fileActions = useMemo(
    () => studio.actions.filter((action) => action.scriptPath === path),
    [path, studio.actions],
  );

  if (loading) return <div className={styles.message}>Loading Python script…</div>;
  if (!script) return <div className={styles.message}>Unable to open script: {error ?? "Unknown error"}</div>;

  return (
    <section className={styles.layout} aria-label={`Script editor: ${path}`}>
      <div className={styles.main}>
        <div className={styles.toolbar}>
          <code title={path}>{path}</code>
          <span className={styles.spacer} />
          {error && <span className={styles.error}>{error}</span>}
          <button onClick={() => void createScript()}>New</button>
          <button onClick={() => void renameScript()}>Rename</button>
          <button onClick={() => void deleteScript()}>Delete</button>
          <button onClick={() => void validate()}>Check syntax</button>
          <button className={styles.save} disabled={saving} onClick={() => void save()}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
        <Editor
          height="100%"
          language="python"
          path={path}
          value={content}
          theme="vs-dark"
          onMount={onMount}
          onChange={(value) => {
            setContent(value ?? "");
            studio.markTabDirty(tabId, true);
          }}
          options={{
            automaticLayout: true,
            fontFamily: "Cascadia Code, Consolas, monospace",
            fontSize: 13,
            minimap: { enabled: true },
            scrollBeyondLastLine: false,
            tabSize: 4,
            insertSpaces: true,
            wordWrap: "off",
            renderWhitespace: "selection",
          }}
        />
      </div>
      <aside className={styles.side}>
        <div className={styles.sideTabs}>
          <button className={sideTab === "actions" ? styles.active : ""} onClick={() => setSideTab("actions")}>Actions</button>
          <button className={sideTab === "search" ? styles.active : ""} onClick={() => setSideTab("search")}>Search</button>
          <button className={sideTab === "problems" ? styles.active : ""} onClick={() => setSideTab("problems")}>Problems {issues.length || ""}</button>
        </div>
        {sideTab === "search" ? (
          <div className={styles.sideBody}>
            <div className={styles.searchRow}>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && void searchProject()}
                placeholder="Search all scripts…"
              />
              <button onClick={() => void searchProject()}>Go</button>
            </div>
            {matches.map((match, index) => (
              <button className={styles.result} key={`${match.path}:${match.line}:${index}`} onClick={() => studio.navigateToScript(match.path, match.line)}>
                <strong>{match.path}:{match.line}</strong>
                <span>{match.preview}</span>
              </button>
            ))}
          </div>
        ) : sideTab === "problems" ? (
          <div className={styles.sideBody}>
            {issues.length ? issues.map((issue, index) => (
              <button className={styles.problem} key={`${issue.code}:${index}`} onClick={() => revealLine(issue.entity?.line ?? 1)}>
                <strong>{issue.code}</strong>
                <span>{issue.message}</span>
                {issue.entity?.line && <small>Line {issue.entity.line}</small>}
              </button>
            )) : <p className={styles.empty}>No syntax problems reported.</p>}
          </div>
        ) : (
          <div className={styles.sideBody}>
            <p className={styles.sectionLabel}>In this file</p>
            {fileActions.length ? fileActions.map((action) => (
              <button
                className={`${styles.action} ${selectedAction?.name === action.name ? styles.selectedAction : ""}`}
                key={action.name}
                onClick={() => void chooseAction(action)}
              >
                <strong>{action.name}</strong>
                <span>{action.signature ?? "@action"}</span>
                {!action.valid && <small>{action.error ?? "Invalid action"}</small>}
              </button>
            )) : <p className={styles.empty}>No registered actions in this file.</p>}
            {selectedAction && (
              <>
                <p className={styles.sectionLabel}>Used by</p>
                {usages.length ? usages.map((usage) => (
                  <button className={styles.usage} key={`${usage.flowId}:${usage.nodeId}`} onClick={() => studio.navigateToUsage(usage)}>
                    <strong>{usage.flowName ?? usage.flowId}</strong>
                    <span>{usage.nodeTitle ?? usage.nodeId}</span>
                  </button>
                )) : <p className={styles.empty}>This action is not used by a flow.</p>}
              </>
            )}
          </div>
        )}
      </aside>
    </section>
  );
}
