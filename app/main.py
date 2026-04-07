import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Временное хранилище в памяти
# Потом заменим на БД
user_state = {}

TEMPLATES = {
    "soft": "Soft Aesthetic",
    "flowers": "Flowers",
    "studio": "Studio Shoot",
    "golden": "Golden Hour",
}

def telegram_api(method: str, payload: dict):
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, json=payload, timeout=20)
        print(f"TELEGRAM API {method} STATUS:", response.status_code)
        print(f"TELEGRAM API {method} RESPONSE:", response.text)
        return response
    except Exception as e:
        print(f"TELEGRAM API {method} ERROR:", str(e))
        return None

def send_message(chat_id: int, text: str, reply_markup: dict | None = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    telegram_api("sendMessage", payload)

def send_template_buttons(chat_id: int):
    keyboard = {
        "inline_keyboard": [
            [{"text": "✨ Soft Aesthetic", "callback_data": "tpl_soft"}],
            [{"text": "🌸 Flowers", "callback_data": "tpl_flowers"}],
            [{"text": "📸 Studio Shoot", "callback_data": "tpl_studio"}],
            [{"text": "🌅 Golden Hour", "callback_data": "tpl_golden"}],
        ]
    }

    send_message(
        chat_id,
        "Choose your photoshoot style 💖",
        reply_markup=keyboard
    )

def answer_callback_query(callback_query_id: str, text: str = ""):
    payload = {
        "callback_query_id": callback_query_id,
        "text": text
    }
    telegram_api("answerCallbackQuery", payload)

@app.get("/")
def root():
    return {
        "status": "bot is running",
        "bot_token_exists": bool(BOT_TOKEN)
    }

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("TELEGRAM UPDATE:", data)

    # 1) Обработка обычных сообщений
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # Команда /start
        if text == "/start":
            # Инициализируем пользователя
            if chat_id not in user_state:
                user_state[chat_id] = {
                    "template": None,
                    "free_credits": 3
                }

            send_message(
                chat_id,
                "✨ Turn your selfie into an aesthetic photoshoot\n\nChoose a style below:"
            )
            send_template_buttons(chat_id)

        # Если пришло фото
        elif "photo" in message:
            state = user_state.get(chat_id)

            if not state or not state.get("template"):
                send_message(
                    chat_id,
                    "Please choose a style first 💖\n\nType /start"
                )
                return {"ok": True}

            photos = message["photo"]
            largest_photo = photos[-1]
            file_id = largest_photo["file_id"]

            selected_template_key = state["template"]
            selected_template_name = TEMPLATES.get(selected_template_key, selected_template_key)

            # Пока просто подтверждаем приём фото
            send_message(
                chat_id,
                f"Photo received ✅\nSelected style: {selected_template_name}\n\nNext: we’ll connect AI generation."
            )

            print("PHOTO FILE ID:", file_id)
            print("SELECTED TEMPLATE:", selected_template_key)

        else:
            send_message(
                chat_id,
                "Send /start to begin ✨"
            )

    # 2) Обработка нажатий на inline-кнопки
    elif "callback_query" in data:
        callback = data["callback_query"]
        callback_id = callback["id"]
        chat_id = callback["message"]["chat"]["id"]
        callback_data = callback.get("data", "")

        print("CALLBACK DATA:", callback_data)

        if chat_id not in user_state:
            user_state[chat_id] = {
                "template": None,
                "free_credits": 3
            }

        if callback_data.startswith("tpl_"):
            template_key = callback_data.replace("tpl_", "")
            if template_key in TEMPLATES:
                user_state[chat_id]["template"] = template_key

                answer_callback_query(callback_id, "Style selected ✨")
                send_message(
                    chat_id,
                    f"Selected style: {TEMPLATES[template_key]}\n\nNow send me your photo 💖"
                )

    return {"ok": True}
