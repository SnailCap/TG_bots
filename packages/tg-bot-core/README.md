# tg-bot-core v2

`tg-bot-core` — runtime для Telegram-ботов с явной конфигурацией и SQLite.
Проект бота состоит из Python-кода, который описывает логику, и ресурсов,
которые описывают интерфейс. Studio редактирует только ресурсы; бот запускается
без Studio.

## Установка и запуск

Для разработки этого репозитория:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\packages\tg-bot-core[dev]"
```

В самостоятельном проекте бота зависимость фиксируется на Git tag релиза:

```toml
dependencies = [
  "tg-bot-core @ git+https://github.com/SnailCap/TG_bots.git@core-v2.0.0#subdirectory=packages/tg-bot-core"
]
```

Задайте `BOT_TOKEN` в окружении и запустите пакет бота:

```powershell
$env:BOT_TOKEN = "<telegram-token>"
python -m my_bot
```

## Структура проекта

```text
my-bot/
  src/my_bot/
    __main__.py
    flows.py
  resources/
    bot.json
    views/home.json
    templates/home.txt
  data/runtime.sqlite3
```

`resources/bot.json` задаёт корневой view и flow, запускаемый по `/start`:

```json
{
  "schema_version": 2,
  "entry_view": "home",
  "start_flow": "onboarding"
}
```

View — это замена прежней `Page`. Текст может быть inline или находиться в
шаблоне, но не в обоих местах одновременно:

```json
{
  "schema_version": 2,
  "id": "home",
  "text": { "template": "home.txt" },
  "keyboard": [[
    { "text": "Начать", "action": { "type": "flow.start", "target": "onboarding" } }
  ]]
}
```

Разрешённые действия клавиатуры:

- `navigate` с `target` — показать другой view;
- `flow.start` с `target` — начать flow;
- `flow.cancel` — отменить текущий flow;
- `flow.event` с `target` — передать callback активному state handler.

Авторы ресурсов не формируют `callback_data`: core кодирует его сам и
проверяет 64-байтный лимит Telegram.

## Логика: flows и states

Прежние `Process` и `Step` заменены явным `FlowDefinition`. Каждый state —
обычная async-функция на входе (`on_enter`), сообщении (`on_message`) или
callback (`on_callback`). Она получает `FlowContext` и событие, затем
возвращает `Transition`.

```python
# src/my_bot/flows.py
from tg_bot_core import FlowDefinition, FlowState, Transition


async def ask_name(ctx, event):
    return Transition.render("ask_name")


async def save_name(ctx, event):
    ctx.set("name", event.text)
    return Transition.finish(view="done")


onboarding = FlowDefinition(
    id="onboarding",
    initial_state="name",
    states={
        "name": FlowState("name", on_enter=ask_name, on_message=save_name),
    },
)
```

Основные transitions:

- `Transition.goto("state", view="view")` — перейти в state; его `on_enter`
  будет вызван автоматически;
- `Transition.render("view")` — сохранить session и показать view;
- `Transition.send("text")` — отправить отдельное сообщение;
- `Transition.finish(view="view")`, `cancel()` и `fail("message")` — завершить
  flow;
- `Transition.enqueue("task", payload={...})` — после сохранения session
  поставить durable job.

Переменные `ctx.set(...)` сохраняются в SQLite вместе с текущими flow/state.
После рестарта бот продолжит активный flow. `/start` по умолчанию сбрасывает
session; для продолжения используйте `StartPolicy.RESUME`.

## Сборка приложения и сервисы

`BotModule` — единственное место регистрации extension points. Здесь нет
decorators, импорт-сканирования или глобальных registry.

```python
# src/my_bot/__main__.py
from pathlib import Path

from tg_bot_core import BotApp, BotConfig, BotModule, ServiceProvider
from my_bot.flows import onboarding


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    module = BotModule(
        flows=[onboarding],
        services=[ServiceProvider("greeting", lambda _container: "Hello")],
    )
    BotApp(
        config=BotConfig.from_env(
            bot_id="my-bot",
            resource_root=root / "resources",
            database_path=root / "data" / "runtime.sqlite3",
        ),
        module=module,
    ).run()


if __name__ == "__main__":
    main()
```

В state handler сервисы доступны через `ctx.services` или `ctx.services["greeting"]`.
Фабрика `ServiceProvider` получает только уже построенный `Container`, поэтому
порядок зависимостей остаётся явным.

## Background jobs и schedules

Задача — async-функция `(TaskContext, payload)`. Очередь хранит jobs в SQLite,
атомарно claim'ит их, продлевает lease при долгом выполнении и повторяет ошибки
с bounded exponential backoff.

```python
from tg_bot_core import BotModule, ScheduleSpec


async def send_digest(ctx, payload):
    print(f"digest for {payload['chat_id']}")


module = BotModule(
    flows=[onboarding],
    task_handlers={"send_digest": send_digest},
    schedules=[ScheduleSpec("daily-digest", "send_digest", interval_seconds=86_400, payload={"chat_id": 123})],
)
```

Для одноразовой работы вызовите из state handler
`Transition.enqueue("send_digest", payload={"chat_id": 123})`. Runtime сам
запускает scheduler и workers; при остановке он перестаёт брать новые jobs и
ждёт уже запущенные.

## Что изменилось относительно legacy core

| Legacy | v2 |
| --- | --- |
| `Page` | JSON `ViewDefinition` в `resources/views/` |
| registry buttons | inline actions в keyboard view |
| `Process` / `Step` | `FlowDefinition` / `FlowState` |
| `ProcessCoordinator`, effects | `Transition` из async handler |
| `AppPlugin`, builder, discovery | явный `BotApp` + `BotModule` |
| PTB `user_data` | SQLite `flow_sessions` |
| background registry | `task_handlers` и `ScheduleSpec` |

Legacy API намеренно удалён: существующие проекты нужно переписать на v2, а не
подключать compatibility layer.
