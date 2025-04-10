import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# State flags
bot_ready = False
temp_update = None  # Will store only 1 update temporarily

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is active and ready!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Bot Status: Running fine!")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))

@app.route("/", methods=["GET"])
def home():
    return "🚀 Bot is Live (Render + Webhook)"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    global bot_ready, temp_update

    update = Update.de_json(request.get_json(force=True), application.bot)

    if not bot_ready:
        print("🕒 Bot not ready yet, saving update...")
        temp_update = update
    else:
        await application.process_update(update)

    return "OK"

if __name__ == "__main__":
    async def main():
        global bot_ready, temp_update

        print("🔄 Initializing bot...")
        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=WEBHOOK_URL)

        # Wait a short moment for app to fully settle
        await asyncio.sleep(1)
        bot_ready = True
        print("✅ Bot is now ready.")

        # Process any temp update received during cold start
        if temp_update:
            print("📬 Processing saved update...")
            await application.process_update(temp_update)
            temp_update = None

    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
