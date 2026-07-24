import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TemplateComposer } from "./TemplateComposer";
import { useFieldHistory } from "../../shared/lib/useFieldHistory";

function Harness({ initial = "" }: { initial?: string }) {
  const [content, setContent] = useState(initial);
  return <><TemplateComposer content={content} onContentChange={setContent} /><output data-testid="source-value">{content}</output></>;
}

function HistoryHarness({ initial = "" }: { initial?: string }) {
  const [content, setContent] = useState(initial);
  useFieldHistory();
  return <><TemplateComposer content={content} onContentChange={setContent} /><output data-testid="source-value">{content}</output></>;
}

function typeVisual(value: string) {
  const editor = screen.getByRole("textbox", { name: "Visual message content" });
  const textElement = editor.querySelector<HTMLElement>("[data-template-node='text']") ?? editor;
  textElement.textContent = value;
  const text = textElement.firstChild;
  if (text) setCaret(text, text.textContent?.length ?? 0);
  fireEvent.input(editor);
  return editor;
}

describe("visual template composer", () => {
  it("opens autocomplete with $, filters it, and closes with Escape", () => {
    render(<Harness />);
    const editor = typeVisual("$");
    expect(screen.getByRole("listbox", { name: "Context fields" })).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(5);

    const textElement = editor.querySelector<HTMLElement>("[data-template-node='text']")!;
    textElement.textContent = "$им";
    setCaret(textElement.firstChild as Node, 3);
    fireEvent.input(editor);
    expect(screen.getByRole("option", { name: /Имя/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Фамилия/ })).not.toBeInTheDocument();

    fireEvent.keyDown(editor, { key: "Escape" });
    expect(screen.queryByRole("listbox", { name: "Context fields" })).not.toBeInTheDocument();
  });

  it("inserts the active token with Enter and exposes its metadata tooltip", () => {
    render(<Harness />);
    const editor = typeVisual("$им");
    fireEvent.keyDown(editor, { key: "Enter" });
    expect(screen.getByTestId("source-value")).toHaveTextContent("{{ user.first_name }}");
    const token = screen.getByLabelText("Пользователь: Имя");
    expect(token).toHaveAttribute("title", expect.stringContaining("user.first_name"));
    expect(token).toHaveAttribute("contenteditable", "false");
  });

  it("undoes and redoes a variable inserted from autocomplete", async () => {
    render(<HistoryHarness />);
    const editor = typeVisual("$");
    fireEvent.focus(editor);
    fireEvent.keyDown(editor, { key: "Enter" });
    await Promise.resolve();
    expect(screen.getByTestId("source-value")).toHaveTextContent("{{ user.first_name }}");

    fireEvent.keyDown(editor, { key: "z", ctrlKey: true });
    expect(screen.getByTestId("source-value")).toHaveTextContent("$");
    fireEvent.keyDown(editor, { key: "z", ctrlKey: true, shiftKey: true });
    expect(screen.getByTestId("source-value")).toHaveTextContent("{{ user.first_name }}");
  });

  it("undoes deletion of an inserted variable", async () => {
    render(<HistoryHarness initial="{{ user.first_name }}" />);
    const editor = screen.getByRole("textbox", { name: "Visual message content" });
    const token = screen.getByLabelText("Пользователь: Имя");
    token.focus();
    fireEvent.keyDown(token, { key: "Backspace" });
    await Promise.resolve();
    expect(screen.getByTestId("source-value")).toBeEmptyDOMElement();

    fireEvent.keyDown(editor, { key: "z", ctrlKey: true });
    expect(screen.getByTestId("source-value")).toHaveTextContent("{{ user.first_name }}");
  });

  it("supports keyboard navigation and inserts the selected field", () => {
    render(<Harness />);
    const editor = typeVisual("$");
    fireEvent.keyDown(editor, { key: "ArrowDown" });
    fireEvent.keyDown(editor, { key: "Enter" });
    expect(screen.getByTestId("source-value")).toHaveTextContent("{{ user.last_name }}");
  });

  it("deletes a focused token as one atomic node", () => {
    render(<Harness initial="Hello {{ user.first_name }}!" />);
    const token = screen.getByLabelText("Пользователь: Имя");
    token.focus();
    fireEvent.keyDown(token, { key: "Backspace" });
    expect(screen.getByTestId("source-value")).toHaveTextContent("Hello !");
    expect(screen.queryByLabelText("Пользователь: Имя")).not.toBeInTheDocument();
  });

  it("can delete the only token without mutating the React-managed editor DOM", () => {
    render(<Harness initial="{{ user.first_name }}" />);
    const token = screen.getByLabelText("Пользователь: Имя");
    token.focus();
    fireEvent.keyDown(token, { key: "Backspace" });
    expect(screen.getByTestId("source-value")).toBeEmptyDOMElement();
    expect(screen.getByRole("textbox", { name: "Visual message content" }).querySelector("[data-template-node='text']")).toBeInTheDocument();
  });

  it("keeps a live caret after deleting text typed immediately after a token", async () => {
    render(<Harness initial="{{ user.first_name }}x" />);
    const editor = screen.getByRole("textbox", { name: "Visual message content" });
    const renderedSuffix = editor.querySelector<HTMLElement>("[data-template-node='text']")!.firstChild!;
    renderedSuffix.textContent = "";
    setCaret(renderedSuffix, 0);
    fireEvent.input(editor);
    await Promise.resolve();

    expect(screen.getByTestId("source-value")).toHaveTextContent("{{ user.first_name }}");
    const trailingTextSlot = editor.querySelector<HTMLElement>("[data-template-node='text']");
    expect(trailingTextSlot).not.toBeNull();
    expect(trailingTextSlot?.contains(window.getSelection()?.anchorNode ?? null) || window.getSelection()?.anchorNode === trailingTextSlot).toBe(true);
  });

  it("switches modes and reparses source changes into visual tokens", () => {
    render(<Harness initial="Hello" />);
    fireEvent.click(screen.getByRole("tab", { name: "Source" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Message source" }), { target: { value: "Hi {{ user.username }}" } });
    fireEvent.click(screen.getByRole("tab", { name: "Visual" }));
    expect(screen.getByLabelText("Пользователь: Username")).toBeInTheDocument();
  });

  it("updates preview when source or test values change", () => {
    render(<Harness initial="Здравствуйте, {{ user.first_name }}!" />);
    expect(screen.getByText("Здравствуйте, Константин!")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Test user values"));
    fireEvent.change(screen.getByLabelText("Preview Имя"), { target: { value: "Анна" } });
    expect(screen.getByText("Здравствуйте, Анна!")).toBeInTheDocument();
  });

  it("shows an unresolved token and inline warning without losing source", () => {
    render(<Harness initial="Total: {{ order.total }}" />);
    expect(screen.getByLabelText("Unknown context field: order.total")).toBeInTheDocument();
    expect(screen.getByText("Unknown context field: order.total")).toBeInTheDocument();
    expect(screen.getByTestId("source-value")).toHaveTextContent("Total: {{ order.total }}");
  });

  it("commits composed text only after composition ends", () => {
    render(<Harness />);
    const editor = screen.getByRole("textbox", { name: "Visual message content" });
    const textElement = editor.querySelector<HTMLElement>("[data-template-node='text']")!;

    fireEvent.compositionStart(editor);
    textElement.textContent = "п";
    setCaret(textElement.firstChild as Node, 1);
    fireEvent.input(editor);
    expect(screen.getByTestId("source-value")).toBeEmptyDOMElement();

    textElement.textContent = "пр";
    setCaret(textElement.firstChild as Node, 2);
    fireEvent.compositionEnd(editor);
    expect(screen.getByTestId("source-value")).toHaveTextContent("пр");
  });
});

function setCaret(node: Node, offset: number) {
  const range = document.createRange();
  range.setStart(node, offset);
  range.collapse(true);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
}
