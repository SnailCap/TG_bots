import { useId, type HTMLAttributes, type ReactNode } from "react";

import "./Form.css";

export interface FormControlProps {
  id: string;
  disabled?: boolean;
  readOnly?: boolean;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

export function FormGrid({ children, columns = 1, width = "fluid", className = "" }: {
  children: ReactNode;
  columns?: 1 | 2;
  width?: "fluid" | "standard";
  className?: string;
}) {
  return <div className={`form-layout form-layout--columns-${columns} form-layout--width-${width} ${className}`.trim()}>{children}</div>;
}

export function FormField({
  label,
  children,
  id,
  hint,
  error,
  disabled = false,
  readOnly = false,
  layout = "row",
  span = "auto",
  className = "",
}: {
  label: ReactNode;
  children(props: FormControlProps): ReactNode;
  id?: string;
  hint?: ReactNode;
  error?: ReactNode;
  disabled?: boolean;
  readOnly?: boolean;
  layout?: "row" | "stacked";
  span?: "auto" | "full";
  className?: string;
}) {
  const generatedId = useId().replace(/:/g, "");
  const controlId = id ?? `form-control-${generatedId}`;
  const messageId = hint || error ? `${controlId}-message` : undefined;
  const controlProps: FormControlProps = {
    id: controlId,
    disabled: disabled || undefined,
    readOnly: readOnly || undefined,
    "aria-describedby": messageId,
    "aria-invalid": error ? true : undefined,
  };

  return (
    <div className={[
      "form-field",
      span === "full" ? "form-field--full" : "",
      disabled ? "form-field--disabled" : "",
      readOnly ? "form-field--readonly" : "",
      error ? "form-field--error" : "",
      layout === "stacked" ? "form-field--stacked" : "",
      className,
    ].filter(Boolean).join(" ")}>
      <label className="form-field__label" htmlFor={controlId}>
        <span className="form-field__label-text">
          {label}{typeof label === "string" && label.endsWith(":") ? null : ":"}
        </span>
      </label>
      <div className="form-field__body">
        {children(controlProps)}
        {messageId && (
          <div
            id={messageId}
            className={error ? "form-field__message form-field__message--error" : "form-field__message"}
            role={error ? "alert" : undefined}
          >
            {error ?? hint}
          </div>
        )}
      </div>
    </div>
  );
}

export function FormControlGroup({
  children,
  prefix,
  layout = "attached",
  className = "",
  ...props
}: Omit<HTMLAttributes<HTMLDivElement>, "prefix"> & {
  prefix?: ReactNode;
  layout?: "attached" | "split";
}) {
  return (
    <div className={`form-control-group form-control-group--${layout}${prefix ? " form-control-group--prefixed" : ""} ${className}`.trim()} {...props}>
      {prefix && <span className="form-control-group__prefix">{prefix}</span>}
      {children}
    </div>
  );
}
