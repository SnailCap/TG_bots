import { lazy, Suspense } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import { FlowEditor } from "../../../features/flow-editor/ui/FlowEditor";
import { BotSettingsEditor } from "../../../features/settings/ui/BotSettingsEditor";
import styles from "./Workspace.module.css";

const ScriptEditor = lazy(() =>
  import("../../../features/script-editor/ui/ScriptEditor").then((module) => ({
    default: module.ScriptEditor,
  })),
);

export function Workspace() {
  const studio = useStudio();
  const activeTab = studio.workspace.tabs.find((tab) => tab.id === studio.workspace.activeTabId);

  function close(tabId: string) {
    const tab = studio.workspace.tabs.find((item) => item.id === tabId);
    if (tab?.dirty && !window.confirm(`Discard unsaved changes in ${tab.title}?`)) return;
    studio.closeTab(tabId);
  }

  return (
    <main className={styles.workspace}>
      <div className={styles.tabs} role="tablist">
        {studio.workspace.tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={tab.id === studio.workspace.activeTabId}
            className={tab.id === studio.workspace.activeTabId ? styles.active : ""}
            onClick={() => studio.activateTab(tab.id)}
          >
            <span>{tab.type === "flow" ? "◇" : tab.type === "script" ? "#" : tab.type === "settings" ? "⚙" : "▧"}</span>
            {tab.title}{tab.dirty ? " •" : ""}
            <span
              className={styles.close}
              role="button"
              aria-label={`Close ${tab.title}`}
              onClick={(event) => {
                event.stopPropagation();
                close(tab.id);
              }}
            >
              ×
            </span>
          </button>
        ))}
      </div>
      <div className={styles.content}>
        {!activeTab ? (
          <div className={styles.welcome}>
            <div className={styles.welcomeLogo}>B</div>
            <h1>Telegram Bot Studio</h1>
            <p>Open a flow or script from Project Explorer, or create a new bot project.</p>
            <div className={styles.shortcuts}>
              <span><kbd>Ctrl</kbd> + <kbd>S</kbd> Save active document</span>
              <span>Double-click resources to open tabs</span>
            </div>
          </div>
        ) : activeTab.type === "flow" && activeTab.resourceId ? (
          <FlowEditor flowId={activeTab.resourceId} tabId={activeTab.id} />
        ) : activeTab.type === "script" && activeTab.path ? (
          <Suspense fallback={<div className={styles.welcome}>Loading Python editor…</div>}>
            <ScriptEditor path={activeTab.path} tabId={activeTab.id} />
          </Suspense>
        ) : activeTab.type === "settings" ? (
          <BotSettingsEditor />
        ) : (
          <div className={styles.assetPreview}>
            <span>Asset</span>
            <strong>{activeTab.title}</strong>
            <code>{activeTab.path}</code>
            <button
              onClick={() =>
                activeTab.path &&
                window.studioDesktop?.revealPath(
                  `${studio.currentProject?.path ?? ""}\\${activeTab.path}`,
                )
              }
            >
              Reveal in folder
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
