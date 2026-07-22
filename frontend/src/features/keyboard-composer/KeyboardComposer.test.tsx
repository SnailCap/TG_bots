import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ViewSpec } from "../../domain/project";
import { KeyboardComposer } from "./KeyboardComposer";

const options = { views: ["home"], flows: [], states: [], handlers: [] };
const handlerActions = { create: vi.fn(), repair: vi.fn(), open: vi.fn(), usages: vi.fn().mockResolvedValue([]) };

describe("KeyboardComposer", () => {
  it("does not render an empty row", () => {
    const { unmount } = render(<KeyboardHarness keyboard={[]} />);

    expect(screen.queryByRole("button", { name: "Delete row 1" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Keyboard rows").querySelectorAll(".keyboard-composer__row")).toHaveLength(0);

    unmount();
    render(<KeyboardHarness keyboard={[[]]} />);
    expect(screen.getByLabelText("Keyboard rows").querySelectorAll(".keyboard-composer__row")).toHaveLength(0);
  });

  it("adds a blank button into the focused label editor and marks it incomplete", () => {
    const { container } = render(<KeyboardHarness keyboard={[]} />);
    expect(screen.getByText("No buttons added yet")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add row" }));

    const label = screen.getByLabelText("Button text");
    expect(label).toHaveFocus();
    expect(container.querySelector(".keyboard-composer__button--invalid")).toBeInTheDocument();
    expect(screen.queryByText("Add a button label")).not.toBeInTheDocument();
  });

  it("plays the entrance animation only for a newly added button", () => {
    const animate = vi.fn();
    const originalAnimate = HTMLElement.prototype.animate;
    HTMLElement.prototype.animate = animate;
    render(<KeyboardHarness keyboard={[[button("continue", "Continue")]]} />);
    expect(animate.mock.calls.filter(([frames]) => Array.isArray(frames) && frames[0]?.opacity === 0)).toHaveLength(0);
    animate.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Add button to row 1" }));

    const entranceCalls = animate.mock.calls.filter(([frames]) => Array.isArray(frames) && frames[0]?.opacity === 0);
    expect(entranceCalls).toHaveLength(1);
    HTMLElement.prototype.animate = originalAnimate;
  });

  it("offers only actions supported by buttons inside a view", () => {
    render(<KeyboardHarness keyboard={[[button("continue", "Continue")]]} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByLabelText("Action"));

    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Go to view",
      "Start flow",
      "Enqueue task",
      "Custom handler",
    ]);
  });

  it("deletes a button directly from the keyboard canvas", () => {
    const { container } = render(<KeyboardHarness keyboard={[[button("continue", "Continue")]]} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete selected button" }));
    expect(container.querySelectorAll("[data-keyboard-button]")).toHaveLength(0);
    expect(container.querySelectorAll(".keyboard-composer__row")).toHaveLength(0);
  });

  it("offers context-specific actions from a button context menu", () => {
    const { container } = render(<KeyboardHarness keyboard={[[button("continue", "Continue")]]} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "Continue" }), { clientX: 40, clientY: 40 });
    expect(screen.getByRole("menuitem", { name: "Edit label" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Duplicate" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));

    expect(container.querySelectorAll("[data-keyboard-button]")).toHaveLength(0);
  });

  it("moves a button to another row through the keyboard canvas", () => {
    const { container } = render(<KeyboardHarness keyboard={[[button("one", "One")], [button("two", "Two")]]} />);
    const transfer = { effectAllowed: "", setData: vi.fn() };

    fireEvent.click(screen.getByRole("button", { name: "One" }));
    expect(screen.getByLabelText("Button text")).toHaveValue("One");
    fireEvent.dragStart(screen.getByRole("button", { name: "One" }), { dataTransfer: transfer });
    expect(container.querySelector(".keyboard-composer__button-slot--dragging")).toBeInTheDocument();
    expect(document.body.querySelector(".keyboard-composer__drag-preview")).toBeInTheDocument();
    const rows = container.querySelectorAll<HTMLElement>(".keyboard-composer__row");
    fireEvent.dragOver(rows[1], { clientX: 100, dataTransfer: transfer });
    fireEvent.drop(container.querySelector<HTMLElement>(".keyboard-composer__row")!, { clientX: 100, dataTransfer: transfer });

    expect(container.querySelectorAll(".keyboard-composer__row")).toHaveLength(1);
    expect(container.querySelectorAll(".keyboard-composer__row")[0].querySelectorAll("[data-keyboard-button]")).toHaveLength(2);
    expect(screen.getByLabelText("Button text")).toHaveValue("One");
    expect(document.body.querySelector(".keyboard-composer__drag-preview")).not.toBeInTheDocument();
  });
});

function KeyboardHarness({ keyboard }: { keyboard: ViewSpec["keyboard"] }) {
  const [value, setValue] = useState(keyboard);
  return <KeyboardComposer viewId="home" keyboard={value} options={options} handlerActions={handlerActions} onChange={setValue} />;
}

function button(id: string, text: string) {
  return { id, text, action: { type: "noop" as const } };
}
