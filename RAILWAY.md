# Деплой на Railway

Пошаговая инструкция: GitHub → Railway → канал работает 24/7.

---

## 1. Подготовка (на компьютере)

Убедитесь, что в проекте **нет** файла `.env` в git (он в `.gitignore`).

```powershell
cd C:\Users\User\Desktop\futureyou
git init
git add .
git status
```

В `git status` не должно быть `.env` и `posts.log`. Если всё ок:

```powershell
git commit -m "Telegram bot Future You for Railway"
```

---

## 2. GitHub

1. Зайдите на [github.com](https://github.com) → **New repository**
2. Имя, например: `futureyou-bot`
3. **Create repository** (без README — он уже есть локально)
4. Выполните команды, которые покажет GitHub:

```powershell
git remote add origin https://github.com/ВАШ_ЛОГИН/futureyou-bot.git
git branch -M main
git push -u origin main
```

---

## 3. Railway

1. [railway.app](https://railway.app) → войти через **GitHub**
2. **New Project** → **Deploy from GitHub repo**
3. Выберите репозиторий `futureyou-bot`
4. Railway сам определит Python и запустит `python bot.py`

---

## 4. Переменные окружения (обязательно!)

В Railway: ваш сервис → **Variables** → **Add Variable**

| Переменная | Значение |
|------------|----------|
| `TELEGRAM_TOKEN` | Токен от @BotFather |
| `CHAT_ID` | `futureyouchanel` или `@futureyouchanel` |
| `DEEPSEEK_API_KEY` | Ваш ключ DeepSeek |
| `TZ` | `Europe/Moscow` |
| `POST_INTERVAL_HOURS` | `2` |

**Не нужны на Railway** (можно не добавлять):

- `PROXY` / `TELEGRAM_PROXY` — серверы Railway не блокируют Telegram
- `OPENAI_API_KEY` — если используете только DeepSeek

После добавления переменных Railway **перезапустит** деплой автоматически.

---

## 5. Проверка

1. Откройте **Deployments** → последний деплой → **View Logs**
2. Должно быть:

```
Бот «Будущий ты» запускается...
Запланировано ежедневно в 00:00 (Europe/Moscow)
Запланировано ежедневно в 02:00 (Europe/Moscow)
...
Следующий запуск: ...
```

3. Дождитесь ближайшего часа по расписанию или проверьте канал.

---

## 6. Стоимость

Railway берёт оплату за использование (~$4–5/мес за постоянно работающий бот).  
Новым аккаунтам дают пробные кредиты.

**Расход DeepSeek:** 12 постов в сутки × ~200 токенов ≈ следите за балансом на [platform.deepseek.com](https://platform.deepseek.com).

---

## 7. Обновление бота

После изменений в коде:

```powershell
git add .
git commit -m "описание изменений"
git push
```

Railway задеплоит новую версию автоматически.

---

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| Бот не стартует | Проверьте Variables — все ключи заданы |
| Посты не в московском времени | Добавьте `TZ=Europe/Moscow` |
| `Chat not found` | Бот — админ канала, `CHAT_ID` верный |
| Деплой падает | Смотрите Logs в Railway |
| Двойные посты | Остановите бота на ноуте (задача FutureYouBot) |

---

## Важно

Запускайте бота **только в одном месте** — либо Railway, либо ноутбук.  
Иначе будут дублирующиеся посты.

Отключите задачу `FutureYouBot` в Планировщике Windows, если переходите на Railway.
