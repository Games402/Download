import os
import re
import asyncio
import yt_dlp
import aiohttp
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = f"/{TOKEN}"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Send me a .m3u8 link and I’ll try to download it for you.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running and ready!")

def is_m3u8_link(text: str) -> bool:
    return bool(re.search(r'https?:\/\/[^\s]+\.m3u8', text))

async def download_and_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not is_m3u8_link(url):
        return

    await update.message.reply_text("🎬 Received .m3u8 link. Downloading...")

    filename = f"{update.effective_user.id}_video.mp4"

    ydl_opts = {
        'outtmpl': filename,
        'format': 'best',
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await update.message.reply_text("⬆️ Uploading...")

        async with aiohttp.ClientSession() as session:
            with open(filename, 'rb') as f:
                data = {'file': f}
                async with session.post("https://file.io", data=data) as resp:
                    json_resp = await resp.json()
                    link = json_resp.get("link")
                    if link:
                        await update.message.reply_text(f"✅ Done! Here's your video link:\n{link}")
                    else:
                        await update.message.reply_text("❌ Upload failed.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to process video: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

# --- Register Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://.*\.m3u8'), download_and_upload))

# --- Webhook Routes ---
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is Live!"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    await application.initialize()
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "OK"

# --- Start Webhook ---
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))
    app.run(host="0.0.0.0", port=10000)
