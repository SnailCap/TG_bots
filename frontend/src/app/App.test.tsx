import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  Diagnostic,
  HandlerDetail,
  HandlerScaffoldResult,
  ViewDetail,
  Workspace,
} from "../domain/project";
import { StudioPage } from "../pages/studio/StudioPage";
import type { StudioApiClient } from "../studio/api";
import { StudioApiError } from "../studio/api";
import { ProjectExplorer } from "../widgets/project-explorer/ProjectExplorer";
import { ValidationPanel } from "../widgets/validation-panel/ValidationPanel";
import { App, BackendStatusCard } from "./App";

const handler: HandlerDetail = {
  id: "checkout.submit",
  kind: "button",
  module: "demo.handlers.checkout_submit",
  symbol: "handle",
  outcomes: ["invalid"],
  source_path: "handlers.json",
  source_file: "src/demo/handlers/checkout_submit.py",
  revision: "handler-one",
  status: "ready",
  usage_count: 1,
};

const workspace: Workspace = {
  project_id: "project-1",
  name: "demo",
  project_root: "C:/demo",
  resource_root: "C:/demo/resources",
  package: "demo",
  schema_version: 3,
  manifest: { source_path: "bot.json", revision: "manifest-one", payload: { schema_version: 3, id: "demo", package: "demo", entry_view: "home", start: { flow: "checkout", policy: "reset" } } },
  views: [{ id: "home", source_path: "views/home.json", revision: "view-one" }],
  templates: [{ path: "home.txt" }],
  flows: [{ id: "checkout", source_path: "flows/checkout.json", revision: "flow-one" }],
  handlers: [handler],
  handlers_revision: "handlers-one",
  commands: { source_path: "commands.json", revision: "commands-one" },
  schedules: [{ id: "daily", source_path: "schedules/daily.json", revision: "schedule-one" }],
};

const viewDetail: ViewDetail = {
  ...workspace.views[0],
  payload: {
    schema_version: 3,
    id: "home",
    text: { inline: "Hello" },
    keyboard: [[{
      id: "submit_order",
      text: "Submit",
      action: { type: "handler.invoke", handler: "checkout.submit", outcomes: { success: { type: "flow.finish" } } },
    }]],
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(window, "studioDesktop");
});

