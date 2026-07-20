import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioApi, StudioApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("StudioApi", () => {
  it("uses typed flow payloads with optimistic revisions", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "checkout", source_path: "flows/checkout.json", revision: "two", payload: { schema_version: 3, id: "checkout", initial_state: "start", lifecycle: {}, states: { start: { view: "home", events: {} } } } }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new StudioApi("http://studio.test");
    const payload = { schema_version: 3 as const, id: "checkout", initial_state: "start", lifecycle: {}, states: { start: { view: "home", events: {} } } };
    await api.saveFlow("project-1", "checkout", payload, "one");
    expect(fetchMock).toHaveBeenCalledWith("http://studio.test/api/v1/projects/project-1/flows/checkout", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ payload, revision: "one" }),
    }));
  });

  it("repairs only the missing source for an existing revisioned binding", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: "checkout.submit",
        kind: "button",
        module: "demo.handlers.checkout.submit",
        symbol: "handle",
        revision: "handlers-two",
        inspection: { status: "ready", used: true, source: { path: "src/demo/handlers/checkout/submit.py", line: 4, column: 1 } },
        file_created: true,
        open_target: { project_root: "C:/demo", file_path: "C:/demo/src/demo/handlers/checkout/submit.py", line: 4, column: 1 },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new StudioApi("http://studio.test");
    const result = await api.repairHandlerSource("project-1", "checkout.submit", "handlers-one");
    expect(fetchMock).toHaveBeenCalledWith("http://studio.test/api/v1/projects/project-1/handlers/checkout.submit/repair", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ registry_revision: "handlers-one" }),
    }));
    expect(result).toMatchObject({ created: true, source: { projectRoot: "C:/demo", line: 4 } });
  });

  it("preserves backend error codes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: { code: "revision_conflict", message: "Changed" } }) }));
    const api = new StudioApi("http://studio.test");
    await expect(api.describe("project-1")).rejects.toMatchObject({ status: 409, code: "revision_conflict", message: "Changed" } satisfies Partial<StudioApiError>);
  });

  it("formats FastAPI validation errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: [{ msg: "Invalid handler kind" }, { msg: "Invalid ID" }] }) }));
    const api = new StudioApi("http://studio.test");
    await expect(api.describe("project-1")).rejects.toThrow("Invalid handler kind; Invalid ID");
  });
});
