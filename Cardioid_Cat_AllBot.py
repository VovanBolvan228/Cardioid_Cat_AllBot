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

# АКТУАЛЬНЫЕ НАЧАЛЬНЫЕ ДАННЫЕ
INITIAL_DATA = {
    "Артём": {"отж": 175, "прис": 100, "план": "3 мин", "вис": "6 мин", "руб": 700},
    "Лиза": {"вис": "3:34 мин", "гант": 85, "план": "2:51 мин", "прис": 165},
    "Вова": {"план": "2 мин", "гант": 50, "отж": 25, "прис": 100},
    "Настя": {"гант": 100, "отж": 100, "прис": 100},
    "Игорь": {"подт": 30, "план": "3 мин", "прис": 100}
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Словарь для расшифровки кодов в красивые названия
EX_MAP = {
    "отж": "отжиманий", "прис": "приседаний", "план": "планка",
    "вис": "вис", "гант": "гантели на спину (каждая рука)", 
    "подт": "подтягиваний", "руб": "рублей"
}

async def get_db_message():
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        pinned = chat.pinned_message
        if pinned and DB_TAG in (pinned.text or ""):
            return pinned
    except: return None

async def load_data():
    msg = await get_db_message()
    if msg:
        try:
            json_part = msg.text.split("📊")[-1].strip()
            return json.loads(json_part)
        except: return INITIAL_DATA
    return INITIAL_DATA

async def save_data(data):
    lines = [f"{DB_TAG}", "<b>ДОЛГИ!!!</b>\n"]
    
    for name, exercises in data.items():
        ex_list = []
        for ex, val in exercises.items():
            label = EX_MAP.get(ex, ex)
            if val != 0: # Не выводим обнуленные позиции
                ex_list.append(f"{val} {label}")
        
        if ex_list:
            lines.append(f"<b>{name}</b> - {', '.join(ex_list)}")
        else:
            lines.append(f"<b>{name}</b> - долгов нет")

    lines.append(FOOTER_TEXT)
    lines.append(f"\n📊 {json.dumps(data, ensure_ascii=False)}")
    
    text = "\n".join(lines)
    
    try:
        await bot.unpin_all_chat_messages(TARGET_GROUP_ID)
        new_msg = await bot.send_message(TARGET_GROUP_ID, text, parse_mode="HTML")
        await bot.pin_chat_message(TARGET_GROUP_ID, new_msg.message_id)
    except Exception as e:
        print(f"Ошибка закрепа: {e}")

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(F.text.lower().contains("@all") | F.text.lower().contains("@все"))
async def call_everyone(message: types.Message):
    await message.answer("📢 <b>Внимание всем!</b> ⚡️", parse_mode="HTML")

# Добавление человека: !добавить Гена
@dp.message(F.text.startswith("!добавить"))
async def add_person(message: types.Message):
    if message.chat.id != TARGET_GROUP_ID: return
    parts = message.text.split()
    if len(parts) < 2: return
    
    name = parts[1]
    data = await load_data()
    if name not in data:
        data[name] = {}
        await save_data(data)
        await message.answer(f"✅ {name} добавлен в список.")
    else:
        await message.answer(f"⚠️ {name} уже есть в списке.")

# Удаление человека: !удалить Гена
@dp.message(F.text.startswith("!удалить"))
async def remove_person(message: types.Message):
    if message.chat.id != TARGET_GROUP_ID: return
    parts = message.text.split()
    if len(parts) < 2: return
    
    name = parts[1]
    data = await load_data()
    # Ищем имя (с учетом регистра или без)
    found_name = next((k for k in data.keys() if k.lower() == name.lower()), None)
    
    if found_name:
        del data[found_name]
        await save_data(data)
        await message.answer(f"❌ {found_name} удален из списка.")
    else:
        await message.answer(f"⚠️ Имя {name} не найдено.")

# Управление долгами
@dp.message(F.text.startswith("!долг"))
async def handle_debts(message: types.Message):
    if message.chat.id != TARGET_GROUP_ID: return
    parts = message.text.split()
    
    # Проверка на очистку: !долг- А очистить
    if len(parts) == 3 and parts[0] == "!долг-" and parts[2].lower() == "очистить":
        name_input = parts[1].upper()
        name_map = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
        full_name = name_map.get(name_input, parts[1])
        
        data = await load_data()
        if full_name in data:
            data[full_name] = {}
            await save_data(data)
            return await message.answer(f"🧹 Все долги {full_name} очищены.")

    if len(parts) < 4: return

    action, name_init, val_str, ex_code = parts[0], parts[1].upper(), parts[2], parts[3].lower()
    name_map = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
    full_name = name_map.get(name_init, parts[1])
    
    try:
        val = int(val_str)
    except: return

    data = await load_data()
    if full_name not in data: data[full_name] = {}
    
    current = data[full_name].get(ex_code, 0)
    if not isinstance(current, int): current = 0 
    
    if "+" in action:
        data[full_name][ex_code] = current + val
    else:
        data[full_name][ex_code] = max(0, current - val)

    await save_data(data)
    try: await message.delete()
    except: pass

async def health_check(request): return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
