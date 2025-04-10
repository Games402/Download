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

# Flag to track if bot is ready
bot_ready = False

# Temporary cache for incoming updates
pending_updates = []

# --- Bot Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is up and ready!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Status: Online and responsive!")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))

# --- Flask Routes ---
@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is Live on Render"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def telegram_webhook():
    global bot_ready, pending_updates

    update = Update.de_json(request.get_json(force=True), application.bot)

    if not bot_ready:
        print("⚠️ Bot not ready, caching update...")
        pending_updates.append(update)
    else:
        await application.process_update(update)

    return "OK"

# --- Setup Webhook & Flush Cache ---
if __name__ == "__main__":
    async def main():
        global bot_ready, pending_updates

        print("🔄 Initializing bot...")
        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook set: {WEBHOOK_URL}")

        # Mark bot as ready
        bot_ready = True

        # Process any cached updates
        print(f"📬 Processing {len(pending_updates)} cached updates...")
        for u in pending_updates:
            await application.process_update(u)
        pending_updates.clear()

    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
