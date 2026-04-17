import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes
)
import openai

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! Send me a voice message, audio file, or video and I will transcribe it to text for you."
    )


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.voice:
        file = await message.voice.get_file()
        ext = "ogg"
    elif message.audio:
        file = await message.audio.get_file()
        ext = "mp3"
    elif message.video:
        file = await message.video.get_file()
        ext = "mp4"
    elif message.video_note:
        file = await message.video_note.get_file()
        ext = "mp4"
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

    status_msg = await message.reply_text("⏳ Transcribing... please wait.")

    file_path = f"/tmp/{file.file_id}.{ext}"
    await file.download_to_drive(file_path)

    try:
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        text = response.text
        if text.strip():
            await status_msg.edit_text(f"📝 Transcription:\n\n{text}")
        else:
            await status_msg.edit_text("⚠️ No speech detected in the file.")
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text("❌ Something went wrong. Please try again.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO |
        filters.VIDEO_NOTE | filters.Document.ALL,
        handle_media
    ))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
