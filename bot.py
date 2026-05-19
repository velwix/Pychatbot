import logging
import sys
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart

# 1. Telegram Bot Token va Webhook Sozlamalari
API_TOKEN = "7731635816:AAH3Lk5Xchn_FRdGUunCLtSwCpVwAk1wOl0"  # Bu yerga bot tokeningizni yozing
WEBHOOK_HOST = "https://pychatbot-3vzv.onrender.com"  # SSL (https) ulanishli domeningiz
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Webhook server porti
WEB_SERVER_HOST = "127.0.0.1"
WEB_SERVER_PORT = 8080

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Bot va Dispatcher obyektlari
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==========================================
# 2. BAZA BILAN ISHLASH (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()
    
    # Biznesmenlar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT
    )""")
    
    # Ulanishlar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_connections (
        connection_id TEXT PRIMARY KEY,
        user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(telegram_id)
    )""")
    
    # Avto-javoblar jadvali (Siz so'ragan trigger va xabar saqlash uchun)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_replies (
        user_id INTEGER PRIMARY KEY,
        trigger_keyword TEXT,
        reply_text TEXT
    )""")
    conn.commit()
    conn.close()

# Ma'lumotlarni bazaga yozish va o'qish funksiyalari
def save_user(user_id, username):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def save_settings(user_id, trigger, reply):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO auto_replies (user_id, trigger_keyword, reply_text) VALUES (?, ?, ?)", (user_id, trigger, reply))
    conn.commit()
    conn.close()

def save_connection(connection_id, user_id):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO business_connections (connection_id, user_id) VALUES (?, ?)", (connection_id, user_id))
    conn.commit()
    conn.close()

def get_reply_by_connection(connection_id, client_text):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()
    # Connection ID orqali biznesmenning sozlamasini olamiz
    cursor.execute("""
        SELECT ar.trigger_keyword, ar.reply_text 
        FROM business_connections bc
        JOIN auto_replies ar ON bc.user_id = ar.user_id
        WHERE bc.connection_id = ?
    """, (connection_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        trigger, reply = row[0], row[1]
        # Agar mijoz yozgan xabarda biznesmen o'rnatgan trigger so'z qatnashgan bo'lsa
        if trigger.lower() in client_text.lower():
            return reply
    return None


# ==========================================
# 3. BOT HANDLERLARI (Mantiq qismi)
# ==========================================

# /start bosilganda
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    save_user(message.from_user.id, message.from_user.username)
    
    # Namunaviy trigger va xabarni avtomatik saqlaymiz (Xohlasangiz buni FSM orqali input qildirish mumkin)
    # Biznesmen profilida mijoz "salom" deb yozsa, bot javob qaytaradi
    save_settings(message.from_user.id, "salom", "Assalomu alaykum! Biznes botimizga xush kelibsiz. Tez orada javob beramiz.")
    
    text = (
        "👋 Salom! Biznes platformaga xush kelibsiz.\n\n"
        "⚙️ Siz uchun standart sozlama saqlandi:\n"
        "🔹 Trigger so'z: *salom*\n"
        "🔹 Javob matni: *Assalomu alaykum! Biznes botimizga xush kelibsiz...*\n\n"
        "🔌 Endi ushbu botni shaxsiy akkauntingizga ulash uchun Telegram Sozlamalari -> Telegram Business -> Chatbots bo'limiga kiring va ushbu botni tanlang."
    )
    await message.answer(text, parse_mode="Markdown")


# Biznesmen shaxsiy akkauntini botga ulaganida (business_connection yangilanishi)
@dp.business_connection()
async def handle_business_connection(connection: types.BusinessConnection):
    if connection.is_enabled:
        # Ulanish muvaffaqiyatli bo'lsa bazaga saqlaymiz
        save_connection(connection.id, connection.user_id)
        
        # Biznesmenga bot orqali xabar yuboramiz
        try:
            await bot.send_message(
                chat_id=connection.user_id,
                text="✅ **Muvaffaqiyatli ulandi!**\nSizning shaxsiy akkauntingiz platformaga ulandi. Endi mijozlaringiz yozganda bot sizning nomingizdan javob qaytaradi.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Biznesmenga bildirishnoma yuborib bo'lmadi: {e}")


# Biznesmenning shaxsiy akkauntiga mijoz xabar yozganda
@dp.business_message()
async def handle_business_message(message: types.Message):
    connection_id = message.business_connection_id
    client_chat_id = message.chat.id
    client_text = message.text if message.text else ""
    
    # Bazadan ushbu ulanishga mos keladigan avto-javobni qidiramiz
    reply_text = get_reply_by_connection(connection_id, client_text)
    
    if reply_text:
        try:
            # Xabarni biznesmen nomidan mijozga yuborish
            await bot.send_message(
                chat_id=client_chat_id,
                text=reply_text,
                business_connection_id=connection_id  # ENG MUHIM PARAMETR
            )
            logging.info(f"Biznesmen nomidan {client_chat_id} ga avto-javob yuborildi.")
        except Exception as e:
            logging.error(f"Biznesmen nomidan xabar yuborishda xatolik: {e}")


# ==========================================
# 4. WEBHOOK SERVER VA ISHGA TUSHIRISH
# ==========================================

async def on_startup(app):
    # Bazani yaratish
    init_db()
    # Telegramga webhook manzilini o'rnatish
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")

async def on_shutdown(app):
    # Webhookni tozalash va sessiyani yopish
    await bot.delete_webhook()
    await bot.session.close()

# Webhook so'rovlarini qabul qiluvchi aiohttp handler
async def handle_webhook(request):
    url = str(request.url)
    if API_TOKEN in url:
        body = await request.text()
        update = types.Update.model_validate_json(body)
        await dp.feed_update(bot, update)
        return web.Response(text="OK")
    return web.Response(text="Forbidden", status=403)

def main():
    app = web.Application()
    # Webhook yo'lini ruterga qo'shish
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    
    # Startup va Shutdown hodisalari
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Serverni ishga tushirish
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
