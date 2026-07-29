import { useEffect, useId, type ReactNode } from "react";
import { Download } from "lucide-react";

import { canDropResource } from "./compatibility";
import { useResourceDragContext } from "./ResourceDragProvider";
import type { DraggableResource, ResourceDropTargetSpec } from "./model";

export function ResourceDropTarget({
  target,
  label,
  className = "",
  children,
  onDrop,
}: {
  target: ResourceDropTargetSpec;
  label: string;
  className?: string;
  children: ReactNode;
  onDrop(resource: DraggableResource): void;
}) {
  const id = useId().replace(/:/g, "");
  const { activeResource, hoveredTargetId, registerTarget } = useResourceDragContext();
  useEffect(() => registerTarget(id, { target, onDrop }), [id, onDrop, registerTarget, target]);
  const compatible = activeResource ? canDropResource(activeResource, target) : false;
  const hovered = compatible && hoveredTargetId === id;
  const classes = [
    "resource-drop-target",
    className,
    compatible ? "resource-drop-target--compatible" : "",
    hovered ? "resource-drop-target--hovered" : "",
  ].filter(Boolean).join(" ");
  return <div className={classes} data-resource-drop-target={id}>
    {children}
    {compatible && <span className="resource-drop-target__hint" aria-hidden="true"><DropIcon />{hovered ? `Release to use ${activeResource?.label}` : label}</span>}
  </div>;
}

function DropIcon() {
  return <Download aria-hidden="true" />;
}
