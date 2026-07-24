# Как расширять schema и runtime

Schema v3 пересекает core, Studio backend и typed frontend. Изменение считается законченным только тогда, когда один и тот же contract можно создать в Studio, загрузить/проверить общим schema layer и выполнить автономным runtime. Backend не должен становиться второй реализацией schema.

## Перед изменением

Ответьте на пять вопросов:

1. Это изменение application graph или только runtime implementation detail?
2. Можно ли выразить его существующим action/event/context без нового формата?
3. Сохраняется ли однозначная ownership: resources задают routing, handler — бизнес-result?
4. Совместимо ли новое значение со всеми существующими v3 projects? Если нет, нужна новая schema version, а не молчаливое изменение semantics.
5. Как диагностировать unsupported/missing/invalid значение до запуска polling?

Не добавляйте Python registry, decorator/discovery или generated registry между resources и runtime.

## Вертикальный checklist

Для schema-visible change последовательно проверьте:

| Слой | Основные места |
| --- | --- |
| Typed contract | `packages/tg-bot-core/src/tg_bot_core/project/models.py` |
| Parsing | `project/loader.py`; required/default/strict allowed fields |
| Graph validation | `project/validation.py`; refs, kinds, stable diagnostic codes |
| Usage/reference index | `project/references.py` |
| Runtime semantics | `dispatcher.py`, `engine.py`, `outcomes.py`, `jobs.py`, `catalog.py` |
| Public SDK | `events.py`, `sdk.py`, root `tg_bot_core/__init__.py` |
| Studio backend | `backend/app/workspace/`, API request/response models и attachment logic |
| Studio frontend | `frontend/src/domain/project.ts`, API normalization, editor feature и validation UX |
| Electron boundary | Только если требуется privileged desktop operation; не переносите туда schema logic |
| Starter | `backend/app/workspace/starter.py`, generated test/README/entrypoint при необходимости |
| Документация | schema, dispatch, custom-code workflow, migration/version notes |

Backend CRUD в основном работает с JSON и затем вызывает общий `ProjectLoader`; не добавляйте локальный validator только ради удобства формы. UI-level constraints допустимы для ранней обратной связи, но authoritative code/semantics остаются в core diagnostics.

## Имена и обязательные значения Studio

Если Studio создаёт сущность с обязательным именем или runtime-required текстом, создавайте безопасное значение сразу: отображайте понятный default как неявную серую подсказку, но сохраняйте технический ID и required content до первого запуска. Human-facing display name хранится отдельно от технического ID; не меняйте ID и ссылки при обычном переименовании. Для кнопки default — непустой видимый текст, для нового view — непустой inline text с его default name.

Не создавайте defaults для optional descriptions. Также не подставляйте обязательные ссылки (`view`, handler, action target) произвольно: они требуют осознанного выбора и должны оставаться validation error, если не настроены.

## Новый event type

Сначала определите, это transport event или новая декларативная точка handler:

1. Добавьте immutable event DTO в `events.py` и решите, какие actor/update/payload fields стабильны.
2. Расширьте `BotTransport` contract только если существующей границы недостаточно.
3. Научите каждый поддерживаемый adapter строить event; для PTB — явно добавьте handler/filter и поведение unsupported update.
4. Добавьте отдельную branch в `EventDispatcher` с точным precedence. Не превращайте dispatch в неявное fall-through.
5. Если custom code получает новый context, добавьте его в `sdk.py`, context construction и public exports.
6. Если появляется новый handler trigger/kind, выполните также checklist handler kind ниже.
7. Если событие настраивается resources, добавьте typed schema, loader, validation, references и Studio editor/attachment.
8. Покройте adapter mapping, dispatch precedence, fallback и session/error behavior.

Документируйте, конфликтует ли событие с message/command branch. Например, command сейчас не проходит через message fallback.

## Новый action type

1. Добавьте type в `ACTION_TYPES` и, если нужны новые данные, расширьте `ActionSpec` либо введите однозначную typed модель.
2. В `ProjectLoader._action()` задайте ровно допустимые поля. Зафиксируйте required fields, defaults и типы; не допускайте два эквивалентных JSON-формата.
3. В `validate_project.validate_action()` проверьте references, trigger context и route target до runtime.
4. Если action содержит handler/task или nested routes, обновите `find_handler_usages()`.
5. Реализуйте одну ветку в `FlowEngine._apply_action()` и определите:

   - когда session сохраняется;
   - вызывает ли действие `on_enter`/lifecycle;
   - входит ли оно в automatic transition counter;
   - что происходит до/после внешнего side effect;
   - какой view рендерится по умолчанию.

