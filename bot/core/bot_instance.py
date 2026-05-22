from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TOKEN')

# Глобальный экземпляр бота
bot_instance = None

def get_bot() -> Bot:
    global bot_instance
    if bot_instance is None:
        bot_instance = Bot(
            token=TOKEN, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    return bot_instance

async def close_bot():
    global bot_instance
    if bot_instance:
        await bot_instance.session.close()
        bot_instance = None
        