from maxapi import Router
from maxapi.types import MessageCreated, Command, CommandStart, BotStarted, MessageCallback
from database.Database import DataBase
from core.log import Logger
from datetime import datetime
from maxapi.context import MemoryContext
import app.keyboards as kb
from maxapi.enums.parse_mode import ParseMode
from maxapi import F
from core.dictionary import *
from maxapi import Bot
from database.models import *
from app.states import *
import re

router = Router()
logger = Logger(__name__)

###########################################################
DOCTOR_CALL_STATES = [
    DoctorCall.CHOOSE_PATIENT,
    DoctorCall.FULL_NAME,
    DoctorCall.BIRTH_DATE,
    DoctorCall.ADDRESS,
    DoctorCall.ADDRESS_DETAILS,
    DoctorCall.ACCESS_NOTES,
    DoctorCall.DOOR_CODE_INPUT,
    DoctorCall.CUSTOM_ACCESS_NOTES,
    DoctorCall.PHONE,
    DoctorCall.TEMPERATURE,
    DoctorCall.SYMPTOMS,
    DoctorCall.SICK_LEAVE,
    DoctorCall.FINAL_CONFIRMATION,
    DoctorCall.EDIT_REQUEST,
]

############################################################
@router.bot_started()
async def bot_started_handler(event: BotStarted, db: DataBase):
    """
    Вызывается, когда пользователь нажимает "Начать" или впервые открывает бота
    """
    user_id = event.user.user_id
    chat_id = event.chat_id
    username = event.user.username if hasattr(event.user, 'username') else None
    full_name = event.user.first_name if hasattr(event.user, 'first_name') else f"User_{user_id}"
    
    await logger.info(f'📱 BOT_STARTED: пользователь {user_id}, чат {chat_id}')
    
    try:
        # Регистрируем пользователя
        is_new = await db.add_new_user(
            user_id=chat_id,
            username=username,
            full_name=full_name
        )
        
        user_state = await db.get_state(chat_id)
        
        # Отправляем приветствие
        if is_new:
            welcome_text = (
                "👋 *Добро пожаловать!*\n\n"
                "Я бот поликлиники.\n\n"
                "📋 *Доступные команды:*\n"
            )
        else:
            welcome_text = (
                "🔔 *С возвращением!*\n\n"
                "Чем могу помочь?\n\n"
            )
        
        sent_mess = await event.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            attachments=[await kb.main_menu_kb(chat_id)]
        )
        await logger.info(f'✅ Приветствие отправлено пользователю {chat_id}')
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
    except Exception as e:
        await logger.error(f'❌ Ошибка отправки приветствия: {e}')
        await event.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка. Попробуйте позже.",
            attachments=[kb.home_keyboard_inline()]
        )

##########################################################################
@router.message_created(CommandStart())
async def cmd_start(event: MessageCreated, context: MemoryContext):
    db = DataBase()
    user_id = event.chat.chat_id
    await logger.info(f'📱 CMD_START: пользователь {user_id}')
    try:
        user_state = await db.get_state(user_id)
        # Всегда сбрасываем состояние и чистим сообщения
        await context.set_state(None)
        
        # Удаляем предыдущие сообщения если нужно
        if user_state and user_state.last_message_ids:
            await db.delete_messages(user_state)
            user_state.last_message_ids = []

        # Регистрируем/обновляем пользователя
        is_new = await db.add_new_user(
            user_id=event.chat.chat_id,
            username=event.from_user.username,
            full_name=event.from_user.full_name
        )
        
        # Отправляем соответствующее сообщение
        text = "👋 Добро пожаловать!" if is_new else "🔔 С возвращением!"
        sent_mess = await event.message.answer(
            f"{text} Чем могу помочь?",
            attachments=[await kb.main_menu_kb(user_id)]
        )
        
        # Сохраняем ID сообщения и обновляем активность
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        await db.update_user_activity(event.chat.chat_id)
        await logger.info(f'✅ CMD_START выполнен для пользователя {user_id}')
        
    except Exception as e:
        await logger.error(f"Ошибка в /start: {e}")
        await event.message.answer("⚠️ Произошла ошибка. Попробуйте позже.", attachments=[kb.home_keyboard_inline()])
    finally:
        await db.close()

##################################################################
@router.message_callback(F.callback.payload == "main_menu")
@router.message_created(F.message.body.text == "❌ Отменить вызов")
@router.message_created(F.message.body.text == "🏠 Главное меню")
async def return_to_main_menu(event: MessageCreated | MessageCallback, context: MemoryContext, db: DataBase):
    """Обработчик возврата в главное меню (работает и для сообщений и для callback)"""
    
    try:
        await logger.info(f'📱 return_to_main_menu: начало')
        # Очищаем состояние
        await context.set_state(None)
        
        # Определяем тип события
        if isinstance(event, MessageCallback):
            message = event.message
            user_id = event.chat.chat_id
        else:
            message = event
            user_id = event.chat.chat_id
        
        await logger.info(f'return_to_main_menu: user_id={user_id}')
        
        user_state = await db.get_state(user_id)
        # Удаляем предыдущие сообщения если нужно
        if user_state and user_state.last_message_ids:
            await db.delete_messages(user_state)
            user_state.last_message_ids = []
        
        # Отправляем новое сообщение
        sent_mess = await event.message.answer(
            "Вы вернулись в главное меню. Чем могу помочь?",
            attachments=[await kb.main_menu_kb(user_id)]
        )
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        
        # Обновляем активность
        await db.update_user_activity(user_id)
        await logger.info(f'✅ return_to_main_menu: завершен для user_id={user_id}')
        
    except Exception as e:
        await logger.error(f"Ошибка при возврате в меню: {e}")
        error_msg = "⚠️ Произошла ошибка. Попробуйте позже."
        if isinstance(event, MessageCallback):
            await event.message.answer(error_msg, attachments=[kb.home_keyboard_inline()])
        else:
            await event.message.answer(error_msg, attachments=[kb.home_keyboard_inline()])
    finally:
        await db.close()

##################################################################

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ УДАЛЕНИЯ СООБЩЕНИЙ ==========
async def delete_previous_messages(event, db):
    """Удаляет все предыдущие сообщения пользователя"""
    user_id = event.chat.chat_id
    user_state = await db.get_state(user_id)
    if user_state and user_state.last_message_ids:
        await db.delete_messages(user_state)
        user_state.last_message_ids = []
        await db.update_state(user_state)

