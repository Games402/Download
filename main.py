import os
import json
import asyncio
import shutil
import psutil
import subprocess
from uuid import uuid4
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ==== CONFIG ====
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH
DOWNLOAD_DIR = "/tmp/videos"
COMPLETED_JSON = "completed.json"
MAX_COMPLETED = 20

# ==== INIT ====
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
if not os.path.exists(COMPLETED_JSON):
    with open(COMPLETED_JSON, "w") as f:
        json.dump([], f)

pending_downloads = {}
download_logs = []

# ==== HANDLERS ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send a `.m3u8` video link to start downloading.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if text.startswith("http") and ".m3u8" in text:
        pending_downloads[chat_id] = {"url": text}
        await update.message.reply_text(
            "📥 Please send a filename (optional) or click cancel.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        )
    elif chat_id in pending_downloads:
        task = pending_downloads.pop(chat_id)
        await download_video(task["url"], chat_id, context, text)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.callback_query.data == "cancel":
        pending_downloads.pop(chat_id, None)
        await update.callback_query.message.reply_text("❌ Cancelled.")

# ==== DOWNLOAD ====
async def download_video(url, chat_id, context, file_name=None):
    uid = str(uuid4())[:8]
    base_name = file_name or uid
    output_path = os.path.join(DOWNLOAD_DIR, f"{base_name}.mp4")

    await context.bot.send_message(chat_id, f"📡 Starting download for:\n{url}")

    process = await asyncio.create_subprocess_exec(
        "yt-dlp", "--no-playlist", "-f", "best", "-o", output_path, url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        line = line.decode().strip()
        if line:
            await context.bot.send_message(chat_id, f"⏳ {line[:4000]}")

    await process.wait()

    if os.path.exists(output_path):
        size = round(os.path.getsize(output_path) / (1024 * 1024), 2)
        curl_output = subprocess.check_output(["curl", "-F", f"file=@{output_path}", "https://file.io"])
        file_io_link = json.loads(curl_output.decode()).get("link")

        await context.bot.send_message(
            chat_id,
            f"✅ Done!\n📦 File: {base_name}.mp4\n📁 Size: {size} MB\n🔗 {file_io_link}"
        )

        # Save in history
        with open(COMPLETED_JSON) as f:
            history = json.load(f)
        history.insert(0, {"name": base_name, "size": f"{size}MB", "link": file_io_link})
        with open(COMPLETED_JSON, "w") as f:
            json.dump(history[:MAX_COMPLETED], f)

        os.remove(output_path)
    else:
        await context.bot.send_message(chat_id, "❌ Download failed.")

# ==== FLASK ROUTES ====
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is Live"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    await application.initialize()
    await application.process_update(Update.de_json(request.get_json(force=True), application.bot))
    return "OK"

@app.route("/admin", methods=["GET"])
def admin_status():
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    with open(COMPLETED_JSON) as f:
        completed = json.load(f)
    return jsonify({
        "ram_used_mb": ram.used // (1024 * 1024),
        "disk_used_mb": disk.used // (1024 * 1024),
        "disk_free_mb": disk.free // (1024 * 1024),
        "active_downloads": list(pending_downloads.keys()),
        "completed_uploads": completed,
        "logs": download_logs[-30:]
    })

# ==== RUN ====
if __name__ == "__main__":
    import asyncio
    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    app.run(host="0.0.0.0", port=10000)
