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

# Список упражнений со временем
TIME_EXERCISES = ["план", "вис"]

def from_seconds(total_seconds):
    """Превращает секунды в формат М:СС."""
    ts = int(total_seconds)
    return f"{ts // 60}:{ts % 60:02d} мин"

# Начальные данные (в секундах для времени, в числах для остального)
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

async def load_data():
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        if chat.pinned_message and DB_TAG in (chat.pinned_message.text or ""):
            json_part = chat.pinned_message.text.split("📊")[-1].strip()
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
    lines.append(f"\n📊 {json.dumps(data, ensure_ascii=False)}")
    
    try:
        await bot.unpin_all_chat_messages(TARGET_GROUP_ID)
        new_msg = await bot.send_message(TARGET_GROUP_ID, "\n".join(lines), parse_mode="HTML")
        await bot.pin_chat_message(TARGET_GROUP_ID, new_msg.message_id)
    except: pass

@dp.message(F.text.startswith("!добавить"))
async def add_p(m: types.Message):
    if m.chat.id != TARGET_GROUP_ID: return
    p = m.text.split()
    if len(p) > 1:
        d = await load_data()
        d[p[1]] = d.get(p[1], {})
        await save_data(d)

@dp.message(F.text.startswith("!удалить"))
async def rem_p(m: types.Message):
    if m.chat.id != TARGET_GROUP_ID: return
    p = m.text.split()
    if len(p) > 1:
        d = await load_data()
        d.pop(p[1], None)
        await save_data(d)

@dp.message(F.text.startswith("!долг"))
async def handle_debts(m: types.Message):
    if m.chat.id != TARGET_GROUP_ID: return
    parts = m.text.split()
    data = await load_data()
    n_map = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
    
    if len(parts) == 3 and parts[2].lower() == "очистить":
        name = n_map.get(parts[1].upper(), parts[1])
        if name in data:
            data[name] = {}
            await save_data(data)
            return

    if len(parts) < 4: return
    name = n_map.get(parts[1].upper(), parts[1])
    val_raw = parts[2]
    ex = parts[3].lower()

    if name not in data: data[name] = {}

    # ПРОВЕРКА ВВОДА
    final_val = 0
    if ex in TIME_EXERCISES:
        # Для времени разрешаем 1:30 или просто секунды
        try:
            if ":" in val_raw:
                m_parts = val_raw.split(":")
                final_val = int(m_parts[0]) * 60 + int(m_parts[1])
            else:
                final_val = int(val_raw)
        except:
            return await m.answer("⚠️ Ошибка! Время пиши как 1:30 или просто секунды.")
    else:
        # Для отжиманий и прочего — только целые числа
        if ":" in val_raw:
            return await m.answer(f"⚠️ Ошибка! Для {ex} нельзя использовать формат времени (двоеточие).")
        try:
            final_val = int(val_raw)
        except:
            return await m.answer("⚠️ Ошибка! Введи целое число.")

    current = data[name].get(ex, 0)
    # Если в базе была строка (старый баг), сбрасываем в 0
    if not isinstance(current, (int, float)): current = 0
    
    if "+" in parts[0]:
        data[name][ex] = current + final_val
    else:
        data[name][ex] = max(0, current - final_val)

    await save_data(data)
    try: await m.delete()
    except: pass

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
