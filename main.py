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

# Environment variables
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/") + WEBHOOK_PATH

# Flask and Telegram setup
app = Flask(__name__)
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()


# Flask route to verify service is running
@app.route("/")
def index():
    return "✅ Bot is running on Render"


# Route to receive webhook updates from Telegram
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send a .m3u8 link and I’ll download it!")


# Handle .m3u8 URL messages
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid .m3u8 link.")
        return

    filename = f"{uuid.uuid4()}.mp4"
    status_msg = await update.message.reply_text("📥 Downloading...")

    def hook(d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "").strip()
            eta = d.get("eta", "")
            msg = f"📥 {percent} (ETA: {eta}s)"
            try:
                asyncio.run_coroutine_threadsafe(status_msg.edit_text(msg), context.application.loop)
            except:
                pass

    ydl_opts = {
        "outtmpl": filename,
        "format": "best",
        "quiet": True,
        "progress_hooks": [hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        await status_msg.edit_text(f"❌ Download failed:\n{e}")
        return

    await status_msg.edit_text("☁️ Uploading to file.io...")

    try:
        with open(filename, "rb") as f:
            res = requests.post("https://file.io", files={"file": f})
        result = res.json()
        if result.get("success"):
            await status_msg.edit_text(f"✅ Done!\n🔗 [Download Link]({result['link']})", parse_mode="Markdown")
        else:
            await status_msg.edit_text("❌ Upload failed.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error uploading:\n{e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


# Set up handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))


# ✅ Run Flask AND Application (this is the fix)
async def main():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set to {WEBHOOK_URL}")

    # Start Application in background so it processes updates
    asyncio.create_task(application.initialize())
    asyncio.create_task(application.start())

    # Run Flask server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    asyncio.run(main())
