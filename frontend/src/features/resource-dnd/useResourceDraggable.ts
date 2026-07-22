import { useRef, type MouseEvent, type PointerEvent } from "react";

import { useResourceDragContext } from "./ResourceDragProvider";
import type { DraggableResource } from "./model";

export function useResourceDraggable(resource: DraggableResource | null) {
  const { beginPointerDrag } = useResourceDragContext();
  const suppressClickRef = useRef(false);
  return {
    onPointerDown: (event: PointerEvent<HTMLElement>) => {
      if (resource) beginPointerDrag(event, resource, () => { suppressClickRef.current = true; });
    },
    onClickCapture: (event: MouseEvent<HTMLElement>) => {
      if (!suppressClickRef.current) return;
      suppressClickRef.current = false;
      event.preventDefault();
      event.stopPropagation();
    },
  };
}
