import type { HandlerKind, Selection } from "../../domain/project";

export type DraggableResourceKind = Exclude<Selection["kind"], "commands" | "command">;

export interface DraggableResource {
  kind: DraggableResourceKind;
  value: string;
  label: string;
  selection: Exclude<Selection, { kind: "commands" } | { kind: "command" }>;
  handlerKind?: HandlerKind;
}

export type ResourceDropTargetSpec =
  | { type: "view-reference" }
  | { type: "flow-reference" }
  | { type: "handler-reference"; handlerKind: HandlerKind };
