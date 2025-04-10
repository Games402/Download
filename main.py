import os
import json
import shutil
import psutil
import asyncio
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from yt_dlp import YoutubeDL

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH

application = Application.builder().token(TOKEN).build()

queue_lock = threading.Lock()
task_queue = []
is_downloading = False
logs = []
completed_files = []

COMPLETED_LOG = "completed.json"

def save_completed():
    with open(COMPLETED_LOG, "w") as f:
        json.dump(completed_files[-20:], f)

def load_completed():
    global completed_files
    if os.path.exists(COMPLETED_LOG):
        with open(COMPLETED_LOG) as f:
            completed_files = json.load(f)

load_completed()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I'm alive! Send a .m3u8 URL to download.")

@app.route("/", methods=["GET"])
def home():
    return "Bot is Live ✅"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    await application.initialize()
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "OK"

@app.route("/admin", methods=["GET"])
def admin_info():
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    return jsonify({
        "status": "running",
        "cpu_percent": psutil.cpu_percent(),
        "ram_used": ram.used // (1024 ** 2),
        "ram_total": ram.total // (1024 ** 2),
        "disk_used": disk.used // (1024 ** 2),
        "disk_total": disk.total // (1024 ** 2),
        "active_tasks": 1 if is_downloading else 0,
        "pending_tasks": len(task_queue),
        "logs": logs[-10:],
        "completed_files": completed_files[-20:]
    })

def append_log(message):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    logs.append(f"{timestamp} {message}")
    if len(logs) > 50:
        logs.pop(0)

async def handle_download(url, chat_id, message_id):
    global is_downloading

    try:
        append_log(f"Starting download for {url}")
        await application.bot.edit_message_text("🔍 Processing URL...", chat_id, message_id)

        filename = f"video_{datetime.now().strftime('%H%M%S')}.mp4"
        output_path = f"./{filename}"

        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'progress_hooks': [lambda d: asyncio.run_coroutine_threadsafe(
                update_progress(d, chat_id, message_id), application.bot.loop)],
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Video")
            size_mb = round(info.get("filesize", 0) / (1024*1024), 2)
            append_log(f"Title: {title} Size: {size_mb}MB")
            await application.bot.edit_message_text(
                f"📥 Downloading:\n<b>{title}</b>\nSize: {size_mb} MB\nStarted...",
                chat_id,
                message_id,
                parse_mode="HTML"
            )
            ydl.download([url])

        import requests
        with open(output_path, "rb") as f:
            response = requests.post("https://file.io", files={"file": f})
            link = response.json().get("link", "Failed to upload.")

        os.remove(output_path)

        await application.bot.edit_message_text(
            f"✅ Download complete!\n🔗 Link: {link}",
            chat_id,
            message_id
        )
        completed_files.append({
            "title": title,
            "size": f"{size_mb} MB",
            "link": link,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_completed()
    except Exception as e:
        append_log(f"Error: {e}")
        await application.bot.edit_message_text(f"❌ Error: {e}", chat_id, message_id)
    finally:
        is_downloading = False
        check_queue()

async def update_progress(d, chat_id, message_id):
    if d.get('status') == 'downloading':
        percent = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        text = f"⬇️ Progress: {percent}\n⚡ Speed: {speed}\n⏱ ETA: {eta}"
        try:
            await application.bot.edit_message_text(text, chat_id, message_id)
        except:
            pass

def check_queue():
    global is_downloading
    with queue_lock:
        if not is_downloading and task_queue:
            url, chat_id, msg_id = task_queue.pop(0)
            is_downloading = True
            asyncio.run_coroutine_threadsafe(
                handle_download(url, chat_id, msg_id), application.bot.loop
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        url = update.message.text.strip()
        if ".m3u8" in url:
            chat_id = update.message.chat_id
            processing_msg = await update.message.reply_text("🕒 Queued or Processing...")
            with queue_lock:
                if is_downloading:
                    task_queue.append((url, chat_id, processing_msg.message_id))
                    await context.bot.send_message(chat_id, f"⏳ System busy. Your task is queued.")
                else:
                    is_downloading = True
                    asyncio.create_task(handle_download(url, chat_id, processing_msg.message_id))

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    import asyncio
    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))
    app.run(host="0.0.0.0", port=10000)
