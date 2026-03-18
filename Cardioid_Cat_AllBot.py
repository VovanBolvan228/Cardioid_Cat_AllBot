import asyncio
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
SETTINGS_FILE = "settings.json"
TARGET_GROUP_ID = None 
DB_TAG = "#DATABASE_EXERCISE_BOT#"

bot = Bot(token=TOKEN)
dp = Dispatcher()

NAME_MAP = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
EX_MAP = {"отж": "отжиманий", "прис": "приседаний", "план": "планки", "вис": "вис", "гант": "гантели на спину", "подт": "подтягиваний"}

# --- Файловая память ---
def load_settings():
    global TARGET_GROUP_ID
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                TARGET_GROUP_ID = data.get("target_group_id")
                print(f"!!! БОТ ЗАГРУЖЕН. ЦЕЛЕВОЙ ЧАТ: {TARGET_GROUP_ID}")
        except: pass

def save_settings(group_id):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"target_group_id": group_id}, f)

# --- Работа с БД (Закрепом) ---
async def get_db_message():
    if not TARGET_GROUP_ID: return None
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        pinned = chat.pinned_message
        if pinned and DB_TAG in (pinned.text or ""):
            return pinned
    except Exception as e:
        print(f"Ошибка поиска закрепа: {e}")
    return None

async def load_data():
    msg = await get_db_message()
    if msg:
        try:
            json_part = msg.text.split("📊")[-1].strip()
            return json.loads(json_part)
        except: return {}
    return {}

async def save_data(data):
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

# 1. Привязка (работает везде)
@dp.message(F.text == "!привязать_тренировки")
async def cmd_link_chat(message: types.Message):
    global TARGET_GROUP_ID
    TARGET_GROUP_ID = message.chat.id
    save_settings(TARGET_GROUP_ID)
    await message.answer(f"✅ Чат привязан!\nID: {TARGET_GROUP_ID}\nПроверьте, что в закрепе есть тег {DB_TAG}")

# 2. @all (работает везде)
@dp.message(F.text.lower().contains("@all") | F.text.lower().contains("@все"))
async def call_everyone(message: types.Message):
    await message.answer("📢 <b>Внимание всем!</b> ⚡️", parse_mode="HTML")

# 3. ДОЛГИ (Улучшенный фильтр)
@dp.message(F.text.startswith("!долг"))
async def handle_debts(message: types.Message):
    # Если чат не тот — молчим
    if TARGET_GROUP_ID and message.chat.id != TARGET_GROUP_ID:
        return

    print(f"Получена команда: {message.text}") # Для логов Render
    parts = message.text.split()
    if len(parts) < 4: 
        return await message.answer("Ошибка! Формат: !долг+ А 50 отж")

    action, name_init, val_str, ex_code = parts[0], parts[1].upper(), parts[2], parts[3].lower()
    
    try:
        val = int(val_str)
    except: return

    full_name = NAME_MAP.get(name_init)
    if not full_name:
        return await message.answer(f"Имя '{name_init}' не найдено.")

    data = await load_data()
    if full_name not in data: data[full_name] = {}
    curr = data[full_name].get(ex_code, 0)
    data[full_name][ex_code] = (curr + val) if "+" in action else max(0, curr - val)
    
    await save_data(data)
    await message.answer(f"✅ Обновлено для {full_name}. Проверьте закреп!")

# --- СЕРВЕР ---
async def health_check(request): return web.Response(text="Bot is running")

async def main():
    load_settings()
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
