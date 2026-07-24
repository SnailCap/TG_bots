import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { canDropResource } from "./compatibility";
import type { DraggableResource } from "./model";
import { ResourceDragProvider } from "./ResourceDragProvider";
import { ResourceDropTarget } from "./ResourceDropTarget";
import { useResourceDraggable } from "./useResourceDraggable";

const viewResource: DraggableResource = {
  kind: "view",
  value: "welcome",
  label: "welcome",
  selection: { kind: "view", id: "welcome" },
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
    expect(canDropResource(viewResource, { type: "view-reference" })).toBe(true);
    expect(canDropResource(taskHandler, { type: "view-reference" })).toBe(false);
  });

  it("checks the handler kind as well as the resource kind", () => {
    expect(canDropResource(taskHandler, { type: "handler-reference", handlerKind: "task" })).toBe(true);
    expect(canDropResource(taskHandler, { type: "handler-reference", handlerKind: "message" })).toBe(false);
  });
});

describe("resource drag interaction", () => {
  it("highlights a compatible target and commits the dropped value", () => {
    render(<DragHarness resource={viewResource} target={{ type: "view-reference" }} />);
    const source = screen.getByRole("button", { name: "welcome" });
    const target = screen.getByTestId("drop-target").closest<HTMLElement>("[data-resource-drop-target]")!;
    const restoreElementFromPoint = mockElementFromPoint(target);

    fireEvent(source, pointerEvent("pointerdown", { button: 0, clientX: 10, clientY: 10 }));
    fireEvent(window, pointerEvent("pointermove", { button: 0, clientX: 30, clientY: 30 }));

    expect(screen.getByText("Release to use welcome")).toBeInTheDocument();
    fireEvent(window, pointerEvent("pointerup", { button: 0, clientX: 30, clientY: 30 }));
    expect(screen.getByRole("textbox", { name: "Reference" })).toHaveValue("welcome");
    restoreElementFromPoint();
  });

  it("does not activate or accept an incompatible target", () => {
    render(<DragHarness resource={taskHandler} target={{ type: "view-reference" }} />);
    const source = screen.getByRole("button", { name: "jobs.cleanup" });
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

function DragHarness({ resource, target }: { resource: DraggableResource; target: { type: "view-reference" } }) {
  return <ResourceDragProvider><HarnessContent resource={resource} target={target} /></ResourceDragProvider>;
}

function HarnessContent({ resource, target }: { resource: DraggableResource; target: { type: "view-reference" } }) {
  const [value, setValue] = useState("");
  const dragProps = useResourceDraggable(resource);
  return <>
    <button type="button" onPointerDown={dragProps.onPointerDown} onClickCapture={dragProps.onClickCapture}>{resource.label}</button>
    <ResourceDropTarget target={target} label="Drop view here" onDrop={(item) => setValue(item.value)}>
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
