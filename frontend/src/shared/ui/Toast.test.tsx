import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_TOAST_TIMEOUT_MS, Toast } from "./Toast";

afterEach(() => vi.useRealTimers());

describe("Toast", () => {
  it("renders an accessible error toast and dismisses it after the default timeout", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(<Toast message="Could not save the view" tone="error" onDismiss={onDismiss} />);

    expect(screen.getByRole("alert")).toHaveClass("toast", "toast--error");
    act(() => vi.advanceTimersByTime(DEFAULT_TOAST_TIMEOUT_MS));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
