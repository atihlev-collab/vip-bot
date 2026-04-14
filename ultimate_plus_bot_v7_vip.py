
  import requests
import asyncio
import threading
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, render_template_string

# ===== CONFIG =====
BOT_TOKEN = "8718087603:AAHb4xWFqrmvexVGPJEgc2GmK2Z29GTCfd0"
API_KEY = "e27351fe232d4274b553a95c2c30f99a"
CHAT_ID = 6488122776
BANKROLL = 100

MODE = "SAFE"
sent_matches = {}

bot = Bot(token=BOT_TOKEN)
BASE_URL = "https://v3.football.api-sports.io"

# ===== WEB =====
app = Flask(__name__)

data = {"signals": [], "mode": MODE}

HTML = """
<html>
<body style="background:#0b0f14;color:white;font-family:Arial;">
<h2>💣 FINAL PRO</h2>
<p>Mode: {{mode}}</p>
{% for s in signals %}
<div style="background:#1f2937;margin:10px;padding:10px;">
{{s}}
</div>
{% endfor %}
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML, **data)

def push(text):
    data["signals"].insert(0, text)
    if len(data["signals"]) > 50:
        data["signals"].pop()

# ===== TIME =====
def bg_now():
    return datetime.utcnow() + timedelta(hours=3)

def is_day():
    return 8 <= bg_now().hour < 24

# ===== API =====
def get_live():
    try:
        return requests.get(BASE_URL+"/fixtures",
            headers={"x-apisports-key":API_KEY},
            params={"live":"all"}).json()["response"]
    except:
        return []

def get_stats(fid):
    try:
        return requests.get(BASE_URL+"/fixtures/statistics",
            headers={"x-apisports-key":API_KEY},
            params={"fixture":fid}).json()["response"]
    except:
        return []

def extract(stats, key):
    for s in stats:
        if s["type"] == key:
            try: return int(str(s["value"]).replace("%",""))
            except: return 0
    return 0

# ===== AI =====
def ai_live(m, stats):

    minute = m["fixture"]["status"]["elapsed"] or 0
    if minute < 15:
        return None

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]

    hs = extract(home,"Shots on Goal")
    as_ = extract(away,"Shots on Goal")
    ha = extract(home,"Dangerous Attacks")
    aa = extract(away,"Dangerous Attacks")

    tempo = hs + as_
    pressure = (hs-as_)*3 + (ha-aa)/2

    # ❌ fake match
    if tempo < 4 and minute > 30:
        return None

    score = 0
    pick = None

    # 🔥 1 / 2
    if abs(pressure) > 25 and minute < 70:
        score, pick = 90, ("1" if pressure > 0 else "2")

    # ⚡ NEXT GOAL
    elif abs(pressure) > 20:
        score, pick = 88, ("NEXT GOAL HOME" if pressure > 0 else "NEXT GOAL AWAY")

    # 🎯 GG
    elif hs >= 4 and as_ >= 4:
        score, pick = 87, "GG"

    # ⚽ OVER
    elif tempo >= 12 and minute > 25:
        score, pick = 85, "OVER 2.5"

    # ❄️ UNDER
    elif tempo <= 4 and minute > 60:
        score, pick = 85, "UNDER 2.5"

    # FILTER
    if score < (88 if MODE == "SAFE" else 78):
        return None

    return score, pick

# ===== COMMANDS =====
async def safe_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    MODE = "SAFE"
    data["mode"] = MODE
    await update.message.reply_text("🟢 SAFE MODE")

async def aggressive_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    MODE = "AGGRESSIVE"
    data["mode"] = MODE
    await update.message.reply_text("🔥 AGGRESSIVE MODE")

# ===== LOOP =====
async def monitor():
    while True:

        signals_count = 0

        if is_day():
            for m in get_live():

                if signals_count >= 4:
                    break

                fid = m["fixture"]["id"]
                now = datetime.now().timestamp()

                if fid in sent_matches and now - sent_matches[fid] < 600:
                    continue

                stats = get_stats(fid)
                if not stats:
                    continue

                result = ai_live(m, stats)
                if not result:
                    continue

                score, pick = result

                msg = f"⚡ LIVE\n{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n🎯 {pick}\n📊 {score}%"

                await bot.send_message(chat_id=CHAT_ID, text=msg)
                push(msg)

                sent_matches[fid] = now
                signals_count += 1

        await asyncio.sleep(60)

# ===== RUN =====
def run_bot():
    app_tg = ApplicationBuilder().token(BOT_TOKEN).build()

    app_tg.add_handler(CommandHandler("safe_mode", safe_mode))
    app_tg.add_handler(CommandHandler("aggressive_mode", aggressive_mode))

    threading.Thread(target=lambda: asyncio.run(monitor())).start()
    app_tg.run_polling()

def run_web():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    run_web()      
