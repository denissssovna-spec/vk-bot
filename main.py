from flask import Flask, request
import requests
import json
import os
import random

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

# ---------------- ENV ----------------
VK_TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# ---------------- SAFETY CHECK ----------------
if not VK_TOKEN:
print("❌ VK_TOKEN is missing")

if not CONFIRMATION_TOKEN:
print("❌ VK_CONFIRMATION_TOKEN is missing")

if not GOOGLE_CREDENTIALS:
print("❌ GOOGLE_CREDENTIALS is missing")
raise Exception("No GOOGLE_CREDENTIALS in environment")

# ---------------- GOOGLE SHEETS ----------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

try:
creds_json = json.loads(GOOGLE_CREDENTIALS)

creds = Credentials.from_service_account_info(
creds_json,
scopes=SCOPES
)

client = gspread.authorize(creds)

sheet = client.open_by_key(
"1WhnWRzrgQ1XuXHaoOyrXmIzjAAqoyxgwDjydvr5wsWM"
).sheet1

print("✅ Google Sheets connected")

except Exception as e:
print("❌ Google Sheets error:", e)
sheet = None


# ---------------- STATE ----------------
users_state = {}
users_closed = set()
users_interest = {}


# ---------------- SAVE LEAD ----------------
def save_lead(user_id, phone):
if sheet is None:
print("❌ Sheet not available")
return

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


# ---------------- VK SEND ----------------
def send_message(user_id, text, keyboard=None):
data = {
"user_id": user_id,
"message": text,
"random_id": random.randint(1, 10**9),
"access_token": VK_TOKEN,
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


# ---------------- KEYBOARD ----------------
def keyboard_main():
return {
"one_time": False,
"buttons": [
[
{
"action": {"type": "text", "label": "💰 Цена"},
"color": "primary"
},
{
"action": {"type": "text", "label": "📦 Наличие"},
"color": "secondary"
}
]
]
}


# ---------------- WEBHOOK ----------------
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

# START
if state == "new":
users_state[user_id] = "choose"

send_message(
user_id,
"Здравствуйте 👋\nВыберите, что вас интересует:",
keyboard_main()
)
return "ok"

# PRICE
if "цен" in text or "сколько" in text or "стоим" in text:
users_state[user_id] = "waiting_details"
users_interest[user_id] = "Цена"

send_message(user_id, "Уточните товар 👀")
return "ok"

# STOCK
if "налич" in text or "есть" in text:
users_state[user_id] = "waiting_details"
users_interest[user_id] = "Наличие"

send_message(user_id, "Уточните товар 👀")
return "ok"

# DETAILS
if state == "waiting_details":
users_state[user_id] = "waiting_phone"
users_interest[user_id] += f": {text}"

send_message(user_id, "Оставьте номер телефона 📞")
return "ok"

# PHONE
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


# ---------------- RUN (LOCAL ONLY) ----------------
if __name__ == "__main__":
port = int(os.getenv("PORT", 10000))
app.run(host="0.0.0.0", port=port)
