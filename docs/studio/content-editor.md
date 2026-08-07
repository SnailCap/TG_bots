# Rich Text Content Editor

Rich Text Content Editor — отдельный редактор текста `view`, который хранит Telegram-разметку как типизированный документ и компилирует её в `text + entities`. Он не заменяет project schema v3 и не меняет модель Visual Template Composer: Composer по-прежнему использует одну Jinja-строку и transient document model, а Rich Text Editor владеет отдельным persisted content document.

## Граница форматов

У проекта остаётся `schema_version: 3`. Structured content подключается к существующему `view.text` опциональной ссылкой:

```json
{
  "schema_version": 3,
  "id": "home",
  "text": {
    "template": "views/home.txt",
    "document": "views/home.json"
  },
  "keyboard": []
}
```

Пути считаются относительно разных каталогов:

```text
resources/
├─ views/home.json                   # schema v3 view
├─ content/views/home.json           # canonical rich source, content schema v1
└─ templates/views/home.txt          # derived plain-Jinja compatibility projection
```

`text` по-прежнему содержит ровно одно из `inline` или `template`; `document` — независимое optional поле. Loader индексирует `resources/content/**/*.json`, если каталог существует. Ссылка должна быть POSIX-style relative `.json` path без `..` и обратных слешей. Studio использует owned path `views/<view-id>.json` и при сохранении требует, чтобы `document.id` совпадал с ID view.

Новый runtime при наличии `text.document` компилирует document. Если ссылки нет, действует прежний inline/template Jinja renderer. Одно из `inline`/`template` остаётся обязательным compatibility source; Studio канонизирует rich view в `template`, поэтому core, который ещё не знает `document`, продолжает читать обычную schema v3 template. Проекция сохраняет простой Jinja variable source и Unicode fallback custom emoji, но намеренно не записывает rich marks как HTML — старый runtime отправил бы эти теги как видимый текст. Для единственного блока `legacyTemplate` исходная строка возвращается без изменений.

`resources/content/` является частью автономного deployable проекта. Studio backend и frontend не нужны runtime для чтения или компиляции этих файлов.

## BotContentDocument schema v1

Content schema версионируется отдельно от project schema. Первая persisted версия использует camelCase JSON и строгий parser: неизвестные поля отклоняются.

```json
{
  "schemaVersion": 1,
  "id": "home",
  "content": [
    {
      "type": "paragraph",
      "content": [
        {
          "type": "text",
          "text": "Hello, ",
          "marks": [{"type": "bold"}]
        },
        {
          "type": "variable",
          "variableReference": {
            "path": "user.first_name",
            "fieldId": "core.user.first_name",
            "source": "{{ user.first_name }}"
          }
        },
        {
          "type": "customEmoji",
          "customEmojiId": "5368324170671202286",
          "fallbackEmoji": "🙂"
        }
      ]
    }
  ],
  "metadata": {
    "createdAt": "2026-07-29T12:00:00.000Z",
    "updatedAt": "2026-07-29T12:01:00.000Z",
    "editorVersion": "1.0.0",
    "source": "botstudio"
  }
}
```

Top-level contract:

| Поле | Правило |
| --- | --- |
| `schemaVersion` | Сейчас только `1`; migration boundary уже отделён от schema v3 |
| `id` | Непустой stable ID; Studio связывает его с view ID |
| `content` | В persisted valid document — непустой массив blocks; authoring normalization подставляет пустой paragraph |
| `metadata.createdAt`, `updatedAt` | Непустые timestamp strings |
| `metadata.editorVersion` | Версия producer/editor, не project schema |
| `metadata.source` | Optional: `botstudio`, `telegram-import` или `legacy-content` |

Поддерживаемые blocks:

| `type` | Поля | Telegram representation |
| --- | --- | --- |
| `paragraph` | `content: InlineNode[]` | Обычный текст |
| `blockquote` | `content: InlineNode[]` | Entity `blockquote` |
| `expandableBlockquote` | `content: InlineNode[]` | Entity `expandable_blockquote` |
| `codeBlock` | `text`, optional `language` | Entity `pre` |
| `legacyTemplate` | `source` | Lossless escape hatch для ещё неструктурируемого Jinja/HTML |

Поддерживаемые inline nodes:

| `type` | Поля |
| --- | --- |
| `text` | `text`, optional `marks` |
| `variable` | `variableReference`, optional `marks` |
| `customEmoji` | decimal `customEmojiId`, видимый `fallbackEmoji` |
| `hardBreak` | Только `type`; компилируется в `\n` |

