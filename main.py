import os
import yt_dlp
import requests
import uuid
import asyncio
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import Dispatcher

# Config from environment
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip('/') + f"/{TOKEN}"

bot = Bot(token=TOKEN)
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

@app.route("/")
def index():
    return "✅ Bot is alive!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        application.update_queue.put_nowait(update)
        return "ok"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a .m3u8 URL and I’ll fetch it for you!")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid .m3u8 link.")
        return

    filename = f"{uuid.uuid4()}.mp4"
    progress_msg = await update.message.reply_text("📥 Starting download...")

    def progress_hook(d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "...")
            eta = d.get("eta", "...")
            asyncio.run_coroutine_threadsafe(
                progress_msg.edit_text(f"📥 Downloading... {percent} (ETA: {eta}s)"),
                context.application.loop
            )

    ydl_opts = {
        'outtmpl': filename,
        'format': 'best',
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        await progress_msg.edit_text(f"❌ Download failed:\n`{e}`", parse_mode="Markdown")
        return

    await progress_msg.edit_text("✅ Uploading to file.io...")

    try:
        with open(filename, "rb") as f:
            r = requests.post("https://file.io", files={"file": f})
        result = r.json()
        if result.get("success"):
            await progress_msg.edit_text(f"✅ Done!\n📎 [Download link]({result['link']})", parse_mode="Markdown")
        else:
            await progress_msg.edit_text("❌ Upload failed.")
    except Exception as e:
        await progress_msg.edit_text(f"❌ Upload error: `{e}`", parse_mode="Markdown")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

if __name__ == "__main__":
    async def setup():
        await bot.set_webhook(WEBHOOK_URL)
        print("✅ Webhook set:", WEBHOOK_URL)

    application.run_task(setup())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
