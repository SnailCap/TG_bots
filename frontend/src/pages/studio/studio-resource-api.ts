import {
  emptyFlow,
  emptySchedule,
  emptyView,
  type Selection,
  type Workspace,
} from "../../domain/project";
import type { StudioApiClient } from "../../studio/api";
import type { CreatableResource } from "../../widgets/project-explorer/ProjectExplorer";
import {
  commandAt,
  findCommandIndex,
  type DeletedResource,
  type EditorState,
} from "./editor-model";

type PersistedEditor = Exclude<EditorState, null>;
type RenameableSelection = Exclude<Selection, { kind: "commands" }>;

export async function loadEditor(api: StudioApiClient, projectId: string, selection: Selection): Promise<PersistedEditor> {
  switch (selection.kind) {
    case "view": return { kind: "view", detail: await api.getView(projectId, selection.id), isNew: false };
    case "template": return { kind: "template", detail: await api.getTemplate(projectId, selection.path), isNew: false };
    case "flow": return { kind: "flow", detail: await api.getFlow(projectId, selection.id), isNew: false };
    case "command": {
      const detail = await api.getCommands(projectId);
      return { kind: "command", detail, commandIndex: findCommandIndex(detail, selection.name) };
    }
    case "commands": return { kind: "commands", detail: await api.getCommands(projectId) };
    case "schedule": return { kind: "schedule", detail: await api.getSchedule(projectId, selection.id), isNew: false };
    case "handler": return { kind: "handler", detail: await api.getHandler(projectId, selection.id) };
  }
}

export async function createResource(
  api: StudioApiClient,
  workspace: Workspace,
  kind: Exclude<CreatableResource, "handler">,
  templatePath = "",
): Promise<{ editor: PersistedEditor; selection: Selection }> {
  if (kind === "view") {
    const id = nextAvailableResourceName("new-view", workspace.views.map((item) => item.id));
    const detail = await api.createView(workspace.project_id, id, emptyView(id));
    return { editor: { kind, isNew: false, detail }, selection: { kind, id: detail.id } };
  }
  if (kind === "template") {
    const path = templatePath || nextAvailableTemplatePath(workspace.templates.map((item) => item.path));
    const detail = await api.saveTemplate(workspace.project_id, path, "");
    return { editor: { kind, isNew: false, detail }, selection: { kind, path: detail.path } };
  }
  if (kind === "flow") {
    const id = nextAvailableResourceName("new-flow", workspace.flows.map((item) => item.id));
    const detail = await api.createFlow(workspace.project_id, id, emptyFlow(id));
    return { editor: { kind, isNew: false, detail }, selection: { kind, id: detail.id } };
  }
  if (kind === "command") {
    const detail = await api.getCommands(workspace.project_id);
    const name = nextAvailableCommandName(detail.payload.commands.map((command) => command.name));
    const saved = await api.saveCommands(workspace.project_id, {
      ...detail.payload,
      commands: [...detail.payload.commands, { name, action: { type: "noop" } }],
    }, detail.revision);
    return {
      editor: { kind, detail: saved, commandIndex: findCommandIndex(saved, name) },
      selection: { kind, name },
    };
  }
  const id = nextAvailableResourceName("new-schedule", workspace.schedules.map((item) => item.id));
  const detail = await api.createSchedule(workspace.project_id, id, emptySchedule(id));
  return { editor: { kind, isNew: false, detail }, selection: { kind, id: detail.id } };
}

