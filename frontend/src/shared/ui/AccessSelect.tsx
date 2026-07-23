import type { FormControlProps } from "./Form";
import { Select } from "./Select";

export type AccessLevel = "everyone" | "members" | "admins";

export function AccessSelect({ value, onChange, ariaLabel = "Resource access", ...controlProps }: FormControlProps & {
  value: AccessLevel;
  onChange(value: AccessLevel): void;
  ariaLabel?: string;
}) {
  return (
    <Select
      {...controlProps}
      ariaLabel={ariaLabel}
      value={value}
      options={ACCESS_OPTIONS}
      onChange={(next) => onChange(next as AccessLevel)}
    />
  );
}

const ACCESS_OPTIONS = [
  { value: "everyone", label: "Everyone", icon: <AccessIcon kind="everyone" /> },
  { value: "members", label: "Members", icon: <AccessIcon kind="members" /> },
  { value: "admins", label: "Administrators", icon: <AccessIcon kind="admins" /> },
];

function AccessIcon({ kind }: { kind: AccessLevel }) {
  const paths = {
    everyone: <><circle cx="8" cy="8" r="5.5" /><path d="M2.5 8h11M8 2.5c1.45 1.5 2.2 3.35 2.2 5.5S9.45 12 8 13.5C6.55 12 5.8 10.15 5.8 8S6.55 4 8 2.5" /></>,
    members: <><circle cx="5.75" cy="5.5" r="2.25" /><circle cx="11.25" cy="6.25" r="1.75" /><path d="M1.9 13.2c.45-2.1 1.82-3.3 3.85-3.3s3.4 1.2 3.85 3.3M9.35 10.15c1.55.08 2.6 1.03 2.95 2.65" /></>,
    admins: <><path d="m8 1.9 4.7 1.9v3.55c0 3.05-1.88 5.18-4.7 6.75-2.82-1.57-4.7-3.7-4.7-6.75V3.8L8 1.9Z" /><path d="m5.75 8.05 1.45 1.45 3.05-3.05" /></>,
  };
  return <svg viewBox="0 0 16 16" focusable="false">{paths[kind]}</svg>;
}
