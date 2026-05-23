from flask import Flask, request
import requests
import json
import os
import random

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

users_state = {}
users_closed = set()
users_interest = {}

# -------- GOOGLE SHEETS --------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES
)

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
            ""  # менеджер вручную
        ])
    except Exception as e:
        print("SHEETS ERROR:", e)

# -------- SEND --------
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
        print("VK ERROR:", e)

# -------- KEYBOARD --------
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

# -------- CALLBACK --------
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

        # если закрыт — молчим
        if user_id in users_closed:
            return "ok"

        state = users_state.get(user_id, "new")

        # -------- START --------
        if state == "new":
            users_state[user_id] = "choose"

            send_message(
                user_id,
                "Здравствуйте 👋\nВыберите, что вас интересует:",
                keyboard_main()
            )
            return "ok"

        # -------- PRICE --------
        if "цен" in text or "стоим" in text or "сколько" in text:
            users_state[user_id] = "waiting_details"
            users_interest[user_id] = "Цена"

            send_message(
                user_id,
                "Уточните, пожалуйста, какой товар вас интересует 👀\n"
                "Мы уточним и свяжемся с вами 📞"
            )
            return "ok"

        # -------- STOCK --------
        if "налич" in text or "есть" in text:
            users_state[user_id] = "waiting_details"
            users_interest[user_id] = "Наличие"

            send_message(
                user_id,
                "Уточните, пожалуйста, какой товар вас интересует 👀\n"
                "Проверим наличие и свяжемся с вами 📦"
            )
            return "ok"

        # -------- DETAILS --------
        if state == "waiting_details":
            users_state[user_id] = "waiting_phone"

            # добавляем конкретный товар
            users_interest[user_id] += f": {text}"

            send_message(
                user_id,
                "Понял 👍\nСпасибо за уточнение.\n\n"
                "Оставьте, пожалуйста, номер телефона 📞"
            )
            return "ok"

        # -------- PHONE --------
        if any(ch.isdigit() for ch in text) and len(text) >= 10:
            save_lead(user_id, text)

            send_message(
                user_id,
                "В ближайшее время свяжемся с вами 😊"
            )

            users_state[user_id] = "closed"
            users_closed.add(user_id)
            return "ok"

        # -------- SAFE EXIT --------
        return "ok"

    except Exception as e:
        print("ERROR:", e)
        return "ok"

# -------- RUN --------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port) 
