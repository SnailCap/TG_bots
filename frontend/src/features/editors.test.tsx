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
  it("shows only the shared Name field and renames through display names", () => {
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
    const onRename = vi.fn();
    render(<FlowEditor
      value={value}
      sourcePath="flows/checkout.json"
      revision="flow-one"
      isNew={false}
      options={{ views: ["home"], flows: ["checkout"], states: ["details"], handlers: [handler("ready", 1, "message")] }}
      handlerActions={handlerActions()}
      onChange={vi.fn()}
      displayName="Checkout"
      onRename={onRename}
    />);

    const input = screen.getByLabelText("Name:");
    expect(input).toHaveValue("Checkout");
    expect(screen.queryByLabelText("Initial state:")).not.toBeInTheDocument();
    expect(screen.queryByText("Flow lifecycle")).not.toBeInTheDocument();
    expect(screen.queryByText("States")).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "Cart flow" } });
    fireEvent.blur(input);
    expect(onRename).toHaveBeenCalledWith("Cart flow");
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
      textContent="View 1"
      onTextContentChange={vi.fn()}
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
      textContent: "Home",
      onTextContentChange: vi.fn(),
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

describe("view message editor", () => {
  it("opens the rich text editor without exposing a template resource", () => {
    const onTextContentChange = vi.fn();
    const onOpenTextEditor = vi.fn();
    render(<ViewEditor
      value={{ schema_version: 3, id: "home", text: { template: "views/home.txt" }, keyboard: [] }}
      textContent="Hello {{ user.first_name }}"
      revision="view-one"
      isNew={false}
      options={{ views: ["home"], flows: [], states: [], handlers: [] }}
      handlerActions={handlerActions()}
      onChange={vi.fn()}
      onTextContentChange={onTextContentChange}
      onOpenTextEditor={onOpenTextEditor}
    />);

    expect(screen.getByLabelText("Message text editor")).toBeInTheDocument();
    expect(screen.queryByLabelText("Text source")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open rich text editor" }));
    expect(onOpenTextEditor).toHaveBeenCalledOnce();
    expect(onTextContentChange).not.toHaveBeenCalled();
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
