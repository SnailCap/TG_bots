import { describe, expect, it } from "vitest";
import { runtimeControlReducer, type RuntimeControlState } from "./types";

const stopped: RuntimeControlState = {
  status: { phase: "stopped", telegramConnected: false },
  pending: null,
  error: null,
};

describe("runtimeControlReducer", () => {
  it("models run and stop transitions without optimistic running state", () => {
    const starting = runtimeControlReducer(stopped, { type: "run_requested" });
    expect(starting).toMatchObject({ pending: "run", status: { phase: "starting" } });

    const running = runtimeControlReducer(starting, {
      type: "status",
      status: { phase: "running", telegramConnected: true },
    });
    const stopping = runtimeControlReducer(running, { type: "stop_requested" });
    expect(stopping).toMatchObject({ pending: "stop", status: { phase: "stopping" } });
  });

  it("retains a backend failure for the status bar and console", () => {
    const failed = runtimeControlReducer(stopped, { type: "failed", message: "Polling crashed" });
    expect(failed.status.phase).toBe("error");
    expect(failed.status.lastError).toBe("Polling crashed");
    expect(failed.error).toBe("Polling crashed");
  });
});
