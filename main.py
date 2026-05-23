from flask import Flask, request
import requests
import json
import os
import random
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

# --- СОСТОЯНИЯ ---
users_state = {}
users_last_time = {}
users_interest = {}

# --- GOOGLE SHEETS ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open("Leads Bot").sheet1

def save_lead(user_id, phone):
    try:
        interest = users_interest.get(user_id, "")

        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(user_id),
            phone,
            interest,
            ""
        ])
    except Exception as e:
        print("SHEETS ERROR:", e)

# --- ОТПРАВКА ---
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

# --- КНОПКИ ---
def keyboard_main():
    return {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "💰 Цена"}, "color": "primary"},
                {"action": {"type": "text", "label": "📦 Наличие"}, "color": "secondary"}
            ]
        ]
    }

# --- CALLBACK ---
@app.route("/", methods=["POST"])
def callback():
    try:
        data = request.get_json(force=True)

        if data.get("type") == "confirmation":
            return CONFIRMATION_TOKEN

        if data.get("type") != "message_new":
            return "ok"

        msg = data["object"]["message"]
        user_id = msg["from_id"]
        text = (msg.get("text") or "").lower().strip()

        now = datetime.now()

        # --- игнор 2 недели ---
        if user_id in users_last_time:
            if now - users_last_time[user_id] < timedelta(days=14):
                return "ok"

        state = users_state.get(user_id, "new")

        # --- СТАРТ ---
        if state == "new":
            users_state[user_id] = "choose"
            send_message(
                user_id,
                "Здравствуйте 👋\nЧто вас интересует?",
                keyboard_main()
            )
            return "ok"

        # --- ВЫБОР ---
        if "цен" in text:
            users_state[user_id] = "waiting_product"
            users_interest[user_id] = "Цена"

            send_message(
                user_id,
                "Отлично! Подскажите, какой конкретно товар рассматриваете 👀"
            )
            return "ok"

        if "налич" in text or "есть" in text:
            users_state[user_id] = "waiting_product"
            users_interest[user_id] = "Наличие"

            send_message(
                user_id,
                "Отлично! Подскажите, какой конкретно товар рассматриваете 👀"
            )
            return "ok"

        # --- ТОВАР ---
        if state == "waiting_product":
            users_state[user_id] = "waiting_phone"
            users_interest[user_id] += f": {text}"

            send_message(
                user_id,
                "Замечательно! Уже вовсю работаем над вашим запросом 👀\n\n"
                "Чтобы мы смогли с вами оперативно связаться — оставьте ваш номер телефона 📞"
            )
            return "ok"

        # --- ТЕЛЕФОН ---
        if state == "waiting_phone":
            save_lead(user_id, text)

            send_message(
                user_id,
                "Спасибо! В ближайшее время менеджер свяжется с вами 😊"
            )

            users_state[user_id] = "done"
            users_last_time[user_id] = now
            return "ok"

        return "ok"

    except Exception as e:
        print("ERROR:", e)
        return "ok"

# --- RUN ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
