import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from "axios";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly code?: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function apiMessage(error: AxiosError): string {
  const payload = error.response?.data;
  if (payload && typeof payload === "object") {
    const source = payload as Record<string, unknown>;
    const errorBody = source.error && typeof source.error === "object"
      ? (source.error as Record<string, unknown>)
      : undefined;
    if (typeof errorBody?.message === "string") return errorBody.message;
    const detail = source.detail ?? source.message ?? source.error;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => JSON.stringify(item)).join("; ");
  }
  return error.message || "Backend request failed";
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    const errorBody = data?.error && typeof data.error === "object"
      ? (data.error as Record<string, unknown>)
      : undefined;
    return new ApiError(
      apiMessage(error),
      error.response?.status,
      typeof errorBody?.code === "string"
        ? errorBody.code
        : typeof data?.code === "string"
          ? data.code
          : error.code,
      errorBody?.details ?? error.response?.data,
    );
  }
  return new ApiError(error instanceof Error ? error.message : "Unexpected API error");
}

export class ApiClient {
  baseUrl: string;

  constructor(
    baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
    private readonly transport: AxiosInstance = axios.create({ timeout: 15_000 }),
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  setBaseUrl(baseUrl: string): void {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  absoluteUrl(path: string): string {
    return `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  }

  async request<T>(config: AxiosRequestConfig): Promise<T> {
    try {
      const response = await this.transport.request<T>({
        ...config,
        url: this.absoluteUrl(config.url ?? ""),
        headers: { Accept: "application/json", ...config.headers },
      });
      return response.data;
    } catch (error) {
      throw toApiError(error);
    }
  }

  async requestFirst<T>(requests: AxiosRequestConfig[]): Promise<T> {
    let lastError: ApiError | null = null;
    for (const request of requests) {
      try {
        return await this.request<T>(request);
      } catch (error) {
        const apiError = toApiError(error);
        lastError = apiError;
        if (apiError.status !== 404 && apiError.status !== 405) throw apiError;
      }
    }
    throw lastError ?? new ApiError("No backend endpoint candidates were provided");
  }
}

export const apiClient = new ApiClient();
