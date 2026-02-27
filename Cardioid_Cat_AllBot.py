import asyncio
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, types
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
GROUP_ID = -1003801387499 
DB_FILE = "users.txt"

bot = Bot(token=TOKEN)
dp = Dispatcher()
known_users = set()

# Загрузка пользователей из файла при старте
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        for line in f:
            if line.strip():
                known_users.add(int(line.strip()))

def save_user(user_id):
    if user_id not in known_users:
        known_users.add(user_id)
        with open(DB_FILE, "a") as f:
            f.write(f"{user_id}\n")

async def send_kv_reminder():
    try:
        if known_users:
            mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in known_users])
            text = f"📢 <b>@all ВСЕ ИГРАЕМ КВ СЕГОДНЯ!</b>{mentions}"
            await bot.send_message(GROUP_ID, text, parse_mode="HTML")
        else:
            await bot.send_message(GROUP_ID, "@all ВСЕ ИГРАЕМ КВ СЕГОДНЯ!")
    except Exception as e:
        print(f"Ошибка рассылки: {e}")

async def health_check(request):
    return web.Response(text="I am alive")

@dp.message()
async def handle_messages(message: types.Message):
    if message.from_user and not message.from_user.is_bot:
        save_user(message.from_user.id)
    
    if message.text == "/start":
        await message.answer("Я в строю! Теперь я не забуду участников даже после перезагрузки.")
    
    elif message.text and any(x in message.text.lower() for x in ["@all", "@все", "/all"]):
        if known_users:
            mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in known_users])
            await message.answer(f"📢 <b>Внимание всем!</b>{mentions}", parse_mode="HTML")
        else:
            await message.answer("Я пока никого не знаю!")

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
