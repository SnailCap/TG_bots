import type { Dispatch, RefObject, SetStateAction } from "react";

import type { ProjectProcessEvent } from "../../../electron/contracts";
import type {
  ActionOptions,
  HandlerCreateOptions,
  HandlerKind,
  HandlerUsage,
  Selection,
  Workspace,
} from "../../domain/project";
import type { HandlerActions } from "../../features/action-editor/ActionEditor";
import type { TelegramPreviewModel } from "../../features/telegram-preview/preview-model";
import type { ProjectSettings, StudioApiClient } from "../../studio/api";
import type { CreatableResource, ExplorerDraft } from "../../widgets/project-explorer/ProjectExplorer";
import type { EditorState, EditorTab } from "./editor-model";

export type StudioPageContext = {
  api: StudioApiClient;
  apiBaseUrl: string;
  workspace: Workspace;
  recentProjects: readonly string[];
  selection: Selection | null;
  editor: EditorState;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  setDirty: Dispatch<SetStateAction<boolean>>;
  tabs: EditorTab[];
  activeTabKey: string | null;
  error: string;
  notice: string;
  conflict: boolean;
  busy: boolean;
  saving: boolean;
  dirty: boolean;
  undoAvailable: boolean;
  previewOpen: boolean;
  setPreviewOpen: Dispatch<SetStateAction<boolean>>;
  terminalOpen: boolean;
  setTerminalOpen: Dispatch<SetStateAction<boolean>>;
  settingsOpen: boolean;
  setSettingsOpen: Dispatch<SetStateAction<boolean>>;
  projectSettings: ProjectSettings | null;
  settingsLoading: boolean;
  settingsSaving: boolean;
  openProjectSettings(): void;
  saveProjectSettings(token: string): Promise<void>;
  clearProjectSettings(): Promise<void>;
  explorerWidth: number;
  terminalHeight: number;
  workspaceRef: RefObject<HTMLDivElement | null>;
  maximumExplorerWidth(width: number): number;
  maximumTerminalHeight(height: number): number;
  resizeExplorer(width: number): void;
  commitExplorerSize(): void;
  resizeTerminal(height: number): void;
  commitTerminalSize(): void;
  startingLocalRun: boolean;
  stoppingLocalRun: boolean;
  localRunPid: number | null;
  terminalEntries: ProjectProcessEvent[];
  localRunActive: boolean;
  canRunLocalProject: boolean;
  runProject(): Promise<void>;
  stopProject(): Promise<void>;
  status: { label: string; tone: string };
  firstContentKey: string | null;
  explorerDraft: ExplorerDraft | null;
  previewModel: TelegramPreviewModel;
  options: ActionOptions;
  handlerActions: HandlerActions;
  switchProject(path: string): void;
  createProject(): void;
  save(): Promise<void>;
  saveAll(): Promise<void>;
  closeTab(tabKey: string): void;
  activateTab(tabKey: string): void;
  performUndo(): Promise<void>;
  reloadCurrent(): void;
  dismissError(): void;
  dismissNotice(): void;
  select(selection: Selection): void;
  addResource(kind: CreatableResource): Promise<void>;
  renameFromExplorer(selection: Exclude<Selection, { kind: "commands" }>, name: string): Promise<void>;
  removeFromExplorer(selection: Selection): void;
  remove(): Promise<void>;
  repairHandler(id: string): Promise<void>;
  openHandler(id: string): Promise<void>;
  findUsages(id: string): Promise<HandlerUsage[]>;
  createAndOpenHandler(
    id: string,
    kind: HandlerKind,
    outcomes?: string[],
    description?: string,
    createOptions?: HandlerCreateOptions,
  ): Promise<void>;
};
