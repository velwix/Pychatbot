import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "7731635816:AAFIYtZfiPzw2toADnnKnl-aW72TXZ3gyZ8"

WEBHOOK_HOST = "https://pychatbot-3vzv.onrender.com"   # ← Renderdagi domeningizni yozing!
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

DB_NAME = "tg_business.db"


# ==================== DATABASE ====================
def init_db():
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO business_users (user_id, welcome_text, btn_text, btn_url)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
               welcome_text=excluded.welcome_text,
               btn_text=excluded.btn_text,
               btn_url=excluded.btn_url""",
        (user_id, text, btn_text, btn_url),
    )
    conn.commit()
    conn.close()


def save_connection(connection_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO business_users (user_id, connection_id)
           VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET connection_id=excluded.connection_id""",
        (user_id, connection_id),
    )
    conn.commit()
    conn.close()


def remove_connection(connection_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE business_users SET connection_id=NULL WHERE connection_id=?", (connection_id,))
    conn.commit()
    conn.close()


def get_settings_by_connection(connection_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT welcome_text, btn_text, btn_url, user_id FROM business_users WHERE connection_id=?",
        (connection_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return {"text": row[0], "btn_text": row[1], "btn_url": row[2], "owner_id": row[3]}
    return None


# ==================== STATES ====================
class SettingsState(StatesGroup):
    waiting_for_text = State()
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()


# ==================== HANDLERS ====================
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Salom! Men Telegram Business avto-javob botiman.\n\n"
        "📝 Mijoz yozganda boradigan xabar matnini kiriting:",
        parse_mode="Markdown"
    )
    await state.set_state(SettingsState.waiting_for_text)


@router.message(SettingsState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    await state.update_data(welcome_text=message.text)
    await message.answer("🔘 Inline tugma matnini kiriting (masalan: Katalogga o'tish):")
    await state.set_state(SettingsState.waiting_for_btn_text)


@router.message(SettingsState.waiting_for_btn_text)
async def process_btn_text(message: types.Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("🔗 Tugma bosilganda ochiladigan URL ni kiriting (https://...):")
    await state.set_state(SettingsState.waiting_for_btn_url)


@router.message(SettingsState.waiting_for_btn_url)
async def process_btn_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        return await message.answer("❌ Havola http:// yoki https:// bilan boshlanishi kerak!")

    data = await state.get_data()
    save_welcome_settings(message.from_user.id, data["welcome_text"], data["btn_text"], url)
    await state.clear()
    await message.answer("✅ Sozlamalar saqlandi!\n\nBotni Telegram Business sozlamalarida ulang.")


@router.business_connection()
async def on_business_connect(connection: types.BusinessConnection):
    if connection.is_enabled:
        save_connection(connection.id, connection.user.id)
        logging.info(f"Biznes ulandi: {connection.id}")
    else:
        remove_connection(connection.id)
        logging.info(f"Biznes uzildi: {connection.id}")


@router.business_message()
async def handle_business_message(message: types.Message):
    settings = get_settings_by_connection(message.business_connection_id)
    if not settings or message.from_user.id == settings["owner_id"]:
        return

    button = InlineKeyboardButton(text=settings["btn_text"], url=settings["btn_url"])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer(text=settings["text"], reply_markup=keyboard)


# ==================== STARTUP / SHUTDOWN ====================
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)
    init_db()
    print(f"✅ Webhook muvaffaqiyatli o‘rnatildi: {WEBHOOK_URL}")


async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    print("🛑 Webhook o‘chirildi.")


# ==================== MAIN ====================
def main():
    dp.include_router(router)

    app = web.Application()
    app["bot"] = bot

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    main()
