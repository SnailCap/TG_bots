# Руководство для coding agents

Перед изменением архитектуры прочитайте документы в `docs/architecture/`. Этот репозиторий реализует только декларативную project schema v3; старую v2-модель нельзя возвращать как параллельный способ конфигурации.

## Неподвижные инварианты

1. Studio — редактор и генератор файлов, а не runtime. Запущенный бот не зависит от Electron, frontend или Studio backend.
2. Папка созданного бота автономна: resources, Python-код, entrypoint, зависимости, runtime data path и deployment files находятся внутри неё.
3. `resources/` — единственный источник истины application graph: flows, states, views, hooks, commands/fallbacks, actions, bindings, outcomes и schedules. Не дублируйте этот graph в Python.
4. Custom handler занимается бизнес-логикой и возвращает `HandlerResult`. Он не выбирает произвольный state/view и не получает публичный `Transition`.
5. Context custom handler ограничен typed SDK. Не добавляйте в него `BotApp`, raw store/transport, dispatcher, catalog internals или mutable runtime registry.
6. Только explicit bindings из `resources/handlers.json`. Запрещены decorators для регистрации, filesystem/import discovery, global mutable registries и регистрация через import side effects.
7. Один handler соответствует одному безопасному module path и, в Studio scaffold, одному файлу с `async def handle(...)`. Studio никогда не перезаписывает существующее тело handler.
8. Schema parsing, typed models, references и validation принадлежат `tg_bot_core.project`. Backend Studio должен переиспользовать этот слой, а не копировать правила.
9. Generated bot не должен импортировать `backend`, `frontend` или Electron-код. Проверяйте автономность starter отдельным процессом/тестом.
10. Core владеет callback protocol `v3:a:<button-id>` и лимитом Telegram 64 bytes. Не кодируйте handler/flow payload напрямую в `callback_data`.
11. Services остаются Python bootstrap-зависимостями; они не являются скрытым registry application graph. Закрывайте services в обратном порядке создания.
12. Файловые изменения Studio должны оставаться path-safe, revision-aware и по возможности атомарными. Не оставляйте binding/reference/file в частично обновлённом состоянии.
13. Не добавляйте v2 compatibility, deprecated aliases или второй runtime без прямого запроса. `pipubot/` — отдельный legacy fixture, его не мигрируйте попутно.
14. Breaking project-format change требует явного решения о новой schema version. Не меняйте смысл существующего v3 JSON молча.
15. Production starter должен pin-ить core на проверенный tag или immutable commit, а не на floating branch.
16. Все обязательные schema directories должны переживать Git round trip. Не удаляйте starter placeholder `resources/schedules/.gitkeep`, пока loader требует существования пустого schedules directory.
17. Visual Template Composer не является новым project format: сохраняйте только обычный Jinja-текст, а визуальную document model держите transient во frontend.
18. Parser/serializer Template Composer должны сохранять исходные данные без потерь. Неизвестные или неподдерживаемые Jinja expressions нельзя удалять либо молча переписывать.
19. Context fields добавляются через отдельный context catalog, а не hard-coded ветвления внутри editor-компонентов. Visual и Source mode всегда используют одну Jinja-строку как источник состояния.

## Карта ответственности

- `packages/tg-bot-core/src/tg_bot_core/project/`: models, parsing, references, diagnostics и cross-resource validation.
- `packages/tg-bot-core/src/tg_bot_core/`: runtime composition, dispatcher, flow/action engine, handler SDK/executor, SQLite sessions/jobs и transport abstraction.
- `backend/app/workspace/`: безопасная работа с deployable files, revisions, starter и handler scaffolding/inspection.
- `frontend/src/`: typed domain model и Studio features; не используйте raw filesystem.
- `frontend/electron/`: минимальный privileged boundary, lifecycle backend и безопасный IDE launch.

При добавлении event/action/handler kind/schedule trigger/context property следуйте [docs/development/extending-schema.md](docs/development/extending-schema.md). Обновляйте loader, validator, references, runtime, Studio backend/frontend, starter и документацию как одну вертикаль; не допускайте расхождения Studio и runtime.

## Проверки по области изменений

Не запускайте тесты и сборку после каждого небольшого или косметического изменения. Выбирайте минимальный набор, способный поймать риск изменения.

- Только документация: проверьте ссылки, пути, команды и отсутствие утверждений о v2 как о текущей архитектуре; build не требуется.
- Core schema/SDK/runtime/jobs:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests
  ```

- Backend, repository, starter или scaffolding:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest .\backend
  ```

- Frontend или Electron:

  ```powershell
  Set-Location .\frontend
  npm.cmd test
  npm.cmd run build
  ```

- Cross-layer schema, starter, public API или release change: запустите полный Python suite, frontend tests/build и standalone acceptance tests:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest .\packages\tg-bot-core\tests .\backend
  Set-Location .\frontend
  npm.cmd test
  npm.cmd run build
  ```

Всегда запускайте `python -m tg_bot_core validate <project>` для изменённых schema fixtures/starter projects. Не добавляйте generated databases, `.env`, build output, caches или virtual environments в Git.

## Архитектурные документы

- `docs/architecture/overview.md` — компоненты и dependency direction.
- `docs/architecture/project-schema-v3.md` — фактический JSON contract.
- `docs/architecture/runtime-dispatch.md` — event/action/flow/job semantics.
- `docs/studio/custom-code-workflow.md` — Studio → handler → IDE workflow.
- `docs/development/extending-schema.md` — change checklist.
- `docs/deployment/vps.md` — autonomous deployment.
- `docs/migration/v2-to-v3.md` — намеренно удалённые v2 concepts.
