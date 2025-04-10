import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + f"/{TOKEN}"

app = Flask(__name__)

# --- Telegram handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! Your bot is live and ready 🚀")

# --- Create Application ---
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))

# --- Flask route to receive webhook updates ---
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return "ok", 200

# --- Basic homepage route (optional) ---
@app.route("/", methods=["GET"])
def home():
    return "Bot is running 😎", 200

# --- Set webhook when server starts ---
async def set_webhook():
    await application.bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())  # Set webhook
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
