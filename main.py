import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Token and Render URL
TOKEN = os.environ['TELEGRAM_TOKEN']
WEBHOOK_URL = os.environ['RENDER_EXTERNAL_URL'] + '/' + TOKEN

# Flask app (with async enabled)
app = Flask(__name__)

# Telegram app
telegram_app = Application.builder().token(TOKEN).build()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive and running!")

# Status command
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Status: Running fine on Render!")

# Add handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("status", status))

# Flask route for webhook
@app.post(f"/{TOKEN}")
async def webhook() -> str:
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as e:
        logger.error(f"Error handling update: {e}")
    return "ok"

# Optional root for testing
@app.get("/")
def root():
    return "Bot is running!"

# Set webhook on start
async def set_webhook():
    await telegram_app.bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
