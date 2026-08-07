import { describe, expect, it } from "vitest";

import {
  contextFieldsFromDefinitions,
  searchContextFields,
  SYSTEM_CONTEXT_FIELDS,
} from "./context-catalog";
import { parseTemplate } from "./parser";
import { defaultPreviewValues, renderTemplatePreview } from "./preview";
import { serializeTemplate } from "./serializer";
import { validateTemplate } from "./validation";

describe("template parser and serializer", () => {
  it("parses ordinary, empty, and multiline text", () => {
    expect(parseTemplate("Hello")).toEqual({ nodes: [{ type: "text", text: "Hello" }] });
    expect(parseTemplate("")).toEqual({ nodes: [] });
    expect(parseTemplate("First\nSecond")).toEqual({ nodes: [{ type: "text", text: "First\nSecond" }] });
  });

  it.each([
    "{{user.first_name}}",
    "{{ user.first_name }}",
    "{{  user.first_name  }}",
  ])("parses a known expression with spacing: %s", (source) => {
    expect(parseTemplate(source).nodes).toEqual([expect.objectContaining({
      type: "context-token",
      fieldId: "core.user.first_name",
      path: "user.first_name",
      source,
    })]);
  });

  it("parses multiple context tokens in sequence", () => {
    const document = parseTemplate("Hello {{ user.first_name }} (@{{ user.username }})");
    expect(document.nodes.map((node) => node.type)).toEqual([
      "text",
      "context-token",
      "text",
      "context-token",
      "text",
    ]);
  });

  it("round-trips Jinja without changing known source spelling", () => {
    const source = "Hello {{user.first_name}}\nID: {{  user.telegram_id  }}";
    expect(serializeTemplate(parseTemplate(source))).toBe(source);
  });

  it("preserves unknown and complex expressions exactly", () => {
    const source = "Total: {{ order.total }} / {{ order.total | round(2) }} {% if user.username %}ok{% endif %}";
    const document = parseTemplate(source);
    expect(document.nodes).toContainEqual({ type: "unresolved-token", path: "order.total", source: "{{ order.total }}" });
    expect(document.nodes.filter((node) => node.type === "raw-fragment")).toHaveLength(3);
    expect(serializeTemplate(document)).toBe(source);
  });

  it("serializes a newly inserted token to canonical Jinja", () => {
    expect(serializeTemplate({ nodes: [
      { type: "text", text: "Hello " },
      { type: "context-token", fieldId: "core.user.first_name", path: "user.first_name" },
      { type: "text", text: "!" },
    ] })).toBe("Hello {{ user.first_name }}!");
  });
});

describe("context catalog", () => {
  it("searches labels, paths, and descriptions", () => {
    expect(searchContextFields("им").map((field) => field.path)).toEqual(["user.first_name", "user.username"]);
    expect(searchContextFields("telegram_id").map((field) => field.path)).toEqual(["user.telegram_id"]);
    expect(searchContextFields("код языка").map((field) => field.path)).toEqual(["user.language_code"]);
    expect(searchContextFields("", SYSTEM_CONTEXT_FIELDS)).toHaveLength(5);
  });

  it("adapts resource definitions into the shared searchable catalog", () => {
    const fields = contextFieldsFromDefinitions([{
      id: "var_order_total",
      owner: { type: "flow", id: "checkout" },
      path: "order.total",
      type: "number",
      source: "custom",
      required: true,
      writable: true,
      persistence: "resource",
      exposedToTemplates: true,
      exampleValue: 120,
      legacyPaths: ["order.legacy_total"],
    }]);

    expect(searchContextFields("checkout", fields)).toEqual([
      expect.objectContaining({
        id: "var_order_total",
        path: "order.total",
        valueType: "number",
        example: 120,
      }),
    ]);
    expect(parseTemplate("{{ order.total }}", fields).nodes).toEqual([
      expect.objectContaining({
        type: "context-token",
        fieldId: "var_order_total",
        path: "order.total",
      }),
    ]);
    expect(parseTemplate("{{ order.legacy_total }}", fields).nodes).toEqual([
      expect.objectContaining({
        type: "context-token",
        fieldId: "var_order_total",
        path: "order.total",
        source: "{{ order.legacy_total }}",
      }),
    ]);
  });

  it("validates unknown fields and unsupported fragments", () => {
    const diagnostics = validateTemplate(parseTemplate("{{ order.total }} {{ user.name | upper }}"));
    expect(diagnostics).toEqual([
      expect.objectContaining({ code: "unknown-context-field", message: "Unknown context field: order.total" }),
      expect.objectContaining({ code: "unsupported-expression" }),
    ]);
  });

  it("renders the isolated simple preview", () => {
    const values = defaultPreviewValues();
    values["user.first_name"] = "Анна";
    expect(renderTemplatePreview(parseTemplate("Привет, {{ user.first_name }}!"), values)).toBe("Привет, Анна!");
  });
});