#====================================================
async def send_and_save(event, text, keyboard=None, db=None):
    """Отправляет сообщение и сохраняет его ID"""
    sent_mess = await event.message.answer(text, attachments=[keyboard] if keyboard else None)
    if db:
        user_id = event.chat.chat_id
        user_state = await db.get_state(user_id)
        if user_state:
            user_state.last_message_ids.append(sent_mess.message.body.mid)
            await db.update_state(user_state)
    return sent_mess

# ========== НАЧАЛО ВЫЗОВА ==========
@router.message_callback(F.callback.payload == "doctor_form_start:new")
async def start_new_doctor_call(event: MessageCallback, context: MemoryContext, db: DataBase):
    """Обработчик новой анкеты (нажата кнопка Новая анкета)"""
    user_id = event.chat.chat_id
    await logger.info(f'📱 start_new_doctor_call: пользователь {user_id}, создаем новую анкету')
    
    # Удаляем предыдущие сообщения
    await delete_previous_messages(event, db)
    
    # Проверка статуса бота
    settings = await db.get_settings()
    if not settings.bot_active:
        sent_mess = await event.message.answer(
            CALLS_FINISHED_TODAY_TEXT % (
                settings.weekday_start.strftime('%H:%M'),
                settings.weekday_end.strftime('%H:%M'),
                settings.weekend_start.strftime('%H:%M'),
                settings.weekend_end.strftime('%H:%M')
            ),
            attachments=[kb.home_keyboard_inline()]
        )
        user_state = await db.get_state(user_id)
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        return
    
    # Сразу начинаем новую анкету
    await start_new_patient_form(event, context, db)
    
    await logger.info(f'✅ start_new_doctor_call: завершен для user_id={user_id}')

#################################################################

@router.message_callback(F.callback.payload == "doctor_form_start")
async def start_doctor_call(event: MessageCallback, context: MemoryContext, db: DataBase):
    """Начало вызова врача"""
    user_id = event.chat.chat_id
    await logger.info(f'📱 start_doctor_call: пользователь {user_id}')
    
    # Удаляем предыдущие сообщения
    await delete_previous_messages(event, db)
    
    # Проверка статуса бота
    settings = await db.get_settings()
    if not settings.bot_active:
        await logger.info(f'start_doctor_call: бот неактивен, user_id={user_id}')
        sent_mess = await event.message.answer(
            CALLS_FINISHED_TODAY_TEXT % (
                settings.weekday_start.strftime('%H:%M'),
                settings.weekday_end.strftime('%H:%M'),
                settings.weekend_start.strftime('%H:%M'),
                settings.weekend_end.strftime('%H:%M')
            ),
            attachments=[kb.home_keyboard_inline()]
        )
        user_state = await db.get_state(user_id)
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        return
    
    # Получаем сохраненных детей
    patients = await db.get_pacient_all(user_id)
    await logger.info(f'start_doctor_call: найдено {len(patients)} пациентов')
    
    if patients:
        # Показываем выбор ребенка
        await logger.info(f'start_doctor_call: показываем выбор пациента')
        sent_mess = await event.message.answer(
            "👶 Кому будем вызывать врача?",
            attachments=[await kb.choice_patients(user_id, patients)]
        )
        await context.set_state(DoctorCall.CHOOSE_PATIENT)
        user_state = await db.get_state(user_id)
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        await logger.info(f'start_doctor_call: установлено состояние CHOOSE_PATIENT')
    else:
        # Сразу начинаем новую анкету
        await logger.info(f'start_doctor_call: нет пациентов, начинаем новую анкету')
        await start_new_patient_form(event, context, db)
    
    await logger.info(f'✅ start_doctor_call: завершен для user_id={user_id}')

#=================================================================

async def start_new_patient_form(event, context, db):
    """Начало анкеты для нового пациента"""
    user_id = event.chat.chat_id
    await logger.info(f'📱 start_new_patient_form: пользователь {user_id}')
    
    # Очищаем данные
    await context.update_data(
        form_data={},
        editing=False
    )
    
    await context.set_state(DoctorCall.FULL_NAME)
    await logger.info(f'start_new_patient_form: установлено состояние FULL_NAME')
    
    await send_and_save(event, 
        "1. 👤 Укажите <b>ФИО полностью</b>:\nПример: <i>Иванов Алексей Сергеевич</i>",
        kb.cancel_kb(), db
    )
    await logger.info(f'✅ start_new_patient_form: завершен для user_id={user_id}')

# ========== ВЫБОР СУЩЕСТВУЮЩЕГО РЕБЕНКА ==========
@router.message_callback(F.callback.payload.startswith("choose_patient:"))
async def choose_patient(event: MessageCallback, context: MemoryContext, db: DataBase):
    """Выбор существующего ребенка"""
    try:
        # Получаем ID пациента из payload (это id из таблицы patients, не max_id)
        parts = event.callback.payload.split(":")
        patient_id = int(parts[1])
        
        user_id = event.chat.chat_id
        await logger.info(f'📱 choose_patient: пользователь {user_id}, patient_id={patient_id}')
        
        # Удаляем предыдущие сообщения
        await delete_previous_messages(event, db)
        
        # Загружаем данные ребенка по его внутреннему ID
        patient = await db.get_patient(patient_id)
        
        if not patient:
            await logger.error(f'choose_patient: пациент с id={patient_id} не найден')
            await send_and_save(event, "❌ Ребенок не найден", kb.cancel_kb(), db)
            return
        
        # Сохраняем в context
        form_data = {
            'patient_id': patient.id,
            'full_name': patient.full_name,
            'birth_date': patient.birth_date,
            'address': patient.address,
            'address_details': patient.address_details,
            'access_notes': patient.access_notes,
            'door_code': patient.door_code,
            'phone': patient.phone,
        }
        await context.update_data(form_data=form_data, editing=False)
        await logger.info(f'choose_patient: данные пациента загружены: {patient.full_name}')
        
        # Сразу переходим к температуре
        await context.set_state(DoctorCall.TEMPERATURE)
        await logger.info(f'choose_patient: установлено состояние TEMPERATURE')
        
        # Отправляем вопрос о температуре
        await send_and_save(event,
            "🌡 <b>Температура на момент вызова</b> (цифрами)\nНапример 36.6",
            kb.get_temperature_keyboard(), db
        )
        
        await logger.info(f'✅ choose_patient: завершен для user_id={user_id}, пациент: {patient.full_name}')
        
    except ValueError as e:
        await logger.error(f'choose_patient: ошибка парсинга ID - {e}')
        await send_and_save(event, "❌ Ошибка выбора пациента. Попробуйте еще раз.", kb.cancel_kb(), db)
    except Exception as e:
        await logger.error(f'choose_patient: ошибка - {e}')
        await send_and_save(event, "⚠️ Произошла ошибка. Попробуйте позже.", kb.home_keyboard_inline(), db)

