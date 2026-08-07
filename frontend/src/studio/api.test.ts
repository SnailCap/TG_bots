import { afterEach, describe, expect, it, vi } from "vitest";

import type { BotContentDocument } from "../domain/content";
import { StudioApi, StudioApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("StudioApi", () => {
  it("saves hydrated view text through the view contract", async () => {
    const payload = {
      schema_version: 3 as const,
      id: "home",
      text: { template: "views/home.txt" },
      keyboard: [],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: "home",
        source_path: "views/home.json",
        revision: "view-two",
        text_content: "Hello team",
        text_revision: "text-two",
        payload,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new StudioApi("http://studio.test");

    await api.saveView("project-1", "home", payload, "view-one", "Hello team", "text-one");

    expect(fetchMock).toHaveBeenCalledWith("http://studio.test/api/v1/projects/project-1/views/home", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({
        payload,
        revision: "view-one",
        text_content: "Hello team",
        text_revision: "text-one",
      }),
    }));
  });

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

  it("reads and saves redacted project settings with a revision", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ telegram_bot_token_configured: true, revision: "settings-two" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new StudioApi("http://studio.test");

    await api.saveProjectSettings("project-1", { telegram_bot_token: "123456:token", revision: "settings-one" });

    expect(fetchMock).toHaveBeenCalledWith("http://studio.test/api/v1/projects/project-1/settings", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ telegram_bot_token: "123456:token", revision: "settings-one" }),
    }));
  });

  it("loads a resource-scoped variable catalog and saves definitions revision-safely", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        source_path: "variables.json",
        revision: "vars-two",
        payload: { schema_version: 3, variables: [] },
        definitions: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new StudioApi("http://studio.test");

    await api.getVariables("project-1", {
      resourceType: "view",
      resourceId: "checkout",
      flowId: "main",
      stateId: "confirm",
    });
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://studio.test/api/v1/projects/project-1/variables?resource_type=view&resource_id=checkout&flow_id=main&state_id=confirm",
      expect.objectContaining({ headers: expect.any(Object) }),
    );

    const payload = { schema_version: 3 as const, variables: [] };
    await api.saveVariables("project-1", payload, "vars-one");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://studio.test/api/v1/projects/project-1/variables",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ payload, revision: "vars-one" }),
      }),
    );
  });

  it("sends an explicit compiled preview through the project-scoped endpoint", async () => {
    const document: BotContentDocument = {
      schemaVersion: 1,
      id: "home",
      content: [{ type: "paragraph", content: [{ type: "text", text: "Hello" }] }],
      metadata: {
        createdAt: "2026-07-29T00:00:00Z",
        updatedAt: "2026-07-29T00:00:00Z",
        editorVersion: "1.0.0",
      },
    };
    const wireResult = {
      sent: true as const,
      sentCount: 1,
      totalCount: 1,
      messageIds: [42],
      warnings: [],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => wireResult,
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new StudioApi("http://studio.test");

    const result = await api.sendPreviewMessage("project-1", {
      document,
      variables: { user: { first_name: "Ada" } },
      chatId: "@preview_chat",
      splitLongMessages: false,
    });

    expect(result).toEqual(wireResult);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://studio.test/api/v1/projects/project-1/content/send-preview",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          document,
          variables: { user: { first_name: "Ada" } },
          chatId: "@preview_chat",
          splitLongMessages: false,
        }),
      }),
    );
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
