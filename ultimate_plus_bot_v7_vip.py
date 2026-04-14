

import requests
import asyncio
import threading
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = "8718087603:AAHb4xWFqrmvexVGPJEgc2GmK2Z29GTCfd0"
API_KEY = "e27351fe232d4274b553a95c2c30f99a"
CHAT_ID = 6488122776

MODE = "AGGRESSIVE"
BANKROLL = 100

bot = Bot(token=BOT_TOKEN)
BASE_URL = "https://v3.football.api-sports.io"

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

# ===== AI ENGINE =====
def ai_engine(m, stats):

    minute = m["fixture"]["status"]["elapsed"] or 0
    total = (m["goals"]["home"] or 0)+(m["goals"]["away"] or 0)

    def ex(st,key):
        for s in st:
            if s["type"]==key:
                try:return int(str(s["value"]).replace("%",""))
                except:return 0
        return 0

    # 💣 fallback ако няма stats
    if not stats:
        if minute > 25 and total < 2:
            return 75, "OVER 1.5"
        return None

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]

    hs = ex(home,"Shots on Goal")
    as_ = ex(away,"Shots on Goal")
    ha = ex(home,"Dangerous Attacks")
    aa = ex(away,"Dangerous Attacks")

    # 💣 силен натиск → гол
    if hs >= 5 or as_ >= 5:
        return 85, "NEXT GOAL"

    # 💣 атаки
    if ha >= 50 or aa >= 50:
        return 82, "NEXT GOAL"

    # 💣 много удари → OVER
    if hs + as_ >= 7 and total < 3:
        return 80, "OVER 2.5"

    # 💣 бавен мач
    if hs + as_ <= 2 and minute > 60:
        return 80, "UNDER 2.5"

    # 💣 fallback
    if minute > 30 and total < 2:
        return 75, "OVER 1.5"

    return None

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
    await update.message.reply_text("📊 LIVE AI ACTIVE")

async def combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 COMBO MODE ON")

# ===== LOOP =====
async def monitor():
    while True:

        matches = get_live()

        for m in matches:

            minute = m["fixture"]["status"]["elapsed"] or 0
            if minute < 5:
                continue

            stats = get_stats(m["fixture"]["id"])

            result = ai_engine(m, stats)
            if not result:
                continue

            score, pick = result

            play, stake_pct = decision(score)
            if not play:
                continue

            stake = round(BANKROLL * stake_pct, 2)

            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            msg = f"{home} vs {away}\n{pick}\n{score}%\nStake: {stake} лв"

            try:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
                print("SENT:", msg)
            except Exception as e:
                print("ERROR:", e)

        await asyncio.sleep(30)

# ===== RUN =====
def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("safe_mode", safe_mode))
    app.add_handler(CommandHandler("aggressive_mode", aggressive_mode))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("combo", combo))

    threading.Thread(target=lambda: asyncio.run(monitor())).start()

    print("🔥 LIVE PRO BOT RUNNING")

    app.run_polling()

if __name__ == "__main__":
    run_bot()
