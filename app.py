from flask import Flask, request
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "YOUR_BOT_TOKEN"

app = Flask(__name__)

# ================= BOT =================
application = ApplicationBuilder().token(TOKEN).build()

users = {}

# ================= MENU =================
def main_menu():
    return ReplyKeyboardMarkup([
        ["🚀 রেজাল্ট বের করুন 🚀"]
    ], resize_keyboard=True)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users[update.effective_chat.id] = {}
    await update.message.reply_text(
        "🎉 Welcome!\n\nResult দেখতে নিচের বাটনে চাপ দিন 👇",
        reply_markup=main_menu()
    )

# ================= HANDLE =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if chat_id not in users:
        users[chat_id] = {}

    data = users[chat_id]

    # MAIN BUTTON
    if text == "🚀 রেজাল্ট বের করুন 🚀":
        users[chat_id] = {}
        keyboard = [["SSC", "HSC"]]
        await update.message.reply_text("📘 Exam নির্বাচন করুন:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    # EXAM
    if "exam" not in data:
        data["exam"] = text.lower()
        await update.message.reply_text("📅 Year লিখুন (e.g. 2020):")
        return

    # YEAR
    if "year" not in data:
        data["year"] = text
        await update.message.reply_text("🏫 Board লিখুন (e.g. dhaka):")
        return

    # BOARD
    if "board" not in data:
        data["board"] = text.lower()
        await update.message.reply_text("🆔 Roll লিখুন:")
        return

    # ROLL
    if "roll" not in data:
        data["roll"] = text
        await update.message.reply_text("📄 Registration লিখুন:")
        return

    # REG
    if "reg" not in data:
        data["reg"] = text

        session = requests.Session()
        data["session"] = session

        await send_captcha(update, data)
        return

    # CAPTCHA RELOAD
    if text == "🔄 Reload Captcha":
        await send_captcha(update, data)
        return

    # CAPTCHA SUBMIT
    if "captcha" not in data:
        data["captcha"] = text

        payload = {
            "board": data["board"],
            "exam": data["exam"],
            "year": data["year"],
            "result_type": "1",
            "roll": data["roll"],
            "reg": data["reg"],
            "captcha": data["captcha"]
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://eboardresults.com",
            "Referer": "https://eboardresults.com/v2/home",
            "User-Agent": "Mozilla/5.0"
        }

        res = data["session"].post("https://eboardresults.com/v2/getres", data=payload, headers=headers)
        result = res.json()

        if result.get("status") != 0:
            await update.message.reply_text("❌ Captcha ভুল")
            await send_captcha(update, data)
            return

        info = result["res"]

        gpa = info.get("res_detail","N/A").replace("GPA=","")

        msg = f"""
👨‍🎓 STUDENT INFORMATION
━━━━━━━━━━━━━━━
👤 Name: {info.get('name')}
👨 Father: {info.get('fname')}
👩 Mother: {info.get('mname')}

📘 {data['exam'].upper()} {data['year']}
🏫 Board: {info.get('board_name')}

⭐ GPA: {gpa}
"""

        await update.message.reply_text(msg, reply_markup=main_menu())

        users[chat_id] = {}

# ================= CAPTCHA =================
async def send_captcha(update, data):
    chat_id = update.effective_chat.id

    url = "https://eboardresults.com/v2/captcha"
    r = data["session"].get(url)

    with open(f"{chat_id}.jpg","wb") as f:
        f.write(r.content)

    keyboard = [["🔄 Reload Captcha"]]

    await update.message.reply_photo(
        photo=open(f"{chat_id}.jpg","rb"),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    await update.message.reply_text("🔐 Captcha লিখুন:")

# ================= ROUTE =================
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route("/")
def home():
    return "Bot running..."

# ================= RUN =================
if __name__ == "__main__":
    application.initialize()
    application.start()
    app.run(host="0.0.0.0", port=10000)