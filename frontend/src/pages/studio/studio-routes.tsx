import type { ComponentType } from "react";
import { GitBranch, LayoutGrid, Users } from "lucide-react";

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
  return <LayoutGrid aria-hidden="true" />;
}

function UsersIcon() {
  return <Users aria-hidden="true" />;
}

function GitIcon() {
  return <GitBranch aria-hidden="true" />;
}