6. Добавьте frontend union/type, `actionFor()` default и editor controls. Backend attachment logic обновляйте только если **Create handler** должен атомарно привязывать action.
7. Добавьте tests на parsing, extra fields, invalid refs, runtime success/error и nested usages.

Если action меняет persistence и queue одновременно, явно решите transaction boundary; не скрывайте частичную failure consistency.

## Новый handler kind

1. Добавьте kind в `HANDLER_KINDS`.
2. Создайте или выберите typed context в `sdk.py`; экспортируйте его из `tg_bot_core.__init__`.
3. Добавьте expected annotation в `project/validation.py`.
4. Укажите runtime owner, который строит context и вызывает единый `HandlerExecutor`; не дублируйте import/error/result logic.
5. Добавьте context mapping и template в `backend/app/workspace/handlers.py`.
6. Расширьте attachment validation в `ProjectService`, если Studio может создать handler из entity slot.
7. Расширьте `HandlerKind` и соответствующие editors в `frontend/src/domain/project.ts`/features.
8. Проверяйте kind mismatch и AST/runtime signature как в positive, так и negative tests.

Не создавайте второй registry для нового kind. Task handlers уже используют тот же `resources/handlers.json` и `HandlerExecutor` — это образец согласованности.

## Новый schedule trigger

Форма `trigger: {"type": ...}` уже расширяема, но runtime реализует только `interval`.

Для `cron`, `once` или другого trigger нужно:

1. Расширить `ScheduleTrigger` и parser с однозначными fields/types.
2. Добавить validation значений, timezone/DST rules и stable unsupported/invalid diagnostics.
3. Определить first-run, missed-run/catch-up, update и restart semantics.
4. Изменить SQLite representation. Текущая table имеет обязательный `interval_seconds`; для нового формата потребуется осознанная database migration, а не reinterpretation старой колонки.
5. Обновить `sync_schedules()` и `materialize_due_schedules()` с atomic claim/materialization.
6. Обновить Schedule editor; не показывать trigger как доступный до рабочей end-to-end реализации.
7. Протестировать boundary times, restart, duplicate materialization, deactivation и retry behavior.

Одного разрешения нового `trigger.type` в validator недостаточно.

## Новое context property

Context — security/maintenance boundary, поэтому сначала предпочитайте project service (`ctx.services["..."]`) прямому доступу к runtime object.

Если property действительно универсально:

1. Добавьте typed, минимальный и по возможности immutable public value в `sdk.py`.
2. Заполните его во всех context construction paths (`FlowEngine` и/или `JobRuntime`).
3. Определите поведение, когда transport не может дать значение.
4. Не раскрывайте `BotApp`, raw transport/store, dispatcher, catalog или mutable registry.
5. Обновите scaffold только если меняется context class/import/signature; Studio не должно переписывать существующие handlers.
6. Добавьте SDK tests на доступность, отсутствие internal capabilities и JSON/persistence semantics, если property влияет на state/result.
7. Обновите custom-code documentation.

## Diagnostics и versioning

Diagnostic contract состоит из `level`, `code`, `message`, optional `source_path`, `entity_id`, `field_path`. UI может зависеть от `code`, поэтому:

- используйте новый стабильный code для нового класса ошибки;
- сохраняйте field path конкретным;
- parse errors должны оставаться `ProjectLoadError`, graph errors — diagnostics;
- runtime startup, core CLI и Studio validation должны видеть одно и то же правило.

Backward-compatible addition с безопасным default может остаться в schema v3. Required field, изменённое значение существующего action или несовместимая persistence semantics обычно требует следующей schema version. V2 compatibility layer в основной runtime не добавляется.

Generated `pyproject.toml` pin должен меняться только вместе с протестированным release tag/commit. Не оставляйте starter на floating branch.

## Тестирование

Минимальный набор зависит от вертикали:

```powershell
# Core schema/runtime
.\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests

# Backend/starter/scaffolding
.\.venv\Scripts\python.exe -m pytest .\backend

# Typed UI и Electron boundary
Set-Location .\frontend
npm.cmd test
npm.cmd run build
```

Для cross-layer изменения запускайте весь набор и standalone acceptance scenario: starter создаётся backend API, custom handler вызывается fake transport, declarative outcome меняет state/view, restart восстанавливает session, imports Studio отсутствуют.

Добавляйте tests на invalid/unsupported input, а не только happy path. После изменения fixtures/starter отдельно запускайте:

```bash
python -m tg_bot_core validate <project>
```

Косметические и docs-only изменения не требуют полной сборки; проверяйте только затронутые риски.
