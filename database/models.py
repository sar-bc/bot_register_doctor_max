from enum import Enum
from sqlalchemy import (ForeignKey, String, BigInteger,
                        TIMESTAMP, Column, func, Integer,
                        Text, CheckConstraint, Date, DateTime, Boolean, JSON, Time, Enum as SQLAlchemyEnum)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import Time 
from datetime import time
from sqlalchemy import event, text


class Base(AsyncAttrs, DeclarativeBase):
    pass


####################################
class AdminBot(Base):
    __tablename__ = 'AdminBot'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_max = Column(BigInteger, nullable=False)
    username = Column(String(100), nullable=True)
    role = Column(Integer, nullable=False) # 0- admin; 1- работник регистратуры кому будет отправлять сообщения

    def __repr__(self):
        return (f"<AdminBot(id={self.id}, id_tg={self.id_max}, username={self.username}, role={self.role})>")

####################################
class UserState(Base):
    __tablename__ = 'UserState'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    last_message_ids = Column(JSON, default=list)  # Поддержка JSON
    
    def __repr__(self):
        return (f"<UserState(id={self.id}, user_id={self.user_id}, "
                f"last_message_ids={self.last_message_ids})>")


####################################
class Logs(Base):
    __tablename__ = 'Logs'  # Имя таблицы в базе данных

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    timestamp = Column(DateTime, nullable=False)  # Временная метка
    name = Column(Text, nullable=False)  # Имя логгера
    level = Column(Text, nullable=False)  # Уровень логирования
    message = Column(Text, nullable=False)  # Сообщение лога

    def __repr__(self):
        return (f"<Log(id={self.id}, timestamp='{self.timestamp}', "
                f"name='{self.name}', level='{self.level}', "
                f"message='{self.message}')>")


####################################
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)  # Telegram MAX
    username = Column(String(100), nullable=True)  # @username может быть None
    full_name = Column(String(200), nullable=False)
    registration_date = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, username=@{self.username})>"
#########################################
class QuestionnaireStatus(Enum):
    """Статусы анкеты вызова врача"""
    NEW = 'new'                   # Новая заявка
    APPROVED = 'approved'         # Одобрена (врач назначен)
    REJECTED = 'rejected'         # Отклонена
    CANCELLED = 'cancelled'       # Отменена пациентом
    PENDING_CANCELLATION = "pending_cancellation" # Ожидание отмены
#########################################
class DoctorCall(Base):
    __tablename__ = 'doctor_calls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    
    # Основные данные
    full_name = Column(String(100), nullable=False)
    birth_date = Column(String(10), nullable=False)
    phone = Column(String(20), nullable=False)
    
    # Адресные данные
    address = Column(String(200), nullable=False)
    address_details = Column(String(100))
    access_notes = Column(String(200))
    door_code = Column(String(20), nullable=True)
    
    # Медицинские данные
    temperature = Column(String(10))
    symptoms = Column(Text, nullable=False)
    need_sick_leave = Column(Boolean, default=False)
    
    # Системные метаданные
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    status = Column(String(50), default='new', nullable=False)
    rejection_reason = Column(String(200), nullable=True)
    staff_message_ids = Column(MutableList.as_mutable(JSON), default=list, nullable=True)

    # Связь с доктором (может быть NULL, пока вызов не принят)
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=True)  # <- nullable=True
    doctor = relationship("Doctor", back_populates="calls")

    # Суточная нумерация
    daily_number = Column(Integer, nullable=True)

    def __repr__(self):
        return (
            f"<DoctorCall("
            f"id={self.id}, "
            f"status='{self.status.name}', "
            f"patient='{self.full_name[:15]}...', "
            f"date={self.created_at.strftime('%d.%m.%Y')}, "
            f"daily_number={self.daily_number}, "
            f"symptoms='{self.symptoms[:30]}...', "
            f"doctor_id={self.doctor_id or 'None'}"
            f")>"
        )
    
    @property
    def call_number(self):
        """Возвращает номер вызова в формате 'NNN'."""
        if self.daily_number and self.created_at:
            num_part = f"{self.daily_number}"  #self.daily_number:03d
            return f"{num_part}"
        return None
    
