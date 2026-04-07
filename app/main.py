import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FAL_KEY = os.getenv("FAL_KEY")

# Временное хранилище в памяти
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
        response = requests.post(url, json=payload, timeout=30)
        print(f"TELEGRAM API {method} STATUS:", response.status_code)
        print(f"TELEGRAM API {method} RESPONSE:", response.text)
        return response
    except Exception as e:
        print(f"TELEGRAM API {method} ERROR:", str(e))
        return None


def send_message(chat_id: int, text: str, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    telegram_api("sendMessage", payload)


def send_photo(chat_id: int, photo_url: str, caption: str = ""):
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption
    }
    telegram_api("sendPhoto", payload)


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


def get_template_prompt(template_key: str) -> str:
    prompts = {
        "soft": (
            "Turn this into a soft aesthetic portrait photoshoot. "
            "Keep the same face, identity, facial features, skin tone, age, and overall likeness. "
            "Use pastel tones, clean beauty look, feminine styling, dreamy atmosphere, realistic photo."
        ),
        "flowers": (
            "Turn this into a romantic flower photoshoot. "
            "Keep the same face, identity, facial features, skin tone, age, and overall likeness. "
            "Add elegant flowers, soft lighting, feminine beauty, realistic editorial portrait."
        ),
        "studio": (
            "Turn this into a professional studio photoshoot. "
            "Keep the same face, identity, facial features, skin tone, age, and overall likeness. "
            "Use studio lighting, clean background, polished beauty look, realistic fashion portrait."
        ),
        "golden": (
            "Turn this into a golden hour outdoor photoshoot. "
            "Keep the same face, identity, facial features, skin tone, age, and overall likeness. "
            "Warm sunlight, glowing skin, cinematic but realistic portrait."
        ),
    }
    return prompts.get(
        template_key,
        "Edit this portrait while keeping the same face, identity, and overall likeness. Realistic result."
    )


def generate_with_flux(local_file_path: str, template_key: str):
    if not FAL_KEY:
        print("ERROR: FAL_KEY is missing")
        return None

    prompt = get_template_prompt(template_key)
    print("FLUX PROMPT:", prompt)

    try:
        # 1) Загружаем локальный файл в fal storage
        target_path = f"telegram/user_upload_{os.path.basename(local_file_path)}"
        upload_url = f"https://api.fal.ai/v1/serverless/files/file/local/{target_path}"

        headers = {
            "Authorization": f"Key {FAL_KEY}"
        }

        with open(local_file_path, "rb") as f:
            files = {
                "file_upload": f
            }
            upload_response = requests.post(
                upload_url,
                headers=headers,
                files=files,
                timeout=120
            )

        print("UPLOAD STATUS:", upload_response.status_code)
        print("UPLOAD TEXT:", upload_response.text)

        if upload_response.status_code != 200:
            return None

        upload_json = upload_response.json()

        uploaded_path = upload_json.get("file_path") or upload_json.get("path") or target_path
        image_url = f"https://api.fal.ai/v1/serverless/files/file/{uploaded_path}"

        print("FAL IMAGE URL:", image_url)

        # 2) Вызываем модель
        run_url = "https://fal.run/fal-ai/flux-kontext/dev"
        payload = {
            "prompt": prompt,
            "image_url": image_url
        }

        model_headers = {
            "Authorization": f"Key {FAL_KEY}",
            "Content-Type": "application/json"
        }

        model_response = requests.post(
            run_url,
            headers=model_headers,
            json=payload,
            timeout=300
        )

        print("MODEL STATUS:", model_response.status_code)
        print("MODEL TEXT:", model_response.text)

        if model_response.status_code != 200:
            return None

        result = model_response.json()
        images = result.get("images", [])

        if not images:
            print("NO IMAGES IN RESPONSE")
            return None

        return images[0]["url"]

    except Exception as e:
        print("FAL ERROR:", str(e))
        return None


@app.get("/")
def root():
    return {
        "status": "bot is running",
        "bot_token_exists": bool(BOT_TOKEN),
        "fal_key_exists": bool(FAL_KEY)
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

            # Получаем путь к файлу в Telegram
            file_info_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
            file_info_response = requests.get(file_info_url, timeout=20)
            file_info = file_info_response.json()

            print("FILE INFO:", file_info)

            if not file_info.get("ok"):
                send_message(chat_id, "Could not get file info 😢")
                return {"ok": True}

            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

            print("FILE URL:", file_url)

            # Скачиваем фото
            photo_response = requests.get(file_url, timeout=30)

            if photo_response.status_code != 200:
                send_message(chat_id, "Could not download photo 😢")
                return {"ok": True}

            os.makedirs("downloads", exist_ok=True)
            local_file_path = f"downloads/user_{chat_id}.jpg"

            with open(local_file_path, "wb") as f:
                f.write(photo_response.content)

            print("PHOTO SAVED:", local_file_path)
            print("SELECTED TEMPLATE:", selected_template_key)

            send_message(chat_id, f"Creating your {selected_template_name} photoshoot... ✨")

            result_image_url = generate_with_flux(local_file_path, selected_template_key)

            if not result_image_url:
                send_message(chat_id, "Generation failed 😢 Try again in a minute.")
                return {"ok": True}

            send_photo(
                chat_id,
                result_image_url,
                caption=f"Here’s your {selected_template_name} result 💖"
            )

        else:
            send_message(chat_id, "Send /start to begin ✨")

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
