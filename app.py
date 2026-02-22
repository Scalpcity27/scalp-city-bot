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

    print("TELEGRAM STATUS:", r.status_code)
    print("TELEGRAM BODY:", r.text)

    r.raise_for_status()


@app.get("/")
def health():
    return "OK", 200


@app.post("/tv")
def tradingview_webhook():
    raw = request.get_data(as_text=True) or ""

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}

    # Secret check
    if TV_SECRET:
        incoming = data.get("secret", "")
        if incoming != TV_SECRET:
            print("SECRET MISMATCH")
            abort(401)

    event = data.get("event", "ALERT")
    ticker = data.get("ticker", "")
    tf = data.get("tf", "")
    price = data.get("price", "")

    tp = data.get("tp", "")
    sl = data.get("sl", "")

    emoji = {
        "🟢 BUY NOW 🟢": "🟢",
        "🔴 SELL NOW 🔴": "🔴",
        "📈 TREND UP 📈": "📈",
        "📉 TREND DOWN 📉": "📉",
        "🧪 TEST_1M": "🧪",
    }.get(event, "🔔")

    pretty_event = {
        "🟢 BUY NOW 🟢": "BUY NOW",
        "🔴 SELL NOW 🔴": "SELL NOW",
        "📈 TREND UP 📈": "TREND UP",
        "📉 TREND DOWN 📉": "TREND DOWN",
        "🧪 TEST_1M": "TEST",
    }.get(event, event)

    lines = [
        f"{emoji} {pretty_event}",
        f"{ticker} • {tf}",
        f"Price: {price}",
    ]

    # Correct indentation (4 spaces)
    if tp and sl:
        lines.append(f"TP: {tp}")
        lines.append(f"SL: {sl}")
        lines.append("")
        lines.append("⚠️ Please trade carefully when scalping ⚠️")

    msg = "\n".join(lines)

    send_to_group(msg)
    return {"status": "sent"}, 200
