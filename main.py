from flask import Flask, request
import requests
import json
import os
import random
from datetime import datetime, timedelta

app = Flask(__name__)

VK_TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

# -------- GOOGLE (через ENV) --------
sheet = None

try:
    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = os.getenv("GOOGLE_CREDENTIALS")

    if creds_json:
        creds_dict = json.loads(creds_json)

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        client = gspread.authorize(creds)

        sheet = client.open_by_key(
            "1WhnWRzrgQ1XuXHaoOyrXmIzjAAqoyxgwDjydvr5wsWM"
        ).sheet1

        print("✅ GOOGLE OK")
    else:
        print("⚠️ GOOGLE_CREDENTIALS NOT FOUND")

except Exception as e:
    print("❌ GOOGLE ERROR:", e)
    sheet = None

# -------- STATE --------
users_state = {}
users_interest = {}

# -------- ПРОВЕРКА 14 ДНЕЙ --------
def is_user_recent(user_id):
    if sheet is None:
        return False

    try:
        records = sheet.get_all_values()

        for row in reversed(records[1:]):
            if len(row) < 2:
                continue

            if row[1] == str(user_id):
                last_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M")

                if datetime.now() - last_time < timedelta(days=14):
                    return True
                return False

    except Exception as e:
        print("CHECK ERROR:", e)

    return False

# -------- SAVE --------
def save_lead(user_id, phone):
    if sheet is None:
        print("⚠️ sheet not ready")
        return

    interest = users_interest.get(user_id, "")

    try:
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(user_id),
            interest,
            phone,
            "new"
        ])
    except Exception as e:
        print("SHEETS ERROR:", e)

# -------- SEND --------
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
            data=data
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
            return CONFIRMATION_TOKEN or "ok"

        if data.get("type") != "message_new":
            return "ok"

        msg = data["object"]["message"]
        user_id = msg["from_id"]
        text = (msg.get("text") or "").lower().strip()

        # ---- игнор 14 дней ----
        if is_user_recent(user_id):
            return "ok"

        state = users_state.get(user_id, "new")

        # ---- старт ----
        if state == "new":
            users_state[user_id] = "choose"

            send_message(
                user_id,
                "Здравствуйте 👋\nЧто вас интересует: узнать про цену или наличие товара?",
                keyboard_main()
            )
            return "ok"

        # ---- выбор ----
        if state == "choose":
            if "цен" in text:
                users_state[user_id] = "waiting_details"
                users_interest[user_id] = "Цена"

                send_message(user_id, "Отлично! Какой конкретно товар рассматриваете? 👀")
                return "ok"

            if "налич" in text or "есть" in text:
                users_state[user_id] = "waiting_details"
                users_interest[user_id] = "Наличие"

                send_message(user_id, "Отлично! Какой конкретно товар рассматриваете? 👀")
                return "ok"

            send_message(user_id, "Выберите вариант ниже 👇", keyboard_main())
            return "ok"

        # ---- уточнение ----
        if state == "waiting_details":
            users_state[user_id] = "waiting_phone"
            users_interest[user_id] += f": {text}"

            send_message(
                user_id,
                "Замечательно! Уже вовсю работаем над вашим запросом 👍\n\n"
                "Чтобы мы смогли оперативно связаться - оставьте ваш номер телефона 📞"
            )
            return "ok"

        # ---- номер ----
        if state == "waiting_phone":
            save_lead(user_id, text)

            send_message(
                user_id,
                "Спасибо! В ближайшее время менеджер с вами свяжется 😊"
            )

            users_state[user_id] = "done"
            return "ok"

        return "ok"

    except Exception as e:
        print("❌ CALLBACK ERROR:", e)
        return "ok"

# -------- RUN --------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
