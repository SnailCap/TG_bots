import type { ComponentType } from "react";

import { GitPage } from "../git/GitPage";
import { ResourcesPage } from "../resources/ResourcesPage";
import { UsersPage } from "../users/UsersPage";

export type StudioRouteId = "resources" | "users" | "git";

export type StudioRouteDefinition = {
  id: StudioRouteId;
  path: `/${string}`;
  label: string;
  icon: ComponentType;
  page: ComponentType;
};

export const STUDIO_ROUTES = [
  {
    id: "resources",
    path: "/resources",
    label: "Resources",
    icon: ResourcesIcon,
    page: ResourcesPage,
  },
  {
    id: "users",
    path: "/users",
    label: "Users",
    icon: UsersIcon,
    page: UsersPage,
  },
  {
    id: "git",
    path: "/git",
    label: "Git",
    icon: GitIcon,
    page: GitPage,
  },
] as const satisfies readonly StudioRouteDefinition[];

export const DEFAULT_STUDIO_ROUTE = STUDIO_ROUTES[0];

export function studioRouteId(pathname: string): StudioRouteId {
  return STUDIO_ROUTES.find((route) => route.path === pathname)?.id ?? DEFAULT_STUDIO_ROUTE.id;
}

function ResourcesIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="3.25" y="3.25" width="5.1" height="5.1" rx=".5" /><rect x="11.65" y="3.25" width="5.1" height="5.1" rx=".5" /><rect x="3.25" y="11.65" width="5.1" height="5.1" rx=".5" /><rect x="11.65" y="11.65" width="5.1" height="5.1" rx=".5" /></svg>;
}

function UsersIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="7.2" cy="7" r="2.7" /><path d="M2.4 16.7c.35-3.5 1.95-5.3 4.8-5.3s4.45 1.8 4.8 5.3M12 5.8a2.55 2.55 0 0 1 0 5m1.2 1.2c2.55.3 3.95 1.85 4.35 4.7" /></svg>;
}

function GitIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="3.05" /><path d="M1.7 10h5.35M12.95 10h5.35" /></svg>;
}