export async function saveEditor(
  api: StudioApiClient,
  projectId: string,
  editor: PersistedEditor,
  currentSelection: Selection | null,
): Promise<{ editor: PersistedEditor; selection: Selection | null }> {
  if (editor.kind === "view") {
    const id = editor.detail.payload.id;
    const detail = editor.isNew
      ? await api.createView(projectId, id, editor.detail.payload)
      : editor.detail.id !== id
        ? await api.renameView(projectId, editor.detail.id, id, editor.detail.revision)
        : await api.saveView(projectId, id, editor.detail.payload, editor.detail.revision);
    return { editor: { kind: "view", detail, isNew: false }, selection: { kind: "view", id: detail.id } };
  }
  if (editor.kind === "template") {
    const detail = await api.saveTemplate(projectId, editor.detail.path, editor.detail.content, editor.isNew ? undefined : editor.detail.revision);
    return { editor: { kind: "template", detail, isNew: false }, selection: { kind: "template", path: detail.path } };
  }
  if (editor.kind === "flow") {
    const id = editor.detail.payload.id;
    const detail = editor.isNew
      ? await api.createFlow(projectId, id, editor.detail.payload)
      : await api.saveFlow(projectId, id, editor.detail.payload, editor.detail.revision);
    return { editor: { kind: "flow", detail, isNew: false }, selection: { kind: "flow", id: detail.id } };
  }
  if (editor.kind === "command") {
    const command = commandAt(editor);
    const detail = await api.saveCommands(projectId, editor.detail.payload, editor.detail.revision);
    return {
      editor: { kind: "command", detail, commandIndex: findCommandIndex(detail, command.name) },
      selection: { kind: "command", name: command.name },
    };
  }
  if (editor.kind === "commands") {
    const detail = await api.saveCommands(projectId, editor.detail.payload, editor.detail.revision);
    return { editor: { kind: "commands", detail }, selection: currentSelection };
  }
  if (editor.kind === "schedule") {
    const id = editor.detail.payload.id;
    const detail = editor.isNew
      ? await api.createSchedule(projectId, id, editor.detail.payload)
      : await api.saveSchedule(projectId, id, editor.detail.payload, editor.detail.revision);
    return { editor: { kind: "schedule", detail, isNew: false }, selection: { kind: "schedule", id: detail.id } };
  }
  return { editor, selection: currentSelection };
}

export async function deleteEditor(api: StudioApiClient, projectId: string, editor: PersistedEditor): Promise<void> {
  if (editor.kind === "view" && !editor.isNew) await api.deleteView(projectId, editor.detail.id, editor.detail.revision);
  else if (editor.kind === "template" && !editor.isNew) await api.deleteTemplate(projectId, editor.detail.path, editor.detail.revision);
  else if (editor.kind === "flow" && !editor.isNew) await api.deleteFlow(projectId, editor.detail.id, editor.detail.revision);
  else if (editor.kind === "command") {
    await api.saveCommands(projectId, {
      ...editor.detail.payload,
      commands: editor.detail.payload.commands.filter((_, index) => index !== editor.commandIndex),
    }, editor.detail.revision);
  }
  else if (editor.kind === "schedule" && !editor.isNew) await api.deleteSchedule(projectId, editor.detail.id, editor.detail.revision);
  else if (editor.kind === "handler") await api.deleteHandler(projectId, editor.detail.id, editor.detail.revision);
}

export async function deleteSelection(api: StudioApiClient, projectId: string, selection: Selection): Promise<DeletedResource | null> {
  if (selection.kind === "view") {
    const detail = await api.getView(projectId, selection.id);
    await api.deleteView(projectId, selection.id, detail.revision);
    return { kind: "view", detail };
  }
  if (selection.kind === "template") {
    const detail = await api.getTemplate(projectId, selection.path);
    await api.deleteTemplate(projectId, selection.path, detail.revision);
    return { kind: "template", detail };
  }
  if (selection.kind === "flow") {
    const detail = await api.getFlow(projectId, selection.id);
    await api.deleteFlow(projectId, selection.id, detail.revision);
    return { kind: "flow", detail };
  }
  if (selection.kind === "command") {
    const detail = await api.getCommands(projectId);
    const index = findCommandIndex(detail, selection.name);
    const snapshot: DeletedResource = { kind: "command", command: detail.payload.commands[index], index };
    await api.saveCommands(projectId, {
      ...detail.payload,
      commands: detail.payload.commands.filter((_, current) => current !== index),
    }, detail.revision);
    return snapshot;
  }
  if (selection.kind === "schedule") {
    const detail = await api.getSchedule(projectId, selection.id);
    await api.deleteSchedule(projectId, selection.id, detail.revision);
    return { kind: "schedule", detail };
  }
  if (selection.kind === "handler") {
    const detail = await api.getHandler(projectId, selection.id);
    await api.deleteHandler(projectId, selection.id, detail.revision);
    return { kind: "handler", detail };
  }
  return null;
}

export async function deletePersistedResource(api: StudioApiClient, projectId: string, selection: Selection): Promise<void> {
  await deleteSelection(api, projectId, selection);
}

