import os
import asyncio
import threading
import logging
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# টেলিগ্রাম বট টোকেন
BOT_TOKEN = os.getenv("8751926796:AAEQBdgeQf9PRYRI9O4SLyp2SjIvY3SGN7E")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

app = Flask(__name__)
user_sessions = {}

# ----------------- স্ক্র্যাপিং ফাংশন -----------------
def get_student_data(exam: str, roll: str, year: str) -> dict:
    url = "https://certificate.comillaboard.gov.bd/find/duplicate"
    params = {"exam": exam.lower(), "roll": str(roll).strip(), "year": str(year).strip()}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://certificate.comillaboard.gov.bd/",
    }

    try:
        session = requests.Session()
        session.get("https://certificate.comillaboard.gov.bd/", headers=headers, timeout=10)
        res = session.get(url, params=params, headers=headers, timeout=15)

        if res.status_code != 200:
            return {"status": "error", "message": "বোর্ড সার্ভার রেসপন্স করছে না।"}

        soup = BeautifulSoup(res.text, "html.parser")

        def get_val(attr):
            elem = soup.find("input", {"name": attr}) or soup.find("input", {"id": attr})
            return elem.get("value").strip() if elem and elem.get("value") else None

        data = {}
        for row in soup.find_all("div", class_="form-group"):
            lbl = row.find("label")
            inp = row.find("input")
            if lbl and inp and inp.get("value"):
                data[lbl.text.strip()] = inp.get("value").strip()

        name = get_val("name") or data.get("Name")
        if not name:
            return {"status": "not_found", "message": "কোনো তথ্য পাওয়া যায়নি।"}

        return {
            "status": "success",
            "exam": exam.upper(),
            "year": year,
            "roll": roll,
            "name": name,
            "father": get_val("father_name") or data.get("Father's Name", "N/A"),
            "mother": get_val("mother_name") or data.get("Mother's Name", "N/A"),
            "reg": get_val("reg_no") or data.get("Registration Number", "N/A"),
            "session": get_val("session") or data.get("Session", "N/A"),
            "dob": get_val("dob") or data.get("Date of Birth", "N/A"),
            "gender": get_val("sex") or data.get("Sex", "N/A"),
            "gpa": get_val("gpa") or data.get("GPA", "N/A"),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ----------------- টেলিগ্রাম হ্যান্ডলার -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 স্বাগতম! শিক্ষার্থীর তথ্য পেতে রোল নম্বর লিখে পাঠান:")

async def handle_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    roll = update.message.text.strip()
    if not roll.isdigit():
        await update.message.reply_text("⚠️ অনুগ্রহ করে সঠিক রোল নম্বর পাঠান।")
        return

    chat_id = update.effective_chat.id
    user_sessions[chat_id] = {"roll": roll}

    keyboard = [
        [
            InlineKeyboardButton("SSC", callback_data="exam_ssc"),
            InlineKeyboardButton("HSC", callback_data="exam_hsc"),
        ]
    ]
    await update.message.reply_text(
        f"রোল: *{roll}*\nপরীক্ষা নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data

    if chat_id not in user_sessions:
        await query.edit_message_text("⚠️ সেশন মেয়াদোত্তীর্ণ হয়েছে। রোল আবার লিখুন।")
        return

    if data.startswith("exam_"):
        exam_type = data.split("_")[1]
        user_sessions[chat_id]["exam"] = exam_type

        years = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]
        keyboard = []
        row = []
        for y in years:
            row.append(InlineKeyboardButton(y, callback_data=f"year_{y}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        await query.edit_message_text(
            f"পরীক্ষা: *{exam_type.upper()}*\nপাশের বছর নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data.startswith("year_"):
        year = data.split("_")[1]
        roll = user_sessions[chat_id].get("roll")
        exam = user_sessions[chat_id].get("exam")

        await query.edit_message_text("⏳ তথ্য খোঁজা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")
        info = get_student_data(exam, roll, year)

        if info["status"] == "success":
            msg = (
                f"🎓 *শিক্ষার্থীর তথ্য ({info['exam']} - {info['year']})*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *নাম:* `{info['name']}`\n"
                f"👨‍👦 *পিতার নাম:* `{info['father']}`\n"
                f"👩‍👦 *মাতার নাম:* `{info['mother']}`\n"
                f"🆔 *রোল:* `{info['roll']}`\n"
                f"📝 *রেজিস্ট্রেশন:* `{info['reg']}`\n"
                f"📅 *সেশন:* `{info['session']}`\n"
                f"🎂 *জন্ম তারিখ:* `{info['dob']}`\n"
                f"⚧️ *লিঙ্গ:* `{info['gender']}`\n"
                f"📊 *GPA:* `{info['gpa']}`\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
        else:
            msg = f"❌ {info['message']}"

        await query.edit_message_text(msg, parse_mode="Markdown")
        user_sessions.pop(chat_id, None)

# ----------------- Flask রাউট -----------------
@app.route("/")
def home():
    return jsonify({"status": "running", "service": "Telegram Bot & Comilla Board Scraper"})

@app.route("/api/student", methods=["GET"])
def api_student():
    roll = request.args.get("roll")
    exam = request.args.get("exam", "ssc")
    year = request.args.get("year", "2026")

    if not roll:
        return jsonify({"status": "error", "message": "Roll parameter is required"}), 400

    data = get_student_data(exam, roll, year)
    return jsonify(data)

# ----------------- টেলিগ্রাম বট থ্রেড রানার -----------------
def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_roll))
    bot_app.add_handler(CallbackQueryHandler(handle_callback))
    
    bot_app.run_polling(close_loop=False)

if __name__ == "__main__":
    # ব্যাকগ্রাউন্ড থ্রেডে বট চালু রাখা
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # মেইন থ্রেডে Flask সার্ভার চালু করা
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
