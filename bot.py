import sqlite3
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    BusinessMessageHandler,
    CommandHandler,
    filters,
    MessageHandler
)

# ==================== SOZLAMALAR ====================
TOKEN = "8999047254:AAFsTqX9AoNhAiSL1JjKNDC3iZFAYt4GFIc"   # <-- O'ZGARTIRING

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    return True, None  # Default: yoqilgan, custom xabar yo'q

def save_user_settings(telegram_id: int, auto_reply_enabled: bool = None, custom_message: str = None):
    conn = sqlite3.connect('user_settings.db')
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    # Mavjud ma'lumotni olish
    cursor.execute("SELECT auto_reply_enabled, custom_message FROM user_settings WHERE telegram_id = ?", (telegram_id,))
    existing = cursor.fetchone()
    
    if existing:
        enabled = auto_reply_enabled if auto_reply_enabled is not None else existing[0]
        message = custom_message if custom_message is not None else existing[1]
    else:
        enabled = auto_reply_enabled if auto_reply_enabled is not None else True
        message = custom_message

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
        "Buyruqlar:\n"
        "/on — Avto-javobni yoqish\n"
        "/off — Avto-javobni o'chirish\n"
        "/setmessage — Avto-xabarni o'zgartirish\n\n"
        "Misol: /setmessage Salom! Men hozir bandman, tez orada javob beraman."
    )

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user_settings(user_id, auto_reply_enabled=True)
    await update.message.reply_text("✅ Avto-javob yoqildi.")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user_settings(user_id, auto_reply_enabled=False)
    await update.message.reply_text("❌ Avto-javob o'chirildi.")

async def set_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = ' '.join(context.args)
    
    if not text:
        await update.message.reply_text(
            "❌ Xabar matnini yozing!\n\n"
            "Misol: `/setmessage Salom! Rahmat, tez orada javob beraman.`"
        )
        return
    
    save_user_settings(user_id, custom_message=text)
    await update.message.reply_text(f"✅ Avto-xabar saqlandi:\n\n{text}")

async def business_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.business_message or not update.business_message.text:
        return

    message = update.business_message
    user_id = message.from_user.id
    business_connection_id = message.business_connection_id

    auto_enabled, custom_msg = get_user_settings(user_id)

    if auto_enabled:
        reply_text = custom_msg or "Salom! Rahmat xabaringiz uchun. Tez orada javob beraman. 😊"
        
        await context.bot.send_message(
            chat_id=message.chat.id,
            text=reply_text,
            business_connection_id=business_connection_id
        )

# ==================== MAIN ====================
def main():
    init_db()
    
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("on", on_command))
    application.add_handler(CommandHandler("off", off_command))
    application.add_handler(CommandHandler("setmessage", set_message_command))

    # Business xabarlarni qayta ishlash
    application.add_handler(
        BusinessMessageHandler(filters.TEXT & \~filters.COMMAND, business_message_handler)
    )

    print("🚀 Business Auto Reply Bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
