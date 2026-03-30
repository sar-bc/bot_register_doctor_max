# Кнопки
from maxapi.types import (
    ChatButton, 
    LinkButton, 
    CallbackButton, 
    RequestGeoLocationButton, 
    MessageButton, 
    ButtonsPayload, # Для постройки клавиатуры без InlineKeyboardBuilder
    RequestContactButton, 
    OpenAppButton 
)
from maxapi.types import (
    MessageCreated, 
    MessageCallback, 
    MessageChatCreated,
    CommandStart, 
    Command
)
# from maxapi.enums.button_type import ButtonType
# from maxapi.enums.intent import Intent
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from datetime import date
from database.Database import DataBase
import calendar
from datetime import datetime, timedelta, time
#===========================================================
# Словарь русских названий месяцев
RUS_MONTHS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь"
}
#===========================================================

#########################################
async def main_menu_kb(user_id: int = None):
    db = DataBase()
    keyboard = InlineKeyboardBuilder()
    # Основные кнопки для всех пользователей
    keyboard.row(CallbackButton(text="🩺 Вызвать врача", payload="doctor_form_start",))
    keyboard.row(CallbackButton(text="📋 Мои вызовы", payload="my_requests",))
    keyboard.row(CallbackButton(text="📜 Правила", payload="rules",))
    keyboard.row(CallbackButton(text="📞 Контакты", payload="contacts",))
    keyboard.row(CallbackButton(text="ℹ️ О сервисе", payload="about",))
    
    # Добавляем кнопку админа, если пользователь является администратором
    if user_id:
        is_admin = await db.check_admin(user_id)
        if is_admin:
            keyboard.row(CallbackButton(text="👨‍💻 Админ-панель", payload="admin",))
    
    return keyboard.as_markup()
############################################################
def home_keyboard():
    """Клавиатура домой"""
    builder = InlineKeyboardBuilder()    
    builder.row(MessageButton(text="🏠 Главное меню"))
    return builder.as_markup()
############################################################
def home_keyboard_inline():
    """Кнопка домой inline"""
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="🏠 Главное меню", payload="main_menu"),)
    return builder.as_markup()
###########################################################
def user_requests_keyboard(requests):
    builder = InlineKeyboardBuilder()
    for request in requests: 
        builder.row(
            CallbackButton(
                text=f"Вызов #{request.call_number}",
                payload=f"request_detail_{request.id}"
            )
        )
    builder.row(
        CallbackButton(
            text="← Назад",
            payload="main_menu"
        )
    )
    return builder.as_markup()
#############################################
async def choice_patients(user_id, patients):
    builder = InlineKeyboardBuilder()
    
    for patient in patients:
        builder.row(
            CallbackButton(
                text=f"👶 {patient.full_name}",
                payload=f"choose_patient:{patient.id}"  # здесь patient.id, а не user_id!
            )
        )
        
    builder.row(
        CallbackButton(
            text="🔍 Новая анкета",
            payload="doctor_form_start:new"
        )
    )
    
    return builder.as_markup() 
#########################################
def cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.row(MessageButton(text="❌ Отменить вызов"))
    return builder.as_markup()
########################################
def get_final_confirmation_kb():
    """Клавиатура для финального подтверждения"""
    builder = InlineKeyboardBuilder()
    builder.row(MessageButton(text="✅ Подтвердить вызов"))
    builder.row(MessageButton(text="✏️ Редактировать данные"))
    builder.row(MessageButton(text="❌ Отменить вызов"))
    return builder.as_markup()
########################################
def get_access_notes_keyboard():
    """Создает клавиатуру для выбора особенностей доступа"""
    builder = InlineKeyboardBuilder()
    
    options = [
        ("🚪 Домофон есть", "has_intercom"),
        ("❌ Нет домофона", "no_intercom"),
        ("🔢 Код двери", "door_code"),
        ("🐕 Собака", "has_dog"),
        ("🐺 Злая собака!", "has_angry_dog"),
        ("👮 Охрана", "has_security"),
        ("🏢 Свободный вход", "free_access"),
        ("✏️ Другое", "custom_notes"),
        ("⏭ Пропустить", "skip")
    ]
    
    for text, payload in options:
        builder.row(MessageButton(text=text))
    builder.row(MessageButton(text="❌ Отменить вызов"))
    return builder.as_markup()
