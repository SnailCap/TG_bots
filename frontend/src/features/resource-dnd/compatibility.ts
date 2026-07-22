import type { DraggableResource, ResourceDropTargetSpec } from "./model";

type CompatibilityRule<T extends ResourceDropTargetSpec["type"]> = (
  resource: DraggableResource,
  target: Extract<ResourceDropTargetSpec, { type: T }>,
) => boolean;

export const RESOURCE_DROP_RULES: { [T in ResourceDropTargetSpec["type"]]: CompatibilityRule<T> } = {
  "template-reference": (resource) => resource.kind === "template",
  "view-reference": (resource) => resource.kind === "view",
  "flow-reference": (resource) => resource.kind === "flow",
  "handler-reference": (resource, target) => resource.kind === "handler" && resource.handlerKind === target.handlerKind,
};

export function canDropResource(resource: DraggableResource, target: ResourceDropTargetSpec): boolean {
  if (target.type === "handler-reference") return RESOURCE_DROP_RULES[target.type](resource, target);
  if (target.type === "template-reference") return RESOURCE_DROP_RULES[target.type](resource, target);
  if (target.type === "view-reference") return RESOURCE_DROP_RULES[target.type](resource, target);
  return RESOURCE_DROP_RULES[target.type](resource, target);
}