# ========== УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ШАГОВ ==========
@router.message_created()
async def handle_doctor_form_steps(event: MessageCreated, context: MemoryContext, db: DataBase):
    """Обработка всех шагов анкеты"""
    current_state = await context.get_state()
    user_id = event.chat.chat_id
    
    # Если не в режиме анкеты - выходим
    if not current_state:
        return
    
    # Проверяем, что это состояние из DoctorCall
    if current_state not in DOCTOR_CALL_STATES:
        return
    
    text = event.message.body.text.strip()
    await logger.info(f'📱 handle_doctor_form_steps: user_id={user_id}, state={current_state}, text={text[:50]}')
    
    # ===== ОБРАБОТКА ОТМЕНЫ =====
    if text == "❌ Отменить вызов":
        await logger.info(f'handle_doctor_form_steps: отмена вызова, user_id={user_id}')
        await cancel_doctor_call(event, context, db)
        return
    
    # Получаем данные
    data = await context.get_data()
    form_data = data.get('form_data', {})
    editing = data.get('editing', False)
    edit_target = data.get('edit_target')
    
    # Удаляем сообщение пользователя
    await event.message.delete()
    
    # ===== ОБРАБОТКА ПО СОСТОЯНИЯМ =====
    
    # Шаг 1: ФИО
    if current_state == DoctorCall.FULL_NAME:
        await logger.info(f'handle_doctor_form_steps: обработка FULL_NAME')
        if len(text.split()) < 2:
            await logger.info(f'handle_doctor_form_steps: ошибка - недостаточно слов в ФИО')
            await send_error(event, context, db, "❌ Пожалуйста, укажите полное ФИО (Фамилия Имя Отчество)")
            return
        
        form_data['full_name'] = text
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'full_name':
            await logger.info(f'handle_doctor_form_steps: возврат к подтверждению')
            await return_to_confirmation(event, context, db)
        else:
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.BIRTH_DATE)
            await send_question(event, context, db, "2. 📅 Укажите дату рождения ДД.ММ.ГГГГ (02.01.2015):")
    
    # Шаг 2: Дата рождения
    elif current_state == DoctorCall.BIRTH_DATE:
        await logger.info(f'handle_doctor_form_steps: обработка BIRTH_DATE')
        try:
            birth_date = datetime.strptime(text, "%d.%m.%Y").date()
            if birth_date > datetime.now().date():
                await logger.info(f'handle_doctor_form_steps: ошибка - дата в будущем')
                await send_error(event, context, db, "❗️ Дата рождения не может быть в будущем.")
                return
            
            form_data['birth_date'] = text
            await context.update_data(form_data=form_data)
            
            if editing and edit_target == 'birth_date':
                await logger.info(f'handle_doctor_form_steps: возврат к подтверждению')
                await return_to_confirmation(event, context, db)
            else:
                await delete_previous_messages(event, db)
                await context.set_state(DoctorCall.ADDRESS)
                await send_question(event, context, db, "3. 📌 Укажите фактический адрес (где находится ребенок):")
        except ValueError:
            await logger.info(f'handle_doctor_form_steps: ошибка - неверный формат даты')
            await send_error(event, context, db, "❗️ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    
    # Шаг 3: Адрес
    elif current_state == DoctorCall.ADDRESS:
        await logger.info(f'handle_doctor_form_steps: обработка ADDRESS')
        if len(text) < 5:
            await logger.info(f'handle_doctor_form_steps: ошибка - адрес слишком короткий')
            await send_error(event, context, db, "Адрес слишком короткий. Укажите полный адрес")
            return
        
        form_data['address'] = text
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'address':
            await return_to_confirmation(event, context, db)
        else:
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.ADDRESS_DETAILS)
            await send_question(event, context, db,
                "4. 💬 Укажите № подъезда, этаж:",
                kb.address_type_kb()
            )
    
    # Шаг 4: Подъезд/этаж
    elif current_state == DoctorCall.ADDRESS_DETAILS:
        await logger.info(f'handle_doctor_form_steps: обработка ADDRESS_DETAILS')
        form_data['address_details'] = text if text != "🏠 Частный дом (нет подъезда/этажа)" else None
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'address_details':
            await return_to_confirmation(event, context, db)
        else:
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.ACCESS_NOTES)
            await send_question(event, context, db,
                "5. 💬 Укажите наличие (домофон, код двери, злая собака):",
                kb.get_access_notes_keyboard()
            )
    
    # Шаг 5: Особенности доступа
    elif current_state == DoctorCall.ACCESS_NOTES:
        await logger.info(f'handle_doctor_form_steps: обработка ACCESS_NOTES, choice={text}')
        if text == "🔢 Код двери":
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.DOOR_CODE_INPUT)
            await send_question(event, context, db, "Введите код двери:")
        elif text == "✏️ Другое":
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.CUSTOM_ACCESS_NOTES)
            await send_question(event, context, db, "Опишите своими словами:")
        elif text == "⏭ Пропустить":
            form_data['access_notes'] = "Не указано"
            await context.update_data(form_data=form_data)
            await go_to_phone(event, context, db, editing)
        else:
            notes_map = {
                "🚪 Домофон есть": "Домофон установлен",
                "❌ Нет домофона": "Домофон отсутствует",
                "🐕 Собака": "Есть собака (не агрессивная)",
                "🐺 Злая собака!": "Есть злая собака! Будьте осторожны",
                "👮 Охрана": "Есть охрана/консьерж",
                "🏢 Свободный вход": "Свободный доступ в подъезд",
            }
            form_data['access_notes'] = notes_map.get(text, text)
            await context.update_data(form_data=form_data)
            await go_to_phone(event, context, db, editing)
    
    # Шаг 5a: Код двери
    elif current_state == DoctorCall.DOOR_CODE_INPUT:
        await logger.info(f'handle_doctor_form_steps: обработка DOOR_CODE_INPUT')
        if not text.isdigit() or len(text) < 2 or len(text) > 6:
            await logger.info(f'handle_doctor_form_steps: ошибка - неверный код двери')
            await send_error(event, context, db, "⚠️ Введите корректный код двери (2-6 цифр):")
            return
        
        form_data['door_code'] = text
        form_data['access_notes'] = f"код двери: {text}"
        await context.update_data(form_data=form_data)
        await go_to_phone(event, context, db, editing)
    
    # Шаг 5b: Свой вариант
    elif current_state == DoctorCall.CUSTOM_ACCESS_NOTES:
        await logger.info(f'handle_doctor_form_steps: обработка CUSTOM_ACCESS_NOTES')
        if len(text) < 5:
            await logger.info(f'handle_doctor_form_steps: ошибка - слишком короткое описание')
            await send_error(event, context, db, "❌ Слишком короткое описание (минимум 5 символов):")
            return
        
        form_data['custom_notes'] = text
        form_data['access_notes'] = f"Особенности: {text}"
        await context.update_data(form_data=form_data)
        await go_to_phone(event, context, db, editing)
    
    # Шаг 6: Телефон
    elif current_state == DoctorCall.PHONE:
        await logger.info(f'handle_doctor_form_steps: обработка PHONE')
        phone = await extract_phone_from_event(event, text)
        if not phone:
            await send_error(event, context, db, "❌ Не удалось получить номер. Попробуйте еще раз:")
            return
        
        normalized = re.sub(r'[^\d]', '', phone)
        if normalized.startswith('8'):
            normalized = '7' + normalized[1:]
        formatted = f"+7{normalized[1:]}"
        
        if len(normalized) != 11:
            await send_error(event, context, db, "❌ Неверный формат. Введите 11 цифр:")
            return
        
        form_data['phone'] = formatted
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'phone':
            await return_to_confirmation(event, context, db)
        else:
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.TEMPERATURE)
            await send_question(event, context, db,
                "7. 🌡 Температура на момент вызова (цифрами)\nНапример 36.6",
                kb.get_temperature_keyboard()
            )
    
    # Шаг 7: Температура
    elif current_state == DoctorCall.TEMPERATURE:
        await logger.info(f'handle_doctor_form_steps: обработка TEMPERATURE')
        if text == "Нет температуры":
            form_data['temperature'] = "36.6"
        elif text == "36.6":
            form_data['temperature'] = "36.6"
        else:
            try:
                temp = text.replace(',', '.').strip()
                temp_float = float(temp)
                if not 35.0 <= temp_float <= 42.0:
                    raise ValueError
                form_data['temperature'] = temp
            except ValueError:
                await send_error(event, context, db, "❌ Температура должна быть между 35.0 и 42.0")
                return
        
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'temperature':
            await return_to_confirmation(event, context, db)
        else:
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.SYMPTOMS)
            await send_question(event, context, db, "8. 📝 Симптомы на данный момент, (кашель, диарея) и т.д.:")
    
    # Шаг 8: Симптомы
    elif current_state == DoctorCall.SYMPTOMS:
        await logger.info(f'handle_doctor_form_steps: обработка SYMPTOMS')
        if len(text) < 3:
            await send_error(event, context, db, "❌ Слишком короткое описание симптомов")
            return
        
        form_data['symptoms'] = text
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'symptoms':
            await return_to_confirmation(event, context, db)
        else:
            await delete_previous_messages(event, db)
            await context.set_state(DoctorCall.SICK_LEAVE)
            await send_question(event, context, db,
                "9. 📃 Требуется ли оформление больничного листа?",
                kb.get_sick_leave_keyboard()
            )
    
    # Шаг 9: Больничный
    elif current_state == DoctorCall.SICK_LEAVE:
        await logger.info(f'handle_doctor_form_steps: обработка SICK_LEAVE')
        sick_map = {
            "✅ Да, требуется": True,
            "❌ Нет, не требуется": False,
            "✏️ Не знаю": False
        }
        form_data['sick_leave'] = sick_map.get(text, False)
        await context.update_data(form_data=form_data)
        
        if editing and edit_target == 'sick_leave':
            await return_to_confirmation(event, context, db)
        else:
            await show_confirmation(event, context, db)
    
    # Шаг 10: Финальное подтверждение
    elif current_state == DoctorCall.FINAL_CONFIRMATION:
        await logger.info(f'handle_doctor_form_steps: обработка FINAL_CONFIRMATION, choice={text}')
        if text == "✅ Подтвердить вызов":
            await logger.info(f'handle_doctor_form_steps: подтверждение вызова')
            await confirm_and_save(event, context, db)
        elif text == "✏️ Редактировать данные":
            await logger.info(f'handle_doctor_form_steps: редактирование данных')
            await show_edit_menu(event, context, db)
        elif text == "❌ Отменить вызов":
            await logger.info(f'handle_doctor_form_steps: отмена вызова')
            await cancel_doctor_call(event, context, db)
    
    # Шаг 11: Редактирование
    elif current_state == DoctorCall.EDIT_REQUEST:
        await logger.info(f'handle_doctor_form_steps: обработка EDIT_REQUEST, choice={text}')
        await handle_edit_choice(event, context, db, text)
    
    await logger.info(f'✅ handle_doctor_form_steps: завершен для user_id={user_id}')

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def go_to_phone(event, context, db, is_editing):
    """Переход к шагу телефона"""
    user_id = event.chat.chat_id
    await logger.info(f'go_to_phone: user_id={user_id}, is_editing={is_editing}')
    if is_editing:
        await return_to_confirmation(event, context, db)
    else:
        await delete_previous_messages(event, db)
        await context.set_state(DoctorCall.PHONE)
        await send_question(event, context, db,
            "6. 📞 Укажите номер телефона в формате +7XXXXXXXXXX",
            kb.get_phone_keyboard()
        )

