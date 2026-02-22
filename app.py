import os
import json
import requests
from flask import Flask, request, abort

app = Flask(__name__)

# Environment variables (set these in Render → Environment)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")          # usually starts with -100...
TV_SECRET = os.getenv("TV_SECRET", "")   # must match Pine script secret

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_to_group(text: str):
    r = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": GROUP_ID,
            "text": text
        },
        timeout=20,
    )
    r.raise_for_status()


@app.get("/")
def health():
    return "OK", 200


@app.post("/tv")
def tradingview_webhook():

    # TradingView often sends text/plain even when JSON is inside.
    raw_body = request.get_data(as_text=True)

    try:
        data = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        data = {}

    # 🔐 Secret check (NOW checking inside JSON body)
    if TV_SECRET:
        incoming_secret = data.get("secret")
        if incoming_secret != TV_SECRET:
            print("Secret mismatch")
            print("Incoming:", incoming_secret)
            print("Expected:", TV_SECRET)
            abort(401)

    # Format message nicely
    event = data.get("event", "TradingView Alert")
    ticker = data.get("ticker", "")
    tf = data.get("tf", "")
    price = data.get("price", "")

    emoji = {
    "BUY NOW": "🟢",
    "SELL NOW": "🔴",
    "TREND_UP": "📈",
    "TREND_DOWN": "📉",
    "TEST_1M": "🧪",
}.get(event, "🔔")

msg = (
    f"{emoji} {event}\n"
    f"{ticker} • {tf}\n"
    f"Price: {price}"
)

    send_to_group(message)

    return {"status": "sent"}, 200