Marks у `text` и `variable`: `bold`, `italic`, `underline`, `strikethrough`, `spoiler`, `code` и `link`. Только `link` имеет `href`; разрешены схемы `http`, `https`, `tg` и `mailto`, whitespace/NUL запрещены, а HTTP(S) URL обязан иметь valid hostname. Inline `code` не может пересекаться с другими marks. Duplicate marks, unsafe links, lone UTF-16 surrogates и невозможные Telegram overlaps являются validation/compile errors.

`customEmojiId` состоит только из цифр. `fallbackEmoji` обязателен, не длиннее 32 UTF-16 units и представляет ровно один Unicode emoji cluster: single emoji с optional variation/skin modifier, корректную ZWJ sequence, keycap, пару regional indicators либо black-flag tag sequence. ASCII text, несколько emoji, orphan tags и повреждённый ZWJ отклоняются. Даже без Telegram capability document остаётся читаемым благодаря fallback.

Normalization сортирует marks в стабильном порядке, удаляет пустые text nodes и объединяет соседние text nodes с одинаковыми marks. Невалидные или будущие marks не удаляются молча: validator должен показать ошибку. Studio ограничивает один document 2 MiB.

## Variables и Jinja

В Studio каталог переменных доступен отдельным экраном `Variables` в левом rail. Внутри resource explorer тот же экран открывается из вложенной настройки `Variables` у view/flow/state либо через контекстное меню handler; scoped-режим показывает только значения, доступные выбранному ресурсу, но сохраняет общий `resources/variables.json`. Built-in Telegram fields отображаются только для чтения, custom definitions можно добавлять и сохранять с revision-aware API.

Rich editor не поддерживает второй hard-coded список переменных. Picker переиспользует существующий context catalog из Template Composer. Запись содержит:

- `fieldId` — stable runtime identity definition, если переменная известна каталогу;
- `path` — сохранённый presentation/Jinja path вроде `user.first_name` и fallback для legacy content;
- `source` — optional точное legacy-написание для lossless round-trip.

Компилятор не выполняет `source` как произвольное выражение. Core resolver сначала ищет `fieldId`, проверяет доступность definition текущему view и подставляет значение по актуальному path. После переименования сохранённый path остаётся alias; path-only legacy nodes разрешаются через current/legacy paths. В production `FlowEngine` объединяет свободный session state, managed resource values и core user fields; preview использует example/default из того же resource-scoped каталога. Поэтому новый context field добавляется в `resources/variables.json`, а не отдельным условием в rich editor.

Простой legacy text и выражения вида `{{ dotted.path }}` мигрируют в структурные nodes. HTML, statements, filters, comments, неизвестные или неоднозначные expressions сохраняются целиком в `legacyTemplate`, пока lossless migration не сможет доказать эквивалентность. При компиляции такого блока Jinja values HTML-экранируются, поддерживаемая Telegram HTML-разметка переводится в entities, unsafe links удаляются до plain text, а неизвестная разметка сохраняется как текст с warning.

## Компиляция в Telegram

Public core boundary:

```python
from tg_bot_core.content import (
    TelegramCompileOptions,
    compile_content_document,
    parse_content_document,
)

document = parse_content_document(raw_json)
result = compile_content_document(
    document,
    variables,
    TelegramCompileOptions(max_message_length=4096, split_long_messages=True),
)
```

`TelegramCompileResult` содержит `messages`, `warnings` и `errors`. Каждый message — это plain `text` и массив entities; parse mode не используется. Поддерживаются `bold`, `italic`, `underline`, `strikethrough`, `spoiler`, `code`, `text_link`, `blockquote`, `expandable_blockquote`, `pre` и `custom_emoji`.

Offsets и lengths всегда считаются в UTF-16 code units, как требует Telegram Bot API, а не в Python/JavaScript code points. Variable output, custom emoji fallback, code block и legacy fragment считаются atomic ranges. Splitter при превышении 4096 units ищет границу в порядке: block boundary, пустая строка, конец предложения, whitespace, затем безопасная Unicode boundary. Он не разрезает atomic value, surrogate/combining/variation/skin-tone/ZWJ/tag sequence или flag pair; entities, пересекающие выбранную границу, корректно обрезаются и смещаются для каждого chunk. Если безопасного разбиения нет — например, один resolved variable или complex `legacyTemplate` сам длиннее limit — compilation возвращает `message_split_impossible`; при отключённом splitting — `message_too_long`.

При успешном splitting entities пересчитываются для каждого chunk. Runtime отправляет chunks последовательно: callback keyboard прикрепляется только к последнему, edit применяется только к первому, остальные отправляются новыми messages. Пустой результат, unresolved variable, невалидный document или невозможный overlap не передаются transport.

