

import requests
import asyncio
import threading
from datetime import datetime, timezone, timedelta

from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8718087603:AAHb4xWFqrmvexVGPJEgc2GmK2Z29GTCfd0"
API_KEY = "e27351fe232d4274b553a95c2c30f99a"
CHAT_ID = 6488122776
BANKROLL = 100

bot = Bot(token=BOT_TOKEN)
BASE_URL = "https://v3.football.api-sports.io"

sent = {}
MODE = "SAFE"

# ================= FILTER =================

TOP_KEYWORDS = [
    "Premier","Liga","Serie","Bundesliga","League",
    "Division","Super","MLS","Brasileirao","Eredivisie"
]

def is_top_league(m):
    return any(k.lower() in m["league"]["name"].lower() for k in TOP_KEYWORDS)

# ================= TIME =================

def bg_time(t):
    return datetime.fromisoformat(t.replace("Z","+00:00")) + timedelta(hours=3)

def is_future(m):
    try:
        return datetime.fromisoformat(m["fixture"]["date"].replace("Z","+00:00")) > datetime.now(timezone.utc)
    except:
        return False

def is_night_match(m):
    return 0 <= int(m["fixture"]["date"][11:13]) < 10

# ================= DATA =================

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
            params={"date":datetime.now().strftime("%Y-%m-%d")}).json()["response"]
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
            try:
                return int(str(s["value"]).replace("%",""))
            except:
                return 0
    return 0

# ================= AI =================

def analyze(m, stats=None):
    score = 0
    pred = ""

    if stats:
        home = stats[0]["statistics"]
        away = stats[1]["statistics"]

        hs = extract(home,"Shots on Goal")
        as_ = extract(away,"Shots on Goal")
        ha = extract(home,"Dangerous Attacks")
        aa = extract(away,"Dangerous Attacks")

        total = (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0)
        diff = (hs*3 + ha/2) - (as_*3 + aa/2)

        if hs + as_ >= 6:
            score += 20

        if diff > 25:
            score += 40
            pred = "1"

        elif diff < -25:
            score += 40
            pred = "2"

        if total < 3 and (hs + as_) >= 8:
            score += 30
            pred = "OVER 2.5"

        if total == 0 and (hs + as_) <= 3:
            score += 50
            pred = "UNDER 1.5"

        if abs(diff) < 10 and hs >= 3 and as_ >= 3:
            score += 35
            pred = "GG"

    else:
        score = 70
        pred = "OVER 2.5"

    return score, pred

# ================= BANKROLL =================

def stake(score):
    if score >= 85:
        return round(BANKROLL * 0.1, 2)
    elif score >= 75:
        return round(BANKROLL * 0.07, 2)
    return round(BANKROLL * 0.05, 2)

# ================= MODE =================

def threshold():
    return 80 if MODE == "SAFE" else 70

# ================= FORMAT =================

def info(m):
    t = bg_time(m["fixture"]["date"]).strftime("%H:%M")
    return f"🌍 {m['league']['country']} | 🏆 {m['league']['name']}\n🕒 {t}"

def label(m):
    if is_night_match(m):
        return "🌙 НОЩЕН VALUE"
    return f"🔥 {MODE} SIGNAL"

# ================= SMART PICKS =================

def get_top_picks(matches, limit=5):
    scored = []

    for m in matches:
        if not is_future(m): continue
        if not is_top_league(m): continue

        score, pred = analyze(m)
        scored.append((score, m, pred))

    scored.sort(reverse=True, key=lambda x: x[0])

    return scored[:limit]

# ================= AUTO =================

async def monitor():
    while True:

        # LIVE
        for m in get_live():
            fid = m["fixture"]["id"]
            now = datetime.now().timestamp()

            if fid in sent and now - sent[fid] < 3600:
                continue

            stats = get_stats(fid)
            if not stats:
                continue

            score, pred = analyze(m, stats)

            if score >= threshold():
                minute = m["fixture"]["status"]["elapsed"] or 0
                bet = stake(score)

                msg = f"{label(m)}\n\n"
                msg += f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n"
                msg += info(m) + "\n"
                msg += f"⏱ МИНУТА: {minute}'\n"
                msg += f"👉 {pred}\n"
                msg += f"📊 {score}%\n"
                msg += f"💰 {bet} лв"

                await bot.send_message(chat_id=CHAT_ID, text=msg)
                sent[fid] = now

        # PREMATCH
        for score, m, pred in get_top_picks(get_today(), limit=5):

            fid = m["fixture"]["id"]
            now = datetime.now().timestamp()

            if fid in sent and now - sent[fid] < 3600:
                continue

            if score >= threshold():
                bet = stake(score)

                msg = f"{label(m)}\n\n"
                msg += f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n"
                msg += info(m) + "\n"
                msg += f"👉 {pred}\n"
                msg += f"📊 {score}%\n"
                msg += f"💰 {bet} лв"

                await bot.send_message(chat_id=CHAT_ID, text=msg)
                sent[fid] = now

        await asyncio.sleep(60)

# ================= COMMANDS =================

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg="📅 ТОП МАЧОВЕ ДНЕС\n\n"

    picks = get_top_picks(get_today(), limit=5)

    if not picks:
        msg += "❌ Няма мачове"
    else:
        for score, m, pred in picks:
            msg+=f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n"
            msg+=info(m)+f"\n👉 {pred} | {score}%\n\n"

    await update.message.reply_text(msg)

async def safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg="🟢 SAFE PICKS\n\n"

    picks = get_top_picks(get_today(), limit=5)

    if not picks:
        msg+="❌ Няма SAFE мачове"
    else:
        for score, m, pred in picks:
            if score >= 75:
                msg+=f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n"
                msg+=info(m)+f"\n👉 OVER 1.5\n\n"

    await update.message.reply_text(msg)

async def combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg="🎯 COMBO\n\n"

    picks = get_top_picks(get_today(), limit=3)

    for score, m, pred in picks:
        msg+=f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}\n"
        msg+=info(m)+"\n👉 GG\n\n"

    await update.message.reply_text(msg)

async def safe_mode(update,context):
    global MODE
    MODE="SAFE"
    await update.message.reply_text("🟢 SAFE MODE")

async def aggressive_mode(update,context):
    global MODE
    MODE="AGGRESSIVE"
    await update.message.reply_text("🔥 AGGRESSIVE MODE")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("safe", safe))
    app.add_handler(CommandHandler("combo", combo))

    app.add_handler(CommandHandler("safe_mode", safe_mode))
    app.add_handler(CommandHandler("aggressive_mode", aggressive_mode))

    threading.Thread(target=lambda: asyncio.run(monitor())).start()

    print("🔥 SMART TOP PICKS BOT RUNNING")

    app.run_polling()

if __name__ == "__main__":
    main()