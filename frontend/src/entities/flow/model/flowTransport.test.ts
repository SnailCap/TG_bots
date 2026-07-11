import { describe, expect, it } from "vitest";
import { normalizeFlow, serializeFlow } from "./flowTransport";

describe("flow transport", () => {
  it("normalizes backend snake_case config into editor data", () => {
    const flow = normalizeFlow({
      schema_version: 1,
      id: "registration",
      name: "Registration",
      start_node_id: "start",
      nodes: [
        { id: "start", type: "start", name: "Start", position: { x: 10, y: 20 }, config: {} },
        {
          id: "ask",
          type: "ask_input",
          name: "Ask age",
          position: { x: 100, y: 120 },
          config: {
            text: "Your age?",
            variable_name: "user.age",
            input_type: "integer",
            required: true,
            regex: "^\\d+$",
            min_value: 18,
            max_value: 120,
            error_message: "Enter a valid age",
            max_attempts: 4,
          },
        },
        {
          id: "condition",
          type: "condition",
          name: "Adult?",
          position: { x: 300, y: 120 },
          config: { variable: "user.age", operator: "gte", value: 18 },
        },
      ],
      transitions: [
        { id: "t1", source_node_id: "start", target_node_id: "ask", kind: "automatic", config: {} },
      ],
      metadata: { color: "blue" },
    });

    expect(flow.startNodeId).toBe("start");
    expect(flow.nodes[1].data).toMatchObject({
      title: "Ask age",
      variableName: "user.age",
      valueType: "integer",
      validationRegex: "^\\d+$",
      minValue: 18,
      maxValue: 120,
      maxAttempts: 4,
    });
    expect(flow.nodes[2].data).toMatchObject({
      conditionVariable: "user.age",
      conditionOperator: "gte",
      conditionValue: 18,
    });
  });

  it("serializes only runtime config fields and preserves choice outcome", () => {
    const serialized = serializeFlow({
      id: "main",
      name: "Main",
      startNodeId: "start",
      nodes: [
        { id: "start", type: "studioNode", position: { x: 0, y: 0 }, data: { kind: "start", title: "Start" } },
        {
          id: "choice",
          type: "studioNode",
          position: { x: 100, y: 40 },
          data: {
            kind: "choice",
            title: "Route",
            text: "Pick",
            keyboard: "inline",
            choices: [{ id: "create", label: "Create", value: "create" }],
          },
        },
        {
          id: "action",
          type: "studioNode",
          position: { x: 320, y: 40 },
          data: {
            kind: "action",
            title: "Create request",
            actionName: "create_request",
            actionTimeoutSeconds: 12,
            actionInputParameters: { description: "{{ request.description }}" },
            actionOutputMapping: { request_id: "request.id" },
          },
        },
      ],
      edges: [
        {
          id: "route-create",
          source: "choice",
          target: "action",
          sourceHandle: "create",
          data: { transitionKind: "button", outcome: "create" },
        },
      ],
    }) as Record<string, unknown>;

    expect(serialized).toMatchObject({ schema_version: 1, start_node_id: "start" });
    const nodes = serialized.nodes as Array<Record<string, unknown>>;
    expect(nodes[1]).toMatchObject({
      type: "choice",
      name: "Route",
      config: {
        text: "Pick",
        keyboard_type: "inline",
        choices: [{ id: "create", label: "Create", value: "create" }],
      },
    });
    expect(nodes[1]).not.toHaveProperty("data");
    expect(nodes[2].config).toEqual({
      action_name: "create_request",
      timeout_seconds: 12,
      input_parameters: { description: "{{ request.description }}" },
      output_mapping: { request_id: "request.id" },
    });
    expect((serialized.transitions as Array<Record<string, unknown>>)[0]).toMatchObject({
      kind: "button",
      outcome: "create",
    });
  });

  it("round-trips media mappings and accepts numeric constraint aliases", () => {
    const flow = normalizeFlow({
      id: "media",
      name: "Media",
      nodes: [
        {
          id: "photo",
          type: "send_message",
          config: {
            text: "Receipt",
            media: { type: "photo", path: "receipts/latest.png", source_type: "asset" },
          },
        },
        {
          id: "amount",
          type: "ask_input",
          config: { input_type: "number", min: 1, maximum: 100 },
        },
      ],
    });

    expect(flow.nodes[0].data).toMatchObject({
      mediaKind: "photo",
      mediaPath: "receipts/latest.png",
    });
    expect(flow.nodes[1].data).toMatchObject({ minValue: 1, maxValue: 100 });

    const serialized = serializeFlow(flow) as { nodes: Array<{ config: Record<string, unknown> }> };
    expect(serialized.nodes[0].config).toMatchObject({
      media: {
        type: "photo",
        path: "receipts/latest.png",
        source_type: "asset",
      },
    });
    expect(serialized.nodes[0].config).not.toHaveProperty("media_path");
  });

  it("normalizes legacy direct media fields and infers a safe kind", () => {
    const flow = normalizeFlow({
      id: "legacy",
      nodes: [
        { id: "document", type: "send_message", config: { document: "terms.pdf" } },
        { id: "image", type: "send_message", config: { media_path: "cover.jpg" } },
        { id: "range", type: "ask_input", config: { minimum: 2, max: 9 } },
      ],
    });

    expect(flow.nodes[0].data).toMatchObject({ mediaKind: "document", mediaPath: "terms.pdf" });
    expect(flow.nodes[1].data).toMatchObject({ mediaKind: "photo", mediaPath: "cover.jpg" });
    expect(flow.nodes[2].data).toMatchObject({ minValue: 2, maxValue: 9 });
  });
});