export async function restoreDeletedResource(api: StudioApiClient, projectId: string, snapshot: DeletedResource): Promise<void> {
  if (snapshot.kind === "view") await api.createView(projectId, snapshot.detail.id, snapshot.detail.payload);
  else if (snapshot.kind === "flow") await api.createFlow(projectId, snapshot.detail.id, snapshot.detail.payload);
  else if (snapshot.kind === "schedule") await api.createSchedule(projectId, snapshot.detail.id, snapshot.detail.payload);
  else if (snapshot.kind === "template") await api.saveTemplate(projectId, snapshot.detail.path, snapshot.detail.content);
  else if (snapshot.kind === "command") {
    const detail = await api.getCommands(projectId);
    const commands = [...detail.payload.commands];
    commands.splice(Math.min(snapshot.index, commands.length), 0, snapshot.command);
    await api.saveCommands(projectId, { ...detail.payload, commands }, detail.revision);
  }
  else {
    const fresh = await api.describe(projectId);
    await api.createHandler(projectId, {
      handler_id: snapshot.detail.id,
      kind: snapshot.detail.kind,
      registry_revision: fresh.handlers_revision,
      outcomes: snapshot.detail.outcomes,
      description: snapshot.detail.description,
    });
  }
}

export async function renameResource(
  api: StudioApiClient,
  projectId: string,
  selection: RenameableSelection,
  name: string,
): Promise<{ selection: RenameableSelection; editor: PersistedEditor }> {
  if (selection.kind === "view") {
    const detail = await api.getView(projectId, selection.id);
    const renamed = await api.renameView(projectId, selection.id, name, detail.revision);
    return { selection: { kind: "view", id: renamed.id }, editor: { kind: "view", detail: renamed, isNew: false } };
  }
  if (selection.kind === "template") {
    const detail = await api.getTemplate(projectId, selection.path);
    const renamed = await api.renameTemplate(projectId, selection.path, name, detail.revision);
    return { selection: { kind: "template", path: renamed.path }, editor: { kind: "template", detail: renamed, isNew: false } };
  }
  if (selection.kind === "flow") {
    const detail = await api.getFlow(projectId, selection.id);
    const renamed = await api.renameFlow(projectId, selection.id, name, detail.revision);
    return { selection: { kind: "flow", id: renamed.id }, editor: { kind: "flow", detail: renamed, isNew: false } };
  }
  if (selection.kind === "schedule") {
    const detail = await api.getSchedule(projectId, selection.id);
    const renamed = await api.renameSchedule(projectId, selection.id, name, detail.revision);
    return { selection: { kind: "schedule", id: renamed.id }, editor: { kind: "schedule", detail: renamed, isNew: false } };
  }
  if (selection.kind === "command") {
    const detail = await api.getCommands(projectId);
    const index = findCommandIndex(detail, selection.name);
    const commandName = normalizeCommandName(name);
    const renamed = await api.saveCommands(projectId, {
      ...detail.payload,
      commands: detail.payload.commands.map((command, current) => current === index
        ? { ...command, name: commandName }
        : command),
    }, detail.revision);
    return {
      selection: { kind: "command", name: commandName },
      editor: { kind: "command", detail: renamed, commandIndex: findCommandIndex(renamed, commandName) },
    };
  }
  const detail = await api.getHandler(projectId, selection.id);
  const renamed = await api.renameHandler(projectId, selection.id, name, detail.revision);
  return { selection: { kind: "handler", id: renamed.id }, editor: { kind: "handler", detail: renamed } };
}

function nextAvailableResourceName(base: string, existing: string[]): string {
  const names = new Set(existing);
  if (!names.has(base)) return base;
  let suffix = 2;
  while (names.has(`${base}-${suffix}`)) suffix += 1;
  return `${base}-${suffix}`;
}

function nextAvailableTemplatePath(existing: string[]): string {
  const paths = new Set(existing);
  if (!paths.has("new-template.txt")) return "new-template.txt";
  let suffix = 2;
  while (paths.has(`new-template-${suffix}.txt`)) suffix += 1;
  return `new-template-${suffix}.txt`;
}

function nextAvailableCommandName(existing: string[]): string {
  const names = new Set(existing);
  if (!names.has("new_command")) return "new_command";
  let suffix = 2;
  while (names.has(`new_command_${suffix}`)) suffix += 1;
  return `new_command_${suffix}`;
}

function normalizeCommandName(value: string): string {
  return value.trim().replace(/^\//, "").toLowerCase();
}
