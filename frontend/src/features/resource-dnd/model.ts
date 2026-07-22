import type { HandlerKind, Selection } from "../../domain/project";

export type DraggableResourceKind = Exclude<Selection["kind"], "commands">;

export interface DraggableResource {
  kind: DraggableResourceKind;
  value: string;
  label: string;
  selection: Exclude<Selection, { kind: "commands" }>;
  handlerKind?: HandlerKind;
}

export type ResourceDropTargetSpec =
  | { type: "template-reference" }
  | { type: "view-reference" }
  | { type: "flow-reference" }
  | { type: "handler-reference"; handlerKind: HandlerKind };
