import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { GitStatus, StudioApiClient } from "../../studio/api";
import { StudioApiError } from "../../studio/api";
import type { StudioPageContext } from "../studio/studio-page-context";
import { GitPage } from "./GitPage";


const clean: GitStatus = {
  connected: true,
  git_installed: true,
  account: "SnailCap",
  repository: "SnailCap/my-family-bot",
  remote_name: "origin",
  branch: "dev",
  development_branch: "dev",
  production_branch: "production",
  local_changes: 0,
  remote_changes: 0,
  ahead: 0,
  behind: 0,
  sync_state: "synced",
  last_commit: {
    hash: "a31f8c2123456789",
    short_hash: "a31f8c2",
    author: "Ada",
    authored_at: "2026-07-23T10:00:00Z",
    message: "Update welcome",
  },
  last_publication: null,
};

function gitApi(overrides: Partial<StudioApiClient> = {}): StudioApiClient {
  return {
    gitStatus: vi.fn().mockResolvedValue(clean),
    gitChanges: vi.fn().mockResolvedValue({ changes: [], suggested_message: "" }),
    gitHistory: vi.fn().mockResolvedValue([{
      ...clean.last_commit!,
      branch: "dev",
      published: false,
      url: "https://github.com/SnailCap/my-family-bot/commit/a31f8c2123456789",
    }]),
    gitFetch: vi.fn().mockResolvedValue(clean),
    gitSync: vi.fn().mockResolvedValue(clean),
    gitPush: vi.fn().mockResolvedValue({ pushed: true, status: clean }),
    gitPublish: vi.fn().mockResolvedValue({ published: true, commit: "a31f8c2", version: "v1.0.1", published_at: "2026-07-23T10:00:00Z", status: clean }),
    gitConnect: vi.fn().mockResolvedValue(clean),
    gitCreateRepository: vi.fn().mockResolvedValue(clean),
    gitDisconnect: vi.fn().mockResolvedValue({ connected: false, git_installed: true }),
    ...overrides,
  } as StudioApiClient;
}

function renderPage(api = gitApi(), tabs: StudioPageContext["tabs"] = []) {
  const context = {
    api,
    workspace: { project_id: "project-1", name: "Family bot" },
    tabs,
    saveAll: vi.fn().mockResolvedValue(undefined),
  } as unknown as StudioPageContext;
  render(<MemoryRouter initialEntries={["/git"]}><Routes><Route element={<Outlet context={context} />}><Route path="/git" element={<GitPage />} /></Route></Routes></MemoryRouter>);
  return { api, context };
}

describe("GitPage", () => {
  it("renders the disconnected setup workflow", async () => {
    renderPage(gitApi({ gitStatus: vi.fn().mockResolvedValue({ connected: false, git_installed: true }) }));
    expect(await screen.findByRole("heading", { name: "Connect this bot to GitHub" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Existing repository" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("GitHub personal access token")).toHaveAttribute("type", "password");
  });

  it("renders a connected clean state and history", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "SnailCap/my-family-bot" })).toBeInTheDocument();
    expect(screen.getByText("Everything is in sync")).toBeInTheDocument();
    expect(screen.getByText("Update welcome")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish" })).toBeEnabled();
  });

  it("renders local semantic changes and opens a diff", async () => {
    const changed = { ...clean, local_changes: 1, sync_state: "changes" as const };
    renderPage(gitApi({
      gitStatus: vi.fn().mockResolvedValue(changed),
      gitFetch: vi.fn().mockResolvedValue(changed),
      gitChanges: vi.fn().mockResolvedValue({
        suggested_message: "Update 1 templates",
        changes: [{ path: "resources/templates/welcome.txt", old_path: null, status: "modified", staged: false, summary: "Template “welcome” updated", binary: false, diff: "@@ -1 +1 @@\n-Hello\n+Hello team" }],
      }),
    }));
    const summary = await screen.findByText("Template “welcome” updated");
    fireEvent.click(summary.closest("summary")!);
    expect(screen.getByText("+Hello team")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Push" })).toBeEnabled();
  });

  it("shows remote updates and keeps Sync disabled while local work exists", async () => {
    const changed = { ...clean, local_changes: 2, behind: 1, remote_changes: 1, sync_state: "conflict" as const };
    renderPage(gitApi({ gitStatus: vi.fn().mockResolvedValue(changed), gitFetch: vi.fn().mockResolvedValue(changed) }));
    expect(await screen.findByText("Local and GitHub history diverged")).toBeInTheDocument();
    expect(screen.getByText("A newer project version is available.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync" })).toBeDisabled();
  });

  it("shows Push preview and sends the editable commit message", async () => {
    const changed = { ...clean, local_changes: 1, sync_state: "changes" as const };
    const push = vi.fn().mockResolvedValue({ pushed: true, status: clean });
    const api = gitApi({
      gitStatus: vi.fn().mockResolvedValue(changed),
      gitFetch: vi.fn().mockResolvedValue(changed),
      gitPush: push,
      gitChanges: vi.fn().mockResolvedValue({
        suggested_message: "Update welcome template",
        changes: [{ path: "resources/templates/home.txt", old_path: null, status: "modified", staged: false, summary: "Template “home” updated", binary: false, diff: "-A\n+B" }],
      }),
    });
    renderPage(api);
    fireEvent.click(await screen.findByRole("button", { name: "Push" }));
    expect(screen.getByRole("heading", { name: "Push 1 changed file" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Commit message"), { target: { value: "Polish welcome" } });
    fireEvent.click(screen.getByRole("button", { name: "Push changes" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("project-1", "Polish welcome", undefined));
  });

  it("opens Publish confirmation with version choices", async () => {
    const publish = vi.fn().mockResolvedValue({ published: true, commit: "a31f8c2", version: "v0.0.1", published_at: "2026-07-23T10:00:00Z", status: clean });
    renderPage(gitApi({ gitPublish: publish }));
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));
    expect(screen.getByRole("heading", { name: "Publish current version?" })).toBeInTheDocument();
    expect(screen.getByText("Patch")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Publish to production" }));
    await waitFor(() => expect(publish).toHaveBeenCalledWith("project-1", expect.objectContaining({ version: "patch" })));
  });

  it("surfaces stable validation errors and affected resources", async () => {
    const changed = { ...clean, local_changes: 1, sync_state: "changes" as const };
    const error = new StudioApiError(422, "validation_failed", "Project validation failed.", {
      detail: { details: { issues: [{ source_path: "resources/views/home.json", message: "Unknown template." }] } },
    });
    renderPage(gitApi({
      gitStatus: vi.fn().mockResolvedValue(changed),
      gitFetch: vi.fn().mockResolvedValue(changed),
      gitPush: vi.fn().mockRejectedValue(error),
      gitChanges: vi.fn().mockResolvedValue({
        suggested_message: "Update view",
        changes: [{ path: "resources/views/home.json", old_path: null, status: "modified", staged: false, summary: "View “home” updated", binary: false, diff: "{}" }],
      }),
    }));
    fireEvent.click(await screen.findByRole("button", { name: "Push" }));
    fireEvent.click(screen.getByRole("button", { name: "Push changes" }));
    expect(await screen.findByText("Project validation failed.")).toBeInTheDocument();
    expect(screen.getByText("resources/views/home.json: Unknown template.")).toBeInTheDocument();
  });
});