#=================================================================
async def extract_phone_from_event(event, text):
    """Извлечение телефона из контакта или текста"""
    if event.message.body.attachments:
        for att in event.message.body.attachments:
            if att.type == 'contact':
                vcf = att.payload.vcf_info
                for line in vcf.split('\n'):
                    if line.startswith('TEL'):
                        phone = line.split(':')[-1].strip()
                        await logger.info(f'extract_phone_from_event: извлечен телефон из контакта: {phone}')
                        return phone
    await logger.info(f'extract_phone_from_event: телефон из текста: {text if text != "✏️ Ввести вручную" else None}')
    return text if text != "✏️ Ввести вручную" else None

#=================================================================
async def send_question(event, context, db, text, keyboard=None):
    """Отправка вопроса и сохранение ID сообщения"""
    await logger.info(f'send_question: {text[:50]}...')
    sent_mess = await event.message.answer(text, attachments=[keyboard] if keyboard else None)
    user_state = await db.get_state(event.chat.chat_id)
    if user_state:
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
    return sent_mess

#=================================================================
async def send_error(event, context, db, text):
    """Отправка ошибки"""
    await logger.info(f'send_error: {text}')
    sent_mess = await event.message.answer(text, attachments=[kb.cancel_kb()])
    user_state = await db.get_state(event.chat.chat_id)
    if user_state:
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)