Studio preview использует тот же compiler через project-scoped endpoint:

```http
POST /api/v1/projects/{project_id}/content/compile
```

```json
{
  "document": {
    "schemaVersion": 1,
    "id": "home",
    "content": [{
      "type": "paragraph",
      "content": [{
        "type": "variable",
        "variableReference": {"path": "user.first_name"}
      }]
    }],
    "metadata": {
      "createdAt": "2026-07-29T12:00:00Z",
      "updatedAt": "2026-07-29T12:00:00Z",
      "editorVersion": "1.0.0",
      "source": "botstudio"
    }
  },
  "variables": {"user": {"first_name": "Ada"}},
  "split_long_messages": true
}
```

Ответ повторяет core wire format. У entity optional поля называются `url`, `language` и `custom_emoji_id`. Endpoint сначала проверяет открытый workspace, поэтому не является несвязанным публичным Jinja evaluator. Preview debounce равен 250 ms; устаревший HTTP request отменяется через `AbortController`.

## Сохранение, migration и drafts

Rich editor сохраняет три согласованных файла одной revision-aware операцией:

1. canonical `resources/content/views/<view-id>.json`;
2. derived `resources/templates/views/<view-id>.txt`;
3. view JSON с обеими ссылками.

```http
PUT /api/v1/projects/{project_id}/views/{view_id}/content
```

Request содержит `payload`, view `revision`, `document`, `document_revision` и `text_revision`. Backend проверяет все revisions под workspace lock, пишет файлы атомарно, повторно загружает project и при любой ошибке восстанавливает предыдущие bytes. Rename/delete/undo обрабатывают owned document вместе с view. Non-canonical внешняя ссылка не удаляется как чужой файл.

При первом переходе legacy view к rich document прежний template копируется в:

```text
.botstudio/backups/content/<view-id>/<UTC-timestamp>.txt
```

Backup создаётся до новой записи, не входит в `resources/` и игнорируется Git в starter. Миграция не переписывает сложный source молча: frontend/core adapters используют `legacyTemplate`, если структурный round-trip не byte-equivalent.

Обычный text editor и rich editor не являются двумя источниками истины. Save из обычного editor сохраняет ссылку `document`, только если derived template фактически не изменился. Если пользователь изменил plain source, ссылка удаляется и view снова становится legacy template view; следующий rich save выполнит явную миграцию заново.

Autosave запускается через 750 ms после последнего изменения и использует те же revisions, что ручной Save/Save All. Conflict не перезаписывает чужую версию. До server save draft best-effort хранится в `localStorage`:

```text
botstudio:content-draft:v1:<encoded-project-root>:<encoded-view-id>
```

Envelope содержит `schemaVersion`, `baseRevision`, `updatedAt` и `document`. Draft обновляется при вводе, перед unload и при unmount. Он восстанавливается только при совпадении schema version, view ID и base revision; после подтверждённого save удаляется. Если storage отключён, in-memory tab и project save продолжают работать.

## Telegram custom emoji

Custom emoji хранится в document только как stable decimal ID и Unicode fallback. Telegram metadata/preview — Studio cache, а не часть application graph:

```http
POST /api/v1/projects/{project_id}/telegram/custom-emojis/resolve
GET  /api/v1/projects/{project_id}/telegram/custom-emojis/{id}/preview
POST /api/v1/projects/{project_id}/telegram/custom-emojis/capability-test
```

Resolve принимает до 200 уникальных ASCII decimal IDs длиной до 32 символов, optional `fallbackById` и source `telegram-message`, `sticker-set`, `manual-id`, `recent` или `favorite`. Результат для каждого ID имеет status `resolved`, `fallback-only` или `unavailable`; отсутствие `BOT_TOKEN`, network/capability failures и недоступный preview не делают document нечитаемым.

Backend берёт token только из `.env` открытого project и не возвращает его renderer. Remote exception details не логируются, потому что URL/текст SDK могут содержать token. Cache располагается вне проекта в `%APPDATA%/BotStudio/cache/custom-emoji` (затем `%LOCALAPPDATA%`, если первый путь недоступен; иначе system temp), использует opaque ID keys и атомарные metadata/preview writes. Допустимы только WebP, TGS и WebM, preview ограничен 5 MiB, metadata — 64 KiB; suffix, magic signature, symlink, canonical path и MIME проверяются до выдачи. Preview response включает immutable cache policy и `X-Content-Type-Options: nosniff`; filesystem path в API не раскрывается.

