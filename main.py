import os
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

# Load environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") + "/" + BOT_TOKEN

# Create Flask app
app = Flask(__name__)
application = None  # We'll create the Telegram application later


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is live and webhook is working!")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Webhook status: OK\n⚙️ Server running fine.")


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        return "ok"


@app.route("/", methods=["GET"])
def home():
    return "Bot is live."


async def main():
    global application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))

    # Set webhook
    await application.bot.delete_webhook()
    await application.bot.set_webhook(url=WEBHOOK_URL)

    print("🚀 Bot webhook set and ready!")

if __name__ == "__main__":
    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
