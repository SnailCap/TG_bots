import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { useInertialDragPreview } from "../../shared/lib/useInertialDragPreview";
import { ResourceIcon } from "../../shared/ui/ResourceIcon";
import { canDropResource } from "./compatibility";
import type { DraggableResource, ResourceDropTargetSpec } from "./model";

const DRAG_START_DISTANCE = 5;

type RegisteredTarget = {
  target: ResourceDropTargetSpec;
  onDrop(resource: DraggableResource): void;
};

type DragContextValue = {
  activeResource: DraggableResource | null;
  hoveredTargetId: string | null;
  beginPointerDrag(
    event: ReactPointerEvent<HTMLElement>,
    resource: DraggableResource,
    onActivated: () => void,
  ): void;
  registerTarget(id: string, target: RegisteredTarget): () => void;
};

const DragContext = createContext<DragContextValue | null>(null);
const fallbackContext: DragContextValue = {
  activeResource: null,
  hoveredTargetId: null,
  beginPointerDrag: () => undefined,
  registerTarget: () => () => undefined,
};

export function ResourceDragProvider({ children }: { children: ReactNode }) {
  const [activeResource, setActiveResource] = useState<DraggableResource | null>(null);
  const [hoveredTargetId, setHoveredTargetId] = useState<string | null>(null);
  const targetsRef = useRef(new Map<string, RegisteredTarget>());
  const { previewRef, startPreview, movePreview, stopPreview } = useInertialDragPreview();

  const registerTarget = useCallback((id: string, target: RegisteredTarget) => {
    targetsRef.current.set(id, target);
    return () => { targetsRef.current.delete(id); };
  }, []);

  const beginPointerDrag = useCallback((event: ReactPointerEvent<HTMLElement>, resource: DraggableResource, onActivated: () => void) => {
    if (event.button !== 0) return;
    const origin = { x: event.clientX, y: event.clientY };
    const source = event.currentTarget;
    let activated = false;
    let currentTargetId: string | null = null;

    const findCompatibleTarget = (x: number, y: number) => {
      const element = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-resource-drop-target]");
      const id = element?.dataset.resourceDropTarget ?? null;
      const registered = id ? targetsRef.current.get(id) : undefined;
      return registered && canDropResource(resource, registered.target) ? id : null;
    };

    const finish = (drop: boolean) => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerCancel);
      if (!activated) return;
      if (drop && currentTargetId) targetsRef.current.get(currentTargetId)?.onDrop(resource);
      stopPreview();
      source.classList.remove("resource-dnd__source--dragging");
      document.body.classList.remove("is-resource-dragging");
      setHoveredTargetId(null);
      setActiveResource(null);
    };

    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!activated && Math.hypot(moveEvent.clientX - origin.x, moveEvent.clientY - origin.y) < DRAG_START_DISTANCE) return;
      if (!activated) {
        activated = true;
        onActivated();
        source.classList.add("resource-dnd__source--dragging");
        document.body.classList.add("is-resource-dragging");
        startPreview(moveEvent.clientX, moveEvent.clientY);
        setActiveResource(resource);
      }
      moveEvent.preventDefault();
      movePreview(moveEvent.clientX, moveEvent.clientY);
      const nextTargetId = findCompatibleTarget(moveEvent.clientX, moveEvent.clientY);
      if (nextTargetId !== currentTargetId) {
        currentTargetId = nextTargetId;
        setHoveredTargetId(nextTargetId);
      }
    };
    const onPointerUp = () => finish(true);
    const onPointerCancel = () => finish(false);

    window.addEventListener("pointermove", onPointerMove, { passive: false });
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerCancel);
  }, [movePreview, startPreview, stopPreview]);

  const value = useMemo<DragContextValue>(() => ({
    activeResource,
    hoveredTargetId,
    beginPointerDrag,
    registerTarget,
  }), [activeResource, beginPointerDrag, hoveredTargetId, registerTarget]);

  return <DragContext.Provider value={value}>
    {children}
    {activeResource && createPortal(
      <div ref={previewRef} className="resource-dnd__preview" aria-hidden="true">
        <div className="resource-dnd__preview-card">
          <ResourceIcon selection={activeResource.selection} title={activeResource.label} />
          <strong>{activeResource.label}</strong>
        </div>
      </div>,
      document.body,
    )}
  </DragContext.Provider>;
}

export function useResourceDragContext(): DragContextValue {
  return useContext(DragContext) ?? fallbackContext;
}
