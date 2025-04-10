import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = "7881285994:AAGB5cPLZ61CuyZqvmzoee7cv-YeHTeX5xM"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Send me a .m3u8 URL and I'll check if it's valid.")

async def check_m3u8(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.endswith(".m3u8"):
        await update.message.reply_text("❌ That doesn't look like a valid .m3u8 link.")
        return

    await update.message.reply_text("🔍 Checking the link...")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'simulate': True,  # Do not download, just probe
        'force_generic_extractor': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        await update.message.reply_text(f"✅ Link is valid!\nTitle: {info.get('title', 'N/A')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Invalid or inaccessible URL.\nError: {e}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_m3u8))
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
