import os
import requests
from flask import Flask, request, abort

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
TV_SECRET = os.getenv("TV_SECRET", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_to_group(text: str):
    r = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": GROUP_ID, "text": text},
        timeout=15,
    )
    r.raise_for_status()


@app.get("/")
def health():
    return "OK", 200


@app.post("/tv")
def tradingview_webhook():
    # Optional secret check:
    secret = request.headers.get("X-TV-SECRET") or request.args.get("secret")
    if TV_SECRET and secret != TV_SECRET:
        abort(401)

    data = request.get_json(silent=True)

    # TradingView can send JSON or plain text. Handle both.
    if isinstance(data, dict):
        # If you send {"message":"..."} from TradingView, it will use that.
        text = data.get("message") or str(data)
    else:
        # If not JSON, read as raw text
        text = request.get_data(as_text=True) or "TradingView alert received"

    send_to_group(text)
    return "sent", 200
