import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# আপনার বটের টোকেন এখানে দিন
BOT_TOKEN = "8751926796:AAEQBdgeQf9PRYRI9O4SLyp2SjIvY3SGN7E"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ইউজার সেশন স্টেট সাময়িকভাবে ধরে রাখার ডিকশনারি
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম! শিক্ষার্থী তথ্য জানতে শুধুমাত্র **রোল নম্বর** লিখে পাঠান।"
    )

async def handle_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    roll = update.message.text.strip()
    if not roll.isdigit():
        await update.message.reply_text("⚠️ অনুগ্রহ করে শুধুমাত্র সঠিক রোল নম্বর লিখুন।")
        return

    chat_id = update.effective_chat.id
    user_sessions[chat_id] = {"roll": roll}

    # SSC / HSC বাটন
    keyboard = [
        [
            InlineKeyboardButton("SSC", callback_data="exam_ssc"),
            InlineKeyboardButton("HSC", callback_data="exam_hsc"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"রোল: *{roll}*\nএখন পরীক্ষার ধরন নির্বাচন করুন:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data

    if chat_id not in user_sessions:
        await query.edit_message_text("⚠️ সেশন মেয়াদোত্তীর্ণ হয়েছে। রোল নম্বর আবার পাঠান।")
        return

    # পরীক্ষার ধরন নির্বাচন
    if data.startswith("exam_"):
        exam_type = data.split("_")[1]
        user_sessions[chat_id]["exam"] = exam_type

        # ২০২০ থেকে ২০২৬ সালের বাটন
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

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"পরীক্ষা: *{exam_type.upper()}*\nপাশের বছর (Passing Year) নির্বাচন করুন:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # পাশের বছর নির্বাচন ও ডেটা স্ক্র্যাপিং
    elif data.startswith("year_"):
        year = data.split("_")[1]
        roll = user_sessions[chat_id].get("roll")
        exam = user_sessions[chat_id].get("exam")

        await query.edit_message_text("⏳ তথ্য খোঁজা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")

        # স্ক্র্যাপিং ফাংশন কল
        result_text = fetch_student_info(exam, roll, year)
        await query.edit_message_text(result_text, parse_mode="Markdown")

        # সেশন ক্লিয়ার
        user_sessions.pop(chat_id, None)

def fetch_student_info(exam: str, roll: str, year: str) -> str:
    url = "https://certificate.comillaboard.gov.bd/find/duplicate"
    params = {"exam": exam, "roll": roll, "year": year}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://certificate.comillaboard.gov.bd/",
    }

    try:
        session = requests.Session()
        # কুকি সংগ্রহের জন্য হোমপেজ ভিজিট
        session.get("https://certificate.comillaboard.gov.bd/", headers=headers, timeout=10)
        # রেজাল্ট রিকোয়েস্ট
        res = session.get(url, params=params, headers=headers, timeout=15)

        if res.status_code != 200:
            return "❌ সার্ভার থেকে তথ্য পাওয়া যায়নি (Server Error)।"

        soup = BeautifulSoup(res.text, "html.parser")

        # ইনপুট ফিল্ডগুলো খুঁজে বের করা
        def get_val(name_attr):
            elem = soup.find("input", {"name": name_attr})
            if elem and elem.get("value"):
                return elem.get("value").strip()
            # অনেক সময় id ও name একই থাকে
            elem = soup.find("input", {"id": name_attr})
            if elem and elem.get("value"):
                return elem.get("value").strip()
            return None

        # বিকল্প হিসেবে লেবেল ধরে ভ্যালু বের করা
        data = {}
        for row in soup.find_all("div", class_="form-group"):
            label = row.find("label")
            inp = row.find("input")
            if label and inp and inp.get("value"):
                data[label.text.strip()] = inp.get("value").strip()

        name = get_val("name") or data.get("Name")
        if not name:
            return f"❌ রোল: *{roll}*, বছর: *{year}* ({exam.upper()}) এর কোনো তথ্য পাওয়া যায়নি।"

        father = get_val("father_name") or data.get("Father's Name", "N/A")
        mother = get_val("mother_name") or data.get("Mother's Name", "N/A")
        reg = get_val("reg_no") or data.get("Registration Number", "N/A")
        session_val = get_val("session") or data.get("Session", "N/A")
        dob = get_val("dob") or data.get("Date of Birth", "N/A")
        gpa = get_val("gpa") or data.get("GPA", "N/A")
        gender = get_val("sex") or data.get("Sex", "N/A")

        output = (
            f"🎓 *শিক্ষার্থীর তথ্য ({exam.upper()} - {year})*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *নাম:* `{name}`\n"
            f"👨‍👦 *পিতার নাম:* `{father}`\n"
            f"👩‍👦 *মাতার নাম:* `{mother}`\n"
            f"🆔 *রোল নম্বর:* `{roll}`\n"
            f"📝 *রেজিস্ট্রেশন:* `{reg}`\n"
            f"📅 *সেশন:* `{session_val}`\n"
            f"🎂 *জন্ম তারিখ:* `{dob}`\n"
            f"⚧️ *লিঙ্গ:* `{gender}`\n"
            f"📊 *GPA:* `{gpa}`\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return output

    except Exception as e:
        return f"⚠️ ত্রুটি ঘটেছে: {str(e)}"

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_roll))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("বট সফলভাবে চালু হয়েছে...")
    app.run_polling()