# Вешаем обработчик на событие before_insert
@event.listens_for(DoctorCall, 'before_insert')
def set_daily_number(mapper, connection, target):
    """Автоматически устанавливает daily_number перед вставкой в БД"""
    try:
        print(f"🐛 Сработал before_insert для вызова {target.id}")
        
        # Убедимся, что created_at установлено
        if target.created_at is None:
            target.created_at = datetime.now()
            print(f"🐛 Установлено created_at: {target.created_at}")
        
        # Форматируем дату для SQL запроса
        date_str = target.created_at.strftime('%Y-%m-%d')
        print(f"🐛 Ищем записи за дату: {date_str}")
        
        # SQL запрос для получения максимального номера за эту дату
        query = text("""
            SELECT COALESCE(MAX(daily_number), 0) 
            FROM doctor_calls 
            WHERE DATE(created_at) = :date
        """)
        
        # Выполняем запрос
        result = connection.execute(query, {'date': date_str})
        max_num = result.scalar()
        print(f"🐛 Найден максимальный номер: {max_num}")
        
        # Устанавливаем следующий номер
        target.daily_number = max_num + 1
        print(f"🐛 Установлен daily_number: {target.daily_number}")
        
    except Exception as e:
        print(f"❌ Ошибка в set_daily_number: {e}")
        # Устанавливаем значение по умолчанию в случае ошибки
        target.daily_number = 1
#########################################
class Doctor(Base):
    __tablename__ = 'doctors'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    max_id = Column(BigInteger, unique=True, nullable=True)  # ID max chat_id
    
    # Основные данные доктора
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    
    # Системные метаданные
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)  # Флаг активности доктора
    
    # Связь с вызовами
    calls = relationship("DoctorCall", back_populates="doctor")

    def __repr__(self):
        return (
            f"<Doctor("
            f"id={self.id}, "
            f"full_name='{self.full_name}', "
            f"active={self.is_active}, "
            f"max_id={self.max_id or 'None'}"
            f")>"
        )
#########################################
class Patient(Base):
    __tablename__ = 'patients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    max_id = Column(BigInteger, index=True, nullable=False)  
    
    # Основные данные
    full_name = Column(String(100), nullable=False)
    birth_date = Column(String(10), nullable=False)
    phone = Column(String(20), nullable=False)
    
    # Адресные данные
    address = Column(String(200), nullable=False)
    address_details = Column(String(100), nullable=True)
    access_notes = Column(String(200), nullable=True)
    door_code = Column(String(20), nullable=True)

    def __repr__(self):
        return (
            f"<Patient("
            f"id={self.id}, "
            f"telegram_id={self.max_id}, "
            f"full_name='{self.full_name[:15]}...', "  # Обрезаем длинное ФИО
            f"birth_date='{self.birth_date}', "
            f"phone='{self.phone[:5]}...'"  # Часть телефона для конфиденциальности
            f")>"
        )

#########################################
class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_active = Column(Boolean, default=True, nullable=False)
    auto_schedule = Column(Boolean, default=True, nullable=False)  # Включено ли авторасписание
    manual_override = Column(Boolean, default=False, nullable=False)  # Ручное управление
    weekday_start = Column(Time, default=time(8, 0))  # Начало работы в будни
    weekday_end = Column(Time, default=time(12, 0))   # Конец работы в будни
    weekend_start = Column(Time, default=time(9, 0))  # Начало работы в выходные
    weekend_end = Column(Time, default=time(12, 0))   # Конец работы в выходные
    last_changed = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    changed_by = Column(BigInteger)  # ID сотрудника
    group_id = Column(BigInteger, nullable=True)  # Может быть NULL
    thread_id = Column(Integer, nullable=True)    # Может быть NULL
    
    def __repr__(self):
        return (f"<Settings(bot_active={self.bot_active}, "
                f"auto_schedule={self.auto_schedule}, "
                f"manual_override={self.manual_override}, "
                f"group_id={self.group_id}, "
                f"thread_id={self.thread_id})>")
#########################################
