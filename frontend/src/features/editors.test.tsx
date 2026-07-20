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
    fireEvent.change(screen.getByDisplayValue("Render view"), { target: { value: "flow.goto" } });
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
    fireEvent.change(screen.getByLabelText("Final view (optional)"), { target: { value: "home" } });
    expect(onChange).toHaveBeenLastCalledWith({ type: "flow.cancel", view: "home" });

    rerender(<ActionEditor {...props} action={{ type: "handler.invoke", handler: "checkout.submit", outcomes: {} }} />);
    fireEvent.change(screen.getByLabelText("Handler payload"), { target: { value: "{\"order_id\": 7}" } });
    expect(onChange).toHaveBeenLastCalledWith({ type: "handler.invoke", handler: "checkout.submit", outcomes: {}, payload: { order_id: 7 } });

    rerender(<ActionEditor {...props} action={{ type: "task.enqueue", target: "jobs.sync" }} />);
    fireEvent.change(screen.getByLabelText("View after enqueue (optional)"), { target: { value: "home" } });
    expect(onChange).toHaveBeenLastCalledWith({ type: "task.enqueue", target: "jobs.sync", view: "home" });
  });

  it("offers flow.event only to buttons and flow.goto only inside a current flow", () => {
    const props = {
      action: { type: "noop" as const },
      onChange: vi.fn(),
      options: { views: [], flows: [], states: [], handlers: [] },
      handlerActions: handlerActions(),
    };
    const { rerender } = render(<ActionEditor {...props} scope={{ expectedKind: "command" }} />);
    expect(actionValues()).not.toContain("flow.event");
    expect(actionValues()).not.toContain("flow.goto");

    rerender(<ActionEditor {...props} scope={{ expectedKind: "button" }} />);
    expect(actionValues()).toContain("flow.event");
    expect(actionValues()).not.toContain("flow.goto");

    rerender(<ActionEditor {...props} scope={{ expectedKind: "lifecycle", currentFlow: "checkout" }} />);
    expect(actionValues()).not.toContain("flow.event");
    expect(actionValues()).toContain("flow.goto");

    rerender(<ActionEditor {...props} scope={{ expectedKind: "button", currentFlow: "checkout" }} />);
    expect(actionValues()).toContain("flow.event");
    expect(actionValues()).toContain("flow.goto");
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
    const [onStart, ...withoutCurrentFlow] = screen.getAllByLabelText("Action") as HTMLSelectElement[];
    expect(selectValues(onStart)).toContain("flow.goto");
    expect(selectValues(onStart)).not.toContain("flow.event");
    for (const select of withoutCurrentFlow) {
      expect(selectValues(select)).not.toContain("flow.goto");
      expect(selectValues(select)).not.toContain("flow.event");
    }
  });
});

describe("view button IDs", () => {
  it("generates stable view-namespaced IDs and advances past existing IDs", () => {
    const onChange = vi.fn();
    const base: ViewSpec = { schema_version: 3, id: "home", text: { inline: "Home" }, keyboard: [[]] };
    const props = {
      sourcePath: "views/home.json",
      revision: "view-one",
      isNew: false,
      options: { views: ["home", "settings"], flows: [], states: [], handlers: [] },
      handlerActions: handlerActions(),
      onChange,
    };
    const { rerender } = render(<ViewEditor {...props} value={base} />);
    fireEvent.click(screen.getByRole("button", { name: "Add button" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      keyboard: [[expect.objectContaining({ id: "home.action_1" })]],
    }));

    const withExisting: ViewSpec = {
      ...base,
      keyboard: [[{ id: "home.action_1", text: "Existing", action: { type: "noop" } }]],
    };
    rerender(<ViewEditor {...props} value={withExisting} />);
    fireEvent.click(screen.getByRole("button", { name: "Add button" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      keyboard: [[
        expect.objectContaining({ id: "home.action_1" }),
        expect.objectContaining({ id: "home.action_2" }),
      ]],
    }));

    rerender(<ViewEditor {...props} value={{ ...base, id: "settings" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add button" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      keyboard: [[expect.objectContaining({ id: "settings.action_1" })]],
    }));
  });
});

describe("template selection", () => {
  it("offers available .txt templates through a searchable datalist", () => {
    const onChange = vi.fn();
    render(<ViewEditor
      value={{ schema_version: 3, id: "home", text: { template: "home.txt" }, keyboard: [] }}
      sourcePath="views/home.json"
      revision="view-one"
      isNew={false}
      options={{ views: ["home"], flows: [], states: [], handlers: [], templates: ["home.txt", "checkout/receipt.txt"] }}
      handlerActions={handlerActions()}
      onChange={onChange}
    />);

    const input = screen.getByLabelText("Template") as HTMLInputElement;
    expect(input.getAttribute("list")).toBe("available-templates");
    expect(document.querySelectorAll("#available-templates option")).toHaveLength(2);
    fireEvent.change(input, { target: { value: "checkout/receipt.txt" } });
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ text: { template: "checkout/receipt.txt" } }));
  });
});

function handlerActions() {
  return { create: vi.fn(), repair: vi.fn(), open: vi.fn(), usages: vi.fn().mockResolvedValue([]) };
}

function actionValues(): string[] {
  return selectValues(screen.getByLabelText("Action") as HTMLSelectElement);
}

function selectValues(select: HTMLSelectElement): string[] {
  return Array.from(select.options, (option) => option.value);
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
