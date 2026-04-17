import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FREE_MINUTES_PER_DAY = 5
PREMIUM_STARS_PRICE = 350
USERS_FILE = "/tmp/users.json"

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def get_user_data(user_id):
    users = load_users()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in users:
        users[uid] = {"used_seconds_today": 0, "date": today, "is_paid": False, "paid_until": None}
    elif users[uid].get("date") != today:
        users[uid]["used_seconds_today"] = 0
        users[uid]["date"] = today
    if users[uid].get("paid_until"):
        if datetime.now().strftime("%Y-%m-%d") > users[uid]["paid_until"]:
            users[uid]["is_paid"] = False
    save_users(users)
    return users[uid]

def update_user_usage(user_id, seconds):
    users = load_users()
    uid = str(user_id)
    users[uid]["used_seconds_today"] = users[uid].get("used_seconds_today", 0) + seconds
    save_users(users)

def activate_premium(user_id):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"used_seconds_today": 0, "date": datetime.now().strftime("%Y-%m-%d")}
    users[uid]["is_paid"] = True
    users[uid]["paid_until"] = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    save_users(users)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user_data(user.id)
    await update.message.reply_text(
        f"👋 Hi {user.first_name}! Welcome to QuickScribe AI\n\n"
        f"🎤 Send me any voice message, audio, or video and I'll transcribe it instantly!\n\n"
        f"✅ Free: {FREE_MINUTES_PER_DAY} minutes per day\n"
        f"💎 Unlimited: {PREMIUM_STARS_PRICE} ⭐ for 30 days\n\n"
        f"Commands:\n"
        f"/status - Check your usage\n"
        f"/pay - Upgrade to unlimited\n"
        f"/help - Get help"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user_data(update.effective_user.id)
    used_min = user_data["used_seconds_today"] / 60
    remaining = max(0, FREE_MINUTES_PER_DAY - used_min)
    if user_data.get("is_paid"):
        body = f"Plan: 💎 Premium (until {user_data.get('paid_until')})\nUnlimited transcription!"
    else:
        body = (f"Plan: 🆓 Free Plan\n"
                f"Used today: {used_min:.1f} min\n"
                f"Remaining today: {remaining:.1f} min\n\n"
                f"Upgrade for unlimited: /pay")
    await update.message.reply_text(f"📊 Your Account\n\n{body}")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = [LabeledPrice(label="Premium - 30 days unlimited", amount=PREMIUM_STARS_PRICE)]
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="QuickScribe Premium",
        description="Unlimited transcription for 30 days. Priority processing. Support the developer!",
        payload="premium_monthly",
        provider_token="",
        currency="XTR",
        prices=prices,
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    activate_premium(user_id)
    await update.message.reply_text(
        "🎉 Payment successful!\n\n"
        "💎 You're now a Premium user for 30 days!\n"
        "✅ Unlimited transcription\n"
        "✅ Priority processing\n\n"
        "Thank you for your support! Start sending audio/video now."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 Help\n\n"
        "Just send me:\n"
        "🎤 Voice messages\n"
        "🎵 Audio files (MP3, WAV, M4A)\n"
        "🎥 Videos (MP4, MOV)\n\n"
        "Commands:\n"
        "/start - Welcome\n"
        "/status - Usage\n"
        "/pay - Upgrade\n"
        "/help - This message"
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_data = get_user_data(message.from_user.id)
    file = None
    ext = None
    duration = 0

    if message.voice:
        file = await message.voice.get_file()
        ext = "ogg"
        duration = message.voice.duration
    elif message.audio:
        file = await message.audio.get_file()
        ext = "mp3"
        duration = message.audio.duration or 0
    elif message.video:
        file = await message.video.get_file()
        ext = "mp4"
        duration = message.video.duration or 0
    elif message.video_note:
        file = await message.video_note.get_file()
        ext = "mp4"
        duration = message.video_note.duration or 0
    elif message.document:
        mime = message.document.mime_type or ""
        if not any(t in mime for t in ["audio", "video"]):
            await message.reply_text("Please send an audio or video file.")
            return
        file = await message.document.get_file()
        ext = message.document.file_name.split(".")[-1]
    else:
        await message.reply_text("Please send a voice message, audio, or video file.")
        return

    if not user_data.get("is_paid"):
        used_today = user_data.get("used_seconds_today", 0)
        limit_seconds = FREE_MINUTES_PER_DAY * 60
        if used_today + duration > limit_seconds:
            remaining = max(0, (limit_seconds - used_today) / 60)
            await message.reply_text(
                f"⚠️ Daily Free Limit Reached!\n\n"
                f"Used: {used_today/60:.1f} min today\n"
                f"Remaining: {remaining:.1f} min\n\n"
                f"💎 Upgrade for unlimited: /pay"
            )
            return

    status_msg = await message.reply_text("⏳ Transcribing... please wait.")
    file_path = f"/tmp/{file.file_id}.{ext}"
    await file.download_to_drive(file_path)

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        text = response.text
        
        if text.strip():
            update_user_usage(message.from_user.id, duration)
            footer = ""
            if not user_data.get("is_paid"):
                remaining = max(0, FREE_MINUTES_PER_DAY - (user_data.get("used_seconds_today", 0) + duration) / 60)
                footer = f"\n\n— — —\n🆓 {remaining:.1f} min left today\n💎 Unlimited: /pay"
            await status_msg.edit_text(f"📝 Transcription:\n\n{text}{footer}")
        else:
            await status_msg.edit_text("⚠️ No speech detected.")
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO |
        filters.VIDEO_NOTE | filters.Document.ALL,
        handle_media
    ))
    print("QuickScribe AI is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()