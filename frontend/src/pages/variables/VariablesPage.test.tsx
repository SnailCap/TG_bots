import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";

import type { VariableCatalogDetail, Workspace } from "../../domain/project";
import type { StudioApiClient } from "../../studio/api";
import type { StudioPageContext } from "../studio/studio-page-context";
import { VariablesPage } from "./VariablesPage";

const workspace: Workspace = {
  project_id: "project-1",
  name: "demo",
  project_root: "C:/demo",
  resource_root: "C:/demo/resources",
  package: "demo",
  schema_version: 3,
  manifest: { source_path: "bot.json", revision: "manifest-one", payload: { schema_version: 3, id: "demo", package: "demo", entry_view: "home", start: { flow: "checkout", policy: "reset" } } },
  views: [{ id: "home", source_path: "views/home.json", revision: "view-one" }],
  flows: [{ id: "checkout", source_path: "flows/checkout.json", revision: "flow-one", states: ["details"] }],
  handlers: [{ id: "checkout.submit", kind: "button", module: "demo.handlers.checkout_submit", symbol: "handle", outcomes: [], source_path: "handlers.json", revision: "handler-one", status: "ready", usage_count: 1 }],
  handlers_revision: "handlers-one",
  commands: { source_path: "commands.json", revision: "commands-one", items: [] },
  schedules: [],
};

const detail: VariableCatalogDetail = {
  source_path: "variables.json",
  revision: "variables-one",
  payload: {
    schema_version: 3,
    variables: [{ id: "checkout.customer", owner: { type: "flow", id: "checkout" }, path: "customer.name", type: "string", source: "custom", required: false, writable: true, exampleValue: "Anna", persistence: "resource", exposedToTemplates: true, legacyPaths: [] }],
  },
  definitions: [
    { id: "core.user.first_name", owner: { type: "bot", id: "*" }, path: "user.first_name", type: "string", source: "core", required: false, writable: false, exampleValue: "Anna", persistence: "user", exposedToTemplates: true, legacyPaths: [] },
    { ...({ id: "checkout.customer", owner: { type: "flow", id: "checkout" }, path: "customer.name", type: "string", source: "custom", required: false, writable: true, exampleValue: "Anna", persistence: "resource", exposedToTemplates: true, legacyPaths: [] }) },
  ],
};

function renderPage(api: StudioApiClient, entry = "/variables") {
  const context = { api, workspace } as unknown as StudioPageContext;
  return render(<MemoryRouter initialEntries={[entry]}><Routes><Route element={<Outlet context={context} />}><Route path="/variables" element={<VariablesPage />} /></Route></Routes></MemoryRouter>);
}

describe("VariablesPage", () => {
  it("loads a resource-scoped catalog and keeps built-in definitions read-only", async () => {
    const getVariables = vi.fn().mockResolvedValue(detail);
    renderPage({ getVariables } as unknown as StudioApiClient, "/variables?resourceType=view&resourceId=home");

    expect(await screen.findByRole("status")).toHaveTextContent("Showing variables available to home.");
    expect(screen.getByText("home")).toBeInTheDocument();
    expect(screen.getByText("user.first_name")).toBeInTheDocument();
    expect(getVariables).toHaveBeenCalledWith("project-1", { resourceType: "view", resourceId: "home", flowId: undefined, stateId: undefined, handlerId: undefined });

    fireEvent.click(screen.getByRole("button", { name: /user\.first_name/ }));
    expect(screen.getByText(/Built-in values are supplied by the Telegram runtime/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("user.first_name")).toBeDisabled();
  });

  it("creates a custom definition through the catalog save API", async () => {
    const saveVariables = vi.fn().mockResolvedValue(detail);
    const api = { getVariables: vi.fn().mockResolvedValue(detail), saveVariables } as unknown as StudioApiClient;
    renderPage(api);

    fireEvent.click(await screen.findByRole("button", { name: "New variable" }));
    fireEvent.change(screen.getByPlaceholderText("checkout.customer_name"), { target: { value: "profile.email" } });
    fireEvent.change(screen.getByPlaceholderText("customer.name"), { target: { value: "profile.email" } });
    fireEvent.click(screen.getByRole("button", { name: "Save variable" }));

    await waitFor(() => expect(saveVariables).toHaveBeenCalledWith("project-1", expect.objectContaining({ variables: expect.arrayContaining([expect.objectContaining({ id: "profile.email", path: "profile.email", owner: { type: "bot", id: "demo" } })]) }), "variables-one"));
  });
});