describe("schema v3 Studio", () => {
  it("shows backend health and opens a v3 project", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    const api = apiMock();
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);
    expect(await screen.findByText("Backend online")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Existing schema v3 project"), { target: { value: "C:/demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Open project" }));
    expect(await screen.findByText("Schema v3")).toBeInTheDocument();
    expect(api.open).toHaveBeenCalledWith("C:/demo");
  });

  it("renders all typed explorer sections", () => {
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={vi.fn()} onAdd={vi.fn()} />);
    for (const section of ["Views", "Templates", "Flows", "Handlers", "Commands", "Schedules"]) {
      expect(screen.getByText(section)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: /checkout\.submit button · ready/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /commands.json commands.json/ })).toBeInTheDocument();
  });

  it("creates a missing custom button handler and asks Electron to open it", async () => {
    const missingWorkspace = { ...workspace, handlers: [] };
    const missingView: ViewDetail = {
      ...viewDetail,
      payload: {
        ...viewDetail.payload,
        keyboard: [[{ ...viewDetail.payload.keyboard[0][0], action: { type: "handler.invoke", handler: "checkout.submit", outcomes: {} } }]],
      },
    };
    const source = { projectRoot: "C:/demo", filePath: "src/demo/handlers/checkout_submit.py", line: 6 };
    const scaffold: HandlerScaffoldResult = { handler, created: true, source };
    const api = apiMock({
      getView: vi.fn().mockResolvedValue(missingView),
      createHandler: vi.fn().mockResolvedValue(scaffold),
      describe: vi.fn().mockResolvedValue(workspace),
    });
    const openCode = vi.fn().mockResolvedValue(undefined);
    window.studioDesktop = { backendInfo: vi.fn(), selectDirectory: vi.fn(), openCode };
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={missingWorkspace} />);
    fireEvent.click(screen.getByRole("button", { name: /home views\/home.json/ }));
    expect(await screen.findByText("Binding missing")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create handler" }));
    await waitFor(() => expect(api.createHandler).toHaveBeenCalledWith("project-1", {
      handler_id: "checkout.submit",
      kind: "button",
      registry_revision: "handlers-one",
      outcomes: [],
      description: undefined,
      attachment: { type: "view_button", view_id: "home", button_id: "submit_order" },
      target_revision: "view-one",
      routes: {},
    }));
    await waitFor(() => expect(openCode).toHaveBeenCalledWith(source));
  });

  it("keeps an unsaved action draft while scaffolding its handler", async () => {
    const draftView: ViewDetail = {
      ...viewDetail,
      payload: {
        ...viewDetail.payload,
        keyboard: [[{ ...viewDetail.payload.keyboard[0][0], action: { type: "noop" } }]],
      },
    };
    const source = { projectRoot: "C:/demo", filePath: "src/demo/handlers/checkout_submit.py", line: 6 };
    const api = apiMock({
      getView: vi.fn().mockResolvedValue(draftView),
      createHandler: vi.fn().mockResolvedValue({ handler, created: true, source }),
      describe: vi.fn().mockResolvedValue(workspace),
    });
    window.studioDesktop = { backendInfo: vi.fn(), selectDirectory: vi.fn(), openCode: vi.fn().mockResolvedValue(undefined) };
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={{ ...workspace, handlers: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: /home views\/home.json/ }));
    fireEvent.change(await screen.findByLabelText("Action"), { target: { value: "handler.invoke" } });
    fireEvent.change(screen.getByLabelText("Handler name"), { target: { value: "checkout.submit" } });
    fireEvent.click(screen.getByRole("button", { name: "Create handler" }));

    await waitFor(() => expect(api.createHandler).toHaveBeenCalledWith("project-1", {
      handler_id: "checkout.submit",
      kind: "button",
      registry_revision: "handlers-one",
      outcomes: [],
      description: undefined,
    }));
    expect(screen.getByDisplayValue("checkout.submit")).toBeInTheDocument();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(await screen.findByText(/reference is still only in this draft/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(api.saveView).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText(/reference is still only in this draft/)).not.toBeInTheDocument());
  });

  it("sends an open-code request for an existing handler", async () => {
    const source = { projectRoot: "C:/demo", filePath: "src/demo/handlers/checkout_submit.py", line: 4, column: 1 };
    const api = apiMock({ getHandler: vi.fn().mockResolvedValue(handler), handlerSource: vi.fn().mockResolvedValue(source) });
    const openCode = vi.fn().mockResolvedValue(undefined);
    window.studioDesktop = { backendInfo: vi.fn(), selectDirectory: vi.fn(), openCode };
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: /checkout.submit button · ready/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Open code" }));
    await waitFor(() => expect(openCode).toHaveBeenCalledWith(source));
  });

  it("creates a missing source for an existing binding before opening it", async () => {
    const missing = {
      ...handler,
      status: "missing_file" as const,
      source_file: "src/demo/handlers/checkout_submit.py",
      inspection: { status: "missing_file" as const, used: true, source: { path: "src/demo/handlers/checkout_submit.py" } },
    };
    const source = { projectRoot: "C:/demo", filePath: "C:/demo/src/demo/handlers/checkout_submit.py", line: 4, column: 1 };
    const api = apiMock({
      getHandler: vi.fn().mockResolvedValue(missing),
      repairHandlerSource: vi.fn().mockResolvedValue({ handler, created: true, source }),
    });
    const openCode = vi.fn().mockResolvedValue(undefined);
    window.studioDesktop = { backendInfo: vi.fn(), selectDirectory: vi.fn(), openCode };
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={{ ...workspace, handlers: [missing] }} />);
    fireEvent.click(screen.getByRole("button", { name: /checkout.submit button · missing_file/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Create missing source" }));

    await waitFor(() => expect(api.repairHandlerSource).toHaveBeenCalledWith("project-1", "checkout.submit", "handlers-one"));
    await waitFor(() => expect(openCode).toHaveBeenCalledWith(source));
  });

  it("scaffolds a global message fallback with an atomic commands attachment", async () => {
    const source = { projectRoot: "C:/demo", filePath: "src/demo/handlers/message_fallback.py", line: 5 };
    const fallbackHandler: HandlerDetail = { ...handler, id: "global.message_fallback", kind: "message", module: "demo.handlers.global_message_fallback", source_file: "src/demo/handlers/global_message_fallback.py" };
    const api = apiMock({
      getCommands: vi.fn().mockResolvedValue({
        source_path: "commands.json",
        revision: "commands-one",
        payload: {
          schema_version: 3,
          commands: [],
          message_fallback: { type: "handler.invoke", handler: "global.message_fallback", outcomes: { success: { type: "view.render", target: "home" } } },
        },
      }),
      createHandler: vi.fn().mockResolvedValue({ handler: fallbackHandler, created: true, source }),
      describe: vi.fn().mockResolvedValue(workspace),
    });
    const openCode = vi.fn().mockResolvedValue(undefined);
    window.studioDesktop = { backendInfo: vi.fn(), selectDirectory: vi.fn(), openCode };
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={{ ...workspace, handlers: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: /commands.json commands.json/ }));
    expect(await screen.findByText("Message fallback")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create handler" }));
    await waitFor(() => expect(api.createHandler).toHaveBeenCalledWith("project-1", {
      handler_id: "global.message_fallback",
      kind: "message",
      registry_revision: "handlers-one",
      outcomes: [],
      description: undefined,
      attachment: { type: "global_message_fallback" },
      target_revision: "commands-one",
      routes: { success: { type: "view.render", target: "home" } },
    }));
    await waitFor(() => expect(openCode).toHaveBeenCalledWith(source));
  });

  it("shows a revision conflict by diagnostic code", async () => {
    const api = apiMock({
      getView: vi.fn().mockResolvedValue({ ...viewDetail, payload: { ...viewDetail.payload, keyboard: [] } }),
      saveView: vi.fn().mockRejectedValue(new StudioApiError(409, "revision_conflict", "Changed outside Studio")),
    });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: /home views\/home.json/ }));
    const text = await screen.findByLabelText("Inline text");
    fireEvent.change(text, { target: { value: "Changed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Changed outside Studio")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload from disk" })).toBeInTheDocument();
  });

  it("does not save a view with an empty inline text or template path", async () => {
    const api = apiMock();
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: /home views\/home.json/ }));

    fireEvent.change(await screen.findByLabelText("Inline text"), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(screen.getByText("Inline text cannot be empty.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Inline text"), { target: { value: "Visible" } });
    expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();

    fireEvent.change(screen.getByLabelText("Text source"), { target: { value: "template" } });
    fireEvent.change(screen.getByLabelText("Template"), { target: { value: "  " } });
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(screen.getByText("Template path is required.")).toBeInTheDocument();
  });

  it("renders stable cross-resource diagnostic fields", () => {
    const issue: Diagnostic = { level: "error", code: "handler_binding_missing", message: "Unknown handler", source_path: "views/home.json", entity_id: "submit_order", field_path: "keyboard.0.0.action.handler" };
    render(<ValidationPanel issues={[issue]} onRefresh={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText("Unknown handler")).toBeInTheDocument();
    expect(screen.getByText("views/home.json · submit_order · keyboard.0.0.action.handler")).toBeInTheDocument();
  });
});

