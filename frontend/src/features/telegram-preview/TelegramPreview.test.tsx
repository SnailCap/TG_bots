import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ViewSpec, Workspace } from "../../domain/project";
import { createTelegramPreviewModel } from "./preview-model";
import { TelegramPreview } from "./TelegramPreview";

const workspace = {
  name: "my-bot",
} as Workspace;

const view: ViewSpec = {
  schema_version: 3,
  id: "home",
  text: { inline: "Welcome to the bot" },
  keyboard: [[{ id: "home.help", text: "Help", action: { type: "noop" } }]],
};

describe("TelegramPreview", () => {
  it("derives a Telegram conversation from the current view", () => {
    const model = createTelegramPreviewModel(workspace, { kind: "view", payload: view });

    expect(model.botName).toBe("my-bot");
    expect(model.messages.at(-1)).toMatchObject({ author: "bot", text: "Welcome to the bot", buttons: [["Help"]] });
  });

  it("lets the local simulator send a message and closes from its header", () => {
    const onClose = vi.fn();
    const model = createTelegramPreviewModel(workspace, { kind: "view", payload: view });
    render(<TelegramPreview open model={model} onClose={onClose} />);

    fireEvent.change(screen.getByLabelText("Preview message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByLabelText("Send preview message"));
    expect(screen.getByText("Hello")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Close preview"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
