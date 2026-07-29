import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TelegramCompiledPreview, renderCompiledEntityText, sliceUtf16 } from "./TelegramCompiledPreview";

describe("Telegram compiled preview", () => {
  it("uses Telegram UTF-16 offsets and renders nested entities", () => {
    expect(sliceUtf16("A😀B", 1, 2)).toBe("😀");
    const { container } = render(<div>{renderCompiledEntityText("😀Hello", [
      { type: "custom_emoji", offset: 0, length: 2, custom_emoji_id: "100" },
      { type: "bold", offset: 2, length: 5 },
      { type: "italic", offset: 3, length: 3 },
    ])}</div>);

    expect(container.querySelector("[data-custom-emoji-id='100']")).toHaveTextContent("😀");
    expect(container.querySelector("strong")).toHaveTextContent("Hello");
    expect(container.querySelector("strong em")).toHaveTextContent("ell");
  });

  it("shows split compiler messages and keeps unsafe links inert", () => {
    const { container } = render(
      <TelegramCompiledPreview
        result={{
          messages: [
            { text: "first", entities: [{ type: "text_link", offset: 0, length: 5, url: "javascript:alert(1)" }] },
            { text: "second", entities: [] },
          ],
          warnings: [],
          errors: [],
        }}
        values={{}}
        onValuesChange={() => undefined}
      />,
    );

    expect(screen.getAllByTestId("compiled-message")).toHaveLength(2);
    expect(screen.getByText("2 messages")).toBeInTheDocument();
    expect(screen.getByText("Split by compiler")).toBeInTheDocument();
    expect(container.querySelector("a")).toBeNull();
  });

  it("forwards test values through the existing context paths", () => {
    const onValuesChange = vi.fn();
    render(<TelegramCompiledPreview result={null} values={{}} onValuesChange={onValuesChange} />);

    fireEvent.change(screen.getByLabelText("Preview Telegram ID"), { target: { value: "42" } });
    expect(onValuesChange).toHaveBeenCalledWith({ "user.telegram_id": 42 });
  });

  it("sends only after an explicit action with the selected chat", async () => {
    const onSendPreview = vi.fn().mockResolvedValue({ sentCount: 2, totalCount: 2 });
    render(<TelegramCompiledPreview
      result={{ messages: [{ text: "first", entities: [] }, { text: "second", entities: [] }], warnings: [], errors: [] }}
      values={{}}
      onValuesChange={() => undefined}
      onSendPreview={onSendPreview}
    />);

    expect(onSendPreview).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Telegram preview chat ID" }), { target: { value: "-100123" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(onSendPreview).toHaveBeenCalledWith("-100123"));
    expect(await screen.findByText("2 of 2 messages sent.")).toBeInTheDocument();
  });
});
