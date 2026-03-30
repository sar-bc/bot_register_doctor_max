from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import ParseMode
import os
import asyncio
from database.Database import DataBase
from dotenv import load_dotenv
from core.log import Logger
from app.user import router as user_router
from app.scheduler import BotScheduler
from app.admin import router as admin_router

# Настройка логирования
logger = Logger(__name__)

# Загружаем переменные из .env
load_dotenv()

TOKEN = os.getenv('MAX_BOT_TOKEN')

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
db = DataBase()
scheduler = None


class DependencyMiddleware:
    """Middleware для внедрения зависимостей в хендлеры"""
    async def __call__(self, handler, event, data):
        data['db'] = db
        data['scheduler'] = scheduler
        return await handler(event, data)


async def startup():
    """Инициализация при запуске"""
    global scheduler
    
    await db.create_db()
    
    await db.init_settings()
    
    # Запускаем планировщик
    scheduler = BotScheduler(bot, db)
    await scheduler.start()
    #----------------------------------
    # settings = await db.get_settings()
    # await scheduler._notify_status_change(
    #             settings.bot_active, 
    #             "System startup"
    #         )
    #----------------------------------
    await logger.info('✅ Бот запущен')

async def shutdown():
    """Очистка при остановке"""
    global scheduler
    
    await logger.info('🛑 Бот останавливается...')
    
    # Останавливаем планировщик
    if scheduler:
        await scheduler.stop()
    
    # Закрываем БД
    if db:
        await db.close()
    
    # Закрываем сессию бота
    if bot.session:
        await bot.session.close()
    
    await logger.info('✅ Бот остановлен')


async def main():
    """Главная функция"""
    # Регистрируем роутеры
    dp.include_routers(admin_router, user_router)
    
    # Добавляем middleware для зависимостей
    dp.middleware(DependencyMiddleware())
    
    # Запускаем инициализацию
    await startup()
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(shutdown())
            loop.close()
        except:
            pass
        import threading
        threading.Timer(0.5, lambda: os._exit(0)).start()