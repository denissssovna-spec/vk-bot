from flask import Flask, request
import requests
import json
import os
import random

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

print("=== STARTING APP ===")

# -------- ENV --------
VK_TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

print("VK_TOKEN:", bool(VK_TOKEN))
print("CONFIRMATION_TOKEN:", bool(CONFIRMATION_TOKEN))
print("GOOGLE_CREDENTIALS:", bool(GOOGLE_CREDENTIALS))

if not GOOGLE_CREDENTIALS:
    raise Exception("GOOGLE_CREDENTIALS EMPTY")

# -------- GOOGLE SHEETS --------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

try:
    print("👉 Parsing JSON...")

    creds_json = json.loads(GOOGLE_CREDENTIALS)

    print("✅ JSON OK")

    creds = Credentials.from_service_account_info(
        creds_json,
        scopes=SCOPES
    )

    print("✅ Credentials created")

    client = gspread.authorize(creds)

    print("✅ gspread authorized")

    sheet = client.open_by_key(
        "1WhnWRzrgQ1XuXHaoOyrXmIzjAAqoyxgwDjydvr5wsWM"
    ).sheet1

    print("✅ Google Sheets connected")

except Exception as e:
    print("❌ GOOGLE INIT ERROR:", e)
    raise

# -------- APP --------
app = Flask(__name__)

users_state = {}
users_closed = set()
users_interest = {}

# -------- SAVE LEAD --------
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

# -------- SEND --------
def send_message(user_id, text):
    data = {
        "user_id": user_id,
        "message": text,
        "random_id": random.randint(1, 10**9),
        "access_token": VK_TOKEN,
        "v": "5.199"
    }

    try:
        requests.post(
            "https://api.vk.com/method/messages.send",
            data=data,
            timeout=10
        )
    except Exception as e:
        print("VK ERROR:", e)

# -------- WEBHOOK --------
@app.route("/", methods=["POST"])
def callback():
    try:
        data = request.get_json(force=True)

        if data.get("type") == "confirmation":
            return CONFIRMATION_TOKEN or "ok"

        if data.get("type") != "message_new":
            return "ok"

        msg = data["object"]["message"]
        user_id = msg["from_id"]
        text = (msg.get("text") or "").lower().strip()

        if user_id in users_closed:
            return "ok"

        state = users_state.get(user_id, "new")

        # старт
        if state == "new":
            users_state[user_id] = "waiting_phone"
            send_message(user_id, "Оставьте номер телефона 📞")
            return "ok"

        # номер
        if any(ch.isdigit() for ch in text) and len(text) >= 10:
            save_lead(user_id, text)

            send_message(user_id, "Спасибо! Скоро свяжемся 😊")

            users_state[user_id] = "closed"
            users_closed.add(user_id)
            return "ok"

        return "ok"

    except Exception as e:
        print("ERROR:", e)
        return "ok"

# -------- RUN LOCAL --------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
