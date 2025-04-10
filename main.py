import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ.get("TELEGRAM_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")  # like https://download-pw.onrender.com
WEBHOOK_PATH = f"/{TOKEN}"

bot = Bot(token=TOKEN)
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

logging.basicConfig(level=logging.INFO)


# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a .m3u8 URL and I’ll process it for you!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")


application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


# Webhook endpoint for Telegram
@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook() -> str:
    update = Update.de_json(request.get_json(force=True), bot)
    await application.process_update(update)
    return "OK"


# Health check
@app.route("/", methods=["GET"])
def index():
    return "Bot is live!"


# Start the bot and set webhook
if __name__ == "__main__":
    import asyncio

    async def main():
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}")
        print("✅ Webhook set successfully.")

    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
