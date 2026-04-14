

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

bot = Bot(token=BOT_TOKEN)
BASE_URL = "https://v3.football.api-sports.io"

# ===== WEB =====
app = Flask(__name__)

data = {
    "signals": [],
    "bank": BANKROLL,
    "mode": MODE
}

HTML = """
<html>
<body style="background:#0b0f14;color:white;font-family:Arial;">
<h2>🔥 LEVEL 100 AI</h2>
<p>Mode: {{mode}} | Bank: {{bank}}</p>

{% for s in signals %}
<div style="background:#1f2937;margin:10px;padding:10px;">
<b>{{s.title}}</b><br>
{{s.text}}<br>
{{s.score}} | {{s.stake}}
</div>
{% endfor %}
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML, **data)

def push_signal(title, text, score, stake):
    data["signals"].insert(0,{
        "title":title,
        "text":text,
        "score":f"{score}%",
        "stake":f"{stake} лв"
    })

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

def extract(stats,key):
    for s in stats:
        if s["type"]==key:
            try:return int(str(s["value"]).replace("%",""))
            except:return 0
    return 0

# ===== AI =====
def ai_engine(m, stats):

    minute = m["fixture"]["status"]["elapsed"] or 0
    total = (m["goals"]["home"] or 0)+(m["goals"]["away"] or 0)

    score = 75
    pick = "OVER 1.5"

    if stats:
        home = stats[0]["statistics"]
        away = stats[1]["statistics"]

        hs = extract(home,"Shots on Goal")
        as_ = extract(away,"Shots on Goal")
        ha = extract(home,"Dangerous Attacks")
        aa = extract(away,"Dangerous Attacks")

        tempo = hs + as_
        pressure = (hs-as_)*3 + (ha-aa)/2

        if abs(pressure) > 25:
            score = 85
            pick = "1" if pressure > 0 else "2"

        elif tempo >= 10:
            score = 82
            pick = "OVER 2.5"

        elif tempo <= 4 and minute > 35:
            score = 80
            pick = "UNDER 2.5"

    return score, pick

# ===== DECISION =====
def decision(score):

    if MODE == "SAFE":
        return score >= 80, 0.1
    else:
        return score >= 75, 0.15

# ===== COMMANDS =====
async def safe_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    MODE = "SAFE"
    await update.message.reply_text("🟢 SAFE MODE (80%)")

async def aggressive_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    MODE = "AGGRESSIVE"
    await update.message.reply_text("🔥 AGGRESSIVE MODE (75%)")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 LIVE ONLY BOT")

async def combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 COMBO ACTIVE")

# ===== LOOP =====
async def monitor():
    while True:

        matches = get_live()

        for m in matches:

            minute = m["fixture"]["status"]["elapsed"] or 0
            if minute < 5:
                continue

            stats = get_stats(m["fixture"]["id"])

            score, pick = ai_engine(m, stats)

            play, stake_pct = decision(score)

            if not play:
                continue

            stake = round(BANKROLL * stake_pct, 2)

            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            msg = f"{home} vs {away}\n{pick}\n{score}%\nStake: {stake} лв"

            try:
                await bot.send_message(chat_id=CHAT_ID,text=msg)
                print("SENT:", msg)
            except Exception as e:
                print("ERROR:", e)

            push_signal("LIVE",msg,score,stake)

        await asyncio.sleep(30)

# ===== RUN =====
def run_bot():
    app_tg = ApplicationBuilder().token(BOT_TOKEN).build()

    app_tg.add_handler(CommandHandler("safe_mode", safe_mode))
    app_tg.add_handler(CommandHandler("aggressive_mode", aggressive_mode))
    app_tg.add_handler(CommandHandler("today", today))
    app_tg.add_handler(CommandHandler("combo", combo))

    threading.Thread(target=lambda: asyncio.run(monitor())).start()

    print("🔥 PRO BOT RUNNING")

    app_tg.run_polling()


if __name__ == "__main__":
    run_web()
