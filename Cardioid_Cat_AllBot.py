import asyncio, os, json
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
TARGET_GROUP_ID = -1003773374182 
DB_TAG = "#DATABASE_EXERCISE_BOT#"

TIME_EXERCISES = ["план", "вис"]
EX_MAP = {"отж": "отжиманий", "прис": "приседаний", "план": "планка", "вис": "вис", "гант": "гантели", "подт": "подтягиваний", "руб": "рублей"}

def force_int(val):
    """Превращает что угодно (даже '3 мин' или None) в число без ошибок."""
    try:
        if isinstance(val, int): return val
        s = str(val or "0").lower().replace("мин", "").replace("сек", "").strip()
        if ":" in s:
            p = s.split(":")
            return int(p[0]) * 60 + int(p[1])
        return int(float(s))
    except: return 0

def format_val(v, ex):
    if ex in TIME_EXERCISES:
        v = force_int(v)
        return f"{v // 60}:{v % 60:02d} мин"
    return str(force_int(v))

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def save_data(data):
    lines = [DB_TAG, "<b>ДОЛГИ!!!</b>\n"]
    for name, exs in data.items():
        res = [f"{format_val(v, e)} {EX_MAP.get(e, e)}" for e, v in exs.items() if force_int(v) > 0]
        lines.append(f"<b>{name}</b> - {', '.join(res) if res else 'долгов нет'}")
    
    # Очищаем JSON перед сохранением, чтобы там были только чистые числа
    clean_db = {n: {e: force_int(v) for e, v in ex_dict.items()} for n, ex_dict in data.items()}
    lines.append(f"\n📊 {json.dumps(clean_db, ensure_ascii=False)}")
    
    try:
        await bot.unpin_all_chat_messages(TARGET_GROUP_ID)
        msg = await bot.send_message(TARGET_GROUP_ID, "\n".join(lines), parse_mode="HTML")
        await bot.pin_chat_message(TARGET_GROUP_ID, msg.message_id)
    except: pass

async def load_data():
    try:
        chat = await bot.get_chat(TARGET_GROUP_ID)
        if chat.pinned_message and DB_TAG in chat.pinned_message.text:
            return json.loads(chat.pinned_message.text.split("📊")[-1])
    except: pass
    return {} # Если база сломана, просто вернем пустую

@dp.message(F.text.startswith("!долг"))
async def handle(m: types.Message):
    if m.chat.id != TARGET_GROUP_ID: return
    p = m.text.split()
    if len(p) < 4: return
    
    n_map = {"А": "Артём", "Л": "Лиза", "В": "Вова", "Н": "Настя", "И": "Игорь"}
    name = n_map.get(p[1].upper(), p[1])
    val_str, ex = p[2], p[3].lower()
    
    # Жесткая проверка на формат времени для обычных упражнений
    if ex not in TIME_EXERCISES and ":" in val_str:
        return await m.answer(f"❌ Для {ex} нельзя использовать формат времени!")

    data = await load_data()
    if name not in data: data[name] = {}
    
    current = force_int(data[name].get(ex, 0))
    new_val = force_int(val_str)
    
    data[name][ex] = (current + new_val) if "+" in p[0] else max(0, current - new_val)
    await save_data(data)
    try: await m.delete()
    except: pass

@dp.message(F.text == "@все" or F.text == "@all")
async def call_all(m: types.Message):
    await m.answer("📢 <b>Внимание всем!</b> ⚡️", parse_mode="HTML")

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
