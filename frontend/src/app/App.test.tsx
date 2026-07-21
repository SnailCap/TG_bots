import { StrictMode } from "react";
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
import { App, BackendStatusCard, LAST_PROJECT_STORAGE_KEY } from "./App";

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
  window.localStorage.clear();
});

describe("Studio", () => {
  it("shows backend health and opens a project", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    const api = apiMock();
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);
    expect(await screen.findByText("Backend online")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Existing project"), { target: { value: "C:/demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Open project" }));
    expect((await screen.findAllByText("demo")).length).toBeGreaterThan(0);
    expect(api.open).toHaveBeenCalledWith("C:/demo");
    expect(window.localStorage.getItem(LAST_PROJECT_STORAGE_KEY)).toBe("C:/demo");
  });

  it("restores the last project during development startup", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    window.localStorage.setItem(LAST_PROJECT_STORAGE_KEY, "C:/demo");
    const api = apiMock();
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);
    await waitFor(() => expect(api.open).toHaveBeenCalledWith("C:/demo"));
    expect((await screen.findAllByText("demo")).length).toBeGreaterThan(0);
  });

  it("restores the last project after React development remounting", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    window.localStorage.setItem(LAST_PROJECT_STORAGE_KEY, "C:/demo");
    const api = apiMock();
    render(<StrictMode><App apiBaseUrl="http://studio.test" apiClient={api} /></StrictMode>);
    expect((await screen.findAllByText("demo")).length).toBeGreaterThan(0);
  });

  it("keeps the last project path after a transient automatic restore failure", async () => {
    window.localStorage.setItem(LAST_PROJECT_STORAGE_KEY, "C:/demo");
    const api = apiMock({ open: vi.fn().mockRejectedValue(new Error("backend restarting")) });
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);
    await waitFor(() => expect(api.open).toHaveBeenCalledWith("C:/demo"));
    expect(window.localStorage.getItem(LAST_PROJECT_STORAGE_KEY)).toBe("C:/demo");
  });

  it("keeps manual project controls available while automatic restore is pending", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    window.localStorage.setItem(LAST_PROJECT_STORAGE_KEY, "C:/stale-project");
    const api = apiMock({ open: vi.fn().mockReturnValue(new Promise<Workspace>(() => undefined)) });
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);
    fireEvent.change(screen.getByLabelText("Existing project"), { target: { value: "C:/demo" } });
    expect(screen.getByRole("button", { name: "Open project" })).toBeEnabled();
  });

  it("renders all typed explorer sections", () => {
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={vi.fn()} onAdd={vi.fn()} />);
    for (const section of ["views", "templates", "flows", "handlers", "commands.json", "schedules"]) {
      expect(screen.getAllByText(section).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("button", { name: "checkout.submit" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "commands.json" })[1]).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "home" }));
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
    fireEvent.click(screen.getByRole("button", { name: "home" }));
    fireEvent.click(await screen.findByLabelText("Action"));
    fireEvent.click(screen.getByRole("option", { name: "Custom handler" }));
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
    expect(await screen.findByText(/reference is still only in this draft/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.saveView).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText(/reference is still only in this draft/)).not.toBeInTheDocument());
  });

  it("sends an open-code request for an existing handler", async () => {
    const source = { projectRoot: "C:/demo", filePath: "src/demo/handlers/checkout_submit.py", line: 4, column: 1 };
    const api = apiMock({ getHandler: vi.fn().mockResolvedValue(handler), handlerSource: vi.fn().mockResolvedValue(source) });
    const openCode = vi.fn().mockResolvedValue(undefined);
    window.studioDesktop = { backendInfo: vi.fn(), selectDirectory: vi.fn(), openCode };
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: "checkout.submit" }));
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
    fireEvent.click(screen.getByRole("button", { name: "checkout.submit" }));
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
    fireEvent.click(screen.getAllByRole("button", { name: "commands.json" })[1]);
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
    fireEvent.click(screen.getByRole("button", { name: "home" }));
    const text = await screen.findByLabelText("Inline text");
    fireEvent.change(text, { target: { value: "Changed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Changed outside Studio")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload from disk" })).toBeInTheDocument();
  });

  it("does not save a view with an empty inline text or template path", async () => {
    const api = apiMock();
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: "home" }));

    fireEvent.change(await screen.findByLabelText("Inline text"), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.queryByText("Inline text cannot be empty.")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Inline text"), { target: { value: "Visible" } });
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();

    fireEvent.click(screen.getByLabelText("Text source"));
    fireEvent.click(screen.getByRole("option", { name: "Template" }));
    expect(screen.queryByRole("listbox", { name: "Text source" })).not.toBeInTheDocument();
    const templateInput = screen.getByLabelText("Template");
    fireEvent.change(templateInput, { target: { value: "ho" } });
    fireEvent.mouseDown(screen.getByRole("option", { name: "home.txt" }));
    expect(templateInput).toHaveValue("home.txt");
    fireEvent.change(templateInput, { target: { value: "  " } });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.queryByText("Template path is required.")).not.toBeInTheDocument();
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
    renameView: vi.fn().mockResolvedValue(viewDetail),
    deleteView: vi.fn().mockResolvedValue(undefined),
    getTemplate: vi.fn().mockResolvedValue({ path: "home.txt", content: "Hello", revision: "template-one" }),
    saveTemplate: vi.fn().mockResolvedValue({ path: "home.txt", content: "Hello", revision: "template-one" }),
    deleteTemplate: vi.fn().mockResolvedValue(undefined),
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