######################################
def get_phone_keyboard():
    """Клавиатура для запроса номера телефона"""
    builder = InlineKeyboardBuilder()
    builder.row(
        RequestContactButton(text="📱 Отправить мой номер"))
    builder.row(MessageButton(text="✏️ Ввести вручную"))
    return builder.as_markup()
######################################
def address_type_kb():
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки
    builder.row(MessageButton(text="🏠 Частный дом (нет подъезда/этажа)"))
    builder.row(MessageButton(text="❌ Отменить вызов"))
    
    return builder.as_markup()
######################################
def get_temperature_keyboard():
    """Клавиатура для выбора температуры"""
    builder = InlineKeyboardBuilder()
    builder.row(MessageButton(text="36.6"))
    builder.row(MessageButton(text="Нет температуры"))
    builder.row(MessageButton(text="❌ Отменить"))
    return builder.as_markup()
########################################
def get_sick_leave_keyboard():
    """Клавиатура для выбора необходимости больничного"""
    builder = InlineKeyboardBuilder()
    builder.row(MessageButton(text="✅ Да, требуется"))
    builder.row(MessageButton(text="❌ Нет, не требуется"))
    builder.row(MessageButton(text="❌ Отменить вызов"))
    return builder.as_markup()
########################################
def get_edit_keyboard():
    """Клавиатура с полями для редактирования (inline)"""
    builder = InlineKeyboardBuilder()
    
    # Персональные данные
    builder.row(
        MessageButton(text="✏️ ФИО"),
        MessageButton(text="✏️ Дата рождения")
    )
    
    # Контакты
    builder.row(
        MessageButton(text="✏️ Телефон")
    )
    
    # Адресные данные
    builder.row(
        MessageButton(text="✏️ Адрес"),
        MessageButton(text="✏️ Подъезд/Этаж")
    )
    builder.row(
        MessageButton(text="✏️ Особенности доступа")
    )
    
    # Медицинские данные
    builder.row(
        MessageButton(text="✏️ Температура"),
        MessageButton(text="✏️ Симптомы")
    )
    builder.row(
        MessageButton(text="✏️ Больничный лист"),
    )
    
    # Действия
    builder.row(
        MessageButton(text="🔙 Назад к подтверждению"),
        MessageButton(text="❌ Отменить вызов")
    )
    
    return builder.as_markup()
#########################################
def accept_cancel_keybord(call_id: int):
    """Клавиатура """
    builder = InlineKeyboardBuilder()
   
    builder.row(CallbackButton(text="✅ Принять", payload=f"accept_choice_doc_{call_id}"),)
    builder.row(CallbackButton(text="❌ Отклонить", payload=f"reject_{call_id}"),)
    return builder.as_markup() 
########################################
async def choice_doctors(call_id: int, doctors):
    """Клавиатура выбора врача для регистратора"""
    builder = InlineKeyboardBuilder()
    
    for doctor in doctors:
        builder.row(
            CallbackButton(
                text=f"👨‍⚕️ {doctor.full_name}",
                payload=f"accept_{call_id}_{doctor.id}"
            )
        )
    
    builder.row(
        CallbackButton(
            text="🔍 Другой врач (без назначения)",
            payload=f"accept_{call_id}_0"
        )
    )
    
    return builder.as_markup()
########################################
def request_details_keyboard(status: str, request_id: int, created_today: bool = False):
    """Клавиатура для деталей вызова (только для пациента)"""
    builder = InlineKeyboardBuilder()
    buttons = []
    
    # Кнопки для пациента
    # Показываем кнопку отмены только для сегодняшних вызовов со статусом new или approved
    if created_today and status in ['new', 'approved']:
        buttons.append(
            CallbackButton(
                text="🚫 Отменить вызов",
                payload=f"patient_cancel_{request_id}"
            )
        )
    
    # Кнопка назад к списку вызовов
    buttons.append(
        CallbackButton(
            text="← К списку вызовов",
            payload="my_requests"
        )
    )
    
    # Распределяем кнопки по рядам
    for btn in buttons:
        builder.row(btn)
    
    return builder.as_markup()

#########################################

