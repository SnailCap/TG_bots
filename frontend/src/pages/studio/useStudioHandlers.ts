import { useCallback, useMemo, type Dispatch, type SetStateAction } from "react";

import type {
  HandlerCreateOptions,
  HandlerKind,
  HandlerUsage,
  Selection,
  Workspace,
} from "../../domain/project";
import type { HandlerActions } from "../../features/action-editor/ActionEditor";
import type { StudioApiClient } from "../../studio/api";
import { openCode } from "../../studio/desktop";
import type { EditorState } from "./editor-model";

type StudioHandlersOptions = {
  api: StudioApiClient;
  workspace: Workspace;
  dirty: boolean;
  selection: Selection | null;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  setNotice: Dispatch<SetStateAction<string>>;
  clearError(): void;
  report(caught: unknown): void;
  refreshWorkspace(): Promise<Workspace>;
  loadSelection(selection: Selection): Promise<void>;
};

export function useStudioHandlers({
  api,
  workspace,
  dirty,
  selection,
  setBusy,
  setEditor,
  setNotice,
  clearError,
  report,
  refreshWorkspace,
  loadSelection,
}: StudioHandlersOptions) {
  const createAndOpenHandler = useCallback(async (id: string, kind: HandlerKind, outcomes: string[] = [], description?: string, createOptions?: HandlerCreateOptions) => {
    // The backend can attach atomically only to the persisted revision. If this
    // editor has a draft, scaffold the binding/file first and keep the draft in
    // memory; the ordinary Save then persists its already-typed reference.
    const attachPersistedTarget = Boolean(createOptions?.attachment) && !dirty;
    const effectiveOptions = attachPersistedTarget ? createOptions : undefined;
    setBusy(true);
    try {
      const result = await api.createHandler(workspace.project_id, {
        handler_id: id,
        kind,
        registry_revision: workspace.handlers_revision,
        outcomes,
        description,
        ...effectiveOptions,
      });
      await refreshWorkspace();
      if (attachPersistedTarget && selection) await loadSelection(selection);
      const referenceStaysInDraft = dirty && Boolean(createOptions);
      setNotice(referenceStaysInDraft
        ? "Handler created. Its reference is still only in this draft; save the resource to persist it."
        : "");
      clearError();
      try {
        await openCode(result.source);
      } catch (caught) {
        report(caught);
      }
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, clearError, dirty, loadSelection, refreshWorkspace, report, selection, setBusy, setNotice, workspace.handlers_revision, workspace.project_id]);

  const openHandler = useCallback(async (id: string) => {
    try {
      await openCode(await api.handlerSource(workspace.project_id, id));
    } catch (caught) {
      report(caught);
    }
  }, [api, report, workspace.project_id]);

  const repairHandler = useCallback(async (id: string) => {
    setBusy(true);
    try {
      const result = await api.repairHandlerSource(workspace.project_id, id, workspace.handlers_revision);
      await refreshWorkspace();
      if (selection?.kind === "handler" && selection.id === id) {
        setEditor({ kind: "handler", detail: result.handler });
      }
      clearError();
      try {
        await openCode(result.source);
      } catch (caught) {
        report(caught);
      }
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [api, clearError, refreshWorkspace, report, selection, setBusy, setEditor, workspace.handlers_revision, workspace.project_id]);

  const findUsages = useCallback(async (id: string): Promise<HandlerUsage[]> => {
    try {
      return await api.handlerUsages(workspace.project_id, id);
    } catch (caught) {
      report(caught);
      return [];
    }
  }, [api, report, workspace.project_id]);

  const handlerActions: HandlerActions = useMemo(() => ({
    create: (id, kind, createOptions) => createAndOpenHandler(
      id,
      kind,
      Object.keys(createOptions?.routes ?? {}).filter((name) => name !== "success"),
      undefined,
      createOptions,
    ),
    repair: repairHandler,
    open: openHandler,
    usages: findUsages,
  }), [createAndOpenHandler, findUsages, openHandler, repairHandler]);

  return { createAndOpenHandler, openHandler, repairHandler, findUsages, handlerActions };
}
