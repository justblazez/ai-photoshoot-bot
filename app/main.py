from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def root():
    return {"status": "bot is running"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("TELEGRAM UPDATE:", data)
    return {"ok": True}