Resolve и cache read никогда не отправляют сообщения. Capability test — отдельное явное действие пользователя: backend отправляет silent message в заданный chat с одной `custom_emoji` entity. HTTP endpoint требует `chatId` и возвращает `available`, `unavailable` или `unknown`; lower-level service использует `test-required`, если chat ещё не выбран. Таким образом проверка прав/доступности Telegram не является side effect обычного редактирования.

## Telegram import в core

Core предоставляет adapter без Studio HTTP/UI зависимости:

```python
from tg_bot_core.content import import_telegram_message

result = import_telegram_message(
    text,
    entities,
    document_id="imported_view",
    created_at="2026-07-29T12:00:00Z",
)
```

`entities` могут быть `TelegramMessageEntity` или mappings с Telegram UTF-16 offsets. Adapter импортирует известные inline/block/custom-emoji entities, нормализует document и ставит metadata source `telegram-import`. Invalid boundaries, unknown types, unsafe links и custom emoji без decimal ID превращаются в warnings; исходный text остаётся plain content. Это core-level API для будущих import workflows, не скрытый runtime registry и не обещание уже существующего Studio import endpoint.

## Как добавить новый entity type

Расширение выполняется одной вертикалью:

1. Добавьте node/mark в `tg_bot_core.content.models`, строгий parser/serializer и validation. Если persisted meaning несовместим, увеличьте independent content `schemaVersion` и добавьте последовательную migration; project schema остаётся v3, пока не меняется её contract.
2. Определите normalization, допустимые overlaps, безопасность payload и legacy projection. Неподдерживаемый source должен сохраняться через lossless escape hatch, а не исчезать.
3. Обновите frontend domain type, Tiptap extension, toolbar/commands и оба conversion direction. Context variables по-прежнему добавляются через общий context catalog.
4. Добавьте compiler mapping в `TelegramMessageEntity`, UTF-16 и splitting semantics, затем PTB conversion. Не вводите HTML/Markdown parse mode параллельно entities.
5. Обновите legacy adapter и `import_telegram_message`, включая поведение при невозможном round-trip.
6. Добавьте core, backend, frontend и runtime integration tests и синхронизируйте этот документ с [project schema](../architecture/project-schema-v3.md) и [runtime dispatch](../architecture/runtime-dispatch.md).

## Явная тестовая отправка и discard draft

Финальный preview можно отправить в выбранный Telegram chat только явным действием пользователя в правой панели редактора:

```http
POST /api/v1/projects/{project_id}/content/send-preview
```

Request содержит текущий `document`, те же вложенные test values, `chatId` и `splitLongMessages`. Backend повторно вызывает тот же `compile_content_document`, который используется preview и production runtime, а затем последовательно отправляет готовые chunks как `text + entities` без `parse_mode`. Сообщения отправляются с `disable_notification: true`. `BOT_TOKEN` читается только из `.env` выбранного project и никогда не возвращается renderer. Ошибка compile блокирует отправку целиком; ошибка Telegram возвращает безопасный общий текст и количество уже отправленных chunks без исходного SDK exception или token.

Draft envelope дополнительно сохраняет `editorSessionId` и `dirty: true`. Обычный unmount или аварийное закрытие flush-ит последнюю версию для восстановления. Если пользователь подтвердил **Discard unsaved changes**, Studio сначала удаляет local draft и помечает закрытие как намеренное, поэтому unmount-cleanup не создаёт отвергнутый draft заново. Такое же правило применяется к подтверждённым rename/delete view.

## Test strategy

Минимальные уровни регрессии:

- core: strict parse/serialize round-trip, normalization, content-version rejection/migration boundary, legacy losslessness, StrictUndefined variables, safe links, entity overlaps, UTF-16 offsets на astral/ZWJ/flags, splitting и Telegram import warnings;
- backend: atomic three-file save/rollback, view/template/document revision conflicts, 2 MiB limit, first-migration backup, rename/delete/restore, path traversal rejection и compile API parity;
- custom emoji: fake Telegram client, missing token/network fallbacks, batch limits, magic/size/symlink/cache checks, отсутствие token в logs/API и explicit-only capability send;
- frontend: document ↔ Tiptap conversion, toolbar/keyboard interactions, variable catalog, draft recovery, autosave timers, aborted preview request, multi-message preview и custom emoji fallback;
- runtime: entities доходят до PTB, multi-message порядок сохраняется, keyboard прикрепляется только к последнему chunk, legacy view остаётся совместимым.

Перед изменением contract запускаются соответствующие suites из корня репозитория:

```powershell
.\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests .\backend
Set-Location .\frontend
npm.cmd test
npm.cmd run build
```

Для изменённых starter/fixtures дополнительно выполняется `python -m tg_bot_core validate <project>`.
