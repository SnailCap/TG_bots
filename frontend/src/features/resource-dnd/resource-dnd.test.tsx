import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { canDropResource } from "./compatibility";
import type { DraggableResource } from "./model";
import { ResourceDragProvider } from "./ResourceDragProvider";
import { ResourceDropTarget } from "./ResourceDropTarget";
import { useResourceDraggable } from "./useResourceDraggable";

const templateResource: DraggableResource = {
  kind: "template",
  value: "welcome.txt",
  label: "welcome.txt",
  selection: { kind: "template", path: "welcome.txt" },
};

const taskHandler: DraggableResource = {
  kind: "handler",
  value: "jobs.cleanup",
  label: "jobs.cleanup",
  selection: { kind: "handler", id: "jobs.cleanup" },
  handlerKind: "task",
};

describe("resource drag compatibility", () => {
  it("accepts only the configured resource kind", () => {
    expect(canDropResource(templateResource, { type: "template-reference" })).toBe(true);
    expect(canDropResource(templateResource, { type: "view-reference" })).toBe(false);
  });

  it("checks the handler kind as well as the resource kind", () => {
    expect(canDropResource(taskHandler, { type: "handler-reference", handlerKind: "task" })).toBe(true);
    expect(canDropResource(taskHandler, { type: "handler-reference", handlerKind: "message" })).toBe(false);
  });
});

describe("resource drag interaction", () => {
  it("highlights a compatible target and commits the dropped value", () => {
    render(<DragHarness resource={templateResource} target={{ type: "template-reference" }} />);
    const source = screen.getByRole("button", { name: "welcome.txt" });
    const target = screen.getByTestId("drop-target").closest<HTMLElement>("[data-resource-drop-target]")!;
    const restoreElementFromPoint = mockElementFromPoint(target);

    fireEvent(source, pointerEvent("pointerdown", { button: 0, clientX: 10, clientY: 10 }));
    fireEvent(window, pointerEvent("pointermove", { button: 0, clientX: 30, clientY: 30 }));

    expect(screen.getByText("Release to use welcome.txt")).toBeInTheDocument();
    fireEvent(window, pointerEvent("pointerup", { button: 0, clientX: 30, clientY: 30 }));
    expect(screen.getByRole("textbox", { name: "Reference" })).toHaveValue("welcome.txt");
    restoreElementFromPoint();
  });

  it("does not activate or accept an incompatible target", () => {
    render(<DragHarness resource={templateResource} target={{ type: "view-reference" }} />);
    const source = screen.getByRole("button", { name: "welcome.txt" });
    const target = screen.getByTestId("drop-target").closest<HTMLElement>("[data-resource-drop-target]")!;
    const restoreElementFromPoint = mockElementFromPoint(target);

    fireEvent(source, pointerEvent("pointerdown", { button: 0, clientX: 10, clientY: 10 }));
    fireEvent(window, pointerEvent("pointermove", { button: 0, clientX: 30, clientY: 30 }));
    expect(screen.queryByText(/Drop view|Release to use/)).not.toBeInTheDocument();
    fireEvent(window, pointerEvent("pointerup", { button: 0, clientX: 30, clientY: 30 }));
    expect(screen.getByRole("textbox", { name: "Reference" })).toHaveValue("");
    restoreElementFromPoint();
  });
});

function DragHarness({ resource, target }: { resource: DraggableResource; target: { type: "template-reference" } | { type: "view-reference" } }) {
  return <ResourceDragProvider><HarnessContent resource={resource} target={target} /></ResourceDragProvider>;
}

function HarnessContent({ resource, target }: { resource: DraggableResource; target: { type: "template-reference" } | { type: "view-reference" } }) {
  const [value, setValue] = useState("");
  const dragProps = useResourceDraggable(resource);
  return <>
    <button type="button" onPointerDown={dragProps.onPointerDown} onClickCapture={dragProps.onClickCapture}>{resource.label}</button>
    <ResourceDropTarget target={target} label={target.type === "template-reference" ? "Drop template here" : "Drop view here"} onDrop={(item) => setValue(item.value)}>
      <input data-testid="drop-target" aria-label="Reference" value={value} readOnly />
    </ResourceDropTarget>
  </>;
}

function mockElementFromPoint(element: Element) {
  Object.defineProperty(document, "elementFromPoint", { configurable: true, value: vi.fn(() => element) });
  return () => { Reflect.deleteProperty(document, "elementFromPoint"); };
}

function pointerEvent(type: string, values: { button: number; clientX: number; clientY: number }) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, {
    button: { value: values.button },
    clientX: { value: values.clientX },
    clientY: { value: values.clientY },
  });
  return event;
}
