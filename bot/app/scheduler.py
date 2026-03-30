# app/scheduler.py
from datetime import datetime, time, timedelta
import asyncio
from typing import Optional
from maxapi import Bot
from database.Database import DataBase
from core.log import Logger
import os

# Настройка логгера
logger = Logger(__name__)

# Флаг отладки
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'


class BotScheduler:
    def __init__(self, bot: Bot, db: DataBase):
        self.bot = bot
        self.db = db
        self._task: Optional[asyncio.Task] = None
        self._last_status: Optional[bool] = None
        self._last_notification_time: Optional[datetime] = None

    async def _notify_status_change(self, new_status: bool, reason: str):
        """Умные уведомления с защитой от спама"""
        now = datetime.now()
        
        if (self._last_notification_time and 
            (now - self._last_notification_time) < timedelta(minutes=5) and
            self._last_status == new_status):
            return
            
        self._last_status = new_status
        self._last_notification_time = now
        
        status_text = "🟢 Бот ВКЛЮЧЕН" if new_status else "🔴 Бот ВЫКЛЮЧЕН"
        message = (
            f"{status_text}\n"
            f"Причина: {reason}\n"
            f"Время: {now.strftime('%d.%m.%Y %H:%M')}"
        )
        
        # Получаем админов и отправляем уведомления
        admins = await self.db.get_admins()
        for admin in admins:
            try:
                await self.bot.send_message(chat_id=admin.id_max, text=message)
                if DEBUG:
                    await logger.info(f"Уведомление отправлено админу {admin.id_max}")
            except Exception as e:
                if DEBUG:
                    await logger.error(f"Не удалось отправить уведомление админу {admin.id_max}: {e}")

    def _is_time_in_range(self, start: time, end: time, current: time) -> bool:
        """Проверка нахождения времени в диапазоне с округлением до минут"""
        current = current.replace(second=0, microsecond=0)
        
        # Для синхронного логирования используем print или добавляем синхронный метод в Logger
        if DEBUG:
            # Временно используем print, так как это синхронный метод
            print(f"Проверка времени: {current} между {start} и {end}")
        
        if start <= end:
            result = start <= current <= end
        else:
            result = start <= current or current <= end
            
        if DEBUG:
            print(f"Результат проверки: {'в диапазоне' if result else 'вне диапазона'}")
        return result

    async def _check_schedule(self):
        """Основная функция проверки расписания"""
        try:
            settings = await self.db.get_settings()
            if settings is None:
                await logger.error("Не удалось получить настройки из базы данных")
                return
                
            if DEBUG:
                await logger.info(f"\n--- Проверка расписания {datetime.now()} ---")
                await logger.info(f"Текущий статус бота: {'Активен' if settings.bot_active else 'Неактивен'}")
                await logger.info(f"Ручное управление: {'Да' if settings.manual_override else 'Нет'}")
            
            if settings.manual_override:
                if DEBUG:
                    await logger.info("Ручное управление активно, расписание игнорируется")
                return
                
            now = datetime.now()
            current_time = now.time().replace(second=0, microsecond=0)
            weekday = now.weekday()
            is_weekend = weekday >= 5
            
            if DEBUG:
                await logger.info(f"День недели: {weekday} ({'выходной' if is_weekend else 'будний'})")
                await logger.info(f"Текущее время: {current_time}")

            schedule_type = "выходные" if is_weekend else "будни"
            start_time = settings.weekend_start if is_weekend else settings.weekday_start
            end_time = settings.weekend_end if is_weekend else settings.weekday_end
            
            if DEBUG:
                await logger.info(f"Расписание {schedule_type}: {start_time} - {end_time}")

            should_be_active = self._is_time_in_range(start_time, end_time, current_time)
            
            if DEBUG:
                await logger.info(f"По расписанию ({schedule_type}) бот должен быть {'активен' if should_be_active else 'неактивен'}")

            if should_be_active != settings.bot_active:
                await logger.info(f"Изменение статуса бота: {'Активен' if should_be_active else 'Неактивен'}")
                await self.db.update_settings(user_id=0, bot_active=should_be_active)
                await self._notify_status_change(should_be_active, f"расписание ({schedule_type})")
                
        except Exception as e:
            await logger.error(f"Ошибка в _check_schedule: {e}")

    async def start(self):
        """Запуск фоновой задачи"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._schedule_loop())
            await logger.info("⏰ Служба расписания запущена")
            
    async def stop(self):
        """Остановка фоновой задачи"""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            await logger.info("⏰ Служба расписания остановлена")
            
    async def _schedule_loop(self):
        """Основной цикл проверки"""
        while True:
            try:
                await self._check_schedule()
                await asyncio.sleep(60)  # Проверяем каждую минуту
            except asyncio.CancelledError:
                await logger.info("Расписание: остановка по запросу")
                break
            except Exception as e:
                await logger.error(f"Ошибка в schedule_loop: {e}")
                await asyncio.sleep(60)