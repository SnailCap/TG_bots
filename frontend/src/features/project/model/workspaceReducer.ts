import type { WorkspaceTab } from "../../../entities/project/model/types";

export interface WorkspaceState {
  tabs: WorkspaceTab[];
  activeTabId: string | null;
}

export type WorkspaceAction =
  | { type: "open"; tab: WorkspaceTab }
  | { type: "close"; tabId: string }
  | { type: "activate"; tabId: string }
  | { type: "dirty"; tabId: string; dirty: boolean }
  | { type: "rename"; tabId: string; title: string }
  | { type: "reset" };

export const initialWorkspaceState: WorkspaceState = { tabs: [], activeTabId: null };

export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case "open": {
      const existing = state.tabs.find((tab) => tab.id === action.tab.id);
      return {
        tabs: existing ? state.tabs : [...state.tabs, action.tab],
        activeTabId: action.tab.id,
      };
    }
    case "close": {
      const index = state.tabs.findIndex((tab) => tab.id === action.tabId);
      if (index < 0) return state;
      const tabs = state.tabs.filter((tab) => tab.id !== action.tabId);
      const activeTabId =
        state.activeTabId === action.tabId
          ? (tabs[Math.min(index, tabs.length - 1)]?.id ?? null)
          : state.activeTabId;
      return { tabs, activeTabId };
    }
    case "activate":
      return state.tabs.some((tab) => tab.id === action.tabId) ? { ...state, activeTabId: action.tabId } : state;
    case "dirty":
      return {
        ...state,
        tabs: state.tabs.map((tab) => (tab.id === action.tabId ? { ...tab, dirty: action.dirty } : tab)),
      };
    case "rename":
      return {
        ...state,
        tabs: state.tabs.map((tab) => (tab.id === action.tabId ? { ...tab, title: action.title } : tab)),
      };
    case "reset":
      return initialWorkspaceState;
  }
}
