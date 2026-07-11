import { describe, expect, it } from "vitest";
import { normalizeActions, normalizeIssues, normalizeLog } from "./normalize";

describe("runtime and validation normalization", () => {
  it("canonicalizes discovered action paths for Explorer tabs", () => {
    expect(
      normalizeActions({ actions: [{ name: "create", file_path: "nested/action.py" }] })[0].scriptPath,
    ).toBe("scripts/nested/action.py");
  });

  it("marks actions with discovery issues as invalid", () => {
    const action = normalizeActions({
      actions: [{ name: "sync_action", file_path: "actions.py" }],
      issues: [
        {
          entity_type: "action",
          entity_id: "sync_action",
          message: "Action must be async",
        },
      ],
    })[0];
    expect(action).toMatchObject({ valid: false, error: "Action must be async" });
  });

  it("keeps runtime source and script navigation context", () => {
    expect(
      normalizeLog({
        id: 7,
        event_type: "action.error",
        level: "error",
        message: "boom",
        context: { script_path: "scripts/actions.py", line: 12 },
      }),
    ).toMatchObject({
      id: "7",
      source: "action.error",
      entity: { scriptPath: "scripts/actions.py", line: 12 },
    });
  });

  it("derives the containing flow for node validation issues", () => {
    expect(
      normalizeIssues({
        issues: [
          {
            code: "node.transition_missing",
            severity: "error",
            message: "Missing edge",
            entity_type: "node",
            entity_id: "ask-name",
            path: "flows/main.flow.json",
          },
        ],
      })[0].entity,
    ).toMatchObject({ flowId: "main", nodeId: "ask-name" });
  });
});
