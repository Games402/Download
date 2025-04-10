import os
import yt_dlp
import uuid
import asyncio
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Env variables
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/") + WEBHOOK_PATH

# Flask app
app = Flask(__name__)

# Telegram Application
application = Application.builder().token(TOKEN).build()

@app.route("/")
def index():
    return "✅ Bot is alive!"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"


# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="👋 Send me a .m3u8 video link!")


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Please send a valid .m3u8 URL.")
        return

    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="📥 Downloading your video...")

    filename = f"{uuid.uuid4()}.mp4"

    def progress_hook(d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "").strip()
            eta = d.get("eta", "")
            text = f"📥 {percent} (ETA: {eta}s)"
            try:
                asyncio.run_coroutine_threadsafe(msg.edit_text(text), application.bot.loop)
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
        await msg.edit_text(f"❌ Download failed:\n{e}")
        return

    await msg.edit_text("☁️ Uploading to file.io...")

    try:
        with open(filename, "rb") as f:
            res = requests.post("https://file.io", files={"file": f})
        result = res.json()
        if result.get("success"):
            await msg.edit_text(f"✅ Done!\n🔗 [Download link]({result['link']})", parse_mode="Markdown")
        else:
            await msg.edit_text("❌ Upload failed.")
    except Exception as e:
        await msg.edit_text(f"❌ Upload error:\n{e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))


# --- Run everything ---
async def main():
    await application.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set to {WEBHOOK_URL}")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()  # just in case, redundant safety

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


if __name__ == "__main__":
    asyncio.run(main())
