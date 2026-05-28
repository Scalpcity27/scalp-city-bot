import os
import json
import time
import uuid
import requests
from flask import Flask, request, abort

app = Flask(__name__)

# Render environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROUP_ID  = os.getenv("GROUP_ID", "")
TV_SECRET = os.getenv("TV_SECRET", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Signal store ──
# Each entry: {"id": str, "ts": float, "delivered": bool, "signal": dict}
# A signal is sent to the EA exactly once. After the first successful poll
# that returns it, it is marked delivered and never sent again.
# It stays in the store for SIGNAL_TTL seconds so we can still ACK it,
# then it is garbage-collected.
SIGNAL_TTL = 30   # seconds before a signal is fully removed from the store
signal_store = []  # list of signal entry dicts

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

EVENT_MAP = {
    "🟢 BUY GOLD NOW 🟢":  ("🟢", "BUY GOLD NOW", None),
    "🔴 SELL GOLD NOW 🔴": ("🔴", "SELL GOLD NOW", None),
    "📈 TREND UP 📈":      ("📈", "TREND UP",   None),
    "📉 TREND DOWN 📉":    ("📉", "TREND DOWN", None),
    "🔵 TP1 HIT 🔵":       ("🔵", "TP1 HIT",    "Take partial"),
    "🔥 TP2 HIT 🔥":       ("🔥", "TP2 HIT",    "Full take profit"),
    "🚀 TP3 HIT 🚀":       ("🚀", "TP3 HIT",    "Let it run"),
    "❌ SL HIT ❌":         ("❌", "STOP LOSS HIT", None),
    "🧪 TEST SIGNAL — DO NOT FOLLOW 🧪": (
        "🧪", "TEST SIGNAL", "⚠️ THIS IS A TEST — DO NOT FOLLOW ⚠️",
    ),
    "🧪 TEST": ("🧪", "TEST", "⚠️ THIS IS A TEST — DO NOT FOLLOW ⚠️"),
}

ACTION_MAP = {
    "🟢 BUY GOLD NOW 🟢":  "BUY",
    "🔴 SELL GOLD NOW 🔴": "SELL",
    "🔵 TP1 HIT 🔵":       "TP1",
    "🔥 TP2 HIT 🔥":       "TP2",
    "🚀 TP3 HIT 🚀":       "TP3",
    "❌ SL HIT ❌":         "SL",
}

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

    event   = data.get("event", "ALERT")
    ticker  = data.get("ticker", "")
    tf      = data.get("tf", "")
    price   = data.get("price", "")
    tp1     = data.get("tp1", "")
    tp2     = data.get("tp2", "")
    tp3     = data.get("tp3", "")
    sl      = data.get("sl", "")
    partial = data.get("partial", "")

    emoji, pretty_event, tagline = EVENT_MAP.get(event, ("🔔", event, None))

    # ── Send to Telegram ──
    lines = [f"{emoji} {pretty_event}"]
    if tagline:
        lines.append(tagline)
    lines.append(f"{ticker} • {tf}")
    lines.append(f"Price: {price}")
    if partial: lines.append(f"Partial: {partial}")
    if tp1:     lines.append(f"TP1: {tp1}")
    if tp2:     lines.append(f"TP2: {tp2}")
    if tp3:     lines.append(f"TP3: {tp3}")
    if sl:      lines.append(f"SL: {sl}")
    if tp1 or tp2 or tp3:
        lines.append("")
        lines.append("⚠️ Please trade carefully scalping ⚠️")
    msg = "\n".join(lines)
    send_to_group(msg)

    # ── Queue signal for MT5 EA ──
    action = ACTION_MAP.get(event)
    if action:
        signal = {
            "id":      str(uuid.uuid4()),   # unique ID — EA echoes this back to ACK
            "action":  action,
            "ticker":  ticker,
            "tf":      tf,
            "price":   float(price)   if price   else 0,
            "partial": float(partial) if partial else 0,
            "tp1":     float(tp1)     if tp1     else 0,
            "tp2":     float(tp2)     if tp2     else 0,
            "tp3":     float(tp3)     if tp3     else 0,
            "sl":      float(sl)      if sl      else 0,
            "event":   event,
        }
        entry = {"id": signal["id"], "ts": time.time(), "delivered": False, "signal": signal}
        signal_store.append(entry)
        print(f"QUEUED SIGNAL id={signal['id']} action={action}")

    return {"status": "sent"}, 200


# ── MT5 EA polls here every 2 seconds ──
# Only undelivered signals are returned. On first successful poll they are
# immediately marked delivered so no subsequent poll ever sees them again.
# The EA can also POST a list of ACK ids to /ack if it wants to confirm receipt,
# but the mark-on-first-poll approach already prevents duplicate trades.
@app.get("/poll")
def poll():
    now = time.time()

    # Collect signals not yet delivered
    pending = [e for e in signal_store if not e["delivered"]]

    # Mark them all delivered right now — before we return —
    # so even if this response is received twice (unlikely but possible)
    # the EA only ever sees each signal in one poll response.
    for e in pending:
        e["delivered"] = True

    # Garbage-collect entries older than SIGNAL_TTL
    signal_store[:] = [e for e in signal_store if now - e["ts"] < SIGNAL_TTL]

    signals = [e["signal"] for e in pending]
    print(f"POLL → returning {len(signals)} signal(s)")
    return {"count": len(signals), "signals": signals}, 200
