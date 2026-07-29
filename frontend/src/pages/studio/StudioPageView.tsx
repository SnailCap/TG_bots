import type { CSSProperties } from "react";
import { Play, Square } from "lucide-react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import botStudioIcon from "../../assets/bot-studio-logo.svg";
import { ResourceDragProvider } from "../../features/resource-dnd";
import { ProjectSettingsDialog } from "../../features/project-settings/ProjectSettingsDialog";
import { StudioActivityRail } from "../../features/studio-activity/StudioActivityRail";
import { StudioTerminal } from "../../features/studio-terminal/StudioTerminal";
import { MainMenu } from "../../shared/ui/MainMenu";
import { ProjectSwitcher } from "../../shared/ui/ProjectSwitcher";
import { ResizeHandle } from "../../shared/ui/ResizeHandle";
import { ResourceIcon } from "../../shared/ui/ResourceIcon";
import { Toast } from "../../shared/ui/Toast";
import {
  canSave,
  editorCategory,
  editorHeaderTitle,
  editorTabLabel,
  editorTabSelection,
} from "./editor-model";
import type { StudioPageContext } from "./studio-page-context";
import { DEFAULT_STUDIO_ROUTE, STUDIO_ROUTES, studioRouteId } from "./studio-routes";

export function StudioPageView(context: StudioPageContext) {
  return (
    <ResourceDragProvider>
      <Routes>
        <Route element={<StudioShell context={context} />}>
          <Route index element={<Navigate to={DEFAULT_STUDIO_ROUTE.path} replace />} />
          {STUDIO_ROUTES.map(({ id, path, page: Page }) => <Route key={id} path={path} element={<Page />} />)}
          <Route path="*" element={<Navigate to={DEFAULT_STUDIO_ROUTE.path} replace />} />
        </Route>
      </Routes>
    </ResourceDragProvider>
  );
}

function StudioShell({ context }: { context: StudioPageContext }) {
  const activeRoute = studioRouteId(useLocation().pathname);
  const {
    workspace,
    recentProjects,
    editor,
    activeTabKey,
    error,
    notice,
    conflict,
    busy,
    saving,
    dirty,
    undoAvailable,
    previewOpen,
    terminalOpen,
    setTerminalOpen,
    settingsOpen,
    setSettingsOpen,
    projectSettings,
    settingsLoading,
    settingsSaving,
    openProjectSettings,
    saveProjectSettings,
    clearProjectSettings,
    explorerWidth,
    terminalHeight,
    workspaceRef,
    maximumTerminalHeight,
    resizeTerminal,
    commitTerminalSize,
    startingLocalRun,
    stoppingLocalRun,
    localRunPid,
    terminalEntries,
    localRunActive,
    canRunLocalProject,
    runProject,
    stopProject,
    status,
    switchProject,
    createProject,
    save,
    closeTab,
    performUndo,
    reloadCurrent,
    dismissError,
    dismissNotice,
  } = context;

  return (
    <main className="studio">
      <header className="topbar">
        <div className="topbar__leading">
          <img className="topbar__brand" src={botStudioIcon} alt="Bot Studio" />
          <MainMenu
            canSave={Boolean(editor && !busy && canSave(editor))}
            canCloseTab={Boolean(activeTabKey)}
            canUndo={undoAvailable && !busy}
            onOpenProject={() => switchProject("")}
            onNewProject={createProject}
            onSave={() => void save()}
            onCloseTab={() => { if (activeTabKey) closeTab(activeTabKey); }}
            onUndo={() => void performUndo()}
          />
          <ProjectSwitcher workspace={workspace} recentProjects={recentProjects} onOpenProject={switchProject} onNewProject={createProject} />
        </div>
        <div className="topbar__actions">
          <button
            type="button"
            className={localRunActive ? "topbar__run topbar__run--stop" : "topbar__run"}
            aria-label={localRunActive ? "Stop local bot" : "Run local bot"}
            aria-busy={startingLocalRun || stoppingLocalRun || undefined}
            disabled={!canRunLocalProject || startingLocalRun || stoppingLocalRun || (!localRunActive && (dirty || busy || saving))}
            title={!canRunLocalProject ? "Local run is available in the desktop Studio application" : localRunActive ? `Stop local bot${localRunPid ? ` (PID ${localRunPid})` : ""}` : dirty ? "Save changes before running" : "Run local bot"}
            onClick={() => void (localRunActive ? stopProject() : runProject())}
          >
            {localRunActive ? <StopIcon /> : <RunIcon />}
          </button>
        </div>
      </header>
      {error && <Toast message={error} tone="error" action={conflict && <button type="button" className="button--secondary" onClick={reloadCurrent}>Reload from disk</button>} onDismiss={dismissError} />}
      {notice && <Toast message={notice} tone="notice" onDismiss={dismissNotice} />}
      <div ref={workspaceRef} className={`workspace${activeRoute === "users" ? " workspace--users" : ""}${activeRoute === "git" ? " workspace--git" : ""}${activeRoute === "resources" && previewOpen ? " workspace--preview-open" : ""}${terminalOpen ? " workspace--terminal-open" : ""}`} style={{ "--explorer-width": `${explorerWidth}px`, "--terminal-height": `${terminalHeight}px` } as CSSProperties}>
        <StudioActivityRail routes={STUDIO_ROUTES} terminalOpen={terminalOpen} onToggleTerminal={() => setTerminalOpen((open) => !open)} settingsOpen={settingsOpen} onOpenSettings={openProjectSettings} />
        <Outlet context={context} />
        {terminalOpen && <>
          <ResizeHandle className="workspace__terminal-resizer" axis="vertical" label="Resize terminal" value={terminalHeight} min={120} max={() => maximumTerminalHeight(workspaceRef.current?.clientHeight ?? 0)} inverted onResize={resizeTerminal} onResizeEnd={commitTerminalSize} />
          <StudioTerminal entries={terminalEntries} running={localRunActive} pid={localRunPid} onClose={() => setTerminalOpen(false)} />
        </>}
      </div>
      <footer className="studio-statusbar" aria-label="Studio status">
        <div className="studio-statusbar__group">
          <span className={`studio-statusbar__state studio-statusbar__state--${status.tone}`} role="status" aria-live="polite">
            <span className="studio-statusbar__dot" aria-hidden="true" />
            {status.label}
          </span>
          {activeRoute === "resources" && editor && <span className="studio-statusbar__resource" title={`${editorCategory(editor)}: ${editorHeaderTitle(editor)}`}>
            <ResourceIcon selection={editorTabSelection(editor)} title={editorTabLabel(editor)} />
            <span>{editorCategory(editor)} · {editorHeaderTitle(editor)}</span>
          </span>}
        </div>
        <div className="studio-statusbar__group studio-statusbar__group--end">
          <span className="studio-statusbar__item" title={workspace.project_root}>{workspace.name}</span>
          <span className="studio-statusbar__item">Schema v{workspace.schema_version}</span>
        </div>
      </footer>
      <ProjectSettingsDialog open={settingsOpen} settings={projectSettings} loading={settingsLoading} saving={settingsSaving} onClose={() => setSettingsOpen(false)} onSave={saveProjectSettings} onClear={clearProjectSettings} />
    </main>
  );
}

function RunIcon() {
  return <Play className="topbar__run-icon" aria-hidden="true" />;
}

function StopIcon() {
  return <Square className="topbar__stop-icon" aria-hidden="true" fill="currentColor" />;
}