def request_details_admin_keyboard(status: str, request_id: int):
    """Клавиатура для деталей вызова (для администратора/регистратора)"""
    builder = InlineKeyboardBuilder()
    buttons = []
    
    # Кнопки для админа/регистратора
    if status == 'new':
        buttons.append(
            CallbackButton(
                text="✅ Принять",
                payload=f"accept_choice_doc_{request_id}"
            )
        )
        buttons.append(
            CallbackButton(
                text="❌ Отклонить",
                payload=f"reject_{request_id}"
            )
        )
    elif status == 'pending_cancellation':
        buttons.append(
            CallbackButton(
                text="✅ Подтвердить отмену",
                payload=f"confirm_cancel_{request_id}"
            )
        )
    
    # Кнопка назад
    buttons.append(
        CallbackButton(
            text="← К списку вызовов",
            payload="my_requests"
        )
    )
    
    # Распределяем кнопки по рядам
    for btn in buttons:
        builder.row(btn)
    
    return builder.as_markup()
#########################################

# Admin keyboars

def admin_main_kb(bot_status: bool, auto_schedule: bool) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    current_year = datetime.now().year
    current_month = datetime.now().month
    current_day = datetime.now().day
    timestamp = int(datetime.now().timestamp())  # Уникальный параметр
    # Статус бота и ручное управление
    builder.row(
        CallbackButton(
            text=f"{'🟢 ВКЛЮЧЕН' if bot_status else '🔴 ВЫКЛЮЧЕН'} (Ручное управление)",
            payload=f"toggle_bot_{timestamp}"
        )
    )
    
    # Управление расписанием
    builder.row(
        CallbackButton(
            text=f"{'✅' if auto_schedule else '❌'} Авторасписание",
            payload="toggle_auto_schedule"
        )
    )
    
    # Дополнительные функции
    builder.row(
        CallbackButton(text="⏰ Настроить часы", payload="edit_schedule"),
    )
    # Статистика за сегодня
    builder.row(
        CallbackButton(
            text="📊 Статистика(за сегодня)",
            payload=f"stats_day_{current_year}_{current_month}_{current_day}"
        )
    )
    # Статистика за период
    builder.row(
        CallbackButton(
            text="📈📅 Статистика",
            payload="period_custom"
        )
    )
    # Сотрудники
    builder.row(
        CallbackButton(
            text="👤 Врачи",
            payload="sotrudniki"
        )
    )
    # Помощь админу
    builder.row(
        CallbackButton(
            text="🆘 Помощь",
            payload="admin_help"
        )
    )
    builder.row(CallbackButton(text="🏠 Главное меню", payload="main_menu"),)
    return builder.as_markup()
##################################################################
async def schedule_settings_kb(db: DataBase) -> InlineKeyboardBuilder:
    """
    Клавиатура настроек расписания работы бота
    """
    builder = InlineKeyboardBuilder()
    
    settings = await db.get_settings()
    
    # Кнопки с текущим временем
    builder.row(
        CallbackButton(
            text=f"🕘 Будни: {settings.weekday_start.strftime('%H:%M')}-{settings.weekday_end.strftime('%H:%M')}",
            payload="weekday_time_setup"
        )
    )
    
    builder.row(
        CallbackButton(
            text=f"🌅 Выходные: {settings.weekend_start.strftime('%H:%M')}-{settings.weekend_end.strftime('%H:%M')}",
            payload="weekend_time_setup"
        )
    )
    
    builder.row(
        CallbackButton(
            text="🔙 Назад",
            payload="admin"
        )
    )
    
    return builder.as_markup()

#################################################################

async def inline_add_doctor():
    kb = InlineKeyboardBuilder()
    # Кнопки управления
    kb.row(CallbackButton(text="➕ Добавить доктора", payload="add_doctor"),)
    
    # Кнопка возврата 
    kb.row(CallbackButton(text="🔙 В админ-панель", payload="admin"),)
    return kb.as_markup()
################################################################

async def inline_pagination(position, pages, id):
    kb = InlineKeyboardBuilder()
    
    # Кнопки пагинации в одном ряду
    row_buttons = []
    
    # Кнопка назад
    if position == 0:
        row_buttons.append(CallbackButton(text="⬅️", payload="noop"))
    else:
        row_buttons.append(CallbackButton(
            text="⬅️", 
            payload=f"sotrudniki_pages:{position - 1}:{id}"
        ))
    
    # Кнопка с номером страницы
    row_buttons.append(CallbackButton(
        text=f"📄 {position + 1}/{pages}", 
        payload="noop"
    ))
    
    # Кнопка вперед
    if position < pages - 1:
        row_buttons.append(CallbackButton(
            text="➡️", 
            payload=f"sotrudniki_pages:{position + 1}:{id}"
        ))
    else:
        row_buttons.append(CallbackButton(text="➡️", payload="noop"))
    
    kb.row(*row_buttons)
    
    # Кнопки действий
    kb.row(CallbackButton(text="🔄 Статус", payload=f"change_status:{id}"))
    kb.row(CallbackButton(text="❌ Удалить", payload=f"delete_doctor:{id}"))
    
    # Кнопки управления
    kb.row(CallbackButton(text="➕ Добавить доктора", payload="add_doctor"))
    
    # Кнопка возврата
    kb.row(CallbackButton(text="🔙 В админ-панель", payload="admin"))
    
    return kb.as_markup()
