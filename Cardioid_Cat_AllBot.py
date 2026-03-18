import asyncio
import os
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
SETTINGS_FILE = "settings.json"

# Переменная для ID, которая подгрузится из файла
TARGET_GROUP_ID = None 
DB_TAG = "#DATABASE_EXERCISE_BOT#"

bot = Bot(token=TOKEN)
dp = Dispatcher()

NAME_MAP = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
EX_MAP = {
    "отж": "отжиманий", "прис": "приседаний", "план": "планки",
    "вис": "вис", "гант": "гантели на спину", "подт": "подтягиваний"
}

# --- Логика работы с файлом настроек ---

def load_settings():
    global TARGET_GROUP_ID
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                TARGET_GROUP_ID = data.get("target_group_id")
        except:
            pass

def save_settings(group_id):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"target_group_id": group_id}, f)

# --- Вспомогательные функции для БД ---

async def get_db_message():
    if not TARGET_GROUP_ID: return None
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        pinned = chat.pinned_message
        if pinned and DB_TAG in (pinned.text or ""):
            return pinned
    except:
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

# Привязка чата (только для админов)
@dp.message(F.text == "!привязать_тренировки")
async def cmd_link_chat(message: types.Message):
    global TARGET_GROUP_ID
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ["creator", "administrator"]:
        TARGET_GROUP_ID = message.chat.id
        save_settings(TARGET_GROUP_ID) # Сохраняем в файл!
        await message.answer(f"✅ Чат привязан навсегда!\nID: {TARGET_GROUP_ID}")
    else:
        await message.reply("❌ Команда только для админов.")

# @ALL работает везде
@dp.message(F.text.lower().contains("@all") | F.text.lower().contains("@все"))
async def call_everyone(message: types.Message):
    await message.answer("📢 <b>Внимание всем!</b> ⚡️", parse_mode="HTML")

# Долги работают только в привязанном чате
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
    curr = data[full_name].get(ex_code, 0)
    data[full_name][ex_code] = (curr + val) if "+" in action else max(0, curr - val)
    await save_data(data)
    await message.answer("✅ Готово.")

# --- ЗАПУСК ---

async def health_check(request):
    return web.Response(text="Bot is running")

async def main():
    load_settings() # Загружаем ID из файла при старте
    
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(lambda: bot.send_message(TARGET_GROUP_ID, "📢 ВСЕ ИГРАЕМ КВ!"), 
                      'cron', day_of_week='thu,fri,sat,sun', hour=21, minute=0)
    scheduler.start()

    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
