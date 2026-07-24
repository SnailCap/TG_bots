import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FlowSpec, HandlerIntegrity, HandlerSummary, ViewSpec } from "../domain/project";
import { ActionEditor } from "./action-editor/ActionEditor";
import { FlowEditor } from "./flow-editor/FlowEditor";
import { HandlerControls, HandlerStatusBadge } from "./handlers/HandlerControls";
import { ViewEditor } from "./view-editor/ViewEditor";

describe("handler UX", () => {
  it("renders every handler inspection state and unused separately", () => {
    const statuses: HandlerIntegrity[] = ["ready", "missing_file", "missing_symbol", "invalid_signature", "invalid_module"];
    render(<div>{statuses.map((status) => <HandlerStatusBadge key={status} handler={handler(status, status === "ready" ? 0 : 1)} />)}</div>);
    expect(screen.getByText("Ready · Unused")).toBeInTheDocument();
    expect(screen.getByText("Missing file")).toBeInTheDocument();
    expect(screen.getByText("Missing symbol")).toBeInTheDocument();
    expect(screen.getByText("Invalid signature")).toBeInTheDocument();
    expect(screen.getByText("Invalid module")).toBeInTheDocument();
  });

  it("repairs a missing source instead of offering an invalid open action", () => {
    const onRepair = vi.fn().mockResolvedValue(undefined);
    const missing = { ...handler("missing_file", 1), source_file: "src/demo/handlers/missing.py" };
    render(<HandlerControls
      handlerId={missing.id}
      kind="button"
      handlers={[missing]}
      onCreate={vi.fn()}
      onRepair={onRepair}
      onOpen={vi.fn()}
      onFindUsages={vi.fn().mockResolvedValue([])}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Create missing source" }));
    expect(onRepair).toHaveBeenCalledWith(missing.id);
    expect(screen.queryByRole("button", { name: "Open code" })).not.toBeInTheDocument();
  });
});

describe("flow outcome editor", () => {
  it("updates a declarative outcome route without exposing runtime transitions", () => {
    const value: FlowSpec = {
      schema_version: 3,
      id: "checkout",
      initial_state: "details",
      lifecycle: {},
      states: {
        details: {
          view: "home",
          events: {},
          on_message: {
            handler: "checkout.message",
            outcomes: { success: { type: "view.render", target: "home" } },
          },
        },
      },
    };
    const onChange = vi.fn();
    render(<FlowEditor
      value={value}
      sourcePath="flows/checkout.json"
      revision="flow-one"
      isNew={false}
      options={{ views: ["home"], flows: ["checkout"], states: ["details"], handlers: [handler("ready", 1, "message")] }}
      handlerActions={handlerActions()}
      onChange={onChange}
    />);
    expect(screen.getByText("success")).toBeInTheDocument();
    fireEvent.click(screen.getAllByLabelText("Action")[0]);
    fireEvent.click(screen.getByRole("option", { name: "Go to state" }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      states: expect.objectContaining({
        details: expect.objectContaining({
          on_message: expect.objectContaining({ outcomes: { success: { type: "flow.goto", target: "" } } }),
        }),
      }),
    }));
  });
});

describe("action editor", () => {
  it("edits every optional field consumed by the core action executor", () => {
    const onChange = vi.fn();
    const props = {
      onChange,
      options: { views: ["home"], flows: [], states: [], handlers: [] },
      scope: { expectedKind: "button" as const },
      handlerActions: handlerActions(),
    };
    const { rerender } = render(<ActionEditor {...props} action={{ type: "flow.cancel" }} />);
    fireEvent.click(screen.getByLabelText("Final view (optional)"));
    fireEvent.click(screen.getByRole("option", { name: "home" }));
    expect(onChange).toHaveBeenLastCalledWith({ type: "flow.cancel", view: "home" });

    rerender(<ActionEditor {...props} action={{ type: "handler.invoke", handler: "checkout.submit", outcomes: {} }} />);
    fireEvent.change(screen.getByLabelText("Handler payload:"), { target: { value: "{\"order_id\": 7}" } });
    expect(onChange).toHaveBeenLastCalledWith({ type: "handler.invoke", handler: "checkout.submit", outcomes: {}, payload: { order_id: 7 } });

    rerender(<ActionEditor {...props} action={{ type: "task.enqueue", target: "jobs.sync" }} />);
    fireEvent.click(screen.getByLabelText("View after enqueue (optional)"));
    fireEvent.click(screen.getByRole("option", { name: "home" }));
    expect(onChange).toHaveBeenLastCalledWith({ type: "task.enqueue", target: "jobs.sync", view: "home" });
  });

  it("searches resource choices without accepting arbitrary target text", () => {
    const onChange = vi.fn();
    render(<ActionEditor
      action={{ type: "flow.start", target: "" }}
      onChange={onChange}
      options={{ views: [], flows: ["checkout", "support"], states: [], handlers: [] }}
      scope={{ expectedKind: "button" }}
      handlerActions={handlerActions()}
    />);

    fireEvent.click(screen.getByLabelText("Flow"));
    fireEvent.change(screen.getByLabelText("Search Flow"), { target: { value: "supp" } });
    expect(screen.queryByRole("option", { name: "checkout" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: "support" }));
    expect(onChange).toHaveBeenLastCalledWith({ type: "flow.start", target: "support" });
  });

  it("offers flow.event only to buttons and flow.goto only inside a current flow", () => {
    const props = {
      action: { type: "noop" as const },
      onChange: vi.fn(),
      options: { views: [], flows: [], states: [], handlers: [] },
      handlerActions: handlerActions(),
    };
    const { rerender } = render(<ActionEditor {...props} scope={{ expectedKind: "command" }} />);
    expect(actionValues()).not.toContain("Emit flow event");
    expect(actionValues()).not.toContain("Go to state");

    rerender(<ActionEditor {...props} scope={{ expectedKind: "button" }} />);
    expect(actionValues()).toContain("Emit flow event");
    expect(actionValues()).not.toContain("Go to state");

    rerender(<ActionEditor {...props} scope={{ expectedKind: "lifecycle", currentFlow: "checkout" }} />);
    expect(actionValues()).not.toContain("Emit flow event");
    expect(actionValues()).toContain("Go to state");

    rerender(<ActionEditor {...props} scope={{ expectedKind: "button", currentFlow: "checkout" }} />);
    expect(actionValues()).toContain("Emit flow event");
    expect(actionValues()).toContain("Go to state");
  });
});

