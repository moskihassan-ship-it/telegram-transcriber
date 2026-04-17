import os
import logging
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Update
import openai

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def start(update, context):
    update.message.reply_text(
        "👋 Hello! Send me a voice message, audio file, or video and I will transcribe it to text for you."
    )

def handle_media(update, context):
    message = update.message
    file = None
    ext = None

    if message.voice:
        file = message.voice.get_file()
        ext = "ogg"
    elif message.audio:
        file = message.audio.get_file()
        ext = "mp3"
    elif message.video:
        file = message.video.get_file()
        ext = "mp4"
    elif message.video_note:
        file = message.video_note.get_file()
        ext = "mp4"
    elif message.document:
        mime = message.document.mime_type or ""
        if not any(t in mime for t in ["audio", "video"]):
            message.reply_text("Please send an audio or video file.")
            return
        file = message.document.get_file()
        ext = message.document.file_name.split(".")[-1]
    else:
        message.reply_text("Please send a voice message, audio, or video file.")
        return

    status_msg = message.reply_text("⏳ Transcribing... please wait.")
    file_path = f"/tmp/{file.file_id}.{ext}"
    file.download(file_path)

    try:
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        text = response.text
        if text.strip():
            status_msg.edit_text(f"📝 Transcription:\n\n{text}")
        else:
            status_msg.edit_text("⚠️ No speech detected in the file.")
    except Exception as e:
        logging.error(f"Error: {e}")
        status_msg.edit_text("❌ Something went wrong. Please try again.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(
        Filters.voice | Filters.audio | Filters.video |
        Filters.video_note | Filters.document.all,
        handle_media
    ))
    print("Bot is running...")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
