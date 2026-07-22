# Resource drag-and-drop

This feature lets Studio resources be dragged from the Resources explorer into typed reference fields. It is a frontend interaction layer only: dropped values are written into the existing project v3 editor model through the field's normal `onChange` callback. The regular editor Save action persists that model through the existing revision-aware API.

## Module boundaries

- `model.ts` defines the resource payload and the public drop-target specification.
- `compatibility.ts` is the only compatibility registry. It decides which resource payload a target accepts.
- `ResourceDragProvider.tsx` owns one pointer drag session, target registration, hit testing and the velocity-driven preview physics.
- `ResourceDropTarget.tsx` provides the reusable highlighted field surface.
- `useResourceDraggable.ts` makes an explorer item a drag source without changing its click behaviour.
- `ResourceIcon.tsx` in `shared/ui` is reused by both the explorer row and the drag preview, so the visual language stays identical.

The provider updates preview position with a compositor-friendly `transform` instead of putting pointer coordinates into React state. React state changes only when a drag starts, ends, or enters another target.

## Supported references

| Resource | Compatible targets |
| --- | --- |
| Template | View text source → Template |
| View | Flow state default view; `view.render`; optional final/enqueued views |
| Flow | `flow.start` target |
| Handler | Handler fields whose expected handler kind matches exactly |
| Schedule | No target yet |

Commands and schedules remain visible resources but are not accepted unless a future schema field explicitly references them. Incompatible targets never call `onDrop` and do not show an active drop treatment.

## Adding a new scenario

1. Add a target variant to `ResourceDropTargetSpec` in `model.ts` if no existing reference type describes the field.
2. Add its compatibility predicate to `RESOURCE_DROP_RULES` in `compatibility.ts`. Keep schema-specific rules here rather than inside UI components.
3. Wrap the editor control in `ResourceDropTarget`, passing the target specification and an `onDrop` callback that calls the same model update used by manual input.
4. If the explorer resource needs extra compatibility metadata, add it when constructing `DraggableResource` in `ProjectExplorer.tsx`.
5. Add a positive and negative compatibility test and, for new interaction behaviour, a provider/drop integration test.

Example:

```tsx
<ResourceDropTarget
  target={{ type: "view-reference" }}
  label="Drop view here"
  onDrop={(resource) => onChange({ ...value, view: resource.value })}
>
  <input value={value.view} onChange={(event) => onChange({ ...value, view: event.target.value })} />
</ResourceDropTarget>
```

## Interaction and accessibility

- A 5 px movement threshold prevents an ordinary click from becoming a drag.
- Compatible targets have both a border treatment and text/icon guidance; compatibility is not communicated by colour alone.
- Target controls remain editable without drag-and-drop, preserving a keyboard alternative.
- The preview is horizontally centred under the pointer and tilts/lifts from pointer velocity instead of running a decorative loop.
- Preview physics and target scaling are disabled by `prefers-reduced-motion`.
- Non-target controls stop receiving pointer hover while a drag is active; compatible targets remain the only hit-testable Studio elements.
- The preview uses `pointer-events: none`, so hit testing always reaches the field below it.