#=================================================================
async def show_confirmation(event, context, db):
    """Показать подтверждение с данными"""
    await delete_previous_messages(event, db)
    
    data = await context.get_data()
    form_data = data.get('form_data', {})
    user_id = event.chat.chat_id
    await logger.info(f'show_confirmation: user_id={user_id}')
    
    confirm_text = format_confirmation(form_data)
    
    await context.set_state(DoctorCall.FINAL_CONFIRMATION)
    sent_mess = await event.message.answer(
        f"✅ Проверьте данные:\n\n{confirm_text}",
        attachments=[kb.get_final_confirmation_kb()]
    )
    
    user_state = await db.get_state(user_id)
    user_state.last_message_ids.append(sent_mess.message.body.mid)
    await db.update_state(user_state)
    await logger.info(f'show_confirmation: подтверждение отправлено')

#=================================================================
async def show_edit_menu(event, context, db):
    """Показать меню редактирования"""
    await delete_previous_messages(event, db)
    
    user_id = event.chat.chat_id
    await logger.info(f'show_edit_menu: user_id={user_id}')
    await context.set_state(DoctorCall.EDIT_REQUEST)
    sent_mess = await event.message.answer(
        "Выберите что хотите изменить:",
        attachments=[kb.get_edit_keyboard()]
    )
    
    user_state = await db.get_state(user_id)
    user_state.last_message_ids.append(sent_mess.message.body.mid)
    await db.update_state(user_state)

#=================================================================
async def handle_edit_choice(event, context, db, choice):
    """Обработка выбора поля для редактирования"""
    user_id = event.chat.chat_id
    await logger.info(f'handle_edit_choice: user_id={user_id}, choice={choice}')
    
    field_map = {
        "✏️ ФИО": ("full_name", DoctorCall.FULL_NAME, "Введите ФИО заново:"),
        "✏️ Дата рождения": ("birth_date", DoctorCall.BIRTH_DATE, "Введите дату рождения (ДД.ММ.ГГГГ):"),
        "✏️ Адрес": ("address", DoctorCall.ADDRESS, "Введите адрес:"),
        "✏️ Подъезд/Этаж": ("address_details", DoctorCall.ADDRESS_DETAILS, "Введите подъезд и этаж:"),
        "✏️ Особенности доступа": ("access_notes", DoctorCall.ACCESS_NOTES, "Укажите особенности доступа:"),
        "✏️ Телефон": ("phone", DoctorCall.PHONE, "Введите телефон:"),
        "✏️ Температура": ("temperature", DoctorCall.TEMPERATURE, "Введите температуру:"),
        "✏️ Симптомы": ("symptoms", DoctorCall.SYMPTOMS, "Опишите симптомы:"),
        "✏️ Больничный лист": ("sick_leave", DoctorCall.SICK_LEAVE, "Нужен ли больничный?"),
    }
    
    if choice == "🔙 Назад к подтверждению":
        await logger.info(f'handle_edit_choice: возврат к подтверждению')
        await show_confirmation(event, context, db)
        return
    
    if choice == "❌ Отменить вызов":
        await logger.info(f'handle_edit_choice: отмена вызова')
        await cancel_doctor_call(event, context, db)
        return
    
    if choice in field_map:
        field, state, question = field_map[choice]
        data = await context.get_data()
        form_data = data.get('form_data', {})
        
        await context.update_data(
            form_data=form_data,
            editing=True,
            edit_target=field
        )
        await context.set_state(state)
        
        await delete_previous_messages(event, db)
        await send_question(event, context, db, question, kb.cancel_kb())
        await logger.info(f'handle_edit_choice: переход к состоянию {state}')

#=================================================================
async def return_to_confirmation(event, context, db):
    """Возврат к подтверждению после редактирования"""
    user_id = event.chat.chat_id
    await logger.info(f'return_to_confirmation: user_id={user_id}')
    
    await delete_previous_messages(event, db)
    
    data = await context.get_data()
    form_data = data.get('form_data', {})
    
    await context.update_data(
        form_data=form_data,
        editing=False,
        edit_target=None
    )
    await show_confirmation(event, context, db)

#=================================================================
async def cancel_doctor_call(event, context, db):
    """Отмена вызова"""
    user_id = event.chat.chat_id
    await logger.info(f'cancel_doctor_call: user_id={user_id}')
    
    await delete_previous_messages(event, db)
    
    await context.set_state(None)
    await context.update_data(form_data={}, editing=False)
    sent_mess = await event.message.answer("❌ Вызов отменен", attachments=[await kb.main_menu_kb(user_id)])
    
    user_state = await db.get_state(user_id)
    user_state.last_message_ids = [sent_mess.message.body.mid]
    await db.update_state(user_state)
    await logger.info(f'cancel_doctor_call: вызов отменен для user_id={user_id}')

