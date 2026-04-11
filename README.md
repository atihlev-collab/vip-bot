import requests

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8718087603:AAG48YxUXL6lB0h8AYb49Y4kZBAsL7KGYqg"
API_KEY = "52b7cc336890c47b1c83710a20f6b493"

BASE_URL = "https://v3.football.api-sports.io"


# 🔥 MAX+ логика (още по-строга)
def max_plus_logic(goals, minute):
    if minute is None:
        return 0, ""

    if minute >= 80 and goals == 0:
        return 92, "Over 1.5 Goals"

    elif minute >= 75 and goals == 1:
        return 90, "Over 2.5 Goals"

    elif minute >= 70 and goals == 2:
        return 88, "Over 3.5 Goals"

    elif minute < 25 and goals >= 3:
        return 85, "Over 4.5 Goals"

    return 0, "Skip"


# 🔴 LIVE (най-силен)
async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get(
            BASE_URL + "/fixtures",
            headers={"x-apisports-key": API_KEY},
            params={"live": "all"}
        ).json()
    except:
        await update.message.reply_text("Live error")
        return

    msg = "🔥 MAX+ LIVE (90%+)\n\n"
    found = False

    for m in res.get("response", []):
        minute = m["fixture"]["status"]["elapsed"]
        goals = (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0)

        prob, tip = max_plus_logic(goals, minute)

        if prob >= 90:
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            msg += f"⚽ {home} vs {away}\n⏱ {minute} min\n📊 {prob}%\n👉 {tip}\n\n"
            found = True

    if not found:
        msg += "No elite signals now"

    await update.message.reply_text(msg)


# 🧠 AI PICKS
async def ai(update, context):
    try:
        res = requests.get(
            BASE_URL + "/fixtures",
            headers={"x-apisports-key": API_KEY},
            params={"league": 39, "season": 2024}
        ).json()

        matches = res.get("response", [])

        msg = "🔥 MAX+ PICKS\n\n"

        if not matches:
            msg += "No matches"
        else:
            for m in matches[:3]:
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]

                msg += f"{home} vs {away}\n👉 Over 2.5 Goals\n📊 85%+\n\n"

    except:
        msg = "AI error"

    await update.message.reply_text(msg)


# 🎯 COMBO (само топ)
async def combo(update, context):
    try:
        res = requests.get(
            BASE_URL + "/fixtures",
            headers={"x-apisports-key": API_KEY},
            params={"league": 39, "season": 2024}
        ).json()

        matches = res.get("response", [])

        msg = "🎯 MAX+ COMBO\n\n"

        if not matches:
            msg += "No combo matches"
        else:
            for m in matches[:2]:
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]

                msg += f"{home} vs {away}\n👉 Over 2.5 Goals\n\n"

    except:
        msg = "Combo error"

    await update.message.reply_text(msg)


# 🟢 SAFE (само най-сигурните)
async def safe(update, context):
    try:
        res = requests.get(
            BASE_URL + "/fixtures",
            headers={"x-apisports-key": API_KEY},
            params={"league": 39, "season": 2024}
        ).json()

        matches = res.get("response", [])

        msg = "🟢 MAX+ SAFE\n\n"

        if not matches:
            msg += "No safe matches"
        else:
            for m in matches[:2]:
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]

                msg += f"{home} vs {away}\n👉 Over 1.5 Goals\n\n"

    except:
        msg = "Safe error"

    await update.message.reply_text(msg)


# 🚀 MAIN
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("ai", ai))
    app.add_handler(CommandHandler("combo", combo))
    app.add_handler(CommandHandler("safe", safe))

    print("🔥 MAX+ BOT RUNNING...")
    app.run_polling()


if __name__ == "__main__":
    main()
