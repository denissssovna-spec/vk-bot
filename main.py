from flask import Flask, request
import requests
import json
import os
import random

from datetime import datetime

app = Flask(__name__)

print("=== STARTING APP ===")

# -------- ENV --------
VK_TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

print("VK_TOKEN:", bool(VK_TOKEN))
print("CONFIRMATION_TOKEN:", bool(CONFIRMATION_TOKEN))
print("GOOGLE_CREDENTIALS:", bool(GOOGLE_CREDENTIALS))

# -------- GOOGLE SAFE INIT --------
sheet = None

try:
    if not GOOGLE_CREDENTIALS:
        raise Exception("GOOGLE_CREDENTIALS EMPTY")

    import gspread
    from google.oauth2.service_account import Credentials

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    print("👉 Parsing JSON...")
    creds_json = json.loads(GOOGLE_CREDENTIALS)

    print("👉 Creating credentials...")
    creds = Credentials.from_service_account_info(
        creds_json,
        scopes=SCOPES
    )

    print("👉 Authorizing gspread...")
    client = gspread.authorize(creds)

    print("👉 Opening sheet...")
    sheet = client.open_by_key(
        "1WhnWRzrgQ1XuXHaoOyrXmIzjAAqoyxgwDjydvr5wsWM"
    ).sheet1

    print("✅ GOOGLE OK")

except Exception as e:
    print("❌ GOOGLE ERROR:", e)

# -------- STATE --------
users_state = {}
users_closed = set()

# -------- SAVE --------
def save_lead(user_id, phone):
    if sheet is None:
        print("⚠️ Sheet not working, skip save")
        return

    try:
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(user_id),
            phone
        ])
    except Exception as e:
        print("SHEETS ERROR:", e)

# -------- SEND --------
def send_message(user_id, text):
    try:
        requests.post(
            "https://api.vk.com/method/messages.send",
            data={
                "user_id": user_id,
                "message": text,
                "random_id": random.randint(1, 10**9),
                "access_token": VK_TOKEN,
                "v": "5.199"
            },
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
        text = (msg.get("text") or "").lower()

        if user_id in users_closed:
            return "ok"

        state = users_state.get(user_id, "new")

        if state == "new":
            users_state[user_id] = "phone"
            send_message(user_id, "Оставьте номер 📞")
            return "ok"

        if any(c.isdigit() for c in text):
            save_lead(user_id, text)

            send_message(user_id, "Приняли 👍")

            users_closed.add(user_id)
            return "ok"

        return "ok"

    except Exception as e:
        print("ERROR:", e)
        return "ok"
