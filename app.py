import os
import json
import requests
from flask import Flask, request, abort

app = Flask(__name__)

# Render env vars
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROUP_ID = os.getenv("GROUP_ID", "")
TV_SECRET = os.getenv("TV_SECRET", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_to_group(text: str) -> None:
    if not BOT_TOKEN or not GROUP_ID:
        # Don’t crash deployment; log useful info
        print("Missing BOT_TOKEN or GROUP_ID env var")
        return

    r = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": GROUP_ID, "text": text},
        timeout=20,
    )

    # Log Telegram response for debugging
    print("TELEGRAM STATUS:", r.status_code)
    print("TELEGRAM BODY:", r.text)

    r.raise_for_status()


@app.get("/")
def health():
    return "OK", 200


@app.post("/tv")
def tradingview_webhook():
    # TradingView often sends JSON as text/plain
    raw = request.get_data(as_text=True) or ""

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}

    # Secret check (inside JSON body)
    if TV_SECRET:
        incoming = data.get("secret", "")
        if incoming != TV_SECRET:
            print("SECRET MISMATCH. Incoming:", incoming, "Expected:", TV_SECRET)
            abort(401)

    event = data.get("event", "ALERT")
    ticker = data.get("ticker", "")
    tf = data.get("tf", "")
    price = data.get("price", "")

    # Emoji + pretty names
    emoji = {
        "CCI_EARLY_BUY": "🟢",
        "CCI_EARLY_SELL": "🔴",
        "TREND_UP": "📈",
        "TREND_DOWN": "📉",
        "TEST_1M": "🧪",
    }.get(event, "🔔")

    pretty_event = {
        "CCI_EARLY_BUY": "BUY NOW",
        "CCI_EARLY_SELL": "SELL NOW",
    }.get(event, event)

    msg = (
        f"{emoji} {pretty_event}\n"
        f"{ticker} • {tf}\n"
        f"Price: {price}"
    )

    send_to_group(msg)
    return {"status": "sent"}, 200