describe("flow action scopes", () => {
  it("allows flow.goto for on_start but not the other lifecycle hooks", () => {
    const invocation = { handler: "checkout.lifecycle", outcomes: { success: { type: "noop" as const } } };
    const value: FlowSpec = {
      schema_version: 3,
      id: "checkout",
      initial_state: "start",
      lifecycle: { on_start: invocation, on_complete: invocation, on_cancel: invocation, on_error: invocation },
      states: { start: { view: "home", events: {} } },
    };
    render(<FlowEditor
      value={value}
      sourcePath="flows/checkout.json"
      revision="flow-one"
      isNew={false}
      options={{ views: ["home"], flows: ["checkout"], states: ["start"], handlers: [] }}
      handlerActions={handlerActions()}
      onChange={vi.fn()}
    />);
    const [onStart, ...withoutCurrentFlow] = screen.getAllByLabelText("Action");
    expect(selectValues(onStart)).toContain("Go to state");
    expect(selectValues(onStart)).not.toContain("Emit flow event");
    for (const select of withoutCurrentFlow) {
      expect(selectValues(select)).not.toContain("Go to state");
      expect(selectValues(select)).not.toContain("Emit flow event");
    }
  });
});

describe("view button IDs", () => {
  it("shows an implicit display name as a gray input hint without changing the technical ID", () => {
    const onRename = vi.fn();
    const value: ViewSpec = { schema_version: 3, id: "view_1", text: { inline: "View 1" }, keyboard: [] };
    render(<ViewEditor
      value={value}
      displayName="View 1"
      nameIsDefault
      revision="view-one"
      isNew={false}
      options={{ views: ["view_1"], flows: [], states: [], handlers: [] }}
      handlerActions={handlerActions()}
      onChange={vi.fn()}
      onRename={onRename}
    />);

    const input = screen.getByLabelText("Name:");
    expect(input).toHaveValue("");
    expect(input).toHaveAttribute("placeholder", "View 1");
    fireEvent.change(input, { target: { value: "Welcome screen" } });
    fireEvent.blur(input);
    expect(onRename).toHaveBeenCalledWith("Welcome screen");
  });

  it("generates stable view-namespaced IDs and advances past existing IDs", () => {
    const onChange = vi.fn();
    const base: ViewSpec = { schema_version: 3, id: "home", text: { inline: "Home" }, keyboard: [] };
    const props = {
      revision: "view-one",
      isNew: false,
      options: { views: ["home", "settings"], flows: [], states: [], handlers: [] },
      handlerActions: handlerActions(),
      onChange,
    };
    const { rerender } = render(<ViewEditor {...props} value={base} />);
    fireEvent.click(screen.getByRole("button", { name: "Add row" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      keyboard: [[expect.objectContaining({ id: "home.action_1" })]],
    }));

    const withExisting: ViewSpec = {
      ...base,
      keyboard: [[{ id: "home.action_1", text: "Existing", action: { type: "noop" } }]],
    };
    rerender(<ViewEditor {...props} value={withExisting} />);
    fireEvent.click(screen.getByRole("button", { name: "Add button to row 1" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      keyboard: [[
        expect.objectContaining({ id: "home.action_1" }),
        expect.objectContaining({ id: "home.action_2" }),
      ]],
    }));

    rerender(<ViewEditor {...props} value={{ ...base, id: "settings" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add row" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      keyboard: [[expect.objectContaining({ id: "settings.action_1" })]],
    }));
  });
});

