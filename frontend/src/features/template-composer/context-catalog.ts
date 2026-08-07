import type { VariableDefinition, VariableType } from "../../domain/project";

export type ContextFieldDefinition = {
  id: string;
  path: string;
  label: string;
  group: string;
  valueType: VariableType;
  optional: boolean;
  description: string;
  example: unknown;
  source: "core" | "custom" | "computed";
  writable: boolean;
  legacyPaths?: readonly string[];
};

export const SYSTEM_CONTEXT_FIELDS: readonly ContextFieldDefinition[] = [
  {
    id: "core.user.first_name",
    path: "user.first_name",
    label: "Имя",
    group: "Пользователь",
    valueType: "string",
    optional: true,
    description: "Имя пользователя из Telegram",
    example: "Константин",
    source: "core",
    writable: false,
  },
  {
    id: "core.user.last_name",
    path: "user.last_name",
    label: "Фамилия",
    group: "Пользователь",
    valueType: "string",
    optional: true,
    description: "Фамилия пользователя из Telegram",
    example: "Кисс",
    source: "core",
    writable: false,
  },
  {
    id: "core.user.username",
    path: "user.username",
    label: "Username",
    group: "Пользователь",
    valueType: "string",
    optional: true,
    description: "Публичное имя пользователя в Telegram",
    example: "konstantin",
    source: "core",
    writable: false,
  },
  {
    id: "core.user.telegram_id",
    path: "user.telegram_id",
    label: "Telegram ID",
    group: "Пользователь",
    valueType: "number",
    optional: false,
    description: "Уникальный идентификатор пользователя Telegram",
    example: 123456789,
    source: "core",
    writable: false,
  },
  {
    id: "core.user.language_code",
    path: "user.language_code",
    label: "Язык",
    group: "Пользователь",
    valueType: "string",
    optional: true,
    description: "Код языка пользователя из Telegram",
    example: "ru",
    source: "core",
    writable: false,
  },
] as const;

export function contextFieldsFromDefinitions(
  definitions: readonly VariableDefinition[],
): ContextFieldDefinition[] {
  const system = new Map(SYSTEM_CONTEXT_FIELDS.map((field) => [field.id, field]));
  return definitions
    .filter((definition) => definition.exposedToTemplates)
    .map((definition) => system.get(definition.id) ?? {
      id: definition.id,
      path: definition.path,
      label: definition.path.split(".").at(-1) ?? definition.path,
      group: definition.source === "core"
        ? "System"
        : `${definition.owner.type}: ${definition.owner.id}`,
      valueType: definition.type,
      optional: !definition.required,
      description: definition.description ?? definition.path,
      example: definition.exampleValue ?? definition.defaultValue ?? previewValueForType(definition.type),
      source: definition.source,
      writable: definition.writable,
      legacyPaths: definition.legacyPaths,
    });
}

function previewValueForType(type: VariableType): unknown {
  if (type === "number") return 0;
  if (type === "boolean") return false;
  if (type === "object") return {};
  if (type === "array") return [];
  if (type === "date") return "2026-01-01";
  if (type === "datetime") return "2026-01-01T12:00:00Z";
  return "";
}

export function findContextField(
  path: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): ContextFieldDefinition | undefined {
  return catalog.find((field) => field.path === path || field.legacyPaths?.includes(path));
}

export function findContextFieldByReference(
  fieldId: string | null | undefined,
  path: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): ContextFieldDefinition | undefined {
  return catalog.find((field) => field.id === fieldId) ?? findContextField(path, catalog);
}

export function searchContextFields(
  query: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): ContextFieldDefinition[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return [...catalog];
  return catalog.filter((field) =>
    [field.label, field.path, field.description, field.group]
      .some((value) => value.toLocaleLowerCase().includes(normalized)),
  );
}
