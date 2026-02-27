import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiohttp import web

# Получаем настройки из Render
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TOKEN)
dp = Dispatcher()
known_users = set()

# Хендлер для упоминаний
@dp.message()
async def handle_messages(message: types.Message):
    known_users.add(message.from_user.id)
    
    if message.text == "/start":
        await message.answer("Бот активен! Напиши что угодно, а затем @all")
    
    elif message.text and any(x in message.text.lower() for x in ["@all", "@все", "/all"]):
        if known_users:
            mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in known_users])
            await message.answer(f"📢 <b>Внимание!</b>{mentions}", parse_mode="HTML")
        else:
            await message.answer("Сначала напишите что-нибудь обычное, чтобы я вас запомнил!")

# Веб-сервер для "здоровья" Render
async def health_check(request):
    return web.Response(text="I am alive")

async def main():
    # Создаем веб-приложение
    app = web.Application()
    app.router.add_get("/", health_check)
    
    # Запускаем сервер параллельно с ботом
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    print(f"Сервер запущен на порту {PORT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
