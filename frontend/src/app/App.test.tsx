import { StrictMode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CommandsDetail,
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
  flows: [{ id: "checkout", source_path: "flows/checkout.json", revision: "flow-one", states: ["details", "confirm"] }],
  handlers: [handler],
  handlers_revision: "handlers-one",
  commands: { source_path: "commands.json", revision: "commands-one", items: [] },
  schedules: [{ id: "daily", source_path: "schedules/daily.json", revision: "schedule-one" }],
};

const viewDetail: ViewDetail = {
  ...workspace.views[0],
  text_content: "Hello",
  text_revision: "text-one",
  payload: {
    schema_version: 3,
    id: "home",
    text: { template: "views/home.txt" },
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
  it("toggles the terminal with Ctrl+` in the russian keyboard layout", () => {
    render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.keyDown(window, { key: "ё", code: "Backquote", ctrlKey: true });
    expect(screen.getByLabelText("Bot terminal")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "ё", code: "Backquote", ctrlKey: true });
    expect(screen.queryByLabelText("Bot terminal")).not.toBeInTheDocument();
  });

  it("saves the active resource with Ctrl+S in the russian keyboard layout", async () => {
    const renameView = vi.fn().mockResolvedValue({ ...viewDetail, id: "start", payload: { ...viewDetail.payload, id: "start" }, revision: "view-two" });
    const api = apiMock({ renameView });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Name:"), { target: { value: "start" } });
    const event = new KeyboardEvent("keydown", { key: "ы", code: "KeyS", ctrlKey: true, cancelable: true });
    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    await waitFor(() => expect(renameView).toHaveBeenCalledWith("project-1", "home", "start", "view-one"));
  });

  it("closes the active tab with Ctrl+W in the russian keyboard layout", async () => {
    render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    expect(await screen.findByLabelText("View editor")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "ц", code: "KeyW", ctrlKey: true });

    expect(screen.queryByLabelText("View editor")).not.toBeInTheDocument();
  });

  it("starts and stops the local bot while streaming its output to the terminal", async () => {
    const runProject = vi.fn().mockResolvedValue({ pid: 4210, alreadyRunning: false });
    const stopProject = vi.fn().mockResolvedValue(undefined);
    const approveProjectRoot = vi.fn().mockResolvedValue(undefined);
    let outputListener: ((event: import("../../electron/contracts").ProjectProcessEvent) => void) | undefined;
    window.studioDesktop = {
      backendInfo: vi.fn(),
      selectDirectory: vi.fn(),
      openCode: vi.fn(),
      approveProjectRoot,
      runProject,
      stopProject,
      projectRunStatus: vi.fn().mockResolvedValue({ running: false, pid: null }),
      onProjectOutput: vi.fn((listener) => { outputListener = listener; return vi.fn(); }),
    };
    render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "Run local bot" }));

    await waitFor(() => expect(runProject).toHaveBeenCalledWith({ projectRoot: "C:/demo", packageName: "demo" }));
    expect(approveProjectRoot).toHaveBeenCalledWith("C:/demo");
    expect(screen.queryByText("Local bot started (PID 4210).")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Bot terminal")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop local bot" })).toBeInTheDocument();

    act(() => outputListener?.({
      sequence: 1,
      projectRoot: "C:/demo",
      stream: "stdout",
      text: "Bot is ready\n",
      timestamp: new Date().toISOString(),
      running: true,
      pid: 4210,
    }));
    expect(screen.getByRole("log")).toHaveTextContent("Bot is ready");

    fireEvent.click(screen.getByRole("button", { name: "Stop local bot" }));
    await waitFor(() => expect(stopProject).toHaveBeenCalledWith("C:/demo"));
    act(() => outputListener?.({
      sequence: 2,
      projectRoot: "C:/demo",
      stream: "lifecycle",
      text: "[studio] Bot stopped.\n",
      timestamp: new Date().toISOString(),
      running: false,
      pid: null,
    }));
    expect(screen.getByRole("button", { name: "Run local bot" })).toBeInTheDocument();
    expect(screen.queryByText("Stopped")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close terminal" }));
    expect(screen.queryByLabelText("Bot terminal")).not.toBeInTheDocument();
  });

  it("saves the active resource before starting the local bot", async () => {
    const saveView = vi.fn().mockResolvedValue(viewDetail);
    const runProject = vi.fn().mockResolvedValue({ pid: 4210, alreadyRunning: false });
    window.studioDesktop = {
      backendInfo: vi.fn(),
      selectDirectory: vi.fn(),
      openCode: vi.fn(),
      approveProjectRoot: vi.fn().mockResolvedValue(undefined),
      runProject,
      stopProject: vi.fn().mockResolvedValue(undefined),
      projectRunStatus: vi.fn().mockResolvedValue({ running: false, pid: null }),
      onProjectOutput: vi.fn(() => vi.fn()),
    };
    const api = apiMock({ saveView });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    setVisualMessage("Changed before run");

    const runButton = screen.getByRole("button", { name: "Run local bot" });
    expect(runButton).toBeEnabled();
    fireEvent.click(runButton);

    await waitFor(() => expect(saveView).toHaveBeenCalled());
    await waitFor(() => expect(runProject).toHaveBeenCalledWith({ projectRoot: "C:/demo", packageName: "demo" }));
  });

  it("shows live editor information in the application status bar", async () => {
    render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    expect(screen.getByRole("status")).toHaveTextContent("Ready");

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    expect(screen.getByText("View · home")).toBeInTheDocument();

    setVisualMessage("Changed");
    expect(screen.getByRole("status")).toHaveTextContent("Unsaved changes");
    expect(screen.getByText("Schema v3")).toBeInTheDocument();
  });

  it("keeps explorer selection independent from switching editor tabs", async () => {
    const { container } = render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    const resourceButton = (label: string) => Array.from(container.querySelectorAll<HTMLButtonElement>(".explorer__item, .explorer__flow-main"))
      .find((button) => button.textContent?.trim() === label)!;

    fireEvent.click(resourceButton("home"));
    await screen.findByLabelText("View editor");
    fireEvent.click(resourceButton("checkout"));
    await screen.findByLabelText("Flow editor");
    expect(resourceButton("checkout")).toHaveAttribute("aria-current", "page");

    const homeTab = Array.from(container.querySelectorAll<HTMLButtonElement>(".editor-tab__select"))
      .find((button) => button.textContent?.includes("home"))!;
    fireEvent.click(homeTab);

    expect(resourceButton("checkout")).toHaveAttribute("aria-current", "page");
    expect(resourceButton("home")).not.toHaveAttribute("aria-current", "page");
    expect(await screen.findByLabelText("View editor")).toBeInTheDocument();
  });

  it("saves the active resource before switching to another resource", async () => {
    const saveView = vi.fn().mockResolvedValue(viewDetail);
    const api = apiMock({ saveView });
    const { container } = render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    const resourceButton = (label: string) => Array.from(container.querySelectorAll<HTMLButtonElement>(".explorer__item, .explorer__flow-main"))
      .find((button) => button.textContent?.trim() === label)!;

    fireEvent.click(resourceButton("home"));
    await screen.findByLabelText("View editor");
    setVisualMessage("Changed before switching");
    fireEvent.click(resourceButton("checkout"));

    await waitFor(() => expect(saveView).toHaveBeenCalled());
    expect(await screen.findByLabelText("Flow editor")).toBeInTheDocument();
  });

  it("opens the rich view text editor in a separate saveable tab", async () => {
    render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));

    expect(await screen.findByLabelText("Rich text editor")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Rich message content" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Telegram message preview" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /home text$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("saves the compact resource before opening its text tab", async () => {
    const saveView = vi.fn().mockResolvedValue(viewDetail);
    const api = apiMock({ saveView });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    setVisualMessage("Changed before opening text");
    fireEvent.click(screen.getByRole("button", { name: "Expand home" }));
    fireEvent.click(screen.getByRole("button", { name: "Open text editor for home" }));

    await waitFor(() => expect(saveView).toHaveBeenCalled());
    expect(await screen.findByLabelText("Rich text editor")).toBeInTheDocument();
  });

  it("mounts the rich view text editor safely in React StrictMode", async () => {
    render(<StrictMode><StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} /></StrictMode>);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));

    expect(await screen.findByRole("textbox", { name: "Rich message content" })).toBeInTheDocument();
    expect(screen.queryByRole("listbox", { name: "Slash commands" })).not.toBeInTheDocument();
  });

  it("migrates legacy view text through the revision-aware rich content save", async () => {
    const saveViewContent = vi.fn().mockImplementation(async (
      _projectId: string,
      _id: string,
      _payload: ViewDetail["payload"],
      _revision: string,
      document: NonNullable<ViewDetail["content_document"]>,
    ): Promise<ViewDetail> => ({
      ...viewDetail,
      revision: "view-two",
      text_revision: "text-two",
      content_revision: "content-one",
      content_document: document,
      payload: { ...viewDetail.payload, text: { template: "views/home.txt", document: "views/home.json" } },
    }));
    const api = apiMock({ saveViewContent });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));
    await screen.findByRole("textbox", { name: "Rich message content" });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(saveViewContent).toHaveBeenCalled());
    const [, id, payload, revision, document, documentRevision, textRevision] = saveViewContent.mock.calls[0];
    expect({ id, payload, revision, documentRevision, textRevision }).toEqual({
      id: "home",
      payload: viewDetail.payload,
      revision: "view-one",
      documentRevision: null,
      textRevision: "text-one",
    });
    expect(document).toMatchObject({
      schemaVersion: 1,
      id: "home",
      content: [{ type: "paragraph", content: [{ type: "text", text: "Hello" }] }],
    });
  });

  it("recovers a revision-matched rich content draft after an interrupted session", async () => {
    const recovered = {
      schemaVersion: 1 as const,
      id: "home",
      content: [{ type: "paragraph" as const, content: [{ type: "text" as const, text: "Recovered draft" }] }],
      metadata: {
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:01:00.000Z",
        editorVersion: "1.0.0",
        source: "botstudio" as const,
      },
    };
    window.localStorage.setItem(
      "botstudio:content-draft:v1:C%3A%2Fdemo:home",
      JSON.stringify({ schemaVersion: 1, baseRevision: "view-one", updatedAt: recovered.metadata.updatedAt, document: recovered }),
    );
    const saveViewContent = vi.fn().mockImplementation(async (
      _projectId: string,
      _id: string,
      _payload: ViewDetail["payload"],
      _revision: string,
      document: NonNullable<ViewDetail["content_document"]>,
    ): Promise<ViewDetail> => ({ ...viewDetail, content_document: document, content_revision: "content-one" }));
    render(<StudioPage api={apiMock({ saveViewContent })} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));

    expect(await screen.findByText("Recovered a newer local draft. It will be saved after validation.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Rich message content" })).toHaveTextContent("Recovered draft"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saveViewContent).toHaveBeenCalled());
    expect(saveViewContent.mock.calls.at(-1)?.[4]).toMatchObject(recovered);
  });

  it("removes the recovery draft when the user explicitly discards a dirty rich tab", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<StudioPage api={apiMock()} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "home" }));
    await screen.findByLabelText("View editor");
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));
    await screen.findByRole("textbox", { name: "Rich message content" });

    const draftKey = "botstudio:content-draft:v1:C%3A%2Fdemo:home";
    window.localStorage.setItem(draftKey, "explicit-discard-sentinel");
    fireEvent.click(screen.getByRole("button", { name: "Close home text" }));

    expect(confirmSpy).toHaveBeenCalledWith("Discard unsaved changes?");
    expect(window.localStorage.getItem(draftKey)).toBeNull();
    expect(screen.queryByLabelText("Rich text editor")).not.toBeInTheDocument();
  });

  it("shows backend health and opens a project", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    const api = apiMock();
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);
    expect(await screen.findByText("Backend online")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.change(screen.getByLabelText("Project folder"), { target: { value: "C:/demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Open project" }));
    expect((await screen.findAllByText("demo")).length).toBeGreaterThan(0);
    expect(api.open).toHaveBeenCalledWith("C:/demo");
    expect(window.localStorage.getItem(LAST_PROJECT_STORAGE_KEY)).toBe("C:/demo");
  });

  it("provides a titlebar drag region before a project is open", () => {
    const { container } = render(<App apiBaseUrl="http://studio.test" apiClient={apiMock()} />);

    expect(container.querySelector(".welcome__titlebar")).toHaveTextContent("Telegram Bot Studio");
    expect(screen.queryByLabelText("Project name")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "New project" }));
    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
    expect(screen.queryByLabelText("Project folder")).not.toBeInTheDocument();
  });

  it("prepares a managed Python environment while creating a project", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    const approveProjectRoot = vi.fn().mockResolvedValue(undefined);
    const prepareProject = vi.fn().mockResolvedValue({ python: "C:/demo/.venv/Scripts/python.exe" });
    window.studioDesktop = {
      backendInfo: vi.fn(),
      selectDirectory: vi.fn(),
      openCode: vi.fn(),
      approveProjectRoot,
      prepareProject,
    };
    const api = apiMock();
    render(<App apiBaseUrl="http://studio.test" apiClient={api} />);

    fireEvent.click(screen.getByRole("button", { name: "New project" }));
    fireEvent.change(screen.getByLabelText("Location"), { target: { value: "C:/bots" } });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(api.create).toHaveBeenCalledWith("C:/bots", "my-bot"));
    expect(approveProjectRoot).toHaveBeenCalledWith("C:/demo");
    expect(prepareProject).toHaveBeenCalledWith({ projectRoot: "C:/demo", packageName: "demo" });
    expect((await screen.findAllByText("demo")).length).toBeGreaterThan(0);
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
    expect(screen.getByRole("button", { name: "Open" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "New project" })).toBeEnabled();
  });

  it("renders all typed explorer sections", () => {
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={vi.fn()} onAdd={vi.fn()} />);
    for (const section of ["views", "flows", "handlers", "commands", "schedules"]) {
      expect(screen.getAllByText(section).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("button", { name: "checkout.submit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "fallbacks" })).toBeInTheDocument();
  });

  it("creates a command as an individual resource from the commands section", async () => {
    const emptyCommands: CommandsDetail = {
      source_path: "commands.json",
      revision: "commands-one",
      payload: { schema_version: 3, commands: [] },
    };
    const createdCommands: CommandsDetail = {
      ...emptyCommands,
      revision: "commands-two",
      payload: { schema_version: 3, commands: [{ name: "command_1", action: { type: "noop" } }] },
    };
    const commandsWorkspace: Workspace = {
      ...workspace,
      commands: { ...workspace.commands, items: [] },
    };
    const saveCommands = vi.fn().mockResolvedValue(createdCommands);
    const api = apiMock({
      getCommands: vi.fn().mockResolvedValue(emptyCommands),
      saveCommands,
      describe: vi.fn().mockResolvedValue({
        ...commandsWorkspace,
        commands: { ...commandsWorkspace.commands, revision: "commands-two", items: [{ name: "command_1" }] },
      }),
    });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={commandsWorkspace} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "commands" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "New command" }));

    await waitFor(() => expect(saveCommands).toHaveBeenCalledWith("project-1", {
      schema_version: 3,
      commands: [{ name: "command_1", action: { type: "noop" } }],
    }, "commands-one"));
    expect(await screen.findByLabelText("Command editor")).toBeInTheDocument();
    expect(screen.getByLabelText("Command name")).toHaveValue("command_1");
  });

  it("edits one selected command without exposing the aggregate list", async () => {
    const commandDetail: CommandsDetail = {
      source_path: "commands.json",
      revision: "commands-one",
      payload: {
        schema_version: 3,
        commands: [{ name: "help", description: "Preserved", action: { type: "view.render", target: "home" } }],
      },
    };
    const renamedDetail: CommandsDetail = {
      ...commandDetail,
      revision: "commands-two",
      payload: {
        ...commandDetail.payload,
        commands: [{ name: "support", description: "Preserved", action: { type: "view.render", target: "home" } }],
      },
    };
    const commandsWorkspace: Workspace = {
      ...workspace,
      commands: { ...workspace.commands, items: [{ name: "help", description: "Preserved" }] },
    };
    const saveCommands = vi.fn().mockResolvedValueOnce(renamedDetail);
    const api = apiMock({
      getCommands: vi.fn().mockResolvedValue(commandDetail),
      saveCommands,
      describe: vi.fn().mockResolvedValue(commandsWorkspace),
    });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={commandsWorkspace} />);

    fireEvent.click(screen.getByRole("button", { name: "help" }));
    expect(await screen.findByLabelText("Command editor")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Command name")).toHaveLength(1);
    expect(screen.getByLabelText("Command access")).toBeInTheDocument();
    expect(screen.getByLabelText("Description:")).toHaveValue("Preserved");
    expect(screen.getByLabelText("Action")).toBeInTheDocument();
    expect(screen.getByLabelText("Action target")).toHaveValue("home");
    expect(screen.getByRole("button", { name: "Browse views" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open current action target" })).toBeEnabled();

    fireEvent.change(screen.getByLabelText("Command name"), { target: { value: "Support" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(saveCommands).toHaveBeenNthCalledWith(1, "project-1", {
      ...commandDetail.payload,
      commands: [{ name: "support", description: "Preserved", action: { type: "view.render", target: "home" } }],
    }, "commands-one"));
    expect(await screen.findByRole("heading", { name: "/support" })).toBeInTheDocument();

  });

  it("opens project settings from the activity rail and saves a bot token", async () => {
    const api = apiMock();
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(await screen.findByRole("dialog", { name: "Project settings" })).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Bot token:"), { target: { value: "123456:token" } });
    fireEvent.click(screen.getByRole("button", { name: "Save token" }));

    await waitFor(() => expect(api.saveProjectSettings).toHaveBeenCalledWith("project-1", {
      telegram_bot_token: "123456:token",
      revision: null,
    }));
  });

  it("routes activity rail links to separate Resources and Users pages", async () => {
    const api = apiMock();
    const { container } = render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    expect(screen.getByRole("link", { name: "Resources" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("link", { name: "Users" }));

    expect(await screen.findByRole("region", { name: "User management" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Users" })).toHaveAttribute("aria-current", "page");
    expect(container.querySelector(".workspace")).toHaveClass("workspace--users");
    expect(api.listUsers).toHaveBeenCalledWith("project-1");

    fireEvent.click(screen.getByRole("link", { name: "Resources" }));
    expect(await screen.findByRole("heading", { name: "Select a resource" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Resources" })).toHaveAttribute("aria-current", "page");
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
    fireEvent.click(await screen.findByRole("button", { name: "Submit" }));
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
    fireEvent.click(await screen.findByRole("button", { name: "Submit" }));
    fireEvent.click(await screen.findByLabelText("Action"));
    fireEvent.click(screen.getByRole("option", { name: "Custom handler" }));
    fireEvent.change(screen.getByLabelText("Handler name:"), { target: { value: "checkout.submit" } });
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
    fireEvent.click(screen.getByRole("button", { name: "fallbacks" }));
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
    await screen.findByLabelText("Message text editor");
    setVisualMessage("Changed");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Changed outside Studio")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload from disk" })).toBeInTheDocument();
  });

  it("allows a view draft to be saved while its content is still empty", async () => {
    const api = apiMock();
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: "home" }));

    await screen.findByLabelText("Message text editor");
    setVisualMessage("   ");
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    expect(screen.getByLabelText("Invalid unsaved changes")).toBeInTheDocument();
    setVisualMessage("Visible");
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    expect(screen.getByLabelText("Unsaved changes")).toBeInTheDocument();
  });

  it("persists a new resource immediately and adds it to Resources", async () => {
    const created: ViewDetail = {
      id: "new-view",
      source_path: "views/new-view.json",
      revision: "view-new",
      text_content: "",
      text_revision: "text-new",
      payload: { schema_version: 3, id: "new-view", text: { template: "views/new-view.txt" }, keyboard: [] },
    };
    const api = apiMock({
      createView: vi.fn().mockResolvedValue(created),
      describe: vi.fn().mockResolvedValue({ ...workspace, views: [...workspace.views, created] }),
    });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "views" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "New view" }));

    await waitFor(() => expect(api.createView).toHaveBeenCalledWith("project-1", "new-view", {
      schema_version: 3,
      id: "new-view",
      text: { inline: "" },
      keyboard: [],
    }));
    expect((await screen.findAllByText("new-view")).length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("new-view")).toBeInTheDocument();
  });

  it("saves a changed view name through the rename operation", async () => {
    const renamed: ViewDetail = {
      ...viewDetail,
      id: "welcome",
      source_path: "views/welcome.json",
      revision: "view-renamed",
      payload: { ...viewDetail.payload, id: "welcome" },
    };
    const api = apiMock({ renameView: vi.fn().mockResolvedValue(renamed) });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: "home" }));

    fireEvent.change(await screen.findByLabelText("Name:"), { target: { value: "welcome" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.renameView).toHaveBeenCalledWith("project-1", "home", "welcome", "view-one"));
    expect(screen.getByDisplayValue("welcome")).toBeInTheDocument();
  });

  it("keeps the selected explorer item mounted until a renamed resource and workspace refresh commit together", async () => {
    const renamed: ViewDetail = {
      ...viewDetail,
      id: "welcome",
      source_path: "views/welcome.json",
      revision: "view-renamed",
      payload: { ...viewDetail.payload, id: "welcome" },
    };
    let resolveDescribe!: (value: Workspace) => void;
    const describe = vi.fn().mockReturnValue(new Promise<Workspace>((resolve) => {
      resolveDescribe = resolve;
    }));
    const api = apiMock({
      renameView: vi.fn().mockResolvedValue(renamed),
      describe,
    });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    fireEvent.click(screen.getByRole("button", { name: "home" }));

    fireEvent.change(await screen.findByLabelText("Name:"), { target: { value: "welcome" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(describe).toHaveBeenCalledWith("project-1"));
    expect(screen.getByRole("button", { name: "home" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: "welcome" })).not.toBeInTheDocument();

    await act(async () => {
      resolveDescribe({ ...workspace, views: [{ id: "welcome", source_path: "views/welcome.json", revision: "view-renamed" }] });
    });

    expect(await screen.findByRole("button", { name: "welcome" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: "home" })).not.toBeInTheDocument();
  });

  it("renames a view from its resource context menu", async () => {
    const renamed: ViewDetail = { ...viewDetail, id: "welcome", source_path: "views/welcome.json", revision: "view-renamed", payload: { ...viewDetail.payload, id: "welcome" } };
    const api = apiMock({ renameView: vi.fn().mockResolvedValue(renamed) });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "home" }));
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const input = await screen.findByLabelText("Rename home");
    fireEvent.change(input, { target: { value: "welcome" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(api.renameView).toHaveBeenCalledWith("project-1", "home", "welcome", "view-one"));
  });

  it("deletes a resource without a confirmation dialog and undoes it with Ctrl+Z", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const api = apiMock();
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "home" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));

    await waitFor(() => expect(api.deleteView).toHaveBeenCalledWith("project-1", "home", "view-one"));
    expect(confirmSpy).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "я", code: "KeyZ", ctrlKey: true });

    await waitFor(() => expect(api.createView).toHaveBeenCalledWith("project-1", "home", viewDetail.payload, viewDetail.text_content, undefined));
  });

  it("saves a dirty rich-text tab before switching back to the compact editor", async () => {
    let resolveSave!: (detail: ViewDetail) => void;
    const saveViewContent = vi.fn().mockReturnValue(new Promise<ViewDetail>((resolve) => { resolveSave = resolve; }));
    const api = apiMock({ saveViewContent });
    const { container } = render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);
    const homeResource = container.querySelector<HTMLButtonElement>(".explorer__view-main")!;

    fireEvent.click(homeResource);
    await screen.findByLabelText("View editor");
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));
    await screen.findByRole("textbox", { name: "Rich message content" });
    fireEvent.click(homeResource);
    await waitFor(() => expect(saveViewContent).toHaveBeenCalled());
    expect(screen.getByLabelText("Rich text editor")).toBeInTheDocument();

    resolveSave({ ...viewDetail, content_revision: "content-one" });
    expect(await screen.findByLabelText("View editor")).toBeInTheDocument();
    expect(screen.queryByText("Save this view text (or wait for autosave) before switching editor modes.")).not.toBeInTheDocument();
  });

  it("undoes a rename with Ctrl+Z", async () => {
    const renamed: ViewDetail = { ...viewDetail, id: "welcome", source_path: "views/welcome.json", revision: "view-renamed", payload: { ...viewDetail.payload, id: "welcome" } };
    const api = apiMock({ renameView: vi.fn().mockResolvedValueOnce(renamed).mockResolvedValueOnce(viewDetail) });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "home" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const input = await screen.findByLabelText("Rename home");
    fireEvent.change(input, { target: { value: "welcome" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(api.renameView).toHaveBeenCalledWith("project-1", "home", "welcome", "view-one"));

    fireEvent.keyDown(window, { key: "z", ctrlKey: true });

    await waitFor(() => expect(api.renameView).toHaveBeenCalledWith("project-1", "welcome", "home", "view-one"));
  });

  it("renames resources inline, including with F2", async () => {
    const api = apiMock({
      renameFlow: vi.fn().mockResolvedValue({ id: "purchase", source_path: "flows/purchase.json", revision: "flow-renamed", payload: { schema_version: 3, id: "purchase", initial_state: "start", lifecycle: {}, states: { start: { view: "home", events: {} } } } }),
      renameSchedule: vi.fn().mockResolvedValue({ id: "nightly", source_path: "schedules/nightly.json", revision: "schedule-renamed", payload: { schema_version: 3, id: "nightly", handler: "task.daily", trigger: { type: "interval", seconds: 60 }, payload: {} } }),
      renameHandler: vi.fn().mockResolvedValue({ ...handler, id: "checkout.process" }),
    });
    render(<StudioPage api={api} apiBaseUrl="http://studio.test" initialWorkspace={workspace} />);

    const rename = async (label: string, name: string) => {
      fireEvent.click(screen.getByRole("button", { name: label }));
      fireEvent.keyDown(window, { key: "F2" });
      const input = await screen.findByLabelText(`Rename ${label}`);
      fireEvent.change(input, { target: { value: name } });
      fireEvent.keyDown(input, { key: "Enter" });
    };
    await rename("checkout", "purchase");
    await waitFor(() => expect(api.renameFlow).toHaveBeenCalledWith("project-1", "checkout", "purchase", "flow-one"));
    await rename("daily", "nightly");
    await waitFor(() => expect(api.renameSchedule).toHaveBeenCalledWith("project-1", "daily", "nightly", "schedule-one"));
    await rename("checkout.submit", "checkout.process");
    await waitFor(() => expect(api.renameHandler).toHaveBeenCalledWith("project-1", "checkout.submit", "checkout.process", "handler-one"));
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

function setVisualMessage(value: string) {
  const editor = screen.getByRole("textbox", { name: "Visual message content" });
  const textNode = editor.querySelector<HTMLElement>("[data-template-node='text']") ?? editor;
  textNode.textContent = value;
  fireEvent.input(editor);
}

function apiMock(overrides: Partial<StudioApiClient> = {}): StudioApiClient {
  return {
    open: vi.fn().mockResolvedValue(workspace),
    create: vi.fn().mockResolvedValue(workspace),
    describe: vi.fn().mockResolvedValue(workspace),
    getProjectSettings: vi.fn().mockResolvedValue({ telegram_bot_token_configured: false, revision: null }),
    saveProjectSettings: vi.fn().mockResolvedValue({ telegram_bot_token_configured: true, revision: "settings-one" }),
    resolveCustomEmojis: vi.fn().mockResolvedValue({ items: [] }),
    customEmojiPreviewUrl: vi.fn().mockReturnValue("http://studio.test/custom-emoji.webp"),
    testCustomEmojiCapability: vi.fn().mockResolvedValue({ capability: "unknown" }),
    listUsers: vi.fn().mockResolvedValue([]),
    updateUser: vi.fn(),
    getView: vi.fn().mockResolvedValue(viewDetail),
    createView: vi.fn().mockResolvedValue(viewDetail),
    saveView: vi.fn().mockResolvedValue(viewDetail),
    saveViewContent: vi.fn().mockResolvedValue(viewDetail),
    renameView: vi.fn().mockResolvedValue(viewDetail),
    deleteView: vi.fn().mockResolvedValue(undefined),
    getFlow: vi.fn().mockResolvedValue({ id: "checkout", source_path: "flows/checkout.json", revision: "flow-one", payload: { schema_version: 3, id: "checkout", initial_state: "start", lifecycle: {}, states: { start: { view: "home", events: {} } } } }),
    createFlow: vi.fn(),
    saveFlow: vi.fn(),
    renameFlow: vi.fn(),
    deleteFlow: vi.fn(),
    getCommands: vi.fn().mockResolvedValue({ source_path: "commands.json", revision: "commands-one", payload: { schema_version: 3, commands: [] } }),
    saveCommands: vi.fn(),
    getSchedule: vi.fn().mockResolvedValue({ id: "daily", source_path: "schedules/daily.json", revision: "schedule-one", payload: { schema_version: 3, id: "daily", handler: "task.daily", trigger: { type: "interval", seconds: 60 }, payload: {} } }),
    createSchedule: vi.fn(),
    saveSchedule: vi.fn(),
    renameSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
    getHandler: vi.fn().mockResolvedValue(handler),
    renameHandler: vi.fn(),
    createHandler: vi.fn(),
    repairHandlerSource: vi.fn(),
    deleteHandler: vi.fn(),
    handlerSource: vi.fn(),
    handlerUsages: vi.fn().mockResolvedValue([]),
    preview: vi.fn().mockResolvedValue({ text: "Hello", keyboard: [], warnings: [] }),
    compileContent: vi.fn().mockResolvedValue({ messages: [{ text: "Hello", entities: [] }], warnings: [], errors: [] }),
    sendPreviewMessage: vi.fn().mockResolvedValue({ sent: true, sentCount: 1, totalCount: 1, messageIds: [1], warnings: [] }),
    validate: vi.fn().mockResolvedValue([]),
    gitStatus: vi.fn().mockResolvedValue({ connected: false, git_installed: true }),
    gitChanges: vi.fn().mockResolvedValue({ changes: [], suggested_message: "" }),
    gitHistory: vi.fn().mockResolvedValue([]),
    gitConnect: vi.fn(),
    gitCreateRepository: vi.fn(),
    gitDisconnect: vi.fn(),
    gitFetch: vi.fn(),
    gitSync: vi.fn(),
    gitPush: vi.fn(),
    gitPublish: vi.fn(),
    ...overrides,
  };
}
