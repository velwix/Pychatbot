import asyncio
import logging
import sys
import sqlite3

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramRetryAfter

API_TOKEN = "7731635816:AAH3Lk5Xchn_FRdGUunCLtSwCpVwAk1wOl0"

WEBHOOK_HOST = "https://pychatbot-3vzv.onrender.com"
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 10000

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=API_TOKEN)

dp = Dispatcher(
    storage=MemoryStorage()
)


def init_db():
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_connections (
        connection_id TEXT PRIMARY KEY,
        user_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_replies (
        user_id INTEGER PRIMARY KEY,
        trigger_keyword TEXT,
        reply_text TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_user(user_id, username):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
        (user_id, username)
    )

    conn.commit()
    conn.close()


def save_settings(user_id, trigger, reply):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR REPLACE INTO auto_replies (user_id, trigger_keyword, reply_text) VALUES (?, ?, ?)",
        (user_id, trigger, reply)
    )

    conn.commit()
    conn.close()


def save_connection(connection_id, user_id):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR REPLACE INTO business_connections (connection_id, user_id) VALUES (?, ?)",
        (connection_id, user_id)
    )

    conn.commit()
    conn.close()


def get_reply_by_connection(connection_id, client_text):
    conn = sqlite3.connect("business_saas.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ar.trigger_keyword, ar.reply_text
        FROM business_connections bc
        JOIN auto_replies ar ON bc.user_id = ar.user_id
        WHERE bc.connection_id = ?
    """, (connection_id,))

    row = cursor.fetchone()

    conn.close()

    if row:
        trigger = row[0]
        reply = row[1]

        if trigger.lower() in client_text.lower():
            return reply

    return None


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    save_user(
        message.from_user.id,
        message.from_user.username
    )

    save_settings(
        message.from_user.id,
        "salom",
        "Assalomu alaykum! Tez orada javob beramiz."
    )

    text = (
        "👋 Salom!\n\n"
        "Bot muvaffaqiyatli ishga tushdi.\n\n"
        "Telegram Business -> Chatbots orqali botni ulang."
    )

    await message.answer(text)


@dp.business_connection()
async def handle_business_connection(connection: types.BusinessConnection):
    if connection.is_enabled:
        save_connection(
            connection.id,
            connection.user_id
        )

        try:
            await bot.send_message(
                chat_id=connection.user_id,
                text="✅ Business account muvaffaqiyatli ulandi."
            )

        except Exception as e:
            logging.error(e)


@dp.business_message()
async def handle_business_message(message: types.Message):
    connection_id = message.business_connection_id

    client_chat_id = message.chat.id

    client_text = message.text or ""

    reply_text = get_reply_by_connection(
        connection_id,
        client_text
    )

    if reply_text:
        try:
            await bot.send_message(
                chat_id=client_chat_id,
                text=reply_text,
                business_connection_id=connection_id
            )

            logging.info(
                f"Reply sent to {client_chat_id}"
            )

        except Exception as e:
            logging.error(e)


async def on_startup(app):
    init_db()

    try:
        webhook_info = await bot.get_webhook_info()

        if webhook_info.url != WEBHOOK_URL:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                drop_pending_updates=True
            )

        logging.info(
            f"Webhook active: {WEBHOOK_URL}"
        )

    except TelegramRetryAfter as e:
        logging.error(
            f"Retry after {e.retry_after}"
        )

        await asyncio.sleep(
            e.retry_after
        )


async def on_shutdown(app):
    await bot.session.close()


async def handle_webhook(request):
    body = await request.text()

    update = types.Update.model_validate_json(
        body
    )

    await dp.feed_update(
        bot,
        update
    )

    return web.Response(text="OK")


def main():
    app = web.Application()

    app.router.add_post(
        WEBHOOK_PATH,
        handle_webhook
    )

    app.on_startup.append(
        on_startup
    )

    app.on_shutdown.append(
        on_shutdown
    )

    web.run_app(
        app,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
    )


if __name__ == "__main__":
    main()
