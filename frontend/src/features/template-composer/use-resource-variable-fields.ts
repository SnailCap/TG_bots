import { useEffect, useState } from "react";

import type { VariableResourceContext } from "../../domain/project";
import type { StudioApiClient } from "../../studio/api";
import {
  contextFieldsFromDefinitions,
  SYSTEM_CONTEXT_FIELDS,
  type ContextFieldDefinition,
} from "./context-catalog";

export function useResourceVariableFields(
  api: Pick<StudioApiClient, "getVariables"> | null | undefined,
  projectId: string,
  context: VariableResourceContext,
): readonly ContextFieldDefinition[] {
  const [fields, setFields] = useState<readonly ContextFieldDefinition[]>(SYSTEM_CONTEXT_FIELDS);
  const { resourceType, resourceId, flowId, stateId, handlerId } = context;

  useEffect(() => {
    if (!api?.getVariables || !projectId) {
      setFields(SYSTEM_CONTEXT_FIELDS);
      return;
    }
    let active = true;
    void api.getVariables(projectId, { resourceType, resourceId, flowId, stateId, handlerId })
      .then((detail) => {
        if (active) setFields(contextFieldsFromDefinitions(detail.definitions));
      })
      .catch(() => {
        if (active) setFields(SYSTEM_CONTEXT_FIELDS);
      });
    return () => { active = false; };
  }, [api, projectId, resourceType, resourceId, flowId, stateId, handlerId]);

  return fields;
}
