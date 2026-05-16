import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Telegram Bot Tokeningizni yozing
BOT_TOKEN = "7731635816:AAFIYtZfiPzw2toADnnKnl-aW72TXZ3gyZ8"

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcherlarni yaratish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

DB_NAME = "tg_business.db"


# 1. MA'LUMOTLAR BAZASI BILAN ISHLASH (SQLite)
def init_db():
    """Ma'lumotlar bazasi va jadvallarni yaratish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_users (
            user_id INTEGER PRIMARY KEY,
            connection_id TEXT,
            welcome_text TEXT,
            btn_text TEXT,
            btn_url TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_welcome_settings(user_id, text, btn_text, btn_url):
    """Biznes egasining avto-javob sozlamalarini saqlash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO business_users (user_id, welcome_text, btn_text, btn_url)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            welcome_text=excluded.welcome_text,
            btn_text=excluded.btn_text,
            btn_url=excluded.btn_url
    """,
        (user_id, text, btn_text, btn_url),
    )
    conn.commit()
    conn.close()


def save_connection(connection_id, user_id):
    """Telegram Business ulanish ID sini bazaga saqlash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO business_users (user_id, connection_id)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET connection_id=excluded.connection_id
    """,
        (user_id, connection_id),
    )
    conn.commit()
    conn.close()


def remove_connection(connection_id):
    """O'chirilgan ulanishni tozalash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE business_users SET connection_id=NULL WHERE connection_id=?",
        (connection_id,),
    )
    conn.commit()
    conn.close()


def get_settings_by_connection(connection_id):
    """Ulanish ID si bo'yicha sozlamalarni olish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT welcome_text, btn_text, btn_url, user_id FROM business_users WHERE connection_id=?",
        (connection_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:  # text mavjud bo'lsa
        return {
            "text": row[0],
            "btn_text": row[1],
            "btn_url": row[2],
            "owner_id": row[3],
        }
    return None


# 2. FSM (STATE) - BIZNES EGASI SOZLAMALARI UCHUN
class SettingsState(StatesGroup):
    waiting_for_text = State()
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()


# 3. BOT BUYRUQLARI VA DIALOG QISMI
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        "👋 Salom! Men Telegram Business avto-javob botiman.\n\n"
        "Mijozlaringiz uchun avto-xabar matnini sozlashni boshlaymiz.\n"
        "📝 **Mijoz yozganda boradigan xabar matnini kiriting:**"
    )
    await message.answer(text, parse_mode="Markdown")
    await state.set_state(SettingsState.waiting_for_text)


@router.message(SettingsState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    await state.update_data(welcome_text=message.text)
    await message.answer("🔘 Endi inline **tugma matnini** kiriting (masalan: `Katalogga o'tish`):", parse_mode="Markdown")
    await state.set_state(SettingsState.waiting_for_btn_text)


@router.message(SettingsState.waiting_for_btn_text)
async def process_btn_text(message: types.Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("🔗 Endi tugma bosilganda ochiladigan **veb-sayt havolasini (URL)** kiriting (masalan: `https://paxsa.uz`):", parse_mode="Markdown")
    await state.set_state(SettingsState.waiting_for_btn_url)


@router.message(SettingsState.waiting_for_btn_url)
async def process_btn_url(message: types.Message, state: FSMContext):
    if not message.text.startswith(("http://", "https://")):
        await message.answer("❌ Xato! Havola `https://` yoki `http://` bilan boshlanishi shart. Qaytadan kiriting:")
        return

    data = await state.get_data()
    save_welcome_settings(
        user_id=message.from_user.id,
        text=data["welcome_text"],
        btn_text=data["btn_text"],
        btn_url=message.text,
    )
    await state.clear()

    success_text = (
        "✅ Sozlamalar muvaffaqiyatli saqlandi!\n\n"
        "⚠️ **MUHIM BOSQICH:**\n"
        "Bot mijozlaringizga javob berishi uchun uni Telegram Business hisobingizga ulashingiz kerak:\n"
        "1️⃣ Telegram sozlamalariga kiring (`Settings` -> `Telegram Business` -> `Chatbots` / `Чат-боты`).\n"
        f"2️⃣ Ushbu botni (`@{ (await bot.get_me()).username }`) ro'yxatdan tanlang va unga ruxsat bering."
    )
    await message.answer(success_text, parse_mode="Markdown")


# 4. TELEGRAM BUSINESS HODISALARINI TUTISH
@router.business_connection()
async def on_business_connect(connection: types.BusinessConnection):
    """Biznes egasi botni o'z profiliga ulaganda yoki o'chirganda ishlaydi"""
    if connection.is_enabled:
        save_connection(connection.id, connection.user.id)
        logging.info(f"Biznes profil ulandi: {connection.id} | User: {connection.user.id}")
    else:
        remove_connection(connection.id)
        logging.info(f"Biznes profil uzildi: {connection.id}")


@router.business_message()
async def handle_business_message(message: types.Message):
    """Biznes profiliga kelgan barcha xabarlarni tekshirish va javob berish"""
    connection_id = message.business_connection_id

    # Bazadan shu ulanishga mos sozlamalarni qidiramiz
    settings = get_settings_by_connection(connection_id)

    if settings:
        # Xabar yozgan odam biznes egasining o'zi bo'lsa - bot JAVOB BERMAYDI
        if message.from_user.id == settings["owner_id"]:
            logging.info("Xabarni biznes egasining o'zi yozdi. Avto-javob bekor qilindi.")
            return

        # Agar yozgan odam mijoz bo'lsa - unga avto-javob yuboramiz
        button = InlineKeyboardButton(text=settings["btn_text"], url=settings["btn_url"])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

        await message.answer(text=settings["text"], reply_markup=keyboard)
        logging.info(f"Mijozga avto-javob yuborildi. Connection ID: {connection_id}")


# 5. BOTNI ISHGA TUSHIRISH
async def main():
    init_db()  # Bazani tayyorlash
    dp.include_router(router)
    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
