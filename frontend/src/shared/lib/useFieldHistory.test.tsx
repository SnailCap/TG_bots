import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { useFieldHistory } from "./useFieldHistory";

function Harness() {
  const [text, setText] = useState("one");
  const [multiline, setMultiline] = useState("first");
  useFieldHistory();
  return <>
    <input aria-label="Text" value={text} onChange={(event) => setText(event.target.value)} />
    <textarea aria-label="Multiline" value={multiline} onChange={(event) => setMultiline(event.target.value)} />
  </>;
}

describe("useFieldHistory", () => {
  it("undoes and redoes controlled input and textarea values", () => {
    render(<Harness />);
    const text = screen.getByLabelText("Text");
    const multiline = screen.getByLabelText("Multiline");

    fireEvent.focus(text);
    fireEvent.change(text, { target: { value: "two" } });
    fireEvent.keyDown(text, { key: "z", ctrlKey: true });
    expect(text).toHaveValue("one");
    fireEvent.keyDown(text, { key: "y", ctrlKey: true });
    expect(text).toHaveValue("two");

    fireEvent.focus(multiline);
    fireEvent.change(multiline, { target: { value: "second" } });
    fireEvent.keyDown(multiline, { key: "z", ctrlKey: true });
    expect(multiline).toHaveValue("first");
    fireEvent.keyDown(multiline, { key: "z", ctrlKey: true, shiftKey: true });
    expect(multiline).toHaveValue("second");
  });
});
