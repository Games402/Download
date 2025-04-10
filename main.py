import os
import yt_dlp
import requests
import uuid
import asyncio
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # e.g., https://your-app.onrender.com
PORT = int(os.environ.get('PORT', 5000))

bot = Bot(token=TOKEN)
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a `.m3u8` link to download and upload the video for you.")

# Download and upload logic
async def handle_m3u8(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid `.m3u8` link.")
        return

    video_filename = f"{uuid.uuid4()}.mp4"
    progress = await update.message.reply_text("📥 Starting download...")

    def hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            eta = d.get('eta', '...')
            asyncio.run_coroutine_threadsafe(
                progress.edit_text(f"📥 Downloading... {percent} (ETA: {eta}s)"),
                context.application.loop
            )

    ydl_opts = {
        'outtmpl': video_filename,
        'format': 'best',
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        await progress.edit_text("✅ Download complete. Uploading to file.io...")
    except Exception as e:
        await progress.edit_text(f"❌ Download failed.\nError: {e}")
        return

    # Upload to file.io
    try:
        with open(video_filename, 'rb') as f:
            response = requests.post('https://file.io', files={'file': f})
        result = response.json()

        if result.get("success"):
            await progress.edit_text(f"✅ Uploaded to File.io:\n🔗 {result['link']}")
        else:
            await progress.edit_text(f"❌ Upload failed: {result.get('message')}")

        # If file < 49MB, also send to user directly
        if os.path.getsize(video_filename) < 49 * 1024 * 1024:
            await update.message.reply_video(video=open(video_filename, 'rb'))
        else:
            await update.message.reply_text("⚠️ File is too large to send via Telegram (limit ~49MB for bots).")

    except Exception as e:
        await progress.edit_text(f"❌ Upload failed.\nError: {e}")
    finally:
        if os.path.exists(video_filename):
            os.remove(video_filename)

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_m3u8))

# Flask route for webhook
@app.route(f'/{TOKEN}', methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"

# Set webhook on startup
async def set_webhook():
    await bot.set_webhook(f"{RENDER_URL}/{TOKEN}")

if __name__ == "__main__":
    import threading

    # Run Flask in separate thread
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()

    # Set webhook and run application
    application.run_task(set_webhook())
    
