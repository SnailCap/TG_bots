import type { CommandsSpec, FlowSpec, ScheduleSpec, ViewDetail, Workspace } from "../../domain/project";

export type PreviewEditor =
  | { kind: "view"; detail: ViewDetail }
  | { kind: "flow"; payload: FlowSpec }
  | { kind: "commands"; payload: CommandsSpec }
  | { kind: "schedule"; payload: ScheduleSpec }
  | { kind: "handler" | "new-handler" };

export interface TelegramPreviewMessage {
  id: string;
  author: "bot" | "user";
  text: string;
  buttons?: string[][];
}

export interface TelegramPreviewModel {
  key: string;
  botName: string;
  contextLabel: string;
  messages: TelegramPreviewMessage[];
  replyKeyboard?: string[][];
}

export function createTelegramPreviewModel(workspace: Workspace, editor: PreviewEditor | null): TelegramPreviewModel {
  const base = { botName: workspace.name, contextLabel: "No resource selected" };
  if (!editor) return {
    ...base,
    key: "empty",
    messages: [{ id: "empty", author: "bot", text: "Choose a view, flow, or command to see its conversation here." }],
  };

  if (editor.kind === "view") {
    const text = editor.detail.text_content || "This message is empty.";
    const keyboard = editor.detail.payload.keyboard.map((row) => row.map((button) => button.text || "Button")).filter((row) => row.length > 0);
    return {
      ...base,
      key: `view:${editor.detail.payload.id}:${text}:${JSON.stringify(keyboard)}`,
      contextLabel: `View · ${editor.detail.payload.id || "new view"}`,
      messages: [
        { id: "view-request", author: "user", text: "Open this screen" },
        { id: "view-response", author: "bot", text, buttons: keyboard.length ? keyboard : undefined },
      ],
    };
  }

  if (editor.kind === "flow") {
    const initial = editor.payload.states[editor.payload.initial_state];
    const targetView = initial?.view;
    return {
      ...base,
      key: `flow:${editor.payload.id}:${editor.payload.initial_state}:${targetView ?? ""}`,
      contextLabel: `Flow · ${editor.payload.id || "new flow"}`,
      messages: [
        { id: "flow-request", author: "user", text: `Start ${editor.payload.id || "this flow"}` },
        { id: "flow-response", author: "bot", text: targetView ? `Initial state: ${editor.payload.initial_state}. It opens view “${targetView}”.` : "Choose an initial state and its view to preview this flow." },
      ],
    };
  }

  if (editor.kind === "commands") {
    const commands = editor.payload.commands.map((command) => `/${command.name || "command"}`);
    return {
      ...base,
      key: `commands:${commands.join(",")}`,
      contextLabel: "Commands",
      messages: [
        { id: "commands-request", author: "user", text: commands[0] ?? "/start" },
        { id: "commands-response", author: "bot", text: commands.length ? "Available commands are shown below." : "No commands have been configured yet." },
      ],
      replyKeyboard: commands.length ? [commands] : undefined,
    };
  }

  if (editor.kind === "schedule") return {
    ...base,
    key: `schedule:${editor.payload.id}:${editor.payload.trigger.seconds}`,
    contextLabel: `Schedule · ${editor.payload.id || "new schedule"}`,
    messages: [{ id: "schedule", author: "bot", text: `This task runs every ${editor.payload.trigger.seconds || 0} seconds.` }],
  };

  return {
    ...base,
    key: editor.kind,
    contextLabel: editor.kind === "handler" ? "Handler" : "New handler",
    messages: [{ id: "handler", author: "bot", text: "Handlers run behind the scenes. Open a view or flow to preview the user conversation." }],
  };
}
