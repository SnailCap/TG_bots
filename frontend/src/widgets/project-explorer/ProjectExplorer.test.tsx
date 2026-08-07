import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Workspace } from "../../domain/project";
import { ProjectExplorer } from "./ProjectExplorer";

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
  handlers: [{
    id: "checkout.submit",
    kind: "button",
    module: "demo.handlers.checkout_submit",
    symbol: "handle",
    outcomes: [],
    source_path: "handlers.json",
    revision: "handler-one",
    status: "ready",
    usage_count: 1,
  }],
  handlers_revision: "handlers-one",
  commands: { source_path: "commands.json", revision: "commands-one", items: [] },
  schedules: [],
};

describe("ProjectExplorer flows", () => {
  it("opens a flow on row click and only expands states from the disclosure toggle", () => {
    const onSelect = vi.fn();
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={onSelect} onAdd={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "flows" }));
    const flowButton = screen.getByRole("button", { name: "checkout" });
    const disclosure = screen.getByRole("button", { name: "Expand checkout" });

    fireEvent.click(flowButton);
    expect(onSelect).toHaveBeenCalledWith({ kind: "flow", id: "checkout" });
    expect(disclosure).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("details")).toBeVisible();
    expect(screen.getByText("confirm")).toBeVisible();
    const stateRow = screen.getByText("details").closest("[data-tree-depth]");
    expect(stateRow).toHaveAttribute("data-tree-depth", "1");
    expect(stateRow).toHaveClass("explorer-tree__row--without-disclosure");
    expect(stateRow?.querySelector(".explorer-tree__toggle")).not.toBeInTheDocument();
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("reveals a view text editor through the same disclosure interaction", () => {
    const onSelect = vi.fn();
    const onOpenViewTextEditor = vi.fn();
    const onOpenVariables = vi.fn();
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={onSelect} onOpenViewTextEditor={onOpenViewTextEditor} onOpenVariables={onOpenVariables} onAdd={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "views" }));
    const viewButton = screen.getByRole("button", { name: "home" });
    const disclosure = screen.getByRole("button", { name: "Expand home" });

    fireEvent.click(viewButton);
    expect(onSelect).toHaveBeenCalledWith({ kind: "view", id: "home" });
    expect(disclosure).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    const textEditor = screen.getByRole("button", { name: "Open text editor for home" });
    expect(textEditor.closest("[data-tree-depth]")).toHaveAttribute("data-tree-depth", "1");
    expect(textEditor.querySelector("svg")).toBeInTheDocument();
    fireEvent.click(textEditor);
    expect(onOpenViewTextEditor).toHaveBeenCalledWith("home", "home");
    fireEvent.click(screen.getByRole("button", { name: "Open variables for home" }));
    expect(onOpenVariables).toHaveBeenCalledWith({ resourceType: "view", resourceId: "home" }, "home");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("shows flow variables beside its state resources", () => {
    const onOpenVariables = vi.fn();
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={vi.fn()} onOpenVariables={onOpenVariables} onAdd={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "flows" }));
    fireEvent.click(screen.getByRole("button", { name: "Expand checkout" }));
    fireEvent.click(screen.getByRole("button", { name: "Open variables for checkout" }));

    expect(onOpenVariables).toHaveBeenCalledWith({ resourceType: "flow", resourceId: "checkout" }, "checkout");
  });

  it("does not reserve disclosure space for any terminal resource node", () => {
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={vi.fn()} onAdd={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "handlers" }));
    const handlerRow = screen.getByRole("button", { name: "checkout.submit" }).closest("[data-tree-depth]");

    expect(handlerRow).toHaveClass("explorer-tree__row--without-disclosure");
    expect(handlerRow?.querySelector(".explorer-tree__toggle")).not.toBeInTheDocument();
  });
});
