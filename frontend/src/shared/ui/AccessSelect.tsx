import { Globe, ShieldCheck, Users } from "lucide-react";

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
  const icons = {
    everyone: Globe,
    members: Users,
    admins: ShieldCheck,
  };
  const Icon = icons[kind];
  return <Icon aria-hidden="true" />;
}
