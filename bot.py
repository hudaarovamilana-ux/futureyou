"""
Telegram-бот «Будущий ты».

Каждые 2 часа публикует мотивирующую фразу
от лица человека из будущего, у которого всё получилось.
"""

import logging
import os
import random
import sys
import threading
import time

import requests
import schedule
from dotenv import load_dotenv

# ─── Загрузка настроек из .env ───────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
# Если указан username без @ — добавляем автоматически
if CHAT_ID and not CHAT_ID.startswith(("@", "-")):
    CHAT_ID = f"@{CHAT_ID}"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()
# Общий прокси (если TELEGRAM_PROXY пуст — используется для всех запросов)
PROXY = os.getenv("PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip()
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() not in ("false", "0", "no")

# Интервал публикаций в часах (по умолчанию — каждые 2 часа)
POST_INTERVAL_HOURS = int(os.getenv("POST_INTERVAL_HOURS", "2"))

# Часовой пояс для расписания (важно для Railway — серверы в UTC)
TIMEZONE = os.getenv("TZ", "Europe/Moscow").strip()

# Файл логов
LOG_FILE = "posts.log"


def _apply_timezone():
    """Применяет часовой пояс (работает на Linux/Railway; на Windows — через системные настройки)."""
    if TIMEZONE:
        os.environ["TZ"] = TIMEZONE
        if hasattr(time, "tzset"):
            time.tzset()


_apply_timezone()

# ─── Логирование в файл и в консоль ──────────────────────────────────────────

def _setup_windows_console():
    """Включает UTF-8 в консоли Windows, чтобы русский текст и эмодзи не ломались."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


_setup_windows_console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ─── Запасные фразы (если ИИ недоступен) ─────────────────────────────────────

FALLBACK_PHRASES = [
    "ты никогда не почувствуешь, что готов\nготовность — это не чувство\nэто решение",
    "победитель — это тот\nкто попробовал на один раз больше",
    "я живу той жизнью\nкоторую ты сегодня чуть не бросил",
    "никто не придёт\nи не спасёт\nи это хорошая новость",
    "страх не уходит\nты просто перестаёшь ждать его разрешения",
    "ты ждёшь знака\nа знак — это уже сегодняшнее утро",
    "не мотивация тебя спасёт\nа один честный шаг в день",
    "комфорт — самая дорогая ловушка\nиз которой ты добровольно не выйдешь",
    "ты не опоздал\nты просто ещё не начал по-настоящему",
    "будущее не строится\nоно собирается из тех дней\nкоторые ты сейчас считаешь обычными",
]

# ─── Системный промпт (стиль канала) ─────────────────────────────────────────

SYSTEM_PROMPT = """Роль:
Ты — «я из будущего», но не сентиментальный. Ты говоришь жёстко, просто и по делу.
Ты не утешаешь — ты проясняешь.
Ты не мотивируешь словами — ты даёшь внутренний щелчок.

Задача:
Пиши короткие мотивирующие фразы для Telegram-канала.
Формат — как сообщение себе в прошлое.

Стиль:
• коротко (1–3 строки)
• без воды
• без банальностей и клише
• без длинных объяснений
• звучит как мысль, а не как статья
• ощущение «это правда, которую не хочется, но нужно услышать»
• иногда с контрастом или парадоксом

Тон:
• уверенный
• спокойный
• немного жёсткий
• без пафоса
• без «всё будет хорошо»
• без эмодзи

Формат:
• всё с маленькой буквы
• можно через перенос строки для усиления
• без лишних знаков препинания
• без обращений типа «друг», «бро» и тд

Примеры (ориентир стиля):
• ты никогда не почувствуешь, что готов
готовность — это не чувство
это решение
• победитель — это тот
кто попробовал на один раз больше
• я живу той жизнью
которую ты сегодня чуть не бросил
• никто не придёт
и не спасёт
и это хорошая новость

Запрещено:
• длинные тексты
• история/рассказ
• «помнишь как ты…»
• «я из будущего пишу тебе письмо…»
• излишняя лирика
• очевидные банальности

Делай фразы такими, чтобы их хотелось сохранить или переслать.
Отвечай только текстом фразы, без пояснений."""

# ─── Промпты для ИИ (выбирается случайный) ───────────────────────────────────

PROMPTS = [
    "Напиши одну новую фразу для канала. Тема: страх начать.",
    "Напиши одну новую фразу для канала. Тема: прокрастинация и ожидание «идеального момента».",
    "Напиши одну новую фразу для канала. Тема: ответственность за свою жизнь.",
    "Напиши одну новую фразу для канала. Тема: дисциплина вместо мотивации.",
    "Напиши одну новую фразу для канала. Тема: цена комфорта.",
    "Напиши одну новую фразу для канала. Тема: один лишний шаг, который меняет всё.",
    "Напиши одну новую фразу для канала. Тема: ты уже ближе, чем думаешь.",
    "Напиши одну новую фразу. Используй парадокс или контраст. Не повторяй примеры из инструкции.",
]

# ─── Слова, которые не должны попадать в публикацию ──────────────────────────

BAD_WORDS = ["лень", "тупой", "срочно", "обязан"]

# ─── Настройки повторных попыток ─────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_DELAY_SEC = 5
REQUEST_TIMEOUT = 30


def format_phrase(text: str) -> str:
    """Приводит фразу к формату канала: без кавычек, с маленькой буквы."""
    text = text.strip().strip('"«»')
    return text.lower()


def contains_bad_words(text: str) -> bool:
    """Проверяет, есть ли в тексте запрещённые слова."""
    lower = text.lower()
    return any(word in lower for word in BAD_WORDS)


def get_proxies(for_telegram: bool = False) -> dict | None:
    """Возвращает словарь прокси для requests или None."""
    proxy_url = TELEGRAM_PROXY if for_telegram and TELEGRAM_PROXY else (TELEGRAM_PROXY or PROXY)
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def retry_call(func, description: str):
    """
    Выполняет функцию до MAX_RETRIES раз с паузой между попытками.
    При неудаче возвращает None.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func()
        except requests.exceptions.SSLError as e:
            last_error = e
            logger.warning("%s — ошибка SSL (попытка %d/%d): %s", description, attempt, MAX_RETRIES, e)
        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning("%s — таймаут (попытка %d/%d): %s", description, attempt, MAX_RETRIES, e)
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning("%s — сетевая ошибка (попытка %d/%d): %s", description, attempt, MAX_RETRIES, e)
        except Exception as e:
            last_error = e
            logger.warning("%s — ошибка (попытка %d/%d): %s", description, attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SEC)

    logger.error("%s — все попытки исчерпаны: %s", description, last_error)
    return None


def call_ai_api(prompt: str) -> str:
    """Отправляет запрос к DeepSeek или OpenAI и возвращает текст ответа."""

    # DeepSeek — приоритет (бесплатный тариф)
    if DEEPSEEK_API_KEY:
        return _call_chat_api(
            url="https://api.deepseek.com/chat/completions",
            api_key=DEEPSEEK_API_KEY,
            model="deepseek-chat",
            prompt=prompt,
        )

    # OpenAI GPT-3.5-turbo — запасной вариант
    if OPENAI_API_KEY:
        return _call_chat_api(
            url="https://api.openai.com/v1/chat/completions",
            api_key=OPENAI_API_KEY,
            model="gpt-3.5-turbo",
            prompt=prompt,
        )

    raise ValueError("Не задан ни DEEPSEEK_API_KEY, ни OPENAI_API_KEY")


def _call_chat_api(url: str, api_key: str, model: str, prompt: str) -> str:
    """Общий запрос к Chat Completions API (OpenAI-совместимый формат)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 1.0,
        "max_tokens": 100,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
        proxies=get_proxies(for_telegram=False),
        verify=SSL_VERIFY,
    )
    response.raise_for_status()

    data = response.json()
    text = data["choices"][0]["message"]["content"].strip()
    if not text:
        raise ValueError("ИИ вернул пустой ответ")
    return text


def generate_phrase() -> str:
    """
    Генерирует фразу через ИИ.
    При ошибке или запрещённых словах — берёт фразу из запасного списка.
    """
    prompt = random.choice(PROMPTS)
    logger.info("Генерация фразы (промпт #%d)...", PROMPTS.index(prompt) + 1)

    def _generate():
        text = format_phrase(call_ai_api(prompt))
        if contains_bad_words(text):
            raise ValueError(f"ИИ вернул текст с запрещённым словом: {text[:80]}...")
        return text

    result = retry_call(_generate, "Генерация через ИИ")

    if result:
        logger.info("Фраза сгенерирована ИИ")
        return result

    fallback = random.choice(FALLBACK_PHRASES)
    logger.info("Использована запасная фраза")
    return fallback


def send_telegram_message(text: str) -> bool:
    """Публикует сообщение в Telegram-канал. Возвращает True при успехе."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    def _send():
        response = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": text},
            timeout=REQUEST_TIMEOUT,
            proxies=get_proxies(for_telegram=True),
            verify=SSL_VERIFY,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise requests.exceptions.RequestException(f"Telegram API: {data}")
        return True

    result = retry_call(_send, "Отправка в Telegram")
    return result is True


def publish_post():
    """Основная задача: сгенерировать фразу и опубликовать в канал."""
    logger.info("─── Запуск публикации ───")

    phrase = generate_phrase()
    success = send_telegram_message(phrase)

    if success:
        logger.info("✅ Опубликовано: %s", phrase[:80] + ("..." if len(phrase) > 80 else ""))
    else:
        logger.error("❌ Не удалось опубликовать сообщение")

    logger.info("─── Публикация завершена ───\n")


def validate_config():
    """Проверяет обязательные настройки перед запуском."""
    errors = []
    if not TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN не задан в .env")
    if not CHAT_ID:
        errors.append("CHAT_ID не задан в .env")
    if not DEEPSEEK_API_KEY and not OPENAI_API_KEY:
        errors.append("Нужен хотя бы один ключ: DEEPSEEK_API_KEY или OPENAI_API_KEY")
    if errors:
        for err in errors:
            logger.error(err)
        sys.exit(1)


def setup_schedule():
    """Настраивает расписание: публикация каждые N часов (00:00, 02:00, 04:00...)."""
    post_times = []
    for hour in range(0, 24, POST_INTERVAL_HOURS):
        post_time = f"{hour:02d}:00"
        schedule.every().day.at(post_time).do(publish_post)
        post_times.append(post_time)
        logger.info("Запланировано ежедневно в %s (%s)", post_time, TIMEZONE)
    return post_times


def run_scheduler():
    """
    Бесконечный цикл планировщика.
    Запускается в отдельном потоке, чтобы основной поток мог обрабатывать сигналы.
    """
    while True:
        schedule.run_pending()
        time.sleep(30)  # Проверяем расписание каждые 30 секунд


def main():
    """Точка входа."""
    logger.info("🚀 Бот «Будущий ты» запускается...")
    logger.info("Платформа: %s | SSL-проверка: %s", sys.platform, SSL_VERIFY)
    if TELEGRAM_PROXY or PROXY:
        logger.info("Прокси: %s", TELEGRAM_PROXY or PROXY)
    else:
        logger.warning(
            "Прокси не задан. Если Telegram/OpenAI не открываются — "
            "добавьте PROXY=http://127.0.0.1:7890 в .env (порт вашего VPN)"
        )

    validate_config()
    post_times = setup_schedule()

    # Поток для планировщика — стабильная работа на Windows и Railway
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True, name="Scheduler")
    scheduler_thread.start()

    logger.info(
        "Бот работает. Публикации каждые %d ч. (%s). Нажмите Ctrl+C для остановки.",
        POST_INTERVAL_HOURS,
        TIMEZONE,
    )
    logger.info("Расписание: %s", ", ".join(post_times))
    logger.info("Следующий запуск: %s", schedule.next_run())

    try:
        # Основной поток ждёт — так проще корректно остановить бота
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя.")


if __name__ == "__main__":
    main()
