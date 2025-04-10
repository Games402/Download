import os
import yt_dlp
import uuid
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

# Load config
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/") + f"/{TOKEN}"

# Init Flask & Bot
app = Flask(__name__)
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

@app.route("/")
def home():
    return "✅ Bot is live on Render!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send a .m3u8 link and I'll download it for you!")

# Handle .m3u8 link
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid .m3u8 URL.")
        return

    filename = f"{uuid.uuid4()}.mp4"
    progress_msg = await update.message.reply_text("📥 Starting download...")

    def progress_hook(d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "...")
            eta = d.get("eta", "...")
            try:
                context.application.create_task(
                    progress_msg.edit_text(f"📥 Downloading: {percent} (ETA: {eta}s)")
                )
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
        await progress_msg.edit_text(f"❌ Upload error: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))

# Start app
if __name__ == "__main__":
    async def run():
        await bot.set_webhook(WEBHOOK_URL)
        print("✅ Webhook set:", WEBHOOK_URL)

    application.run_task(run())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
