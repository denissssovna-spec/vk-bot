from flask import Flask, request, jsonify
import requests
import json
import os
import logging

app = Flask(__name__)

# Настройки из переменных окружения
TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

print("VK_TOKEN:", TOKEN)
print("CONFIRMATION:", CONFIRMATION_TOKEN)

# Простое хранилище (сбрасывается при перезапуске)
users_greeted = set()

logging.basicConfig(level=logging.INFO)

def send_message(user_id, text, keyboard=None):
    """Отправка сообщения с обработкой ошибок"""
    data = {
        "user_id": user_id,
        "message": text,
        "random_id": 0,
        "access_token": TOKEN,
        "v": "5.199"
    }
    if keyboard:
        data["keyboard"] = json.dumps(keyboard)

    try:
        response = requests.post("https://api.vk.com/method/messages.send", data=data, timeout=10)
        result = response.json()
        if "error" in result:
            logging.error(f"VK API Error: {result['error']}")
        else:
            logging.info(f"Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")

def get_main_keyboard():
    """Основная клавиатура"""
    return {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "💰 Узнать цену"}, "color": "primary"},
                {"action": {"type": "text", "label": "📦 Наличие"}, "color": "secondary"}
            ]
        ]
    }

@app.route("/", methods=["POST"])
def callback():
    data = request.json

    # Подтверждение сервера
    if data.get("type") == "confirmation":
        return CONFIRMATION_TOKEN

    if data.get("type") == "message_new":
        message = data["object"]["message"]
        user_id = message["from_id"]
        text = message.get("text", "").lower()

        # Приветствие новым пользователям
        if user_id not in users_greeted:
            send_message(
                user_id,
                "Добрый день! 👋\nПросто напишите, что вас интересует, и мы сразу приступим к расчету 😊",
                keyboard=get_main_keyboard()
            )
            users_greeted.add(user_id)
            return "ok"

        # Ответы
