import asyncio
import os
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

# Глобальная переменная для ID (в идеале её стоит хранить в файле или БД, 
# но для Render пока оставим в памяти — до перезагрузки сервера)
TARGET_GROUP_ID = None 
DB_TAG = "#DATABASE_EXERCISE_BOT#"

bot = Bot(token=TOKEN)
dp = Dispatcher()

NAME_MAP = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
EX_MAP = {
    "отж": "отжиманий", "прис": "приседаний", "план": "планки",
    "вис": "вис", "гант": "гантели на спину", "подт": "подтягиваний"
}

# --- Вспомогательные функции ---

async def get_db_message():
    if not TARGET_GROUP_ID: return None
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        pinned = chat.pinned_message
        if pinned and DB_TAG in (pinned.text or ""):
            return pinned
    except:
        return None
    return None

async def load_data():
    msg = await get_db_message()
    if msg:
        try:
            json_part = msg.text.split("📊")[-1].strip()
            return json.loads(json_part)
        except:
            return {}
    return {}

async def save_data(data):
    if not TARGET_GROUP_ID: return
    lines = ["<b>📊 АКТУАЛЬНЫЕ ДОЛГИ</b>\n"]
    has_debts = False
    for name, exercises in data.items():
        ex_list = [f"{val} {EX_MAP.get(ex, ex)}" for ex, val in exercises.items() if val > 0]
        if ex_list:
            lines.append(f"• <b>{name}</b>: {', '.join(ex_list)}")
            has_debts = True
    
    if not has_debts: lines.append("Все долги закрыты! Красавчики.")
    lines.extend([f"\n{DB_TAG}", f"\n📊 {json.dumps(data, ensure_ascii=False)}"])
    
    text = "\n".join(lines)
    msg = await get_db_message()
    
    if msg:
        await bot.edit_message_text(text, TARGET_GROUP_ID, msg.message_id, parse_mode="HTML")
    else:
        new_msg = await bot.send_message(TARGET_GROUP_ID, text, parse_mode="HTML")
        await bot.pin_chat_message(TARGET_GROUP_ID, new_msg.message_id)

# --- ОБРАБОТЧИКИ ---

# 1. ПРИВЯЗКА ЧАТА (только для админов)
@dp.message(F.text == "!привязать_тренировки")
async def cmd_link_chat(message: types.Message):
    global TARGET_GROUP_ID
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    
    if member.status in ["creator", "administrator"]:
        TARGET_GROUP_ID = message.chat.id
        await message.answer(f"✅ Чат привязан! ID: {TARGET_GROUP_ID}\nТеперь команды долгов работают только здесь.")
    else:
        await message.reply("❌ Эту команду может выполнить только админ.")

# 2. @ALL / @ВСЕ (РАБОТАЮТ ВЕЗДЕ)
@dp.message(F.text.lower().contains("@all") | F.text.lower().contains("@все"))
async def call_everyone(message: types.Message):
    await message.answer("📢 <b>Внимание всем!</b> ⚡️", parse_mode="HTML")

# 3. ДОЛГИ (ТОЛЬКО В ПРИВЯЗАННОМ ЧАТЕ)
@dp.message(lambda msg: TARGET_GROUP_ID and msg.chat.id == TARGET_GROUP_ID, 
            F.text.startswith(("!долг+", "!долг-")))
async def handle_debts(message: types.Message):
    parts = message.text.split()
    if len(parts) < 4: return

    action, name_init, val_str, ex_code = parts[0], parts[1].upper(), parts[2], parts[3].lower()
    try:
        val = int(val_str)
    except: return

    full_name = NAME_MAP.get(name_init)
    if not full_name: return

    data = await load_data()
    if full_name not in data: data[full_name] = {}
    current = data[full_name].get(ex_code, 0)
    data[full_name][ex_code] = (current + val) if "+" in action else max(0, current - val)

    await save_data(data)
    await message.answer("✅ Таблица обновлена.")

# --- СИСТЕМНОЕ ---

async def send_kv_reminder():
    if TARGET_GROUP_ID:
        try:
            await bot.send_message(TARGET_GROUP_ID, "📢 <b>Внимание всем! ВСЕ ИГРАЕМ КВ СЕГОДНЯ!</b>", parse_mode="HTML")
        except: pass

async def health_check(request):
    return web.Response(text="Bot is running")

async def main():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_kv_reminder, 'cron', day_of_week='thu,fri,sat,sun', hour=21, minute=0)
    scheduler.start()

    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
