import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App, BackendStatusCard } from "./App";

describe("BackendStatusCard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an online backend after a valid health response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok", api_version: "v1" }),
      }),
    );

    render(<BackendStatusCard apiBaseUrl="http://studio.test" />);

    expect(screen.getByText("Connecting to local backend…")).toBeInTheDocument();
    expect(await screen.findByText("Backend online")).toBeInTheDocument();
  });

  it("shows an unavailable backend when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    render(<BackendStatusCard apiBaseUrl="http://studio.test" />);

    await waitFor(() => expect(screen.getByText("Backend unavailable")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("opens a v2 project and renders a selected view with preview", async () => {
    const workspace = {
      project_id: "project-1",
      name: "demo",
      project_root: "C:/demo",
      resource_root: "C:/demo/resources",
      views: [{ id: "home", source_path: "views/home.json", revision: "one" }],
      texts: [],
      templates: [],
    };
    const fetchMock = vi.fn(async (input: string, options?: RequestInit) => {
      if (input.includes("/health")) return { ok: true, json: async () => ({ status: "ok", api_version: "v1" }) };
      if (input.endsWith("/projects/open")) return { ok: true, json: async () => workspace };
      if (input.includes("/views/home")) return { ok: true, json: async () => ({ ...workspace.views[0], payload: { schema_version: 2, id: "home", text: { inline: "Hello" }, keyboard: [] } }) };
      if (input.endsWith("/preview")) return { ok: true, json: async () => ({ text: "Hello", keyboard: [], warnings: [] }) };
      return { ok: true, json: async () => workspace };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App apiBaseUrl="http://studio.test" />);
    fireEvent.change(screen.getByLabelText("Existing v2 project"), { target: { value: "C:/demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Open project" }));

    const view = await screen.findByRole("button", { name: "home views/home.json" });
    fireEvent.click(view);
    expect(await screen.findByText("Save view")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Telegram preview")).toHaveTextContent("Hello"));
  });
});
