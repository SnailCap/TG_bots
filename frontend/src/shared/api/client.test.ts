import type { AxiosInstance } from "axios";
import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "./client";

describe("ApiClient", () => {
  it("turns backend detail responses into typed API errors", async () => {
    const transport = {
      request: vi.fn().mockRejectedValue({
        isAxiosError: true,
        message: "Request failed",
        response: { status: 422, data: { detail: "Token is invalid", code: "INVALID_TOKEN" } },
      }),
    } as unknown as AxiosInstance;
    const client = new ApiClient("http://localhost/api/v1", transport);

    await expect(client.request({ method: "POST", url: "/token" })).rejects.toMatchObject({
      message: "Token is invalid",
      status: 422,
      code: "INVALID_TOKEN",
    });
  });

  it("reads the Studio error envelope returned by FastAPI", async () => {
    const transport = {
      request: vi.fn().mockRejectedValue({
        isAxiosError: true,
        message: "Request failed",
        response: {
          status: 422,
          data: {
            error: {
              code: "token_validation_failed",
              message: "Telegram token is not configured",
              details: { project_id: "project-1" },
            },
          },
        },
      }),
    } as unknown as AxiosInstance;
    const client = new ApiClient("http://localhost/api/v1", transport);

    await expect(client.request({ method: "POST", url: "/runtime/run" })).rejects.toMatchObject({
      message: "Telegram token is not configured",
      status: 422,
      code: "token_validation_failed",
      details: { project_id: "project-1" },
    });
  });

  it("uses a fallback endpoint only for missing or unsupported routes", async () => {
    const transport = {
      request: vi
        .fn()
        .mockRejectedValueOnce({ isAxiosError: true, message: "Not found", response: { status: 404, data: {} } })
        .mockResolvedValueOnce({ data: { phase: "running" } }),
    } as unknown as AxiosInstance;
    const client = new ApiClient("http://localhost/api/v1", transport);

    await expect(
      client.requestFirst([{ url: "/canonical" }, { url: "/legacy" }]),
    ).resolves.toEqual({ phase: "running" });
    expect(transport.request).toHaveBeenCalledTimes(2);
  });

  it("can adopt the backend address exposed by Electron", () => {
    const client = new ApiClient("http://127.0.0.1:8000/api/v1");
    client.setBaseUrl("http://127.0.0.1:8765/api/v1/");
    expect(client.absoluteUrl("/health")).toBe("http://127.0.0.1:8765/api/v1/health");
  });
});