#=================================================================
async def confirm_and_save(event, context, db):
    """Подтверждение и сохранение вызова"""
    data = await context.get_data()
    form_data = data.get('form_data', {})
    user_id = event.chat.chat_id
    
    await logger.info(f'confirm_and_save: user_id={user_id}')
    
    # Сохраняем вызов в DoctorCall
    call = await db.create_doctor_call(
        user_id=user_id,
        full_name=form_data['full_name'],
        birth_date=form_data['birth_date'],
        phone=form_data['phone'],
        address=form_data['address'],
        address_details=form_data.get('address_details'),
        access_notes=form_data.get('access_notes'),
        door_code=form_data.get('door_code'),
        temperature=form_data.get('temperature'),
        symptoms=form_data['symptoms'],
        need_sick_leave=form_data.get('sick_leave', False)
    )
    await logger.info(f'confirm_and_save: создан вызов ID={call.id}, номер={call.call_number}')
    
    # Если это новый пациент, сохраняем в Patient
    if not form_data.get('patient_id'):
        await logger.info(f'confirm_and_save: сохраняем нового пациента')
        await db.save_patient(user_id, form_data)
    
    # Удаляем предыдущие сообщения
    await delete_previous_messages(event, db)
    
    # Уведомляем пользователя
    await send_and_save(event,
        f"✅ Ваш вызов отправлен!\nНомер вызова: <b>#{call.call_number}</b>\n\n"
        "Ожидайте подтверждения от регистратора.",
        kb.home_keyboard(), db
    )
    
    # Уведомляем всех регистраторов (role=1)
    staff_list = await db.get_registration_staff()
    staff_message = format_for_staff(form_data, call.call_number)
    await logger.info(f'confirm_and_save: отправка уведомлений {len(staff_list)} регистраторам')
    
    for staff in staff_list:
        try:
            await event.bot.send_message(
                chat_id=staff.id_max,
                text=staff_message,
                attachments=[kb.accept_cancel_keybord(call.id)]
            )
            await logger.info(f'confirm_and_save: уведомление отправлено регистратору {staff.id_max}')
        except Exception as e:
            await logger.error(f'confirm_and_save: ошибка отправки регистратору {staff.id_max}: {e}')
    
    # Очищаем состояние
    await context.set_state(None)
    await context.update_data(form_data={}, editing=False)
    await logger.info(f'✅ confirm_and_save: завершен для user_id={user_id}')

#=================================================================

def format_confirmation(data):
    """Форматирование данных для подтверждения"""
    return (
        "🚑 <b>Медицинская анкета</b>\n\n"
        f"👤 <b>ФИО:</b> {data.get('full_name', 'не указано')}\n"
        f"🎂 <b>Дата рождения:</b> {data.get('birth_date', 'не указана')}\n\n"
        f"📞 <b>Телефон:</b> {data.get('phone', 'не указан')}\n\n"
        f"🏠 <b>Адрес:</b>\n"
        f"- {data.get('address', 'не указан')}\n"
        f"- <b>Подъезд/этаж:</b> {data.get('address_details', 'не указано')}\n"
        f"- <b>Дополнительно:</b> {data.get('access_notes', 'не указано')}\n\n"
        f"🌡 <b>Температура:</b> {data.get('temperature', 'не указана')}\n"
        f"📝 <b>Симптомы:</b>\n{data.get('symptoms', 'не указаны')}\n\n"
        f"📃 <b>Больничный лист:</b> {'Нужен' if data.get('sick_leave') else 'Не нужен'}\n"
    )

def format_for_staff(data, call_number):
    """Форматирование для регистратора"""
    return (
        f"🚨 <b>НОВЫЙ ВЫЗОВ #{call_number}</b>\n\n"
        f"👤 <b>Пациент:</b> {data.get('full_name', 'не указано')}\n"
        f"🎂 <b>Дата рождения:</b> {data.get('birth_date', 'не указана')}\n"
        f"📞 <b>Телефон:</b> {data.get('phone', 'не указан')}\n\n"
        f"🏠 <b>Адрес:</b> {data.get('address', 'не указан')}\n"
        f"🚪 <b>Подъезд/этаж:</b> {data.get('address_details', 'не указано')}\n"
        f"ℹ️ <b>Доп. информация:</b> {data.get('access_notes', 'нет')}\n\n"
        f"🌡 <b>Температура:</b> {data.get('temperature', 'не указана')}\n"
        f"🤒 <b>Симптомы:</b> {data.get('symptoms', 'не указаны')}\n"
        f"🏥 <b>Больничный:</b> {'Нужен' if data.get('sick_leave') else 'Не нужен'}"
    )

#=================================================================
async def delete_patient_previous_messages(event, user_id, db):
    """Удаляет предыдущие сообщения пациента"""
    user_state = await db.get_state(user_id)
    if user_state and user_state.last_message_ids:
        await db.delete_messages(user_state)
        user_state.last_message_ids = []
        await db.update_state(user_state)

#=================================================================

##################################################################

@router.message_callback(F.callback.payload == "my_requests")
async def show_user_requests(event: MessageCallback, db: DataBase):
    try:
        user_id = event.chat.chat_id
        # Получаем текущее состояние пользователя
        user_state = await db.get_state(user_id)
        
        # Удаляем предыдущие сообщения если нужно
        if user_state and user_state.last_message_ids:
            await db.delete_messages(user_state)
            user_state.last_message_ids = []
            await db.update_state(user_state)
        
        # Получаем вызовы пользователя (последние 5)
        requests = await db.get_requests_by_user(user_id, limit=5)
        
        if not requests:
            sent_msg = await event.message.answer(
                "📭 У вас пока нет вызовов врача.",
                attachments=[kb.home_keyboard_inline()]
            )
            user_state = await db.get_state(user_id)
            user_state.last_message_ids.append(sent_msg.message.body.mid)
            await db.update_state(user_state)
            return
        
        # Словарь статусов (только строки)
        status_display = {
            'new': '🟡 Новый',
            'approved': '🟢 Принят',
            'rejected': '🔴 Отклонен',
            'cancelled': '⚪ Отменен',
            'pending_cancellation': '🟠 Ожидает отмены'
        }
        
        # Формируем сообщение со списком вызовов
        message_text = ["📋 <b>Ваши последние вызовы:</b>\n\n"]
        
        for request in requests:
            # Форматируем дату
            created_at = request.created_at.strftime('%d.%m.%Y %H:%M')
            
            # Получаем статус (это строка из БД)
            status = request.status
            status_text = status_display.get(status, f"❓ {status}")
            
            message_text.append(
                f"🔹 <b>Вызов #{request.call_number}</b>\n"
                f"📅 {created_at}\n"
                f"🩺 Статус: {status_text}\n"
            )
            
            # Если вызов отклонен и есть причина (проверяем строку)
            if status == 'rejected' and request.rejection_reason:
                message_text.append(f"📝 Причина: {request.rejection_reason}\n")
            
            message_text.append("\n")
        
        # Добавляем подсказку
        message_text.append("ℹ️ Для просмотра деталей выберите вызов из списка")
        
        # Отправляем сообщение
        sent_msg = await event.message.answer(
            ''.join(message_text),
            attachments=[kb.user_requests_keyboard(requests)]
        )
        
        # Сохраняем ID сообщения
        user_state = await db.get_state(user_id)
        user_state.last_message_ids.append(sent_msg.message.body.mid)
        await db.update_state(user_state)
        
    except Exception as e:
        await logger.error(f"Ошибка при получении вызовов: {e}")
        sent_msg = await event.message.answer(
            "⚠️ Произошла ошибка при загрузке ваших вызовов. Попробуйте позже.",
            attachments=[kb.home_keyboard_inline()]
        )
        user_state = await db.get_state(user_id)
        user_state.last_message_ids.append(sent_msg.message.body.mid)
        await db.update_state(user_state)

