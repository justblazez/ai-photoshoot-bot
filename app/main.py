import requests
from fastapi import FastAPI, Request
import os

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN")

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=data)

@app.get("/")
def root():
    return {"status": "bot is running"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("TELEGRAM UPDATE:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "✨ Turn your selfie into an aesthetic photoshoot\n\nSend me a photo 💖")

    return {"ok": True}
