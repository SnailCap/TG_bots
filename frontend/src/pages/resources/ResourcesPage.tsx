import { useOutletContext } from "react-router-dom";

import { PreviewToolRail } from "../../features/telegram-preview/PreviewToolRail";
import { TelegramPreview } from "../../features/telegram-preview/TelegramPreview";
import { ResizeHandle } from "../../shared/ui/ResizeHandle";
import { ResourceEditorHeader } from "../../shared/ui/ResourceEditorHeader";
import { ResourceIcon } from "../../shared/ui/ResourceIcon";
import { ProjectExplorer } from "../../widgets/project-explorer/ProjectExplorer";
import {
  canSave,
  editorCategory,
  editorHeaderTitle,
  editorTabLabel,
  editorTabSelection,
  isEditorInvalid,
  isSaveableEditor,
} from "../studio/editor-model";
import type { StudioPageContext } from "../studio/studio-page-context";
import { StudioEditor } from "../studio/StudioEditor";

export function ResourcesPage() {
  const {
    workspace,
    selection,
    editor,
    setEditor,
    setDirty,
    tabs,
    activeTabKey,
    busy,
    saving,
    previewOpen,
    setPreviewOpen,
    explorerWidth,
    workspaceRef,
    maximumExplorerWidth,
    resizeExplorer,
    commitExplorerSize,
    firstContentKey,
    explorerDraft,
    previewModel,
    options,
    handlerActions,
    select,
    addResource,
    renameFromExplorer,
    removeFromExplorer,
    save,
    closeTab,
    activateTab,
    remove,
    repairHandler,
    openHandler,
    findUsages,
    createAndOpenHandler,
  } = useOutletContext<StudioPageContext>();

  return <>
    <ProjectExplorer workspace={workspace} selection={selection} draft={explorerDraft} onSelect={select} onAdd={addResource} onRename={renameFromExplorer} onDelete={removeFromExplorer} />
    <ResizeHandle className="workspace__resizer" axis="horizontal" label="Resize resource list" value={explorerWidth} min={180} max={() => maximumExplorerWidth(workspaceRef.current?.clientWidth ?? 0)} onResize={resizeExplorer} onResizeEnd={commitExplorerSize} />
    <section className="workspace__main" aria-busy={busy}>
      {tabs.length > 0 && <nav className="editor-tabs" aria-label="Open resources" role="tablist">
        {tabs.map((tab) => <div key={tab.key} className={tab.key === activeTabKey ? "editor-tab editor-tab--active" : "editor-tab"} role="presentation">
          <button type="button" className="editor-tab__select" role="tab" aria-selected={tab.key === activeTabKey} onClick={() => activateTab(tab.key)}><span className="editor-tab__dirty-slot">{tab.dirty && <span className={isEditorInvalid(tab.editor) ? "editor-tab__dirty editor-tab__dirty--invalid" : "editor-tab__dirty"} aria-label={isEditorInvalid(tab.editor) ? "Invalid unsaved changes" : "Unsaved changes"} title={isEditorInvalid(tab.editor) ? "This resource needs attention before it can be used" : "Unsaved changes"} />}</span><ResourceIcon selection={editorTabSelection(tab.editor)} title={editorTabLabel(tab.editor)} /><span className="editor-tab__label">{editorTabLabel(tab.editor)}</span></button>
          <button type="button" className="editor-tab__close" aria-label={`Close ${editorTabLabel(tab.editor)}`} title="Close tab" onClick={() => closeTab(tab.key)}><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m5 5 6 6m0-6-6 6" /></svg></button>
        </div>)}
      </nav>}
      <div key={firstContentKey ?? "empty"} className={firstContentKey ? "workspace__content workspace__content--enter" : "workspace__content"}>
        {editor && <ResourceEditorHeader category={editorCategory(editor)} title={editorHeaderTitle(editor)} saveAction={isSaveableEditor(editor) ? { disabled: busy || !canSave(editor), saving, onSave: () => void save() } : undefined} />}
        <StudioEditor editor={editor} options={options} handlerActions={handlerActions} setEditor={setEditor} setDirty={setDirty} repairHandler={repairHandler} openHandler={openHandler} findUsages={findUsages} createHandler={createAndOpenHandler} select={select} renameDisplayName={renameFromExplorer} createTemplate={(suggestedPath) => { void addResource("template", suggestedPath); }} />
        {editor?.kind === "handler" && <footer className="editor__actions editor__actions--danger"><span>Deleting a binding can break the resources that use it.</span><button type="button" className="button--danger" disabled={busy} onClick={() => void remove()}>Delete binding</button></footer>}
        {!editor && <div className="workspace__empty"><div><p className="eyebrow">Ready to edit</p><h2>Select a resource</h2><p>Choose an item from the explorer, or add a view, flow, schedule or handler to begin.</p></div></div>}
      </div>
    </section>
    <TelegramPreview open={previewOpen} model={previewModel} onClose={() => setPreviewOpen(false)} />
    <PreviewToolRail open={previewOpen} onToggle={() => setPreviewOpen((open) => !open)} />
  </>;
}
