import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NodeInspector } from "./Inspector";

describe("NodeInspector", () => {
  it("emits typed Ask Input validation changes", async () => {
    const user = userEvent.setup();
    const onPatch = vi.fn();
    render(
      <NodeInspector
        actions={[]}
        onPatch={onPatch}
        data={{
          kind: "ask_input",
          title: "Age",
          text: "How old are you?",
          variableName: "user.age",
          valueType: "integer",
          required: true,
          maxAttempts: 3,
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText("Validation regex"), { target: { value: "^\\d+$" } });
    fireEvent.change(screen.getByLabelText("Minimum"), { target: { value: "18" } });
    expect(onPatch).toHaveBeenCalledWith({ validationRegex: "^\\d+$" });
    expect(onPatch).toHaveBeenCalledWith({ minValue: 18 });
  });

  it("edits structured Condition and Action values", async () => {
    const user = userEvent.setup();
    const conditionPatch = vi.fn();
    const { unmount } = render(
      <NodeInspector
        actions={[]}
        onPatch={conditionPatch}
        data={{ kind: "condition", title: "Paid?", conditionVariable: "payment.status", conditionOperator: "eq", conditionValue: "paid" }}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Operator"), "contains");
    expect(conditionPatch).toHaveBeenCalledWith({ conditionOperator: "contains" });
    unmount();

    const actionPatch = vi.fn();
    render(
      <NodeInspector
        actions={[]}
        onPatch={actionPatch}
        data={{ kind: "action", title: "Create", actionName: "", actionTimeoutSeconds: 30, actionInputParameters: {}, actionOutputMapping: {} }}
      />,
    );
    const output = screen.getByLabelText("Output mapping (JSON)");
    fireEvent.change(output, { target: { value: '{"request_id":"request.id"}' } });
    fireEvent.blur(output);
    expect(actionPatch).toHaveBeenCalledWith({ actionOutputMapping: { request_id: "request.id" } });
  });

  it("edits the send-message media kind independently from its asset path", async () => {
    const user = userEvent.setup();
    const onPatch = vi.fn();
    render(
      <NodeInspector
        actions={[]}
        onPatch={onPatch}
        data={{
          kind: "send_message",
          title: "Receipt",
          mediaKind: "photo",
          mediaPath: "receipts/latest.png",
        }}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Media type"), "document");
    fireEvent.change(screen.getByLabelText("Media / file path"), {
      target: { value: "receipts/latest.pdf" },
    });

    expect(onPatch).toHaveBeenCalledWith({ mediaKind: "document" });
    expect(onPatch).toHaveBeenLastCalledWith({ mediaPath: "receipts/latest.pdf" });
  });
});
