import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FormControlGroup, FormField, FormGrid } from "./Form";
import { Select } from "./Select";

describe("shared form components", () => {
  it("connects labels, controls and validation messages", () => {
    render(
      <FormGrid columns={2}>
        <FormField label="Name" error="Name is required">
          {(controlProps) => <input {...controlProps} />}
        </FormField>
      </FormGrid>,
    );

    const input = screen.getByLabelText("Name:");
    const message = screen.getByRole("alert");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", message.id);
  });

  it("supports composed, disabled and read-only controls", () => {
    render(
      <FormGrid>
        <FormField label="Content:" span="full" readOnly>
          {(controlProps) => (
            <FormControlGroup layout="split">
              <Select
                {...controlProps}
                value="template"
                options={[{ value: "template", label: "Template" }]}
                onChange={() => undefined}
              />
              <input aria-label="Template path" readOnly />
            </FormControlGroup>
          )}
        </FormField>
        <FormField label="Disabled:" disabled>
          {(controlProps) => <textarea {...controlProps} />}
        </FormField>
      </FormGrid>,
    );

    expect(screen.getByLabelText("Content:")).toHaveAttribute("aria-readonly", "true");
    expect(screen.getByLabelText("Disabled:")).toBeDisabled();
  });
});
