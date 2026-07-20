# Развёртывание автономного бота на VPS

Generated schema v3 project не требует Telegram Bot Studio на сервере. На VPS нужны сам project, Python 3.12/3.13, доступ к pinned `tg-bot-core` dependency, Telegram token и persistent каталог `data/`.

Ниже предполагаются project `my-bot`, package `my_bot` и Linux user `mybot`; замените их своими значениями.

## Что переносить

Переносите целиком созданную Studio папку:

```text
resources/
src/my_bot/
tests/
data/
pyproject.toml
Dockerfile
.env.example
README.md
```

Не копируйте repository `backend/`, `frontend/` или Electron build. Runtime их не импортирует.

## Подготовка Linux host

Установите Python 3.12 с venv support и Git. Git нужен, потому что текущий starter pin-ит core прямой Git dependency:

```toml
"tg-bot-core @ git+https://github.com/SnailCap/TG_bots.git@core-v3.0.0#subdirectory=packages/tg-bot-core"
```

Tag `core-v3.0.0` должен существовать в remote repository. В production допустим и предпочтителен проверенный immutable commit pin.

Создайте отдельного непривилегированного пользователя и разместите project, например, в `/opt/my-bot`. Конкретные package-manager commands зависят от Linux distribution; после установки Python/Git:

```bash
cd /opt/my-bot
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python -m tg_bot_core validate .
python -m my_bot --validate
```

Resources намеренно остаются deployable files рядом с project, а не включаются в Python wheel. Поэтому process должен запускаться с `WorkingDirectory` в корне project либо с `BOT_PROJECT_ROOT=/opt/my-bot`. Entrypoint ищет root в порядке `BOT_PROJECT_ROOT` → текущий рабочий каталог → source-tree fallback; editable install не обязателен.

Каталог `data/` должен быть writable service user:

```bash
chown -R mybot:mybot /opt/my-bot
chmod 700 /opt/my-bot/data
```

## Environment и secrets

Core читает token только из process environment:

```bash
export BOT_TOKEN="123456:replace-me"
python -m my_bot
```

Копирование `.env.example` в `.env` само по себе ничего не загружает: `python-dotenv` в starter не вызывается. Используйте systemd `EnvironmentFile=`, Docker `--env-file` или export shell. Не коммитьте `.env`; ограничьте права `chmod 600`.

Default database — `<project>/data/runtime.sqlite3`. Другой path задаётся аргументом `BotConfig.from_env(database_path=...)` в project entrypoint; специальной environment variable для database path сейчас нет.

## systemd

Создайте `/etc/my-bot.env`:

```text
BOT_TOKEN=123456:replace-me
```

и unit `/etc/systemd/system/my-bot.service`:

```ini
[Unit]
Description=My Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mybot
Group=mybot
WorkingDirectory=/opt/my-bot
EnvironmentFile=/etc/my-bot.env
ExecStart=/opt/my-bot/.venv/bin/python -m my_bot
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

`BotApp.run_async()` регистрирует SIGINT и SIGTERM (с fallback для event loops, где это поддерживается только основным thread). Оба сигнала переводят runtime к `finally: stop()`: scheduler/workers получают graceful stop, polling останавливается, services закрываются. `TimeoutStopSec=30` оставляет запас для worker drain.

Активируйте и проверьте:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now my-bot.service
sudo systemctl status my-bot.service
sudo journalctl -u my-bot.service -f
```

Перед первым start полезно выполнить validation именно service interpreter/user:

```bash
sudo -u mybot /opt/my-bot/.venv/bin/python -m tg_bot_core validate /opt/my-bot
```

## Docker

Generated `Dockerfile` использует `python:3.12-slim`, устанавливает Git, копирует project в `/app`, выполняет `pip install .`, объявляет `/app/data` volume и запускает package из `WORKDIR /app`.

```bash
docker build -t my-bot:core-v3 /opt/my-bot
docker run -d \
  --name my-bot \
  --restart unless-stopped \
  --env-file /opt/my-bot/.env \
  -v /srv/my-bot-data:/app/data \
  my-bot:core-v3
```

Проверьте validation отдельным ephemeral container:

```bash
docker run --rm --entrypoint python my-bot:core-v3 -m tg_bot_core validate /app
```

Generated Dockerfile declares `STOPSIGNAL SIGTERM`, поэтому обычный graceful stop работает без особого сигнала:

```bash
docker stop --time=30 my-bot
```

В Compose при необходимости задайте `stop_grace_period: 30s`; `stop_signal` можно не переопределять. Без persistent mount `/app/data` sessions/jobs пропадут вместе с container.

## SQLite persistence

Одна database хранит sessions, processed update IDs, schedules, jobs и job run history. Сохраняйте весь `data/` на persistent disk; SQLite WAL может использовать соседние `runtime.sqlite3-wal` и `runtime.sqlite3-shm`.

Для согласованного online backup используйте SQLite backup API/CLI, а не простое копирование только `.sqlite3` во время работы:

```bash
mkdir -p /var/backups/my-bot
sqlite3 /opt/my-bot/data/runtime.sqlite3 \
  ".backup '/var/backups/my-bot/runtime-$(date +%F-%H%M%S).sqlite3'"
```

Альтернатива — остановить service, сделать snapshot/copy всего `data/`, затем запустить снова. Периодически проверяйте восстановление backup на отдельном host/project.

Текущая queue имеет atomic SQLite claim и renewable leases, но не имеет owner/fencing token. Не запускайте несколько OS processes/containers на одной database. Для параллельных tasks используйте `BotConfig.worker_count` внутри одного process.

## Обновление runtime/project

1. Остановите service/container штатно.
2. Сделайте database backup.
3. Обновите project code/resources и pin core на протестированный tag/commit.
4. Обновите или пересоздайте venv/image.
5. Выполните `python -m tg_bot_core validate .`, project tests и короткий smoke test с test bot/token.
6. Запустите service и проверьте logs/jobs/session behavior.

Не переводите production project на floating Git branch. Breaking schema change нельзя применять только обновлением package: сначала нужна явная migration ресурсов и проверка совместимости runtime database.

## Операционные ограничения

- Только polling; ingress/webhook endpoint не создаётся.
- Нет встроенного HTTP health endpoint или metrics exporter у generated bot.
- Custom handlers выполняются внутри process без sandbox; доверяйте project code и его dependencies.
- Только interval schedules. Для cron-like запуска пока используйте внешнюю систему, которая вызывает отдельную безопасную операцию, либо дождитесь полноценного schema/runtime trigger; не записывайте unsupported `cron` в resources.
