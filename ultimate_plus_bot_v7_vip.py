
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

BANKROLL = 100
MODE = "SAFE"

sent_matches = {}

bot = Bot(token=BOT_TOKEN)
BASE_URL = "https://v3.football.api-sports.io"

# ===== WEB APP =====
app = Flask(__name__)

data = {"signals": [], "bank": BANKROLL, "mode": MODE}

HTML = """
<html>
<body style="background:#0b0f14;color:white;font-family:Arial;">
<h2>💣 PRO BET SYSTEM</h2>
<p>Mode: {{mode}} | Bank: {{bank}}</p>
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

def get_today():
    try:
        return requests.get(BASE_URL+"/fixtures",
            headers={"x-apisports-key":API_KEY},
            params={"date":bg_now().strftime("%Y-%m-%d")}).json()["response"]
    except:
        return []

def get_tomorrow():
    try:
        t = bg_now() + timedelta(days=1)
        return requests.get(BASE_URL+"/fixtures",
            headers={"x-apisports-key":API_KEY},
            params={"date":t.strftime("%Y-%m-%d")}).json()["response"]
    except:
        return []

def get_stats(fid):
    try:
        return requests.get(BASE_URL+"/fixtures/statistics",
            headers={"x-apisports-key":API_KEY},
            params={"fixture":fid}).json()["response"]
    except:
        return []

def get_last_matches(team_id):
    try:
        return requests.get(BASE_URL+"/fixtures",
            headers={"x-apisports-key":API_KEY},
            params={"team":team_id, "last":5}).json()["response"]
    except:
        return []

def extract(stats, key):
    for s in stats:
        if s["type"] == key:
            try:
                return int(str(s["value"]).replace("%", ""))
            except:
                return 0
    return 0

def avg_goals(matches):
    if not matches:
        return 0
    goals = 0
    for m in matches:
        goals += (m["goals"]["home"] or 0)
        goals += (m["goals"]["away"] or 0)
    return goals / len(matches)

# ===== LIVE AI =====
def ai_live(m, stats):

    minute = m["fixture"]["status"]["elapsed"] or 0
    total = (m["goals"]["home"] or 0)+(m["goals"]["away"] or 0)

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]

    hs = extract(home,"Shots on Goal")
    as_ = extract(away,"Shots on Goal")
    ha = extract(home,"Dangerous Attacks")
    aa = extract(away,"Dangerous Attacks")

    tempo = hs + as_
    pressure = (hs-as_)*3 + (ha-aa)/2

    best_score = 0
    best_pick = None
    best_reason = ""

    if minute > 25 and abs(pressure) > 30:
        best_score, best_pick, best_reason = 90, ("1" if pressure > 0 else "2"), "Domination"

    if minute > 20 and abs(pressure) > 20:
        if 85 > best_score:
            best_score, best_pick, best_reason = 85, ("NEXT GOAL HOME" if pressure > 0 else "NEXT GOAL AWAY"), "Pressure"

    if hs >= 3 and as_ >= 3:
        if 85 > best_score:
            best_score, best_pick, best_reason = 85, "GG", "Both attacking"

    if tempo >= 10 and total < 3:
        if 85 > best_score:
            best_score, best_pick, best_reason = 85, "OVER 2.5", "High tempo"

    if tempo <= 4 and minute > 35:
        if 85 > best_score:
            best_score, best_pick, best_reason = 85, "UNDER 2.5", "Slow"

    if abs(pressure) < 5 and tempo >= 6:
        if 80 > best_score:
            best_score, best_pick, best_reason = 80, "X", "Balanced"

    if best_score < (85 if MODE == "SAFE" else 75):
        return None

    return best_score, best_pick, best_reason

# ===== PREMATCH AI =====
def prematch_ai(m):

    home_id = m["teams"]["home"]["id"]
    away_id = m["teams"]["away"]["id"]

    home_matches = get_last_matches(home_id)
    away_matches = get_last_matches(away_id)

    if not home_matches or not away_matches:
        return None

    home_avg = avg_goals(home_matches)
    away_avg = avg_goals(away_matches)

    total_avg = (home_avg + away_avg) / 2

    best_score = 0
    best_pick = None
    reason = ""

    if total_avg >= 2.8:
        best_score, best_pick, reason = 88, "OVER 2.5", "Goals"

    elif total_avg <= 2.0:
        best_score, best_pick, reason = 88, "UNDER 2.5", "Low goals"

    if home_avg >= 1.2 and away_avg >= 1.2:
        if 86 > best_score:
            best_score, best_pick, reason = 86, "GG", "Both score"

    home_form = sum((m["goals"]["home"] or 0) for m in home_matches)
    away_form = sum((m["goals"]["away"] or 0) for m in away_matches)

    if home_form > away_form + 2:
        if 85 > best_score:
            best_score, best_pick, reason = 85, "1", "Home form"

    elif away_form > home_form + 2:
        if 85 > best_score:
            best_score, best_pick, reason = 85, "2", "Away form"

    if best_score < (85 if MODE == "SAFE" else 75):
        return None

    return best_score, best_pick, reason

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

                if signals_count >= 5:
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

                score, pick, reason = result

                msg = f"⚡ LIVE\n{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n🎯 {pick}\n📊 {score}%\n📌 {reason}"

                await bot.send_message(chat_id=CHAT_ID, text=msg)
                push(msg)

                sent_matches[fid] = now
                signals_count += 1

        for m in get_today():

            result = prematch_ai(m)
            if not result:
                continue

            score, pick, reason = result

            msg = f"🎯 PREMATCH\n{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n🎯 {pick}\n📊 {score}%\n📌 {reason}"

            await bot.send_message(chat_id=CHAT_ID, text=msg)
            push(msg)

        if bg_now().hour >= 18:
            for m in get_tomorrow():
                hour = int(m["fixture"]["date"][11:13])

                if hour < 8:
                    msg = f"🌙 NIGHT\n{m['teams']['home']['name']} vs {m['teams']['away']['name']}\nOVER 2.5"
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
                    push(msg)

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
