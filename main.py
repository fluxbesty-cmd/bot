#!/usr/bin/env python3
"""
VK Бот с автоворонкой:
1. Выдаёт видео в обмен на email/телефон (сохраняет в Bitrix24).
2. Предлагает записаться на сессию через Calendly.
3. Логирует все действия.

Использует прямые HTTP-запросы к VK API (без внешних библиотек).
"""

import requests
import logging
import re
import time
import json
from config import VK_TOKEN, BITRIX_WEBHOOK, CALENDLY_LINK, LOG_FILE, VK_GROUP_ID

# --- Настройка логирования ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Валидация контактов ---
def is_valid_email(email: str) -> bool:
    """Проверка email на валидность."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone: str) -> bool:
    """Проверка телефона на валидность (простая проверка)."""
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10

# --- Интеграция с Bitrix24 ---
def send_to_bitrix(contact: str, user_id: int, contact_type: str = "EMAIL") -> bool:
    """
    Отправка контакта в Bitrix24.
    contact_type: "EMAIL" или "PHONE"
    """
    try:
        data = {
            "fields": {
                "TITLE": f"Контакт от VK пользователя {user_id}",
                "NAME": f"VK User {user_id}",
                "SOURCE_ID": str(user_id),
                "COMMENTS": f"Пользователь оставил контакт через VK бота"
            },
            "params": {"REGISTER_SONET_EVENT": "Y"}
        }

        if contact_type == "EMAIL":
            data["fields"]["EMAIL"] = [{"VALUE": contact, "VALUE_TYPE": "WORK"}]
        else:
            data["fields"]["PHONE"] = [{"VALUE": contact, "VALUE_TYPE": "WORK"}]

        response = requests.post(
            f"{BITRIX_WEBHOOK}crm.lead.add",
            json=data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            logger.info(f"Bitrix24: Контакт {contact} (тип: {contact_type}) от пользователя {user_id} сохранён.")
            return True
        else:
            logger.error(f"Bitrix24 ошибка: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при отправке в Bitrix24: {e}")
        return False

# --- Клавиатуры (JSON для VK API) ---
def get_start_keyboard() -> str:
    """Клавиатура для стартового сообщения."""
    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "get_video"}),
                        "label": "Получить видео"
                    },
                    "color": "positive"
                }
            ]
        ]
    })

def get_calendly_keyboard() -> str:
    """Клавиатура с кнопкой для записи на сессию."""
    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "register"}),
                        "label": "Записаться на сессию"
                    },
                    "color": "primary"
                }
            ]
        ]
    })

# --- VK API Helper ---
def vk_api_request(method: str, params: dict = None) -> dict:
    """Выполняет запрос к VK API."""
    if params is None:
        params = {}
    params["access_token"] = VK_TOKEN
    params["v"] = "5.131"
    url = f"https://api.vk.com/method/{method}"

    try:
        response = requests.post(url, data=params)
        data = response.json()
        if "error" in data:
            logger.error(f"VK API ошибка: {data['error']}")
            return {"error": data["error"]}
        return data.get("response", {})
    except Exception as e:
        logger.error(f"Ошибка при запросе к VK API: {e}")
        return {"error": str(e)}

def send_message(user_id: int, message: str, keyboard: str = None) -> bool:
    """Отправляет сообщение пользователю в VK."""
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": int(time.time() * 1000) % 1000000000
    }
    if keyboard:
        params["keyboard"] = keyboard

    result = vk_api_request("messages.send", params)
    if "error" in result:
        logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {result['error']}")
        return False
    return True

def get_longpoll_server() -> dict:
    """Получает данные для Long Poll сервера."""
    return vk_api_request("groups.getLongPollServer", {"group_id": VK_GROUP_ID})

def longpoll_listen():
    """Слушает события через Long Poll."""
    server_data = get_longpoll_server()
    if "error" in server_data:
        logger.error(f"Не удалось получить данные Long Poll сервера: {server_data['error']}")
        return

    ts = server_data.get("ts", 0)
    key = server_data["key"]
    server_url = server_data["server"]

    while True:
        try:
            response = requests.get(
                f"{server_url}?act=a_check&key={key}&ts={ts}&wait=25"
            ).json()

            if "failed" in response and response["failed"] == 1:
                ts = response.get("ts", ts)
                continue

            if "updates" in response:
                ts = response["ts"]
                for update in response["updates"]:
                    yield update
        except Exception as e:
            logger.error(f"Ошибка в Long Poll: {e}")
            time.sleep(5)

# --- Основная логика бота ---
def main():
    logger.info("Запуск VK бота...")

    user_states = {}

    logger.info("Бот подключён к VK API. Ожидание сообщений...")

    for update in longpoll_listen():
        try:
            if update[0] == 4:  # Новое сообщение (type 4)
                user_id = update[3]
                text = update[5].strip().lower()

                logger.info(f"Пользователь {user_id} написал: {text}")

                if text in ["начать", "/start", "start"]:
                    send_message(
                        user_id=user_id,
                        message="👋 Привет!\n\nПолучите бесплатное видео с ценными инсайтами. "
                               "Оставьте свой email или телефон, и я отправлю ссылку.",
                        keyboard=get_start_keyboard()
                    )
                    user_states[user_id] = "waiting_for_contact"

                elif text in ["получить видео", "видео"] or user_states.get(user_id) == "waiting_for_contact":
                    if text in ["получить видео", "видео"]:
                        send_message(
                            user_id=user_id,
                            message="📩 Введите свой email или телефон для получения видео:"
                        )
                        user_states[user_id] = "waiting_for_contact"
                    else:
                        if is_valid_email(text):
                            contact_type = "EMAIL"
                            success = send_to_bitrix(text, user_id, contact_type)
                            if success:
                                send_message(
                                    user_id=user_id,
                                    message="✅ Спасибо! Вот ваше видео: [ССЫЛКА_НА_ВИДЕО]\n\n"
                                           "Хотите записаться на бесплатную 15-минутную стратегическую сессию?",
                                    keyboard=get_calendly_keyboard()
                                )
                                user_states[user_id] = "video_sent"
                                logger.info(f"Пользователь {user_id} получил видео (email: {text})")
                            else:
                                send_message(
                                    user_id=user_id,
                                    message="❌ Произошла ошибка при сохранении контакта. Попробуйте ещё раз."
                                )
                        elif is_valid_phone(text):
                            contact_type = "PHONE"
                            success = send_to_bitrix(text, user_id, contact_type)
                            if success:
                                send_message(
                                    user_id=user_id,
                                    message="✅ Спасибо! Вот ваше видео: [ССЫЛКА_НА_ВИДЕО]\n\n"
                                           "Хотите записаться на бесплатную 15-минутную стратегическую сессию?",
                                    keyboard=get_calendly_keyboard()
                                )
                                user_states[user_id] = "video_sent"
                                logger.info(f"Пользователь {user_id} получил видео (телефон: {text})")
                            else:
                                send_message(
                                    user_id=user_id,
                                    message="❌ Произошла ошибка при сохранении контакта. Попробуйте ещё раз."
                                )
                        else:
                            send_message(
                                user_id=user_id,
                                message="⚠️ Некорректный формат. Введите email (например: user@example.com) "
                                       "или телефон (например: +79991234567)."
                            )

                elif text in ["записаться на сессию", "записаться"]:
                    send_message(
                        user_id=user_id,
                        message=f"📅 Выберите удобное время в календаре:\n{CALENDLY_LINK}"
                    )
                    logger.info(f"Пользователь {user_id} перешёл на запись в Calendly")

                else:
                    send_message(
                        user_id=user_id,
                        message="❓ Неизвестная команда. Напишите 'Начать' или нажмите кнопку."
                    )

        except Exception as e:
            logger.error(f"Ошибка при обработке события: {e}")

if __name__ == "__main__":
    main()