################################################################
async def inline_back_admin():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Админ-панель", payload="admin"),)
    return kb.as_markup()
#################################################################

def request_details_admin_keyboard(status: str, request_id: int):
    """Клавиатура для деталей вызова (для администратора/регистратора)"""
    builder = InlineKeyboardBuilder()
    
    if status == 'pending_cancellation':
        builder.row(
            CallbackButton(
                text="✅ Подтвердить отмену",
                payload=f"confirm_cancel_{request_id}"
            )
        )
        builder.row(
            CallbackButton(
                text="❌ Отклонить отмену",
                payload=f"reject_cancel_{request_id}"
            )
        )
    
    builder.row(
        CallbackButton(
            text="← К списку вызовов",
            payload="my_requests"
        )
    )
    
    return builder.as_markup()
##################################################################
async def admin_home_kb(date: str = None):
    """Клавиатура админ-панели с поддержкой даты
    Args:
        date: Дата в формате ДД-ММ-ГГГГ (если None - текущая дата)
    """
    from datetime import datetime
    
    # Если дата не передана, используем текущую с ведущими нулями
    if date is None:
        date = datetime.now().strftime("%d-%m-%Y")
    
    # Если дата передана в неправильном формате (без ведущих нулей), преобразуем её
    try:
        date_obj = datetime.strptime(date, "%d-%m-%Y")
        date = date_obj.strftime("%d-%m-%Y")
    except ValueError:
        # Если не удалось распарсить, оставляем как есть
        pass
    
    builder = InlineKeyboardBuilder()
    
    # Кнопка экспорта (пока без функционала)
    builder.row(
        CallbackButton(
            text=f"📊 Скачать Excel ({date})",
            payload=f"export_{date}"
        )
    )
    
    # Кнопка возврата в админ-панель
    builder.row(
        CallbackButton(
            text="⚙️ В админ панель",
            payload="admin"
        )
    )
    
    return builder.as_markup()
###################################################################
def admin_kb() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text="⚙️ В админ панель",
            payload="admin"
        )
    )
    return builder.as_markup()
#################################################################
async def stats_calendar_kb(year: int = None, month: int = None, select_start: bool = True):
    """Календарь для выбора даты периода"""
    builder = InlineKeyboardBuilder()
    
    if year is None or month is None:
        today = datetime.now()
        year = today.year
        month = today.month
    
    # Получаем календарь на месяц
    cal = calendar.monthcalendar(year, month)
    month_name = RUS_MONTHS[month]
    
    # 1. Заголовок с указанием, что выбираем
    builder.row(
        CallbackButton(
            text=f"{month_name} {year} ({'Начало' if select_start else 'Конец'})",
            payload=f"ignore_{year}_{month}"
        )
    )
    
    # 2. Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[
        CallbackButton(text=day, payload=f"ignore_{year}_{month}")
        for day in week_days
    ])
    
    # 3. Числа месяца
    for week in cal:
        row_buttons = []
        for day in week:
            if day == 0:
                row_buttons.append(
                    CallbackButton(text="ㅤ", payload=f"ignore_{year}_{month}")
                )
            else:
                row_buttons.append(
                    CallbackButton(
                        text=str(day),
                        payload=f"stats_select_date_{year}_{month}_{day}_{'start' if select_start else 'end'}"
                    )
                )
        builder.row(*row_buttons)
            
        
   
    # 4. Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    builder.row(
        CallbackButton(
            text="◀️",
            payload=f"stats_calendar_{prev_year}_{prev_month}_{'start' if select_start else 'end'}"
        ),
        CallbackButton(
            text="▶️",
            payload=f"stats_calendar_{next_year}_{next_month}_{'start' if select_start else 'end'}"
        )
    )
    
    # 5. Кнопка отмены
    builder.row(
        CallbackButton(
            text="⚙️ В админ панель",  # Добавлен эмодзи настроек
            payload="admin"
        )
    )
    
    return builder.as_markup()
################################################################