##################################################################

@router.message_callback(F.callback.payload.startswith("request_detail_"))
async def show_request_details(event: MessageCallback, db: DataBase):
    """Показать детали вызова"""
    try:
        user_id = event.chat.chat_id
        request_id = int(event.callback.payload.split("_")[-1])

        # Получаем текущее состояние пользователя
        user_state = await db.get_state(user_id)
        
        # Удаляем предыдущие сообщения если нужно
        # if user_state and user_state.last_message_ids:
        #     await db.delete_messages(user_state)
        #     user_state.last_message_ids = []
        #     await db.update_state(user_state)

        # Получаем данные вызова
        call = await db.get_call_by_id(request_id)
        if not call:
            await event.message.answer("❌ Вызов не найден")
            return

        # Форматируем дату рождения
        birth_date = call.birth_date
        if hasattr(birth_date, 'strftime'):
            birth_date = birth_date.strftime('%d.%m.%Y')
        elif not isinstance(birth_date, str):
            birth_date = 'не указана'

        # Проверяем, создан ли вызов сегодня
        today = datetime.now().date()
        created_today = call.created_at.date() == today
       
        # Словарь статусов
        status_display = {
            'new': '🟡 Новый',
            'approved': '🟢 Принят',
            'rejected': '🔴 Отклонен',
            'cancelled': '⚪ Отменен',
            'pending_cancellation': '🟠 Ожидает отмены'
        }
        
        # Формируем текст сообщения
        details = [
            "🚨 <b>Детали вызова врача</b>\n\n",
            f"📋 <b>Номер вызова:</b> #{call.call_number}\n",
            f"👤 <b>Пациент:</b> {call.full_name}\n",
            f"🎂 <b>Дата рождения:</b> {birth_date}\n",
            f"📞 <b>Телефон:</b> {call.phone}\n\n",
            f"🏠 <b>Адрес:</b> {call.address}\n",
            f"🚪 <b>Подъезд/этаж:</b> {call.address_details or 'не указано'}\n",
            f"ℹ️ <b>Доп. информация:</b> {call.access_notes or 'нет'}\n\n",
            f"🌡 <b>Температура:</b> {call.temperature or 'не указана'}\n",
            f"🤒 <b>Симптомы:</b> {call.symptoms}\n",
            f"🏥 <b>Больничный:</b> {'Нужен' if call.need_sick_leave else 'Не нужен'}\n\n",
            f"🕒 <b>Дата создания:</b> {call.created_at.strftime('%d.%m.%Y %H:%M')}\n",
            f"🩺 <b>Статус:</b> {status_display.get(call.status, call.status)}"
        ]

        if call.status == 'rejected' and call.rejection_reason:
            details.append(f"\n\n📝 <b>Причина:</b>\n{call.rejection_reason}")
        
        # Получаем клавиатуру
        markup = kb.request_details_keyboard(
            status=call.status,
            request_id=call.id,
            created_today=created_today
        )

        # Отправляем или редактируем сообщение
        try:
            await event.message.edit(
                ''.join(details),
                attachments=[markup]
            )
            # Сохраняем ID сообщения
            user_state = await db.get_state(user_id)
            user_state.last_message_ids.append(event.message.body.mid)
            await db.update_state(user_state)
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            await logger.error(f"Ошибка редактирования: {edit_error}")
            sent_msg = await event.message.answer(
                ''.join(details),
                attachments=[markup]
            )
            user_state = await db.get_state(user_id)
            user_state.last_message_ids = [sent_msg.message.body.mid]
            await db.update_state(user_state)

    except ValueError:
        await event.message.answer("❌ Неверный ID вызова")
    except Exception as e:
        await logger.error(f"Ошибка при показе вызова: {e}")
        await event.message.answer("⚠️ Ошибка загрузки данных", attachments=[kb.home_keyboard_inline()])

##################################################################

@router.message_callback(F.callback.payload.startswith("patient_cancel_"))
async def patient_cancel_request(event: MessageCallback, db: DataBase):
    """Пациент отменяет вызов"""
    try:
        request_id = int(event.callback.payload.split("_")[-1])
        user_id = event.chat.chat_id
        
        # Получаем текущее состояние пользователя
        user_state = await db.get_state(user_id)
        
        # Удаляем предыдущие сообщения если нужно
        if user_state and user_state.last_message_ids:
            await db.delete_messages(user_state)
            user_state.last_message_ids = []
            await db.update_state(user_state)

        # Получаем данные вызова
        call = await db.get_call_by_id(request_id)
        if not call:
            await event.message.answer("❌ Вызов не найден")
            return
            
        # Проверяем, что вызов создан сегодня
        today = datetime.now().date()
        if call.created_at.date() != today:
            await event.message.answer("❌ Можно отменять только сегодняшние вызовы")
            return
            
        # Меняем статус на ожидание подтверждения отмены
        await db.update_call_status(request_id, 'pending_cancellation')
        
        # Удаляем сообщение с деталями
        await event.message.delete()
        
        # Отправляем уведомление сотрудникам call-центра (role=1)
        staff_list = await db.get_registration_staff()
        for staff in staff_list:
            try:
                await event.bot.send_message(
                    chat_id=staff.id_max,
                    text=f"🚨 Пациент хочет отменить вызов #{call.call_number}\n"
                         f"👤 Пациент: {call.full_name}\n"
                         f"📞 Телефон: {call.phone}\n\n"
                         "Пожалуйста, подтвердите или отклоните отмену.",
                    attachments=[kb.request_details_admin_keyboard('pending_cancellation', request_id)]
                )
                await logger.info(f"Уведомление отправлено регистратору {staff.id_max}")
            except Exception as e:
                await logger.error(f"Не удалось отправить уведомление регистратору {staff.id_max}: {e}")
        
        # Отправляем подтверждение пациенту
        await event.message.answer(
            "✅ Запрос на отмену отправлен в Call-центр.\n🏠 Главное меню => /start"
        )
        
        await logger.info(f'patient_cancel_request: вызов #{call.call_number} ожидает отмены')
        
    except Exception as e:
        await logger.error(f"Ошибка при отмене вызова: {e}")
        await event.message.answer("⚠️ Ошибка при отмене вызова", attachments=[kb.home_keyboard_inline()])

