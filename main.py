import os
import yt_dlp
import requests
import uuid
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") + f"/{TOKEN}"
bot = Bot(token=TOKEN)

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is alive!", 200

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a .m3u8 link and I’ll download and process the video for you!")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid .m3u8 link.")
        return

    await update.message.reply_text("📥 Downloading video... Please wait.")

    filename = f"{uuid.uuid4()}.mp4"
    ydl_opts = {
        'outtmpl': filename,
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        await update.message.reply_text(f"❌ Download failed.\n{e}")
        return

    size_mb = os.path.getsize(filename) / (1024 * 1024)

    if size_mb < 48:
        await update.message.reply_video(video=open(filename, "rb"), caption="✅ Here's your video!")
    else:
        await update.message.reply_text("🔄 Uploading large file to file.io...")
        with open(filename, "rb") as f:
            r = requests.post("https://file.io", files={"file": f})
        result = r.json()
        if result.get("success"):
            await update.message.reply_text(f"✅ Video uploaded!\n🔗 {result['link']}")
        else:
            await update.message.reply_text("❌ Upload to file.io failed.")

    os.remove(filename)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))

if __name__ == "__main__":
    import asyncio

    async def main():
        await bot.set_webhook(WEBHOOK_URL)
        await application.initialize()
        await application.start()
        print("✅ Bot is running on webhook...")

    asyncio.run(main())
    app.run(host="0.0.0.0", port=10000)
