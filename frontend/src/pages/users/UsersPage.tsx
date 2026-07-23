import { useOutletContext } from "react-router-dom";

import { UsersPage as UsersFeaturePage } from "../../features/users/UsersPage";
import type { StudioPageContext } from "../studio/studio-page-context";

export function UsersPage() {
  const { api, apiBaseUrl, workspace } = useOutletContext<StudioPageContext>();
  return <UsersFeaturePage api={api} apiBaseUrl={apiBaseUrl} projectId={workspace.project_id} />;
}
