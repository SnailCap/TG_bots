# Callback Data Cheatsheet

## Общая структура

```
svc:<namespace>:<segment>[:<segment>...]
st:<action>[:<arg>...]
```

```
svc → инфраструктура фреймворка
st  → действия текущего шага
```

---

# Быстрый выбор callback

| Ситуация                   | Использовать     | Пример                           |
|----------------------------|------------------|----------------------------------|
| Перейти на другую страницу | `svc:nav:`       | `svc:nav:home`                   |
| Вернуться назад            | `svc:nav:`       | `svc:nav:previous`               |
| Запустить процесс          | `svc:prc:start:` | `svc:prc:start:buy_subscription` |
| Следующий шаг              | `svc:prc:cmd:`   | `svc:prc:cmd:next`               |
| Предыдущий шаг             | `svc:prc:cmd:`   | `svc:prc:cmd:prev`               |
| Отмена процесса            | `svc:prc:cmd:`   | `svc:prc:cmd:cancel`             |
| Действие внутри шага       | `st:`            | `st:choose_plan:basic`           |
| Переключение опции шага    | `st:`            | `st:toggle_day:mon`              |

---

# svc:nav — навигация страниц

Используется, когда **нужно перейти между страницами UI**.

```
svc:nav:<target>
```

Примеры:

```
svc:nav:home
svc:nav:profile
svc:nav:settings
svc:nav:previous
svc:nav:current
```

Обрабатывает:

```
UserInputRouter
```

---

# svc:prc:start — запуск процесса

Используется, когда **кнопка запускает wizard / процесс**.

```
svc:prc:start:<process_key>
```

Примеры:

```
svc:prc:start:buy_subscription
svc:prc:start:create_lesson
svc:prc:start:edit_profile
```

Обрабатывает:

```
UserInputRouter
```

---

# svc:prc:cmd — управление процессом

Используется внутри **wizard flow**.

```
svc:prc:cmd:<command>
```

Примеры:

```
svc:prc:cmd:next
svc:prc:cmd:prev
svc:prc:cmd:cancel
svc:prc:cmd:restart
```

Обрабатывает:

```
Process.handle_input()
```

---

# st — действия шага

Используется для **логики конкретного шага**.

Router **не интерпретирует** эти callback.

```
st:<action>
st:<action>:<arg>
st:<action>:<arg1>:<arg2>
```

Примеры:

```
st:choose_plan
st:choose_plan:basic
st:set_language:et
st:toggle_day:mon
st:select_student:42
```

Обрабатывает:

```
текущий Step
```

---

# Типичный flow

Пример сценария покупки подписки:

```
svc:nav:home
svc:prc:start:buy_subscription
st:choose_plan:basic
svc:prc:cmd:next
svc:prc:cmd:confirm
svc:prc:cmd:cancel
```

---

# Правило выбора

### Если кнопка…

| Кнопка делает         | Использовать    |
|-----------------------|-----------------|
| Переход по страницам  | `svc:nav`       |
| Запуск wizard         | `svc:prc:start` |
| Управление wizard     | `svc:prc:cmd`   |
| Выбор пользователя    | `st`            |
| Выбор опции           | `st`            |
| Переключение значения | `st`            |

---

# Нельзя делать

❌

```
back
next
cancel
choose_basic
```

✔

```
svc:nav:previous
svc:prc:cmd:next
st:choose_plan:basic
```

---

# Ментальная модель

Очень полезно запомнить так:

```
svc = framework control
st  = domain action
```

или

```
svc → инфраструктура
st  → логика шага
```
