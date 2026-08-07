import { createContext, useContext } from "react";

import { SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "./context-catalog";

export const VariableFieldsContext = createContext<readonly ContextFieldDefinition[]>(SYSTEM_CONTEXT_FIELDS);

export function useVariableFields(): readonly ContextFieldDefinition[] {
  return useContext(VariableFieldsContext);
}
