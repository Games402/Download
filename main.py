import os
import yt_dlp
import uuid
import asyncio
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Load environment variables
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/") + WEBHOOK_PATH

# Initialize Flask
app = Flask(__name__)
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

@app.route("/")
def index():
    return "✅ Bot is live!"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send a .m3u8 link and I'll download it!")

# Handle .m3u8 link
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid .m3u8 URL.")
        return

    filename = f"{uuid.uuid4()}.mp4"
    progress_msg = await update.message.reply_text("📥 Downloading...")

    def progress_hook(d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "")
            eta = d.get("eta", "")
            text = f"📥 Downloading: {percent} (ETA: {eta}s)"
            try:
                asyncio.run_coroutine_threadsafe(progress_msg.edit_text(text), context.application.loop)
            except:
                pass

    ydl_opts = {
        "outtmpl": filename,
        "format": "best",
        "quiet": True,
        "progress_hooks": [progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        await progress_msg.edit_text(f"❌ Download failed:\n{e}")
        return

    await progress_msg.edit_text("☁️ Uploading to file.io...")

    try:
        with open(filename, "rb") as f:
            r = requests.post("https://file.io", files={"file": f})
        result = r.json()
        if result.get("success"):
            await progress_msg.edit_text(f"✅ Done!\n🔗 [Download Link]({result['link']})", parse_mode="Markdown")
        else:
            await progress_msg.edit_text("❌ Upload failed.")
    except Exception as e:
        await progress_msg.edit_text(f"❌ Upload error: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))

# Set webhook and start Flask app
async def set_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    print("✅ Webhook set at:", WEBHOOK_URL)

if __name__ == "__main__":
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
