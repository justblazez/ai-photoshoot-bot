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


def answer_callback_query(callback_query_id: str, text: str = ""):
    payload = {
        "callback_query_id": callback_query_id,
        "text": text
    }
    telegram_api("answerCallbackQuery", payload)


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

    # Обычные сообщения
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/start":
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

            print("PHOTO FILE ID:", file_id)

            # 1. Получаем путь к файлу
            file_info_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
            file_info_response = requests.get(file_info_url, timeout=20)
            file_info = file_info_response.json()

            print("FILE INFO:", file_info)

            if not file_info.get("ok"):
                send_message(chat_id, "Could not get file info 😢")
                return {"ok": True}

            file_path = file_info["result"]["file_path"]

            # 2. Формируем URL файла
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            print("FILE URL:", file_url)

            # 3. Скачиваем фото
            photo_response = requests.get(file_url, timeout=30)

            if photo_response.status_code != 200:
                send_message(chat_id, "Could not download photo 😢")
                return {"ok": True}

            os.makedirs("downloads", exist_ok=True)
            file_name = f"downloads/user_{chat_id}.jpg"

            with open(file_name, "wb") as f:
                f.write(photo_response.content)

            print("PHOTO SAVED:", file_name)
            print("SELECTED TEMPLATE:", selected_template_key)

            send_message(
                chat_id,
                f"Photo received & saved ✅\nStyle: {selected_template_name}\n\nNext: AI generation 🔥"
            )

        else:
            send_message(
                chat_id,
                "Send /start to begin ✨"
            )

    # Нажатия на inline-кнопки
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
