import sqlite3
import logging
import os
from datetime import datetime
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    BusinessMessageHandler,
    CommandHandler,
    filters
)

# ==================== TOKENNI BU YERGA YOZING ====================
TOKEN = "8999047254:AAEIFKdBS4xN8FHHor8fD0jCJzjH_dD6V-o"   # <-- SHU YERGA BOT TOKENINGIZNI QO'YING

PORT = int(os.getenv("PORT", 8080))

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('user_settings.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            telegram_id INTEGER PRIMARY KEY,
            auto_reply_enabled BOOLEAN DEFAULT 1,
            custom_message TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user_settings(telegram_id: int):
    conn = sqlite3.connect('user_settings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT auto_reply_enabled, custom_message FROM user_settings WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return bool(result[0]), result[1]
    return True, None

def save_user_settings(telegram_id: int, auto_reply_enabled: bool = None, custom_message: str = None):
    conn = sqlite3.connect('user_settings.db')
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute("SELECT auto_reply_enabled, custom_message FROM user_settings WHERE telegram_id = ?", (telegram_id,))
    existing = cursor.fetchone()
    
    enabled = auto_reply_enabled if auto_reply_enabled is not None else (existing[0] if existing else True)
    message = custom_message if custom_message is not None else (existing[1] if existing else None)

    cursor.execute('''
        INSERT INTO user_settings 
        (telegram_id, auto_reply_enabled, custom_message, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            auto_reply_enabled = ?,
            custom_message = ?,
            updated_at = ?
    ''', (telegram_id, enabled, message, now, now, enabled, message, now))
    
    conn.commit()
    conn.close()

# ==================== HANDLERLAR ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Business Auto Reply Bot*\n\n"
        "/on — Avto-javobni yoqish\n"
        "/off — Avto-javobni o'chirish\n"
        "/setmessage — Avto-xabar matnini sozlash"
    )

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_settings(update.effective_user.id, auto_reply_enabled=True)
    await update.message.reply_text("✅ Avto-javob yoqildi.")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_settings(update.effective_user.id, auto_reply_enabled=False)
    await update.message.reply_text("❌ Avto-javob o'chirildi.")

async def set_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ' '.join(context.args)
    if not text:
        await update.message.reply_text("❌ Matn yozing!\nMisol: `/setmessage Salom, hozir bandman.`")
        return
    save_user_settings(update.effective_user.id, custom_message=text)
    await update.message.reply_text(f"✅ Saqlandi:\n\n{text}")

async def business_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.business_message or not update.business_message.text:
        return

    msg = update.business_message
    user_id = msg.from_user.id
    business_conn_id = msg.business_connection_id

    auto_enabled, custom_msg = get_user_settings(user_id)

    if auto_enabled:
        reply_text = custom_msg or "Salom! Rahmat xabaringiz uchun. Tez orada javob beraman. 😊"
        await context.bot.send_message(
            chat_id=msg.chat.id,
            text=reply_text,
            business_connection_id=business_conn_id
        )

# ==================== FLASK ROUTES ====================

@app.route('/')
def home():
    return "Business Auto Reply Bot ishlamoqda! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    application.update_queue.put(update)
    return 'OK', 200

# ==================== MAIN ====================
def main():
    global application
    init_db()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("on", on_command))
    application.add_handler(CommandHandler("off", off_command))
    application.add_handler(CommandHandler("setmessage", set_message_command))

    application.add_handler(
        BusinessMessageHandler(filters.TEXT & \~filters.COMMAND, business_message_handler)
    )

    # Webhook
    print(f"🚀 Bot ishga tushdi | Port: {PORT}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"https://pychatbot-1.onrender.com/webhook"   # <-- Bu yerni o'zgartiring!
    )

if __name__ == '__main__':
    main()
