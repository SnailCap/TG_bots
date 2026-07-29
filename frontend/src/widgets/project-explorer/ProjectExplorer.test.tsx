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
  handlers: [],
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
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("reveals a view text editor through the same disclosure interaction", () => {
    const onSelect = vi.fn();
    const onOpenViewTextEditor = vi.fn();
    render(<ProjectExplorer workspace={workspace} selection={null} onSelect={onSelect} onOpenViewTextEditor={onOpenViewTextEditor} onAdd={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "views" }));
    const viewButton = screen.getByRole("button", { name: "home" });
    const disclosure = screen.getByRole("button", { name: "Expand home" });

    fireEvent.click(viewButton);
    expect(onSelect).toHaveBeenCalledWith({ kind: "view", id: "home" });
    expect(disclosure).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "Open text editor for home" }));
    expect(onOpenViewTextEditor).toHaveBeenCalledWith("home", "home");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
