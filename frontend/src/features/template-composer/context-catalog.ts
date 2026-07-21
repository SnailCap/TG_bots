export type ContextFieldDefinition = {
  id: string;
  path: string;
  label: string;
  group: string;
  valueType: "string" | "integer";
  optional: boolean;
  description: string;
  example: string | number | null;
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
  },
  {
    id: "core.user.telegram_id",
    path: "user.telegram_id",
    label: "Telegram ID",
    group: "Пользователь",
    valueType: "integer",
    optional: false,
    description: "Уникальный идентификатор пользователя Telegram",
    example: 123456789,
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
  },
] as const;

export function findContextField(
  path: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): ContextFieldDefinition | undefined {
  return catalog.find((field) => field.path === path);
}

export function searchContextFields(
  query: string,
  catalog: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): ContextFieldDefinition[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return [...catalog];
  return catalog.filter((field) =>
    [field.label, field.path, field.description]
      .some((value) => value.toLocaleLowerCase().includes(normalized)),
  );
}

