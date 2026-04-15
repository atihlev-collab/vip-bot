

import requests
import asyncio
import threading
import time
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

sent_matches = {}
last_signals = []

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
    home_goals = m["goals"]["home"] or 0
    away_goals = m["goals"]["away"] or 0
    total = home_goals + away_goals

    def ex(st,key):
        for s in st:
            if s["type"]==key:
                try:
                    return int(str(s["value"]).replace("%",""))
                except:
                    return 0
        return 0

    # fallback (ако няма stats)
    if not stats:
        if minute > 30 and total < 2:
            return 75, "OVER 1.5"
        return None

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]

    hs = ex(home,"Shots on Goal")
    as_ = ex(away,"Shots on Goal")
    ha = ex(home,"Dangerous Attacks")
    aa = ex(away,"Dangerous Attacks")

    tempo = hs + as_
    pressure = abs(ha - aa)

    # ===== GAME STATE LOGIC =====

    # 0:0 → търсим гол
    if total == 0 and minute > 25:
        if tempo >= 6:
            return 80, "OVER 1.5"

    # 1 гол → next goal
    if total == 1:
        if pressure > 20 and tempo >= 5:
            return 80, "NEXT GOAL"

    # 2+ гола → over
    if total >= 2:
        if tempo >= 7:
            return 82, "OVER 3.5"

    # силен натиск
    if (hs >= 5 or as_ >= 5) and pressure > 25:
        return 82, "NEXT GOAL"

    # слаб мач
    if tempo <= 2 and minute > 65:
        return 80, "UNDER 2.5"

    return None

# ===== SMART STAKE =====
def calculate_stake(score):
    if score >= 85:
        return round(BANKROLL * 0.2, 2)
    elif score >= 83:
        return round(BANKROLL * 0.15, 2)
    elif score >= 80:
        return round(BANKROLL * 0.1, 2)
    else:
        return round(BANKROLL * 0.05, 2)

def should_play(score):
    if MODE == "SAFE":
        return score >= 80
    return score >= 75

# ===== COMMANDS =====
async def safe_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    MODE = "SAFE"
    await update.message.reply_text("🟢 SAFE MODE")

async def aggressive_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    MODE = "AGGRESSIVE"
    await update.message.reply_text("🔥 AGGRESSIVE MODE")

# ===== LOOP =====
async def monitor():
    while True:

        now = time.time()

        # limit сигнали (макс 6 на 10 мин)
        last_signals[:] = [t for t in last_signals if now - t < 600]
        if len(last_signals) >= 6:
            await asyncio.sleep(30)
            continue

        matches = get_live()

        for m in matches:

            fid = m["fixture"]["id"]

            # anti-spam (3 мин)
            if fid in sent_matches and now - sent_matches[fid] < 180:
                continue

            minute = m["fixture"]["status"]["elapsed"] or 0
            if minute < 5:
                continue

            stats = get_stats(fid)

            result = ai_engine(m, stats)
            if not result:
                continue

            score, pick = result

            if not should_play(score):
                continue

            stake = calculate_stake(score)

            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            msg = f"{home} vs {away}\n{pick}\n{score}%\nStake: {stake} лв"

            try:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
                print("SENT:", msg)

                sent_matches[fid] = now
                last_signals.append(now)

            except Exception as e:
                print("ERROR:", e)

        await asyncio.sleep(30)

# ===== RUN =====
def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("safe_mode", safe_mode))
    app.add_handler(CommandHandler("aggressive_mode", aggressive_mode))

    threading.Thread(target=lambda: asyncio.run(monitor())).start()

    print("🔥 FINAL ELITE BOT RUNNING")

    app.run_polling()

if __name__ == "__main__":
    run_bot()
# update v2
# fix update
