from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from typing import Callable, Dict, Any, Awaitable, Union
from database.Database import DataBase
from core.log import Logger
from core.dictionary import *

logger = Logger(__name__)


class BotStatusMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable,
        event: Union[Message, CallbackQuery, Update],
        data: Dict[str, Any]
    ) -> Any:
        db = DataBase()
        user_id = None
        original_event = event  # Сохраняем оригинальное событие

        try:
            # Если пришел Update, извлекаем из него сообщение или callback
            if isinstance(event, Update):
                if event.message:
                    event = event.message
                elif event.callback_query:
                    event = event.callback_query
                else:
                    await logger.warning(f"Update без сообщения или callback: {event.update_id}")
                    return await handler(original_event, data)

            # Получаем user_id для Message или CallbackQuery
            if isinstance(event, (Message, CallbackQuery)):
                user_id = event.from_user.id
            else:
                await logger.warning(f"Необрабатываемый тип события: {type(event)}")
                return await handler(original_event, data)

            # Основная логика middleware
            try:
                # Проверяем админские права
                if await db.check_admin(user_id):
                    return await handler(original_event, data)

                # Проверяем статус бота
                if not await db.get_bot_status():
                    if isinstance(event, CallbackQuery):
                        await event.answer("❌ Бот отключен", show_alert=True)
                    elif isinstance(event, Message):
                        # await event.answer("⏸ Бот временно недоступен")
                        await event.answer(CALLS_FINISHED_TODAY_TEXT)
                    return None

                return await handler(original_event, data)

            except Exception as e:
                await logger.error(f"Ошибка в логике middleware: {str(e)}")
                return await handler(original_event, data)

        except Exception as e:
            await logger.error(f"Ошибка обработки события: {str(e)}")
            return await handler(original_event, data)
