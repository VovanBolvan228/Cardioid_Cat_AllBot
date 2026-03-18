import asyncio
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

TARGET_GROUP_ID = -1003773374182 
DB_TAG = "#DATABASE_EXERCISE_BOT#"

FOOTER_TEXT = (
    "\nРасчёт по долгам происходит только при свидетелях "
    "(минимум 3 из данной группы, +1 - тот, кто делает), либо на видео!"
)

# Список упражнений, которые бот считает как ВРЕМЯ
TIME_EXERCISES = ["план", "вис"]

def to_seconds(value):
    """Превращает '3:34', '3 мин' или число в секунды."""
    if isinstance(value, int): return value
    try:
        s_val = str(value).lower().replace("мин", "").strip()
        if ":" in s_val:
            parts = s_val.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        return int(s_val)
    except: return 0

def from_seconds(total_seconds):
    """Превращает секунды в формат М:СС."""
    total_seconds = int(total_seconds)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d} мин"

# Начальные данные (уже в секундах)
INITIAL_DATA = {
    "Артём": {"отж": 175, "прис": 100, "план": 180, "вис": 360, "руб": 700},
    "Лиза": {"вис": 214, "гант": 85, "план": 171, "прис": 165},
    "Вова": {"план": 120, "гант": 50, "отж": 25, "прис": 100},
    "Настя": {"гант": 100, "отж": 100, "прис": 100},
    "Игорь": {"подт": 30, "план": 180, "прис": 100}
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

EX_MAP = {
    "отж": "отжиманий", "прис": "приседаний", "план": "планка",
    "вис": "вис", "гант": "гантели на спину (каждая рука)", 
    "подт": "подтягиваний", "руб": "рублей"
}

async def get_db_message():
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        if chat.pinned_message and DB_TAG in (chat.pinned_message.text or ""):
            return chat.pinned_message
    except: pass
    return None

async def load_data():
    msg = await get_db_message()
    if msg:
        try:
            json_part = msg.text.split("📊")[-1].strip()
            return json.loads(json_part)
        except: pass
    return INITIAL_DATA

async def save_data(data):
    lines = [f"{DB_TAG}", "<b>ДОЛГИ!!!</b>\n"]
    for name, exercises in data.items():
        ex_list = []
        for ex, val in exercises.items():
            if val == 0: continue
            label = EX_MAP.get(ex, ex)
            display_val = from_seconds(val) if ex in TIME_EXERCISES else val
            ex_list.append(f"{display_val} {label}")
        lines.append(f"<b>{name}</b> - {', '.join(ex_list) if ex_list else 'долгов нет'}")
    
    lines.append(FOOTER_TEXT)
    # Скрытый JSON для базы
    lines.append(f"\n📊 {json.dumps(data, ensure_ascii=False)}")
    
    try:
        await bot.unpin_all_chat_messages(TARGET_GROUP_ID)
        new_msg = await bot.send_message(TARGET_GROUP_ID, "\n".join(lines), parse_mode="HTML")
        await bot.pin_chat_message(TARGET_GROUP_ID, new_msg.message_id)
    except Exception as e:
        print(f"Error in save: {e}")

@dp.message(F.text.startswith("!добавить"))
async def add_person(message: types.Message):
    if message.chat.id != TARGET_GROUP_ID: return
    parts = message.text.split()
    if len(parts) > 1:
        data = await load_data()
        data[parts[1]] = {}
        await save_data(data)

@dp.message(F.text.startswith("!удалить"))
async def remove_person(message: types.Message):
    if message.chat.id != TARGET_GROUP_ID: return
    parts = message.text.split()
    if len(parts) > 1:
        data = await load_data()
        data.pop(parts[1], None)
        await save_data(data)

@dp.message(F.text.startswith("!долг"))
async def handle_debts(message: types.Message):
    if message.chat.id != TARGET_GROUP_ID: return
    parts = message.text.split()
    data = await load_data()
    name_map = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
    
    # Очистка
    if len(parts) == 3 and parts[2].lower() == "очистить":
        name = name_map.get(parts[1].upper(), parts[1])
        if name in data:
            data[name] = {}
            await save_data(data)
            return

    # Изменение долга
    if len(parts) < 4: return
    full_name = name_map.get(parts[1].upper(), parts[1])
    val = to_seconds(parts[2])
    ex = parts[3].lower()

    if full_name not in data: data[full_name] = {}
    current = to_seconds(data[full_name].get(ex, 0))
    
    if "+" in parts[0]:
        data[full_name][ex] = current + val
    else:
        data[full_name][ex] = max(0, current - val)
    
    await save_data(data)
    try: await message.delete()
    except: pass

async def handle_ping(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