describe("BackendStatusCard", () => {
  it("shows an unavailable backend and retry action", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<BackendStatusCard apiBaseUrl="http://studio.test" />);
    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

function apiMock(overrides: Partial<StudioApiClient> = {}): StudioApiClient {
  return {
    open: vi.fn().mockResolvedValue(workspace),
    create: vi.fn().mockResolvedValue(workspace),
    describe: vi.fn().mockResolvedValue(workspace),
    getView: vi.fn().mockResolvedValue(viewDetail),
    createView: vi.fn().mockResolvedValue(viewDetail),
    saveView: vi.fn().mockResolvedValue(viewDetail),
    deleteView: vi.fn().mockResolvedValue(undefined),
    getTemplate: vi.fn().mockResolvedValue({ path: "home.txt", content: "Hello", revision: "template-one" }),
    saveTemplate: vi.fn().mockResolvedValue({ path: "home.txt", content: "Hello", revision: "template-one" }),
    getFlow: vi.fn().mockResolvedValue({ id: "checkout", source_path: "flows/checkout.json", revision: "flow-one", payload: { schema_version: 3, id: "checkout", initial_state: "start", lifecycle: {}, states: { start: { view: "home", events: {} } } } }),
    createFlow: vi.fn(),
    saveFlow: vi.fn(),
    deleteFlow: vi.fn(),
    getCommands: vi.fn().mockResolvedValue({ source_path: "commands.json", revision: "commands-one", payload: { schema_version: 3, commands: [] } }),
    saveCommands: vi.fn(),
    getSchedule: vi.fn().mockResolvedValue({ id: "daily", source_path: "schedules/daily.json", revision: "schedule-one", payload: { schema_version: 3, id: "daily", handler: "task.daily", trigger: { type: "interval", seconds: 60 }, payload: {} } }),
    createSchedule: vi.fn(),
    saveSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
    getHandler: vi.fn().mockResolvedValue(handler),
    createHandler: vi.fn(),
    repairHandlerSource: vi.fn(),
    deleteHandler: vi.fn(),
    handlerSource: vi.fn(),
    handlerUsages: vi.fn().mockResolvedValue([]),
    preview: vi.fn().mockResolvedValue({ text: "Hello", keyboard: [], warnings: [] }),
    validate: vi.fn().mockResolvedValue([]),
    ...overrides,
  };
}
