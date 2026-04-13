import asyncio
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import psycopg2
from psycopg2.extras import RealDictCursor

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
# Список ID чатов для ежедневной рассылки (через запятую). Например: "-1001234567890"
TARGET_GROUP_IDS = [int(x.strip()) for x in os.getenv("TARGET_GROUP_IDS", "-1003801387499").split(",") if x.strip()]
DATABASE_URL = os.environ.get("DATABASE_URL")  # обязательная переменная на Railway

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === РАБОТА С POSTGRESQL ===

def get_db_connection():
    """Создаёт соединение с PostgreSQL."""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Создаёт таблицу для участников групп, если её нет."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            chat_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def add_member(chat_id: int, user_id: int):
    """Добавляет участника в таблицу."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO group_members (chat_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (chat_id, user_id)
        )
        conn.commit()
    except Exception as e:
        print(f"Ошибка добавления участника {user_id} в чат {chat_id}: {e}")
    finally:
        cur.close()
        conn.close()

def get_all_members(chat_id: int):
    """Возвращает список user_id всех участников чата."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM group_members WHERE chat_id = %s", (chat_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]

# === ФУНКЦИЯ УВЕДОМЛЕНИЯ ПО РАСПИСАНИЮ ===

async def send_kv_reminder():
    """Отправляет напоминание во все целевые чаты, упоминая всех участников (скрытые упоминания)."""
    for chat_id in TARGET_GROUP_IDS:
        members = get_all_members(chat_id)
        if members:
            # Скрытые упоминания через \u2060
            mentions = "".join([f'<a href="tg://user?id={uid}">\u2060</a>' for uid in members])
            text = f"📢 <b>Внимание всем!</b> Сегодня играем КВ! ⚡️{mentions}"
        else:
            text = "📢 <b>Внимание всем!</b> Сегодня играем КВ! ⚡️"
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка рассылки в чат {chat_id}: {e}")

# === ОБРАБОТЧИКИ ===

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def track_and_call(m: types.Message):
    """Запоминает всех активных участников (не ботов) и обрабатывает команды @all."""
    chat_id = m.chat.id
    user_id = m.from_user.id

    if not m.from_user.is_bot:
        add_member(chat_id, user_id)

    if m.text and ("@all" in m.text.lower() or "@все" in m.text.lower()):
        members = get_all_members(chat_id)
        if members:
            mentions = "".join([f'<a href="tg://user?id={uid}">\u2060</a>' for uid in members])
            await m.answer(f"📢 <b>Внимание всем!</b> ⚡️{mentions}", parse_mode="HTML")
        else:
            await m.answer("📢 Пока нет участников для упоминания.", parse_mode="HTML")

# === ЗАПУСК ===

async def main():
    init_db()
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        send_kv_reminder,
        trigger='cron',
        day_of_week='thu,fri,sat,sun',
        hour=22,
        minute=0
    )
    scheduler.start()

    # Веб-сервер для healthcheck (требуется Railway)
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Cardioid_Cat Bot Active"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
