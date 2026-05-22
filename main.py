from flask import Flask, request
import requests
import json
import os
import logging
import random

app = Flask(__name__)

# VK данные из Render
TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

users_greeted = set()

logging.basicConfig(level=logging.INFO)

def send_message(user_id, text, keyboard=None):
    data = {
        "user_id": user_id,
        "message": text,
        "random_id": random.randint(1, 10**9),
        "access_token": TOKEN,
        "v": "5.199"
    }

    if keyboard:
        data["keyboard"] = json.dumps(keyboard)

    try:
        requests.post(
            "https://api.vk.com/method/messages.send",
            data=data,
            timeout=10
        )
    except Exception as e:
        print("VK SEND ERROR:", e)

def get_main_keyboard():
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
    try:
        data = request.get_json(force=True)
        print("EVENT:", data)

        # подтверждение сервера VK
        if data.get("type") == "confirmation":
            return CONFIRMATION_TOKEN

        # новые сообщения
        if data.get("type") == "message_new":
            message = data["object"]["message"]
            user_id = message["from_id"]
            text = (message.get("text") or "").lower().strip()

            # первое приветствие
            if user_id not in users_greeted:
                send_message(
                    user_id,
                    "Добрый день! 👋\nНапишите, что вас интересует 😊",
                    keyboard=get_main_keyboard()
                )
                users_greeted.add(user_id)
                return "ok"

            # ключевые слова
            if "цен" in text or "стоим" in text or "сколько" in text:
                send_message(user_id, "Уточняем цену 👀", keyboard=get_main_keyboard())

            elif "налич" in text or "есть" in text:
                send_message(user_id, "Проверяем наличие 📦", keyboard=get_main_keyboard())

            else:
                send_message(user_id, "Напишите подробнее 👌", keyboard=get_main_keyboard())

        return "ok"

    except Exception as e:
        print("ERROR:", e)
        return "ok"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

        # Ответы