describe("template selection", () => {
  it("creates a new template from the suggestion list", () => {
    const onCreateTemplate = vi.fn();
    render(<ViewEditor
      value={{ schema_version: 3, id: "home", text: { template: "receipt.txt" }, keyboard: [] }}
      revision="view-one"
      isNew={false}
      options={{ views: ["home"], flows: [], states: [], handlers: [], templates: [] }}
      handlerActions={handlerActions()}
      onChange={vi.fn()}
      onCreateTemplate={onCreateTemplate}
    />);

    fireEvent.focus(screen.getByLabelText("Template"));
    fireEvent.mouseDown(screen.getByRole("button", { name: "Create template" }));
    fireEvent.click(screen.getByRole("button", { name: "Create template" }));
    expect(onCreateTemplate).toHaveBeenCalledWith("receipt.txt");
  });

  it("shows recent templates on first focus, then filters after typing", () => {
    window.localStorage.setItem("tg-bot-studio.recent-templates", JSON.stringify(["recent.txt"]));
    const onChange = vi.fn();
    const props = {
      revision: "view-one",
      isNew: false,
      options: { views: ["home"], flows: [], states: [], handlers: [], templates: ["home.txt", "recent.txt", "receipt.txt"] },
      handlerActions: handlerActions(),
      onChange,
    };
    const { rerender } = render(<ViewEditor
      value={{ schema_version: 3, id: "home", text: { template: "home.txt" }, keyboard: [] }}
      {...props}
    />);

    const input = screen.getByLabelText("Template");
    fireEvent.focus(input);
    expect(screen.queryByRole("option", { name: "home.txt" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "recent.txt" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "receipt.txt" })).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "receipt" } });
    rerender(<ViewEditor {...props} value={{ schema_version: 3, id: "home", text: { template: "receipt" }, keyboard: [] }} />);
    expect(screen.queryByRole("option", { name: "recent.txt" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "receipt.txt" })).toBeInTheDocument();
    window.localStorage.removeItem("tg-bot-studio.recent-templates");
  });

  it("allows typing a template name or choosing one from the template picker", () => {
    const onChange = vi.fn();
    render(<ViewEditor
      value={{ schema_version: 3, id: "home", text: { template: "home.txt" }, keyboard: [] }}
      revision="view-one"
      isNew={false}
      options={{ views: ["home"], flows: [], states: [], handlers: [], templates: ["home.txt", "checkout/receipt.txt"] }}
      handlerActions={handlerActions()}
      onChange={onChange}
    />);

    const input = screen.getByLabelText("Template") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "checkout/receipt.txt" } });
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ text: { template: "checkout/receipt.txt" } }));
    fireEvent.click(screen.getByRole("button", { name: "Browse templates" }));
    expect(screen.getByRole("dialog", { name: "Choose template" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "home.txt" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ text: { template: "home.txt" } }));
  });

  it("selects an inline template suggestion with arrow keys", () => {
    const onChange = vi.fn();
    const value = { schema_version: 3 as const, id: "home", text: { template: "" }, keyboard: [] };
    const props = {
      revision: "view-one",
      isNew: false,
      options: { views: ["home"], flows: [], states: [], handlers: [], templates: ["home.txt", "help.txt"] },
      handlerActions: handlerActions(),
      onChange,
    };
    const { rerender } = render(<ViewEditor {...props} value={value} />);

    const input = screen.getByLabelText("Template");
    fireEvent.change(input, { target: { value: "h" } });
    rerender(<ViewEditor {...props} value={{ ...value, text: { template: "h" } }} />);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ text: { template: "home.txt" } }));
  });

  it("selects the first inline template suggestion with Enter", () => {
    const onChange = vi.fn();
    const value = { schema_version: 3 as const, id: "home", text: { template: "" }, keyboard: [] };
    const props = {
      revision: "view-one",
      isNew: false,
      options: { views: ["home"], flows: [], states: [], handlers: [], templates: ["home.txt", "help.txt"] },
      handlerActions: handlerActions(),
      onChange,
    };
    const { rerender } = render(<ViewEditor {...props} value={value} />);

    const input = screen.getByLabelText("Template");
    fireEvent.change(input, { target: { value: "h" } });
    rerender(<ViewEditor {...props} value={{ ...value, text: { template: "h" } }} />);
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ text: { template: "home.txt" } }));
  });
});

function handlerActions() {
  return { create: vi.fn(), repair: vi.fn(), open: vi.fn(), usages: vi.fn().mockResolvedValue([]) };
}

function actionValues(): string[] {
  return selectValues(screen.getByLabelText("Action"));
}

function selectValues(select: HTMLElement): string[] {
  if (select.getAttribute("aria-expanded") !== "true") fireEvent.click(select);
  const menu = document.getElementById(select.getAttribute("aria-controls") ?? "");
  return Array.from(menu?.querySelectorAll('[role="option"]') ?? [], (option) => option.textContent ?? "");
}

function handler(status: HandlerIntegrity, usageCount: number, kind: HandlerSummary["kind"] = "button"): HandlerSummary {
  return {
    id: kind === "message" ? "checkout.message" : `handler.${status}`,
    kind,
    module: "demo.handlers.example",
    symbol: "handle",
    outcomes: [],
    source_path: "handlers.json",
    revision: "handlers-one",
    status,
    usage_count: usageCount,
  };
}
