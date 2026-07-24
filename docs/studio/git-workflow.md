# Git workflow в Telegram Bot Studio

Страница **Git** связывает папку открытого bot-project с GitHub. Studio не создаёт
вторую модель проекта: Git работает с теми же `resources/`, `src/`, deployment-файлами
и тестами, которые редактируются на странице Resources и запускаются автономным
runtime.

## Подключение

Откройте bot-project и выберите **Git** в левом rail. Доступны два варианта:

- **Existing repository** — укажите `owner/repository` и названия общей и production
  веток. Для существующего clone Studio проверит remote и совместимость истории.
- **Create new** — укажите имя, visibility и ветки. Studio инициализирует Git строго
  внутри папки бота, создаст initial commit и отправит обе ветки.

По умолчанию общая ветка называется `dev`, production — `production`. Их можно
изменить при подключении. Они должны быть разными.

В текущей версии desktop Studio использует fine-grained Personal Access Token.
Он шифруется Electron `safeStorage` и хранится в системном каталоге приложения.
Токен не записывается в bot-project, `.env`, Git remote URL, frontend
`localStorage` или `.botstudio/git.json`. Backend получает credential только в памяти
на время Git/GitHub-запроса. Слой авторизации отделён от Git workflow, поэтому его
можно заменить GitHub App device flow без изменения project format.

## Sync, Push и Publish

**Sync** получает новые commits из общей development-ветки. Обновление выполняется
только fast-forward. Если есть локальные файлы, Studio не перезаписывает их и просит
сначала выполнить Push или осознанно отменить изменения. `reset --hard`, force pull и
force push не используются.

**Push** сохраняет текущие редакторы, повторно проверяет GitHub, запускает schema/graph/
handler/view-text validation, показывает файлы и commit message, затем создаёт commit и
отправляет development-ветку. Если другой человек уже отправил новую версию, Push
останавливается до Sync.

**Publish** доступен только для чистой, синхронизированной development-ветки. Studio
выполняет полную validation и, если подготовлено project-local окружение, запускает
`pytest`. Production обновляется только fast-forward. Отдельные production commits
считаются divergence: Studio останавливается и ничего не перезаписывает.

При Publish можно создать patch/minor/major/custom annotated tag либо выпустить commit
без нового tag. GitHub Release пока не создаётся.

## Совместная работа двух пользователей

1. Первый пользователь создаёт repository на странице Git и выполняет Push.
2. Второй клонирует repository обычным способом, открывает clone как bot-project и
   подключает существующий repository.
3. Перед началом работы и перед Push каждый проверяет indicator и выполняет Sync.
4. Если изменения появились локально и на GitHub одновременно, Studio показывает
   конфликт и не удаляет ни одну версию. В текущем scope сложный merge выполняется
   внешним Git-инструментом/IDE; визуального merge-editor пока нет.
5. После проверки проекта один из участников выполняет Publish.

При открытии Git page remote проверяется в фоне. Автоматического pull нет.

## History и Changes

**Changes** показывает added/modified/deleted/renamed/untracked файлы, semantic summary
для views, включая внутренние `templates/views/*.txt`, flows/commands/schedules/handlers и обычный text diff. Binary diff
не отображается.

**History** показывает автора, дату, short hash, development/production status и ссылку
на commit в GitHub. Git остаётся источником истины; semantic summary — только
дополнительное представление.

## Настройки и файлы

`.botstudio/git.json` содержит только переносимые настройки:

- `owner/repository`;
- имя remote;
- development и production branches.

Commit/version/time последней публикации вычисляются из production ref, commit и
version tag самого Git. Это не создаёт служебное незакоммиченное изменение сразу после
Publish.

Локальный путь, credential, состояние системного хранилища и backups туда не попадают.
Starter и pre-commit check исключают или блокируют:

- `.env`, Telegram/GitHub tokens и private keys;
- `data/*.sqlite3`, WAL/SHM, sessions и jobs;
- `.venv`, `__pycache__`, pytest/package/build output;
- IDE directories;
- `.botstudio/backups/` и credential-like metadata.

Runtime SQLite намеренно не синхронизируется: это mutable production state, а не часть
declarative project schema. Telegram token также остаётся deployment secret.

## Внешний deployment

Studio не управляет Railway, Render, Vercel или VPS API. Настройте выбранный deployment
service так, чтобы он отслеживал production branch и запускал автономный project
entrypoint. Практический VPS/systemd workflow описан в
[deployment guide](../deployment/vps.md).

## API и ошибки

Backend предоставляет `status`, `changes`, `history`, `connect`, `create-repository`,
`disconnect`, `fetch`, `sync`, `push` и `publish` под
`/api/v1/projects/{project_id}/git/`. Git выполняется без shell, с массивом аргументов,
project root как working directory и timeout.

UI получает стабильные коды, например `git_not_installed`,
`authentication_required`, `working_tree_dirty`, `remote_changes_detected`,
`validation_failed`, `secret_detected`, `production_diverged` и
`network_unavailable`, а не raw stdout/stderr.
