import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UsersPage, type BotUser } from "./UsersPage";

const users: BotUser[] = [
  { telegramId: "10001", firstName: "Anna", lastName: "Keller", username: "annak", languageCode: "en", role: "trusted", status: "active", note: "", avatarVersion: null },
  { telegramId: "10002", firstName: "Marcus", lastName: "Chen", username: "marcusc", languageCode: null, role: "user", status: "active", note: "", avatarVersion: null },
];

describe("UsersPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal("PointerEvent", MouseEvent);
  });

  it("supports search and opens a user details card", () => {
    render(<UsersPage initialUsers={users} />);

    fireEvent.change(screen.getByPlaceholderText("Search name, username, or Telegram ID"), { target: { value: "10001" } });
    expect(screen.getByText("Anna Keller")).toBeInTheDocument();
    expect(screen.queryByText("Marcus Chen")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Anna Keller"));
    const dialog = screen.getByRole("dialog", { name: "Anna Keller details" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByLabelText("User role")).toHaveTextContent("Trusted user");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(dialog).toHaveClass("user-details--closing");
    fireEvent.animationEnd(dialog);
    expect(screen.queryByRole("dialog", { name: "Anna Keller details" })).not.toBeInTheDocument();
  });

  it("blocks the user list and closes with animation after a backdrop click", () => {
    const { container } = render(<UsersPage initialUsers={users} />);
    fireEvent.click(screen.getByText("Anna Keller"));

    expect(container.querySelector(".users-manager")).toHaveAttribute("inert");
    const backdrop = screen.getByTestId("user-details-backdrop");
    fireEvent.pointerDown(backdrop);
    const dialog = screen.getByRole("dialog", { name: "Anna Keller details" });
    expect(backdrop).toHaveClass("user-details-layer--closing");
    expect(dialog).toHaveClass("user-details--closing");
    fireEvent.animationEnd(dialog);
    expect(screen.queryByRole("dialog", { name: "Anna Keller details" })).not.toBeInTheDocument();
  });

  it("discards unsaved drawer changes when it closes", () => {
    render(<UsersPage initialUsers={users} />);
    fireEvent.click(screen.getByText("Anna Keller"));
    fireEvent.click(screen.getByLabelText("User role"));
    fireEvent.click(screen.getByRole("option", { name: "Administrator" }));
    expect(screen.getByLabelText("User role")).toHaveTextContent("Administrator");

    fireEvent.pointerDown(screen.getByTestId("user-details-backdrop"));
    fireEvent.animationEnd(screen.getByRole("dialog", { name: "Anna Keller details" }));
    fireEvent.click(screen.getByText("Anna Keller"));
    expect(screen.getByLabelText("User role")).toHaveTextContent("Trusted user");
  });

  it("resizes the details drawer and restores the saved width", () => {
    const firstRender = render(<UsersPage initialUsers={users} />);
    fireEvent.click(screen.getByText("Anna Keller"));
    const resizer = screen.getByRole("separator", { name: "Resize user details" });
    fireEvent.pointerDown(resizer, { clientX: 500 });
    fireEvent.pointerMove(window, { clientX: 450 });
    fireEvent.pointerUp(window);
    expect(screen.getByRole("dialog", { name: "Anna Keller details" })).toHaveStyle({ width: "422px" });
    expect(window.localStorage.getItem("tg-bot-studio.users.details-width")).toBe("422");

    firstRender.unmount();
    render(<UsersPage initialUsers={users} />);
    fireEvent.click(screen.getByText("Anna Keller"));
    expect(screen.getByRole("dialog", { name: "Anna Keller details" })).toHaveStyle({ width: "422px" });
  });

  it("applies a bulk status change to selected users", async () => {
    render(<UsersPage initialUsers={users} />);

    fireEvent.click(screen.getByLabelText("Select Anna Keller"));
    fireEvent.click(screen.getByLabelText("Bulk status"));
    fireEvent.click(screen.getByRole("option", { name: "Blocked" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply changes" }));

    const annaRow = screen.getByText("Anna Keller").closest("tr");
    expect(annaRow).not.toBeNull();
    expect(within(annaRow!).getByText("Blocked")).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent("Updated 1 user.");
  });

  it("shows an instructive empty state", () => {
    render(<UsersPage initialUsers={[]} />);
    expect(screen.getByText("No users yet")).toBeInTheDocument();
    expect(screen.getByText(/after they interact with this bot/)).toBeInTheDocument();
  });

  it("keeps identifiers and metrics out of the table", () => {
    render(<UsersPage initialUsers={users} />);
    expect(screen.queryByRole("columnheader", { name: "Telegram ID" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Interactions" })).not.toBeInTheDocument();
    expect(screen.queryByText("Restricted")).not.toBeInTheDocument();
  });
});
