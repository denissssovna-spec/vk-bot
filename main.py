from flask import Flask, request
import requests
import json
import os
import logging
import random

app = Flask(__name__)

TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

logging.basicConfig(level=logging.INFO)

users_greeted = set()
users_stage = {}      # NEW: этап диалога
users_closed = set()   # NEW: закрытые диалоги

# ---------------- SEND ----------------
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

    requests.post("https://api.vk.com/method/messages.send", data=data)

# ---------------- KEYBOARD ----------------
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

# ---------------- CALLBACK ----------------
@app.route("/", methods=["POST"])
def callback():
    try:
        data = request.get_json(force=True)

        if data.get("type") == "confirmation":
            return CONFIRMATION_TOKEN

        if data.get("type") != "message_new":
            return "ok"

        message = data["object"]["message"]
        user_id = message["from_id"]
        text = (message.get("text") or "").lower().strip()

        # ❌ если диалог закрыт — игнорируем
        if user_id in users_closed:
            return "ok"

        # ---------------- ПРИВЕТСТВИЕ ----------------
        if user_id not in users_greeted:
            users_greeted.add(user_id)
            users_stage[user_id] = "start"

            send_message(
                user_id,
                "Здравствуйте 👋\nВыберите, что вас интересует:",
                keyboard=get_main_keyboard()
            )
            return "ok"

        # ---------------- ЦЕНА ----------------
        if "цен" in text or "стоим" in text or "сколько" in text:
            if users_stage.get(user_id) == "price":
                return "ok"  # ❌ защита от спама

            users_stage[user_id] = "price"

            send_message(
                user_id,
                "Уточните, пожалуйста, на какой товар нужна цена 👀\n"
                "После уточнения мы свяжемся с вами.\n\n"
                "Оставьте, пожалуйста, номер телефона 📞"
            )
            return "ok"

        # ---------------- НАЛИЧИЕ ----------------
        if "налич" in text or "есть" in text:
            users_stage[user_id] = "stock"

            send_message(
                user_id,
                "Уточните, пожалуйста, какой товар вас интересует 👀\n"
                "Проверим наличие и свяжемся с вами 📦\n\n"
                "Оставьте, пожалуйста, номер телефона 📞"
            )
            return "ok"

        # ---------------- ТЕЛЕФОН ----------------
        if any(ch.isdigit() for ch in text) and len(text) >= 10:
            send_message(
                user_id,
                "В ближайшее время свяжемся с вами 😊"
            )

            users_closed.add(user_id)
            users_stage[user_id] = "closed"
            return "ok"

        # ---------------- ПОСЛЕ СЦЕНАРИЯ ----------------
        send_message(
            user_id,
            "Напишите, пожалуйста, что вас интересует 👇",
            keyboard=get_main_keyboard()
        )

        return "ok"

    except Exception as e:
        print("ERROR:", e)
        return "ok"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

        # Ответы
