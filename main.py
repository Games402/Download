import os
import yt_dlp
import uuid
import requests
import asyncio
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
APP_URL = os.getenv("RENDER_EXTERNAL_URL")  # Auto-filled by Render
PORT = int(os.environ.get("PORT", 8443))

bot = Bot(token=TOKEN)
app_flask = Flask(__name__)

application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send a .m3u8 link to get started!")

async def handle_m3u8(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Invalid .m3u8 link.")
        return

    temp_filename = f"{uuid.uuid4()}.mp4"
    msg = await update.message.reply_text("📥 Downloading...")

    def hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            asyncio.run_coroutine_threadsafe(
                msg.edit_text(f"📥 Downloading... {percent}"),
                application.loop
            )

    ydl_opts = {
        'outtmpl': temp_filename,
        'format': 'best',
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        await msg.edit_text(f"❌ Download failed: {e}")
        return

    await msg.edit_text("☁️ Uploading to file.io...")

    try:
        with open(temp_filename, 'rb') as f:
            res = requests.post("https://file.io", files={"file": f})
        result = res.json()
        if result.get("success"):
            await msg.edit_text(f"✅ Done!\n🔗 [Download link]({result['link']})", parse_mode="Markdown")
        else:
            await msg.edit_text(f"❌ Upload failed: {result.get('message')}")
    except Exception as e:
        await msg.edit_text(f"❌ Upload failed: {e}")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_m3u8))

@app_flask.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return 'OK'

@app_flask.route("/", methods=["GET"])
def index():
    return "✅ Telegram bot is running with webhook!"

async def setup_webhook():
    webhook_url = f"{APP_URL}/{TOKEN}"
    await bot.set_webhook(url=webhook_url)

def run():
    # Set webhook once before starting Flask
    asyncio.run(setup_webhook())
    app_flask.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    run()
