import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH

# Create Flask app
app = Flask(__name__)

# Set up Telegram bot application
application = Application.builder().token(TOKEN).build()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is ready and working!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Status: All systems go!")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is Live!"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        print("Error in webhook:", e)
    return "OK"

# Run async setup before launching Flask
if __name__ == "__main__":
    async def main():
        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook set to: {WEBHOOK_URL}")

    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
