from dotenv import load_dotenv
import os
from sqlalchemy import select, update, delete, func, BigInteger, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, NoResultFound
from database.models import Base, User, UserState, AdminBot, Logs, QuestionnaireStatus, DoctorCall, Settings, Doctor, Patient
from datetime import datetime, date
import logging
from typing import Optional, Union, List
# from aiogram import Bot
from datetime import time
# from core.bot_instance import get_bot
import aiohttp

load_dotenv()
# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

class DataBase:
    def __init__(self):
        # # For SQLITE
        # self.connect = 'sqlite+aiosqlite:///db.sqlite3'
        # self.async_engine = create_async_engine(url=self.connect, echo=False)
        # self.Session = async_sessionmaker(bind=self.async_engine, class_=AsyncSession)
        # For MySQL
        self.db_host = os.getenv('MYSQL_HOST') #' 22.0.1.9'  # os.getenv('MYSQL_HOST')
        self.db_user = os.getenv('MYSQL_USER')
        self.db_password = os.getenv('MYSQL_PASSWORD')
        self.db_name = os.getenv('MYSQL_DATABASE')
        self.connect = (f'mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}/'
                        f'{self.db_name}?charset=utf8mb4')
        self.async_engine = create_async_engine(url=self.connect, echo=False)
        self.Session = async_sessionmaker(bind=self.async_engine, class_=AsyncSession)

    # Статус-константы для удобства
    # STATUS_DISPLAY = {
    #     QuestionnaireStatus.NEW: "⏳ Ожидает обработки",
    #     QuestionnaireStatus.APPROVED: "✅ Вызов принят",
    #     QuestionnaireStatus.REJECTED: "👉 Приглашён на приём",
    #     QuestionnaireStatus.CANCELLED: "🚫 Вызов отменен",
    #     QuestionnaireStatus.PENDING_CANCELLATION: "⏳ Ожидает отмены"
    # }
    STATUS_DISPLAY = {
        'new': "⏳ Ожидает обработки",
        'approved': "✅ Вызов принят",
        'rejected': "👈 Приглашён на приём",
        'cancelled': "🚫 Вызов отменен",
        'pending_cancellation': "⏳ Ожидает отмены"
    }
    async def close(self):
        """Закрывает соединение с базой данных"""
        await self.async_engine.dispose()

    async def create_db(self):
        """Создает все таблицы в базе данных"""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
    async def init_settings(self):
        """Инициализирует настройки по умолчанию, если их нет"""
        async with self.Session() as session:
            try:
                from .models import Settings
                from datetime import time
                
                # Проверяем, есть ли настройки
                result = await session.execute(select(Settings).limit(1))
                settings = result.scalars().first()
                
                if not settings:
                    # Создаем настройки по умолчанию
                    settings = Settings(
                        bot_active=True,
                        auto_schedule=True,
                        manual_override=False,
                        weekday_start=time(8, 0),   # 08:00
                        weekday_end=time(12, 0),    # 12:00
                        weekend_start=time(9, 0),   # 09:00
                        weekend_end=time(12, 0),    # 12:00
                        last_changed=datetime.now(),
                        changed_by=0,
                        group_id=None,
                        thread_id=None
                    )
                    session.add(settings)
                    await session.commit()
                    logger.info("✅ Настройки по умолчанию созданы")
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка инициализации настроек: {e}")
                raise e
    # ========== LOGGING METHODS ==========
    async def log_to_db(self, level: str, message: str, logger_name: str):
        """Записывает лог в базу данных"""
        async with self.Session() as session:
            try:
                log = Logs(
                    timestamp=datetime.utcnow(),
                    name=logger_name,
                    level=level,
                    message=message
                )
                session.add(log)
                await session.commit()
                logger.debug(f"Logged to DB: {message}")
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Failed to log to DB: {e}")

    # #==========*********===============
    # database/Database.py

    async def get_settings(self):
        """Получает текущие настройки бота"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    select(Settings).order_by(Settings.id.desc()).limit(1)
                )
                settings = result.scalars().first()
                
                if not settings:
                    # Создаем настройки по умолчанию
                    from datetime import time
                    settings = Settings(
                        bot_active=True,
                        auto_schedule=True,
                        manual_override=False,
                        weekday_start=time(8, 0),
                        weekday_end=time(20, 0),
                        weekend_start=time(9, 0),
                        weekend_end=time(18, 0),
                        changed_by=0
                    )
                    session.add(settings)
                    await session.commit()
                    await session.refresh(settings)
                
                return settings
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Ошибка получения настроек: {e}")
                raise e

    async def update_settings(self, user_id: int, **kwargs) -> bool:
        """Обновляет настройки бота"""
        async with self.Session() as session:
            try:
                settings = await self.get_settings()
                
                for key, value in kwargs.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                
                # Явно обновляем эти поля после всех изменений
                settings.changed_by = user_id
                settings.last_changed = datetime.now()
                
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
                
                return True
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Ошибка обновления настроек: {e}")
                raise e                    
    # ========== USER METHODS ==========
    async def add_new_user(self, user_id: int, username: Optional[str], full_name: str) -> bool:
        """
        Добавляет нового пользователя или обновляет существующего
        Returns:
            bool: True если пользователь новый, False если обновлен
        """
        async with self.Session() as session:
            try:
                user = await session.scalar(select(User).where(User.user_id == user_id))
                
                if user:
                    user.username = username
                    user.full_name = full_name
                    logger.info(f"User {user_id} updated")
                else:
                    user = User(
                        user_id=user_id,
                        username=username,
                        full_name=full_name
                    )
                    session.add(user)
                    logger.info(f"New user {user_id} added")
                
                await session.commit()
                return not bool(user)
                
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"Integrity error for user {user_id}: {e}")
                raise
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Database error for user {user_id}: {e}")
                raise

    # async def check_user_exists(self, user_id: int) -> bool:
    #     """Проверяет существование пользователя в БД"""
    #     async with self.Session() as session:
    #         exists = await session.scalar(
    #             select(User.user_id).where(User.user_id == user_id))
    #         return bool(exists)

    async def update_user_activity(self, user_id: int):
        """Обновляет время последней активности пользователя"""
        async with self.Session() as session:
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(last_activity=datetime.utcnow())
            )
            await session.commit()
            logger.debug(f"Updated activity for user {user_id}")

    # ========== USER STATE METHODS ==========
    async def get_state(self, id_max: BigInteger):
        async with self.Session() as session:
            # Попытка получить состояние пользователя по user_id
            state = await session.scalar(select(UserState).where(UserState.user_id == id_max))

            if state is None:
                logger.info(f'Состояние не найдено для user_state_id: {id_max}. Создание нового состояния.')
                # Если состояния нет, создаем новое
                state = UserState(user_id=id_max)
                session.add(state)
                await session.commit()  # Сохраняем изменения
                await session.refresh(state)  # Обновляем объект state данными из БД
                logger.info(f'Создано состояние user_state:{state.user_id}')
                return state
            else:
                logger.info(f'Получено состояние для user_state_id: {id_max}.')
                return state
   
    async def update_state(self, state: UserState) -> Optional[UserState]:
        """Обновляет состояние пользователя в БД"""
        async with self.Session() as session:
            try:
               # Убедитесь, что объект связан с текущей сессией
                existing_state = await session.execute(select(UserState).where(UserState.user_id == state.user_id))
                current_state = existing_state.scalars().one_or_none()

                if current_state:
                    # Обновление атрибутов
                    current_state.last_message_ids = state.last_message_ids
                    
                    # Сохранение изменений
                    await session.commit()
                    return current_state  # Возвращаем обновленный объект
                else:
                    return None  # Состояние не найдено 
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error updating state: {e}")
                raise

    async def delete_messages(self, state):
        if state.last_message_ids:
            from dotenv import load_dotenv
            import os
            
            load_dotenv()
            TOKEN = os.getenv('MAX_BOT_TOKEN')
            
            headers = {"Authorization": TOKEN}
            
            for lst in state.last_message_ids:
                try:
                    url = f"https://platform-api.max.ru/messages?message_id={lst}"
                    async with aiohttp.ClientSession() as session:
                        async with session.delete(url, headers=headers) as response:
                            if response.status == 200:
                                logger.info(f"Сообщение {lst} удалено")
                            else:
                                logger.error(f"Ошибка удаления {lst}: {response.status}")
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {lst}: {e}")
            
            state.last_message_ids = []
            await self.update_state(state)

    # async def delete_inline_messages(self, bot: Bot, user_id: int):
    #     user_state = await self.get_state(user_id)
    #     if not user_state.inline_message_ids:
    #         return
            
    #     for msg_id in user_state.inline_message_ids:
    #         try:
    #             await bot.delete_message(
    #                 chat_id=user_id,
    #                 message_id=msg_id
    #             )
    #         except:
    #             continue
                
    #     user_state.inline_message_ids = []
    #     await self.update_state(user_state)
    # ========== ADMIN METHODS ==========
    async def check_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором (role=0)"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    select(AdminBot).where(
                        AdminBot.id_max == user_id,
                        AdminBot.role == 0
                    )
                )
                return result.scalar_one_or_none() is not None
            except SQLAlchemyError as e:
                logger.error(f"Ошибка проверки админа: {e}")
                return False

    async def get_admins(self):
        """Получить всех администраторов (role=0)"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    select(AdminBot).where(AdminBot.role == 0)
                )
                return result.scalars().all()
            except SQLAlchemyError as e:
                logger.error(f"Ошибка при получении администраторов: {e}")
                return []  # возвращаем пустой список

    async def get_bot_status(self) -> bool:
        """Получить текущий статус бота (включен/выключен)"""
        async with self.Session() as session:
            result = await session.execute(select(Settings).order_by(Settings.id.desc()).limit(1))
            settings = result.scalars().first()
            return settings.bot_active if settings else True  # По умолчанию включен

    # async def set_bot_status(self, status: bool, changed_by: int) -> bool:
    #     """Установить новый статус бота"""
    #     async with self.Session() as session:
    #         try:
    #             # Создаем новую запись с новым статусом
    #             new_settings = Settings(
    #                 bot_active=status,
    #                 changed_by=changed_by
    #             )
    #             session.add(new_settings)
    #             await session.commit()
    #             return True
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             logger.error(f"Error changing bot status: {e}")
    #             return False        

    # database/Database.py - исправленный метод

    async def get_daily_statistics(self, date: str | date = None):
        """Получает статистику вызовов за указанный день"""
        # Обрабатываем входную дату
        if date is None:
            target_date = datetime.now().date()
        elif isinstance(date, str):
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError as e:
                logger.error(f"Неверный формат даты: {date}. Ожидается 'YYYY-MM-DD'")
                return False
        else:
            target_date = date
        
        async with self.Session() as session:
            try:
                # Всего вызовов
                total_calls = await session.scalar(
                    select(func.count(DoctorCall.id))
                    .where(func.date(DoctorCall.created_at) == target_date)
                ) or 0
                
                # Принятые (status = 'approved')
                approved_calls = await session.scalar(
                    select(func.count(DoctorCall.id))
                    .where(
                        func.date(DoctorCall.created_at) == target_date,
                        DoctorCall.status == 'approved'
                    )
                ) or 0

                # Отклоненные (status = 'rejected')
                rejected_calls = await session.scalar(
                    select(func.count(DoctorCall.id))
                    .where(
                        func.date(DoctorCall.created_at) == target_date,
                        DoctorCall.status == 'rejected'
                    )
                ) or 0

                # В ожидании (status = 'new')
                pending_calls = await session.scalar(
                    select(func.count(DoctorCall.id))
                    .where(
                        func.date(DoctorCall.created_at) == target_date,
                        DoctorCall.status == 'new'
                    )
                ) or 0

                # Отмененные (status = 'cancelled')
                cancelled_calls = await session.scalar(
                    select(func.count(DoctorCall.id))
                    .where(
                        func.date(DoctorCall.created_at) == target_date,
                        DoctorCall.status == 'cancelled'
                    )
                ) or 0
                
                statistics = {
                    'total_calls': total_calls,
                    'approved_calls': approved_calls,
                    'rejected_calls': rejected_calls,
                    'pending_calls': pending_calls,
                    'cancelled_calls': cancelled_calls,
                }

                return statistics
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Ошибка получения статистики: {e}")
                return False

    async def get_questionnaires_by_date(self, date_str: str) -> List[DoctorCall]:
        """Получение всех анкет по указанной дате (ДД-ММ-ГГГГ)"""
        try:
            target_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            raise ValueError("Неверный формат даты. Используйте ДД-ММ-ГГГГ")
        
        async with self.Session() as session:
            from sqlalchemy import func
            result = await session.execute(
                select(DoctorCall)
                .where(func.date(DoctorCall.created_at) == target_date)
                .order_by(DoctorCall.created_at)
            )
            return result.scalars().all()

    async def get_questionnaires_by_period(self, start_date: str, end_date: str) -> list[DoctorCall]:
        """Получение всех анкет за период (ДД-ММ-ГГГГ)"""
        try:
            # Преобразуем строки в даты
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y").date()
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y").date()
            
            # Проверяем, что начальная дата не позже конечной
            if start_date_obj > end_date_obj:
                raise ValueError("Начальная дата не может быть позже конечной")
                
        except ValueError as e:
            if "Неверный формат даты" in str(e):
                raise ValueError("Неверный формат даты. Используйте ДД-ММ-ГГГГ")
            else:
                raise e
        
        async with self.Session() as session:
            result = await session.execute(
                select(DoctorCall)
                .where(
                    func.date(DoctorCall.created_at) >= start_date_obj,
                    func.date(DoctorCall.created_at) <= end_date_obj
                )
                .order_by(DoctorCall.created_at)
            )
            return result.scalars().all()
         
    



    # async def update_group_settings(self, user_id: int, group_id: int, thread_id: int) -> bool:
    #     """Специализированный метод для обновления group_id и thread_id"""
    #     return await self.update_settings(
    #         user_id=user_id,
    #         group_id=group_id,
    #         thread_id=thread_id
    #     )

    # async def toggle_bot_status(self, user_id: int) -> bool:
    #     """Переключает статус бота (вкл/выкл)"""
    #     async with self.Session() as session:
    #         try:
    #             settings = await self.get_settings()
    #             settings.bot_active = not settings.bot_active
    #             settings.changed_by = user_id
    #             settings.last_changed = datetime.now()
    #             await session.commit()
    #             return settings.bot_active
                
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             raise e

    # async def toggle_auto_schedule(self, user_id: int) -> bool:
    #     """Переключает автоматическое расписание"""
    #     async with self.Session() as session:
    #         try:
    #             settings = await self.get_settings()
    #             settings.auto_schedule = not settings.auto_schedule
    #             settings.changed_by = user_id
    #             settings.last_changed = datetime.now()
    #             await session.commit()
    #             return settings.auto_schedule
                
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             raise e

    # async def set_manual_override(self, user_id: int, active: bool) -> bool:
    #     """Устанавливает ручное управление"""
    #     async with self.Session() as session:
    #         try:
    #             settings = await self.get_settings()
    #             settings.manual_override = True
    #             settings.bot_active = active
    #             settings.changed_by = user_id
    #             settings.last_changed = datetime.now()
    #             await session.commit()
    #             return True
                
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             raise e

    # async def reset_to_schedule(self, user_id: int) -> bool:
    #     """Сбрасывает ручное управление"""
    #     async with self.Session() as session:
    #         try:
    #             settings = await self.get_settings()
    #             settings.manual_override = False
    #             settings.changed_by = user_id
    #             settings.last_changed = datetime.now()
    #             await session.commit()
    #             return True
                
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             raise e

    # async def update_working_hours(self, user_id: int, 
    #                              weekday_start: time, weekday_end: time,
    #                              weekend_start: time, weekend_end: time) -> bool:
    #     """Обновляет часы работы"""
    #     async with self.Session() as session:
    #         try:
    #             settings = await self.get_settings()
    #             settings.weekday_start = weekday_start
    #             settings.weekday_end = weekday_end
    #             settings.weekend_start = weekend_start
    #             settings.weekend_end = weekend_end
    #             settings.changed_by = user_id
    #             settings.last_changed = datetime.now()
    #             await session.commit()
    #             return True
                
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             raise e
            
    # async def adduser(self, user_id: int, role: int, username: str = None) -> str:
    #     """Добавление пользователя"""
    #     try:
    #         async with self.Session() as session:
    #             # Проверка существующей записи
    #             stmt = select(AdminBot).where(
    #                 AdminBot.id_tg == user_id,
    #                 AdminBot.role == role
    #             )
    #             existing = await session.scalar(stmt)
                
    #             if existing:
    #                 return "exists"
                    
    #             # Добавление новой записи
    #             new_user = AdminBot(
    #                 id_tg=user_id,
    #                 username=username,
    #                 role=role
    #             )
    #             session.add(new_user)
    #             await session.commit()
    #             return "added"
                
    #     except Exception as e:
    #         await session.rollback()
    #         logger.error(f"Adduser error: {e}", exc_info=True)
    #         return "error"    

    async def get_active_doctors(self):
        """Получить всех активных врачей (is_active=True)"""
        async with self.Session() as session:
            try:
                from .models import Doctor
                result = await session.execute(
                    select(Doctor).where(Doctor.is_active == True)
                )
                return result.scalars().all()
            except SQLAlchemyError as e:
                logger.error(f"Ошибка получения активных врачей: {e}")
                return []
            

    async def get_all_doctors(self, activ: Optional[bool] = None) -> Union[List[Doctor], str]:
        """Получить список докторов с возможностью фильтрации по активности
        
        Args:
            activ: Опциональный параметр для фильтрации по статусу активности:
                - None: вернуть всех докторов (без фильтрации)
                - True: вернуть только активных докторов
                - False: вернуть только неактивных докторов
        
        Returns:
            Список докторов или строка "error" в случае ошибки
        """
        try:
            async with self.Session() as session:
                # Базовый запрос с сортировкой по ФИО
                stmt = select(Doctor).order_by(Doctor.full_name)
                
                # Добавляем фильтр по активности, если параметр указан
                if activ is not None:
                    stmt = stmt.where(Doctor.is_active == activ)
                
                # Выполняем запрос
                result = await session.execute(stmt)
                doctors = result.scalars().all()
                
                return list(doctors)
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка докторов: {e}", exc_info=True)
            return "error"
    

    # async def get_doctors_items(self, page, page_size):
    #         async with self.Session() as session:
    #             offset = (page - 1) * page_size
    #             result = await session.execute(
    #                 select(Doctor).limit(page_size).offset(offset)
    #             )
    #             return result.scalars().all()

    async def change_status_doctor(self, id: int) -> bool:
        """
        Изменяет статус активности доктора
        Args:
            id: ID доктора
        Returns:
            bool: True если успешно, False при ошибке
        """
        async with self.Session() as session:
            try:
                # Явно начинаем транзакцию
                async with session.begin():
                    result = await session.execute(
                        select(Doctor).where(Doctor.id == id))
                    doctor = result.scalar_one()
                    
                    doctor.is_active = not doctor.is_active
                    doctor.updated_at = datetime.now()
                    
                    # Не нужно явно коммитить - коммит произойдет при выходе из блока begin()
                    logger.info(f"Статус доктора {id} изменен на {doctor.is_active}")
                    return True
                    
            except NoResultFound:
                logger.warning(f"Доктор с ID {id} не найден")
                return False
            except Exception as e:
                logger.error(f"Ошибка при изменении статуса доктора {id}: {e}")
                # Не нужно явно откатывать - откат произойдет автоматически при исключении
                return False
    
    async def doctor_delete(self, id: int) -> bool:
        """
        Удаляет доктора по ID
        Возвращает True при успешном удалении, False при ошибке
        """
        async with self.Session() as session:
            try:
                async with session.begin():
                    # 1. Проверяем существование доктора
                    doctor = await session.get(Doctor, id)
                    if not doctor:
                        logger.warning(f"Доктор с ID {id} не найден")
                        return False
                    
                    # 2. Обнуляем doctor_id в связанных вызовах (если нужно)
                    await session.execute(
                        update(DoctorCall)
                        .where(DoctorCall.doctor_id == id)
                        .values(doctor_id=None)
                    )
                    
                    # 3. Удаляем самого доктора
                    await session.delete(doctor)
                    
                    logger.info(f"Доктор {id} ({doctor.full_name}) удален")
                    return True
                    
            except Exception as e:
                logger.error(f"Ошибка удаления доктора {id}: {e}")
                return False
    
    async def add_doctor(self, data: dict) -> dict:
        """Добавляет доктора в базу и возвращает словарь с результатом"""
        try:
            async with self.Session() as session:
                async with session.begin():
                    # Проверка уникальности телефона
                    exists = await session.scalar(
                        select(Doctor).where(Doctor.phone == data['phone'])
                    )
                    if exists:
                        return {
                            'success': False,
                            'message': 'Доктор с таким телефоном уже существует'
                        }

                    # Создаем нового доктора
                    doctor = Doctor(
                        max_id=data.get('max_id'),
                        full_name=data['full_name'],
                        phone=data['phone'],
                        is_active=True,
                        created_at=datetime.now()
                    )
                    
                    session.add(doctor)
                    await session.flush()  # Получаем ID до коммита
                    
                    return {
                        'success': True,
                        'doctor_id': doctor.id,
                        'message': 'Доктор успешно добавлен'
                    }
                    
        except Exception as e:
            logger.error(f"Ошибка при добавлении доктора: {e}")
            return {
                'success': False,
                'message': 'Внутренняя ошибка сервера'
            }

    async def get_doctor(self, doc_id: int) -> Optional[Doctor]:
        """Получаем данные доктора по его id
        
        Args:
            doc_id: ID врача для поиска
            
        Returns:
            Объект Doctor если найден, иначе None
        Raises:
            SQLAlchemyError: при ошибках работы с БД
        """
        try:
            async with self.Session() as session:
                result = await session.execute(
                    select(Doctor)
                    .where(Doctor.id == doc_id)
                )
                return result.scalar_one_or_none()  # Возвращает одну запись или None
                
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении данных врача (ID: {doc_id}): {e}")
            raise  # Пробрасываем исключение выше для обработки на уровне выше


    # # ========== DOCTOR METHODS ==========
    async def create_doctor_call(
    self,
    user_id: int,
    full_name: str,
    birth_date: str,
    phone: str,
    address: str,
    symptoms: str,
    address_details: str = None,
    access_notes: str = None,
    door_code: str = None,
    temperature: str = None,
    need_sick_leave: bool = False
) -> DoctorCall:
        """
        Создание новой анкеты вызова врача
        Args:
            user_id: ID пользователя в MAX
            full_name: ФИО
            birth_date: Дата рождения
            phone: Телефон
            address: Адрес
            symptoms: Симптомы
            address_details: Подъезд/этаж (опционально)
            access_notes: Особенности доступа (опционально)
            door_code: Код двери (опционально)
            temperature: Температура (опционально)
            need_sick_leave: Нужен ли больничный
        Returns:
            DoctorCall: созданный объект вызова
        """
        async with self.Session() as session:
            try:
                # Валидация обязательных полей
                if not all([user_id, full_name, birth_date, phone, address, symptoms]):
                    raise ValueError("Отсутствуют обязательные поля")

                # Подготовка данных для вызова врача
                questionnaire_data = {
                    'user_id': user_id,
                    'full_name': full_name.strip(),
                    'birth_date': birth_date,
                    'phone': phone.strip(),
                    'address': address.strip(),
                    'symptoms': symptoms,
                    'need_sick_leave': need_sick_leave,
                    'status': 'new'
                }

                # Добавляем необязательные поля
                if address_details:
                    questionnaire_data['address_details'] = address_details.strip()
                if access_notes:
                    questionnaire_data['access_notes'] = access_notes
                if door_code:
                    questionnaire_data['door_code'] = door_code
                if temperature:
                    questionnaire_data['temperature'] = temperature

                # Создание и сохранение анкеты
                questionnaire = DoctorCall(**questionnaire_data)
                session.add(questionnaire)
                await session.commit()
                await session.refresh(questionnaire)
                
                logger.info(f"Создана новая анкета ID: {questionnaire.id}, номер: {questionnaire.call_number}")
                return questionnaire

            except ValueError as e:
                await session.rollback()
                logger.error(f"Ошибка валидации: {str(e)}")
                raise
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Ошибка БД при создании анкеты: {str(e)}")
                raise RuntimeError("Ошибка сохранения данных")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
                raise RuntimeError("Внутренняя ошибка сервера")
            
    async def save_patient(self, user_id: int, form_data: dict) -> int:
        """
        Сохранение данных ребенка (пациента)
        Args:
            user_id: ID пользователя в MAX
            form_data: словарь с данными анкеты
        Returns:
            int: ID созданного пациента
        """
        async with self.Session() as session:
            try:
                # Подготовка данных пациента
                patient_data = {
                    'max_id': user_id,
                    'full_name': form_data['full_name'].strip(),
                    'birth_date': form_data['birth_date'],
                    'phone': form_data['phone'].strip(),
                    'address': form_data['address'].strip(),
                    'address_details': form_data.get('address_details'),
                    'door_code': form_data.get('door_code'),
                    'access_notes': form_data.get('access_notes')
                }
                
                # Проверяем, существует ли уже такой пациент у этого пользователя
                from sqlalchemy import and_
                
                existing_patient = await session.execute(
                    select(Patient).where(
                        and_(
                            Patient.max_id == user_id,
                            Patient.full_name == patient_data['full_name'],
                            Patient.birth_date == patient_data['birth_date']
                        )
                    )
                )
                existing_patient = existing_patient.scalar_one_or_none()
                
                if existing_patient:
                    # Обновляем данные существующего пациента
                    update_needed = False
                    for key, value in patient_data.items():
                        if key != 'max_id' and getattr(existing_patient, key) != value:
                            setattr(existing_patient, key, value)
                            update_needed = True
                    
                    if update_needed:
                        await session.commit()
                        logger.info(f"Обновлены данные пациента ID: {existing_patient.id}")
                    return existing_patient.id
                else:
                    # Создаем нового пациента
                    patient = Patient(**patient_data)
                    session.add(patient)
                    await session.commit()
                    await session.refresh(patient)
                    logger.info(f"Создан новый пациент ID: {patient.id} для пользователя {user_id}")
                    return patient.id
                    
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Ошибка БД при сохранении пациента: {str(e)}")
                raise RuntimeError("Ошибка сохранения данных пациента")
            except Exception as e:
                await session.rollback()
                logger.error(f"Неожиданная ошибка при сохранении пациента: {str(e)}")
                raise

    async def get_registration_staff(self) -> List[AdminBot]:
        """Получить всех сотрудников регистратуры (role=1)"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    select(AdminBot).where(AdminBot.role == 1)
                )
                return result.scalars().all()
            except SQLAlchemyError as e:
                logger.error(f"Ошибка при получении сотрудников регистратуры: {e}")
                return []  # возвращаем пустой список вместо raise                
    # async def create(self, user_id: int, form_data: dict) -> DoctorCall:
    #     """Создание новой анкеты с безопасной обработкой данных и обновлением информации о пациенте"""
    #     # print(f'form_data:{form_data}')
    #     async with self.Session() as session:
    #         try:
    #             # Валидация обязательных полей
    #             required_fields = {
    #                 'FULL_NAME': 'ФИО',
    #                 'BIRTH_DATE': 'Дата рождения',
    #                 'PHONE': 'Телефон',
    #                 'ADDRESS': 'Адрес',
    #                 'SYMPTOMS': 'Симптомы'
    #             }
                
    #             missing_fields = [name for field, name in required_fields.items() 
    #                             if field not in form_data or not form_data[field]]
                
    #             if missing_fields:
    #                 raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")

    #             # Подготовка данных для вызова врача
    #             questionnaire_data = {
    #                 'user_id': user_id,
    #                 'full_name': form_data['FULL_NAME'].strip(),
    #                 'birth_date': form_data['BIRTH_DATE'],
    #                 'phone': form_data['PHONE'].strip(),
    #                 'address': form_data['ADDRESS'].strip(),
    #                 'symptoms': form_data['SYMPTOMS'],
    #                 'need_sick_leave': form_data.get('SICK_LEAVE') == "Требуется"
    #             }

    #             # Обработка необязательных полей для вызова врача
    #             optional_mapping = {
    #                 'address_details': ('ADDRESS_DETAILS', str),
    #                 'temperature': ('TEMPERATURE', str),
    #                 'door_code': ('DOOR_CODE_INPUT', str)
    #             }

    #             for field, (key, type_) in optional_mapping.items():
    #                 if key in form_data and form_data[key]:
    #                     questionnaire_data[field] = type_(form_data[key])

    #             # Специальная обработка для access_notes
    #             access_notes = form_data.get('ACCESS_NOTES')
    #             if access_notes is None:
    #                 custom_notes = form_data.get('CUSTOM_ACCESS_NOTES')
    #                 door_code = form_data.get('DOOR_CODE_INPUT')
                    
    #                 if custom_notes and door_code:
    #                     access_notes = f"{custom_notes} (код двери: {door_code})"
    #                 elif door_code:
    #                     access_notes = f"код двери: {door_code}"
    #                 else:
    #                     access_notes = custom_notes
                
    #             if access_notes:
    #                 questionnaire_data['access_notes'] = access_notes

    #             # Проверяем существует ли пациент с таким telegram_id
    #             existing_patient = await session.execute(
    #                 select(Patient).where(
    #                     Patient.telegram_id == user_id, Patient.full_name == form_data['FULL_NAME'].strip(),
    #                     Patient.birth_date == form_data['BIRTH_DATE']))
    #             existing_patient = existing_patient.scalar_one_or_none()

    #             # Подготовка данных пациента
    #             patient_data = {
    #                 'telegram_id': user_id,
    #                 'full_name': form_data['FULL_NAME'].strip(),
    #                 'birth_date': form_data['BIRTH_DATE'],
    #                 'phone': form_data['PHONE'].strip(),
    #                 'address': form_data['ADDRESS'].strip(),
    #                 'address_details': form_data.get('ADDRESS_DETAILS', '').strip(),
    #                 'door_code': form_data.get('DOOR_CODE_INPUT', '').strip(),
    #                 'access_notes': access_notes
    #             }

    #             if not existing_patient:
    #                 # Создаем нового пациента
    #                 patient = Patient(**patient_data)
    #                 session.add(patient)
    #                 logger.info(f"Создан новый пациент с telegram_id: {user_id}")
    #             else:
    #                 # Проверяем, изменились ли данные
    #                 update_needed = False
    #                 for key, value in patient_data.items():
    #                     if key != 'telegram_id' and getattr(existing_patient, key) != value:
    #                         setattr(existing_patient, key, value)
    #                         update_needed = True
                    
    #                 if update_needed:
    #                     logger.info(f"Обновлены данные пациента с telegram_id: {user_id}")

    #             # Создание и сохранение анкеты вызова врача
    #             questionnaire = DoctorCall(**questionnaire_data)
    #             session.add(questionnaire)
    #             await session.commit()
    #             await session.refresh(questionnaire)
                
    #             logger.info(f"Создана новая анкета ID: {questionnaire.id}")
    #             return questionnaire

    #         except ValueError as e:
    #             await session.rollback()
    #             logger.error(f"Ошибка валидации: {str(e)}")
    #             raise
                
    #         except SQLAlchemyError as e:
    #             await session.rollback()
    #             logger.error(f"Ошибка БД при создании анкеты: {str(e)}")
    #             raise RuntimeError("Ошибка сохранения данных")
                
    #         except Exception as e:
    #             await session.rollback()
    #             logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
    #             raise RuntimeError("Внутренняя ошибка сервера")
    # # async def create(self, user_id: int, form_data: dict) -> DoctorCall:
    # #     """Создание новой анкеты с безопасной обработкой данных"""
    # #     async with self.Session() as session:
    # #         try:
    # #             # Валидация обязательных полей
    # #             required_fields = {
    # #                 'FULL_NAME': 'ФИО',
    # #                 'BIRTH_DATE': 'Дата рождения',
    # #                 'PHONE': 'Телефон',
    # #                 'ADDRESS': 'Адрес',
    # #                 'SYMPTOMS': 'Симптомы'
    # #             }
                
    # #             missing_fields = [name for field, name in required_fields.items() 
    # #                             if field not in form_data or not form_data[field]]
                
    # #             if missing_fields:
    # #                 raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")

    # #             # Подготовка данных
    # #             questionnaire_data = {
    # #                 'user_id': user_id,
    # #                 'full_name': form_data['FULL_NAME'].strip(),
    # #                 'birth_date': form_data['BIRTH_DATE'],
    # #                 'phone': form_data['PHONE'].strip(),
    # #                 'address': form_data['ADDRESS'].strip(),
    # #                 'symptoms': form_data['SYMPTOMS'],
    # #                 'need_sick_leave': form_data.get('SICK_LEAVE') == "Требуется"
    # #             }

    # #             # Обработка необязательных полей
    # #             optional_mapping = {
    # #                 'address_details': ('ADDRESS_DETAILS', str),
    # #                 'temperature': ('TEMPERATURE', str),
    # #                 'door_code': ('DOOR_CODE_INPUT', str)
    # #             }

    # #             for field, (key, type_) in optional_mapping.items():
    # #                 if key in form_data and form_data[key]:
    # #                     questionnaire_data[field] = type_(form_data[key])

    # #             # Специальная обработка для access_notes с учетом всех возможных полей
    # #             access_notes = form_data.get('ACCESS_NOTES')
    # #             if access_notes is None:
    # #                 custom_notes = form_data.get('CUSTOM_ACCESS_NOTES')
    # #                 door_code = form_data.get('DOOR_CODE_INPUT')
                    
    # #                 if custom_notes and door_code:
    # #                     access_notes = f"{custom_notes} (код двери: {door_code})"
    # #                 elif door_code:
    # #                     access_notes = f"код двери: {door_code}"
    # #                 else:
    # #                     access_notes = custom_notes
                
    # #             if access_notes:
    # #                 questionnaire_data['access_notes'] = access_notes

    # #             # Создание и сохранение анкеты
    # #             questionnaire = DoctorCall(**questionnaire_data)
    # #             session.add(questionnaire)
    # #             await session.commit()
    # #             await session.refresh(questionnaire)
                
    # #             logger.info(f"Создана новая анкета ID: {questionnaire.id}")
    # #             return questionnaire

    # #         except ValueError as e:
    # #             await session.rollback()
    # #             logger.error(f"Ошибка валидации: {str(e)}")
    # #             raise
                
    # #         except SQLAlchemyError as e:
    # #             await session.rollback()
    # #             logger.error(f"Ошибка БД при создании анкеты: {str(e)}")
    # #             raise RuntimeError("Ошибка сохранения данных")
                
    # #         except Exception as e:
    # #             await session.rollback()
    # #             logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
    # #             raise RuntimeError("Внутренняя ошибка сервера")
    
    
            
    async def update_call_status(self, call_id: int, new_status: str, rejection_reason=None, doc_id=None) -> bool:
        """Обновление статуса вызова (принимает строку)"""
        async with self.Session() as session:
            try:
                values = {
                    'status': new_status,  # теперь просто строка
                    'updated_at': datetime.now()
                }
                if rejection_reason is not None:
                    values['rejection_reason'] = rejection_reason
                if doc_id is not None:
                    values['doctor_id'] = doc_id if doc_id != 0 else None
                
                await session.execute(
                    update(DoctorCall)
                    .where(DoctorCall.id == call_id)
                    .values(**values)
                )
                await session.commit()
                logger.info(f"Статус вызова {call_id} обновлен на {new_status}")
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error updating call status: {e}")
                return False
            except Exception as e:
                await session.rollback()
                logger.error(f"Unexpected error: {e}")
                return False

    async def get_call_by_id(self, call_id: int) -> DoctorCall:
        """Получение полных данных о вызове"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    select(DoctorCall).where(DoctorCall.id == call_id))
                return result.scalars().first()
            except SQLAlchemyError as e:
                logger.error(f"Error getting call by ID: {e}")
                return None
            
    # async def add_staff_message_id(self, call_id: int, message_id: int):
    #     """Добавляем ID сообщения в список (работает для SQLite и MySQL)"""
    #     async with self.Session() as session:
    #         async with session.begin():  # Явное управление транзакцией
    #             call = await session.get(DoctorCall, call_id)
    #             if not call:
    #                 return False
                    
    #             # Инициализация списка если нужно
    #             if call.staff_message_ids is None:
    #                 call.staff_message_ids = []
                
    #             # Добавляем новый ID (убедимся, что это int)
    #             if message_id not in call.staff_message_ids:
    #                 call.staff_message_ids.append(int(message_id))
    #                 session.add(call)  # Явно помечаем объект как измененный
                
    #             await session.commit()
    #             return True
        
    # async def clear_staff_message_ids(self, call_id: int):
    #     """Очищаем список ID сообщений"""
    #     async with self.Session() as session:
    #         call = await session.get(DoctorCall, call_id)
    #         if call:
    #             call.staff_message_ids = []
    #             await session.commit()

    async def add_staff(self, user_id: int, role: int, username: str = None) -> bool:
        """Добавить сотрудника (0 - админ, 1 - регистратор)"""
        async with self.Session() as session:
            try:
                # Проверяем, есть ли уже такая запись
                existing = await session.execute(
                    select(AdminBot).where(AdminBot.id_max == user_id, AdminBot.role == role)
                )
                if existing.scalar_one_or_none():
                    return False
                
                staff = AdminBot(
                    id_max=user_id,
                    username=username,
                    role=role
                )
                session.add(staff)
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка добавления сотрудника: {e}")
                return False
            
    async def remove_staff(self, user_id: int, role: int) -> bool:
        """Удалить сотрудника по роли"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    delete(AdminBot).where(AdminBot.id_max == user_id, AdminBot.role == role)
                )
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка удаления сотрудника: {e}")
                return False

    async def get_requests_by_user(self, user_id: int, limit: int = 5):
        """Получает список последних заявок на вызов врача для указанного пользователя."""
        async with self.Session() as session:
            result = await session.execute(
                select(DoctorCall)
                .where(DoctorCall.user_id == user_id)
                .order_by(DoctorCall.created_at.desc())
                .limit(limit)
            )
            return result.scalars().all()       

    async def get_staff_by_role(self, role: int):
        """Получить всех сотрудников с определенной ролью"""
        async with self.Session() as session:
            try:
                result = await session.execute(
                    select(AdminBot).where(AdminBot.role == role)
                )
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Ошибка получения сотрудников: {e}")
                return []

    async def get_pacient_all(self, user_id: int) -> List[Patient]:
        """
        Получаем список всех пациентов, привязанных к указанному user_id
        
        Args:
            user_id: Идентификатор пользователя в Telegram
            
        Returns:
            Список объектов Patient или пустой список, если пациентов нет
            
        Raises:
            SQLAlchemyError: Если произошла ошибка при работе с базой данных
        """
        try:
            async with self.Session() as session:
                result = await session.execute(
                    select(Patient)
                    .where(Patient.max_id == user_id)
                    .order_by(Patient.id)  # Сортировка по ID для стабильного порядка
                )
                return result.scalars().all()
                
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пациентов для user_id {user_id}: {str(e)}")
            raise  # Пробрасываем исключение для обработки на уровне выше


    async def get_patient(self, patient_id: int) -> Patient | None:
        """Получить пациента по ID.
        
        Args:
            patient_id: ID пациента для поиска
            
        Returns:
            Объект Patient если найден, иначе None
            
        Raises:
            SQLAlchemyError: если произошла ошибка базы данных
        """
        try:
            async with self.Session() as session:
                result = await session.execute(
                    select(Patient)
                    .where(Patient.id == patient_id)  # Используем id вместо _id
                )
                patient = result.scalars().first()
                
                if not patient:
                    logger.debug(f"Пациент с ID {patient_id} не найден")
                
                return patient
                
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при получении пациента {patient_id}: {str(e)}")
            raise  # Пробрасываем исключение для обработки на уровне выше



