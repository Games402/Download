import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH

app = Flask(__name__)

# Set up Telegram bot application
application = Application.builder().token(TOKEN).build()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is up and running on webhook!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Status: OK ✅")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))

@app.route("/", methods=["GET"])
def home():
    return "Bot is Live ✅"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    await application.initialize()
    await application.process_update(Update.de_json(request.get_json(force=True), application.bot))
    return "OK"

if __name__ == "__main__":
    import asyncio
    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))
    app.run(host="0.0.0.0", port=10000)
