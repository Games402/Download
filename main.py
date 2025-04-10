import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import subprocess
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
bot = Bot(TOKEN)

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send me an .m3u8 video URL to download.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive and working!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid .m3u8 URL.")
        return

    msg = await update.message.reply_text("⏬ Download started... please wait.")

    filename = "video.mp4"
    try:
        command = [
            "yt-dlp", url,
            "-o", filename,
            "--no-part"
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if os.path.exists(filename):
            await msg.edit_text("✅ Download complete. Uploading to file.io...")

            with open(filename, "rb") as f:
                upload = requests.post("https://file.io", files={"file": f})
            upload_url = upload.json().get("link", "Upload failed")

            await update.message.reply_text(f"📁 File.io link: {upload_url}")

            # If file is small enough (<50MB), send via Telegram
            if os.path.getsize(filename) < 50 * 1024 * 1024:
                await update.message.reply_document(document=open(filename, "rb"))

            os.remove(filename)
        else:
            await msg.edit_text("❌ Download failed.")
    except Exception as e:
        await msg.edit_text(f"⚠️ Error: {str(e)}")


application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return "ok"

@app.route("/", methods=["GET"])
def root():
    return "Bot is running."

async def set_webhook():
    await bot.delete_webhook()
    await bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(set_webhook())
    app.run(host="0.0.0.0", port=10000)
