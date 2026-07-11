import { describe, expect, it } from "vitest";
import { initialWorkspaceState, workspaceReducer } from "./workspaceReducer";

describe("workspaceReducer", () => {
  it("opens one tab per resource and keeps dirty state", () => {
    const tab = { id: "flow:main", type: "flow" as const, title: "Main", resourceId: "main" };
    let state = workspaceReducer(initialWorkspaceState, { type: "open", tab });
    state = workspaceReducer(state, { type: "open", tab });
    state = workspaceReducer(state, { type: "dirty", tabId: tab.id, dirty: true });
    expect(state.tabs).toHaveLength(1);
    expect(state.tabs[0].dirty).toBe(true);
    expect(state.activeTabId).toBe(tab.id);
  });

  it("activates the nearest tab after closing the active document", () => {
    let state = workspaceReducer(initialWorkspaceState, {
      type: "open",
      tab: { id: "flow:a", type: "flow", title: "A" },
    });
    state = workspaceReducer(state, {
      type: "open",
      tab: { id: "script:b", type: "script", title: "B" },
    });
    state = workspaceReducer(state, { type: "close", tabId: "script:b" });
    expect(state.activeTabId).toBe("flow:a");
  });
});
