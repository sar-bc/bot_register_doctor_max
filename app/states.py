from maxapi.context  import State, StatesGroup

class DoctorCall(StatesGroup):
    FULL_NAME = State()            # ФИО полностью
    BIRTH_DATE = State()          # Дата рождения
    ADDRESS = State()             # Фактический адрес
    ADDRESS_DETAILS = State()     # Детали адреса (подъезд/этаж или пометка для частного дома)
    ACCESS_NOTES = State()        # Особенности доступа
    PHONE = State()              # Номер телефона
    TEMPERATURE = State()        # Температура
    SYMPTOMS = State()           # Симптомы
    SICK_LEAVE = State()  # Требуется ли больничный лист

    DOOR_CODE_INPUT = State()    # Код двери(если есть)
    CUSTOM_ACCESS_NOTES = State() # Описание своими словами

    FINAL_CONFIRMATION = State()
    EDIT_REQUEST = State()  # Редактирование
    is_editing = State()
    REASON = State() # отказ для пациента
    PATIENT_ID = State() # ID пациента
    CHOOSE_PATIENT = State()        # Выбор существующего ребенка
    
# Флаговые состояния
class Flags(StatesGroup):
    editing = State()  # Для отслеживания режима редактирования


class UserStatus(StatesGroup):
    NEW_USER = State()
    RETURNING_USER = State()
    FILLING_FORM = State()
        

class CalendarStates(StatesGroup):
    select_year = State()
    select_month = State()
    select_day = State()
    selected_period = State()  # Для хранения выбранного периода


class TimeSetupStates(StatesGroup):
    WAITING_WEEKDAY_START = State()
    WAITING_WEEKDAY_END = State()
    WAITING_WEEKEND_START = State()
    WAITING_WEEKEND_END = State()
        

class PaginationState(StatesGroup):
    position = State()
    sent_mess_id = State()

class AddDoctor(StatesGroup):
    max_id = State()
    full_name = State()
    phone = State()   
             