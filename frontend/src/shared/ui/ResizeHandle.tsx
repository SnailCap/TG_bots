import { useCallback, useEffect, useRef, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

type ResizeAxis = "horizontal" | "vertical";

export function ResizeHandle({
  className,
  axis,
  label,
  value,
  min,
  max: maxValue,
  step = 16,
  inverted = false,
  onResize,
  onResizeEnd,
}: {
  className?: string;
  axis: ResizeAxis;
  label: string;
  value: number;
  min: number;
  max: number | (() => number);
  step?: number;
  inverted?: boolean;
  onResize(value: number): void;
  onResizeEnd?(): void;
}) {
  const cleanupRef = useRef<(() => void) | null>(null);
  const cursor = axis === "horizontal" ? "ew-resize" : "ns-resize";
  const direction = inverted ? -1 : 1;
  const max = typeof maxValue === "function" ? maxValue() : maxValue;

  const finishResize = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    onResizeEnd?.();
  }, [onResizeEnd]);

  useEffect(() => () => finishResize(), [finishResize]);

  const resizeWithKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    const increaseKey = axis === "horizontal" ? "ArrowRight" : "ArrowDown";
    const decreaseKey = axis === "horizontal" ? "ArrowLeft" : "ArrowUp";
    if (event.key === "Home") {
      event.preventDefault();
      onResize(min);
      onResizeEnd?.();
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      onResize(max);
      onResizeEnd?.();
      return;
    }
    if (event.key !== increaseKey && event.key !== decreaseKey) return;
    event.preventDefault();
    const delta = (event.key === increaseKey ? step : -step) * direction;
    onResize(clamp(value + delta, min, max));
    onResizeEnd?.();
  };

  const beginResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    finishResize();
    const startCoordinate = axis === "horizontal" ? event.clientX : event.clientY;
    const startValue = value;
    const maximum = typeof maxValue === "function" ? maxValue() : maxValue;
    const resizingClass = axis === "horizontal" ? "is-resizing-horizontal" : "is-resizing-vertical";
    document.body.classList.add(resizingClass);

    const move = (moveEvent: globalThis.PointerEvent) => {
      const coordinate = axis === "horizontal" ? moveEvent.clientX : moveEvent.clientY;
      onResize(clamp(startValue + (coordinate - startCoordinate) * direction, min, maximum));
    };
    const end = () => finishResize();
    cleanupRef.current = () => {
      document.body.classList.remove(resizingClass);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
    window.addEventListener("pointercancel", end, { once: true });
  };

  return <div className={["resize-handle", `resize-handle--${axis}`, className].filter(Boolean).join(" ")} role="separator" aria-label={label} aria-orientation={axis === "horizontal" ? "vertical" : "horizontal"} aria-valuemin={min} aria-valuemax={max} aria-valuenow={value} tabIndex={0} style={{ cursor }} onPointerDown={beginResize} onKeyDown={resizeWithKeyboard} />;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
