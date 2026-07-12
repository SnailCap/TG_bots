export interface ViewSummary { id: string; source_path: string; revision: string; }
export interface ViewDetail extends ViewSummary { payload: Record<string, unknown>; }
export interface TemplateSummary { path: string; }
export interface TemplateDetail extends TemplateSummary { content: string; revision: string; }
export interface Workspace { project_id: string; name: string; project_root: string; resource_root: string; views: ViewSummary[]; templates: TemplateSummary[]; }
export interface Preview { text: string; keyboard: Array<Array<{ text: string; action: Record<string, unknown> }>>; warnings: string[]; }
export interface ValidationIssue { level: "error" | "warning"; code: string; message: string; source_path?: string; }

export class StudioApiError extends Error { constructor(readonly status: number, message: string) { super(message); this.name = "StudioApiError"; } }

export class StudioApi {
  constructor(private readonly baseUrl: string) {}
  open(root_path: string): Promise<Workspace> { return this.request("/projects/open", { method: "POST", body: { root_path } }); }
  create(parent_path: string, name: string, package_name?: string): Promise<Workspace> { return this.request("/projects", { method: "POST", body: { parent_path, name, package_name: package_name || undefined } }); }
  describe(id: string): Promise<Workspace> { return this.request(`/projects/${id}`); }
  getView(project: string, id: string): Promise<ViewDetail> { return this.request(`/projects/${project}/views/${encodeURIComponent(id)}`); }
  createView(project: string, id: string, payload: Record<string, unknown>): Promise<ViewDetail> { return this.request(`/projects/${project}/views`, { method: "POST", body: { view_id: id, payload } }); }
  saveView(project: string, id: string, payload: Record<string, unknown>, revision: string): Promise<ViewDetail> { return this.request(`/projects/${project}/views/${encodeURIComponent(id)}`, { method: "PUT", body: { payload, revision } }); }
  deleteView(project: string, id: string, revision: string): Promise<void> { return this.request(`/projects/${project}/views/${encodeURIComponent(id)}?revision=${encodeURIComponent(revision)}`, { method: "DELETE" }); }
  getTemplate(project: string, path: string): Promise<TemplateDetail> { return this.request(`/projects/${project}/templates/${this.path(path)}`); }
  saveTemplate(project: string, path: string, content: string, revision?: string): Promise<TemplateDetail> { return this.request(`/projects/${project}/templates/${this.path(path)}`, { method: "PUT", body: { content, revision } }); }
  preview(project: string, payload: Record<string, unknown>): Promise<Preview> { return this.request(`/projects/${project}/preview`, { method: "POST", body: { payload } }); }
  async validate(project: string): Promise<ValidationIssue[]> { return (await this.request<{ issues: ValidationIssue[] }>(`/projects/${project}/validation`)).issues; }
  private path(value: string): string { return value.split("/").map(encodeURIComponent).join("/"); }
  private async request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}/api/v1${path}`, { method: options.method ?? "GET", headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) }, body: options.body ? JSON.stringify(options.body) : undefined });
    if (response.status === 204) return undefined as T;
    const data = await response.json().catch(() => null) as { detail?: { message?: string } } | T | null;
    if (!response.ok) throw new StudioApiError(response.status, data && typeof data === "object" && "detail" in data ? data.detail?.message ?? "Request failed" : `Request failed with ${response.status}`);
    return data as T;
  }
}
