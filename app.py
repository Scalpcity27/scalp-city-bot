import os
import json
import requests
from flask import Flask, request, abort

app = Flask(__name__)

# Render environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROUP_ID = os.getenv("GROUP_ID", "")
TV_SECRET = os.getenv("TV_SECRET", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_to_group(text: str) -> None:
    if not BOT_TOKEN or not GROUP_ID:
        print("ERROR: Missing BOT_TOKEN or GROUP_ID environment variable")
        return

    r = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": GROUP_ID, "text": text},
        timeout=20,
    )

    # Helpful debug output in Render logs
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

    # Fields from Pine payload
    event = data.get("event", "ALERT")
    ticker = data.get("ticker", "")
    tf = data.get("tf", "")
    price = data.get("price", "")

    # Optional TP/SL fields (present only for BUY/SELL alerts in your Pine script)
    tp = data.get("tp", "")
    sl = data.get("sl", "")

    # Emoji mapping (your Pine script sends emojis inside event text)
    emoji = {
        "🟢 BUY NOW 🟢": "🟢",
        "🔴 SELL NOW 🔴": "🔴",
        "📈 TREND UP 📈": "📈",
        "📉 TREND DOWN 📉": "📉",
        "🧪 TEST_1M": "🧪",
    }.get(event, "🔔")

    # Prettier event text
    pretty_event = {
        "🟢 BUY NOW 🟢": "BUY NOW",
        "🔴 SELL NOW 🔴": "SELL NOW",
        "📈 TREND UP 📈": "TREND UP",
        "📉 TREND DOWN 📉": "TREND DOWN",
        "🧪 TEST_1M": "TEST",
    }.get(event, event)

    # Build Telegram message
    lines = [
        f"{emoji} {pretty_event}",
        f"{ticker} • {tf}",
        f"Price: {price}",
    ]

    # Only show TP/SL if provided
    if tp and sl:
        lines.append(f"TP: {tp}")
        lines.append(f"SL: {sl}")

    msg = "\n".join(lines)

    send_to_group(msg)
    return {"status": "sent"}, 200
