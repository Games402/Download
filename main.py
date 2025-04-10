import os
import yt_dlp
import requests
import asyncio
import uuid
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "7881285994:AAGB5cPLZ61CuyZqvmzoee7cv-YeHTeX5xM"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a `.m3u8` video link, and I'll fetch it, upload it to File.io, and send you the download link!")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ Please send a valid `.m3u8` link.")
        return

    temp_filename = f"/tmp/{uuid.uuid4()}.mp4"
    progress_msg = await update.message.reply_text("📥 Starting download...")

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            eta = d.get('eta', '...')
            asyncio.run_coroutine_threadsafe(
                progress_msg.edit_text(f"📥 Downloading... {percent} (ETA: {eta}s)"),
                context.application.loop
            )

    ydl_opts = {
        'outtmpl': temp_filename,
        'format': 'best',
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        await progress_msg.edit_text(f"❌ Failed to download.\nError: `{e}`", parse_mode="Markdown")
        return

    await progress_msg.edit_text("✅ Downloaded! Uploading to file.io...")

    try:
        with open(temp_filename, 'rb') as f:
            response = requests.post('https://file.io', files={'file': f})
        result = response.json()
        if result.get("success"):
            link = result['link']
            await progress_msg.edit_text(f"✅ Upload complete!\n📎 [Click here to download]({link})", parse_mode="Markdown")
        else:
            await progress_msg.edit_text("❌ Upload failed.")
    except Exception as e:
        await progress_msg.edit_text(f"❌ Upload error: {e}")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