####################################################################

@router.message_callback(F.callback.payload.startswith("confirm_cancel_"))
async def confirm_cancel_request(event: MessageCallback, db: DataBase):
    """Регистратор подтверждает отмену вызова"""
    try:
        request_id = int(event.callback.payload.split("_")[-1])
        
        # Получаем данные вызова
        call = await db.get_call_by_id(request_id)
        if not call:
            await event.message.answer("❌ Вызов не найден")
            return
            
        # Обновляем статус вызова на отмененный
        await db.update_call_status(request_id, 'cancelled')
        
        # Удаляем сообщение регистратора с кнопками
        await event.message.delete()
        
        # Отправляем уведомление регистратору
        await event.message.answer(f"⚠️ Вызов #{call.call_number} успешно отменен")
        
        # Удаляем предыдущие сообщения пациента
        user_state_patient = await db.get_state(call.user_id)
        if user_state_patient and user_state_patient.last_message_ids:
            await db.delete_messages(user_state_patient)
            user_state_patient.last_message_ids = []
            await db.update_state(user_state_patient)
        
        # Отправляем уведомление пациенту
        await event.bot.send_message(
            chat_id=call.user_id,
            text=f"✅ Ваш вызов #{call.call_number} был отменен администратором\n\n"
                 "Если это произошло по ошибке, вы можете создать новый вызов.",
            attachments=[kb.home_keyboard()]
        )
        
        await logger.info(f'confirm_cancel_request: вызов #{call.call_number} отменен')
        
    except Exception as e:
        await logger.error(f"Ошибка при подтверждении отмены: {e}")
        await event.message.answer("⚠️ Ошибка при подтверждении отмены", attachments=[kb.home_keyboard_inline()])

########################################################################
@router.message_callback(F.callback.payload.startswith("reject_cancel_"))
async def reject_cancel_request(event: MessageCallback, db: DataBase):
    """Регистратор отклоняет отмену вызова"""
    try:
        request_id = int(event.callback.payload.split("_")[-1])
        
        # Проверяем права (только регистратор)
        # Можно проверить роль, но для простоты пока пропускаем
        
        # Получаем данные вызова
        call = await db.get_call_by_id(request_id)
        if not call:
            await event.message.answer("❌ Вызов не найден")
            return
        
        # Возвращаем статус на прежний (new или approved)
        # Нужно определить, какой был статус до отмены
        # По умолчанию возвращаем new
        await db.update_call_status(request_id, 'new')
        
        # Удаляем сообщение регистратора с кнопками
        await event.message.delete()
        
        # Отправляем уведомление регистратору
        await event.message.answer(f"❌ Отмена вызова #{call.call_number} отклонена")
        
        # Удаляем предыдущие сообщения пациента
        user_state_patient = await db.get_state(call.user_id)
        if user_state_patient and user_state_patient.last_message_ids:
            await db.delete_messages(user_state_patient)
            user_state_patient.last_message_ids = []
            await db.update_state(user_state_patient)
        
        # Отправляем уведомление пациенту
        await event.bot.send_message(
            chat_id=call.user_id,
            text=f"ℹ️ Ваш запрос на отмену вызова #{call.call_number} был отклонен.\n\n"
                 "Вызов остается активным. Если у вас остались вопросы, пожалуйста, свяжитесь с нами.",
            attachments=[kb.home_keyboard()]
        )
        
        await logger.info(f'reject_cancel_request: отмена вызова #{call.call_number} отклонена')
        
    except Exception as e:
        await logger.error(f"Ошибка при отклонении отмены: {e}")
        await event.message.answer("⚠️ Ошибка при отклонении отмены", attachments=[kb.home_keyboard_inline()])
###################################################################
@router.message_callback(F.callback.payload == "rules")
async def about_service_handler(callback: MessageCallback, db: DataBase):
    user_state = await db.get_state(callback.chat.chat_id)
    # Удаляем предыдущие сообщения если нужно
    if user_state and user_state.last_message_ids:
        await db.delete_messages(user_state)
    try:
        settings = await db.get_settings()
        # Редактируем сообщение, удаляя клавиатуру
        sent_mess =  await callback.message.answer(
            text=RULES_TEXT%(settings.weekday_start.strftime('%H:%M'),
            settings.weekday_end.strftime('%H:%M'),settings.weekend_start.strftime('%H:%M'),settings.weekend_end.strftime('%H:%M')),
            attachments=[kb.home_keyboard_inline()]
        )
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        
    except Exception as e:
        await logger.error(f"Ошибка в about_service_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка", attachments=[kb.home_keyboard_inline()])
###################################################################
@router.message_callback(F.callback.payload == "contacts")
async def about_service_handler(callback: MessageCallback, db: DataBase):
    user_state = await db.get_state(callback.chat.chat_id)
    # Удаляем предыдущие сообщения если нужно
    if user_state and user_state.last_message_ids:
        await db.delete_messages(user_state)
    try:
        
        # Редактируем сообщение, удаляя клавиатуру
        sent_mess = await callback.message.answer(
            text=CONTACT_TEXT,
            attachments=[kb.home_keyboard_inline()]
        )
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        
    except Exception as e:
        await logger.error(f"Ошибка в about_service_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка", attachments=[kb.home_keyboard_inline()])
####################################################################
@router.message_callback(F.callback.payload == "about")
async def about_service_handler(callback: MessageCallback, db: DataBase):
    await logger.info(f'ID_MX:{callback.chat.chat_id}|callback about')
    user_state = await db.get_state(callback.chat.chat_id)
    # Удаляем предыдущие сообщения если нужно
    if user_state and user_state.last_message_ids:
        await db.delete_messages(user_state)
    try:
        # Редактируем сообщение, удаляя клавиатуру
        sent_mess = await callback.message.answer(
            text=ABOUT_TEXT,
            attachments=[kb.home_keyboard_inline()]
        )
        user_state.last_message_ids.append(sent_mess.message.body.mid)
        await db.update_state(user_state)
        # Подтверждаем обработку callback
        
    except Exception as e:
        await logger.error(f"Ошибка в about_service_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка", attachments=[kb.home_keyboard_inline()])
####################################################################