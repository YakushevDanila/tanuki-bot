from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from datetime import datetime, date as dt, timedelta
import logging
import os
from dotenv import load_dotenv
import atexit

# Импорты для уведомлений
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from notifications import setup_scheduler

# Загружаем переменные из .env.local
load_dotenv('.env.local')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверяем обязательные переменные
required_vars = ['BOT_TOKEN', 'GOOGLE_CREDENTIALS', 'SHEET_ID']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
    logger.info("💡 Создайте файл .env.local с необходимыми переменными")
    exit(1)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Функция очистки ввода от временных меток
def clean_user_input(text):
    if not text:
        return ""
    parts = text.strip().split()
    return parts[0] if parts else ""

# Умный парсинг времени
async def parse_flexible_time(time_str):
    """Умный парсинг времени в разных форматах"""
    try:
        # Очищаем строку
        time_str = time_str.strip().replace(' ', '')
        
        # Проверяем разные разделители
        for separator in ['-', '–', '—', 'до', 'по']:
            if separator in time_str:
                parts = time_str.split(separator)
                if len(parts) == 2:
                    start, end = parts
                    
                    # Нормализуем форматы времени
                    def normalize_time(t):
                        t = t.strip()
                        # Если только часы, добавляем :00
                        if len(t) <= 2 and t.isdigit():
                            return f"{t.zfill(2)}:00"
                        # Если формат 900, преобразуем в 09:00
                        elif len(t) == 3 and t.isdigit():
                            return f"0{t[0]}:{t[1:]}"
                        # Если формат 900, преобразуем в 09:00
                        elif len(t) == 4 and t.isdigit():
                            return f"{t[:2]}:{t[2:]}"
                        # Если уже в формате ЧЧ:ММ, проверяем
                        elif ':' in t:
                            hours, minutes = t.split(':')
                            return f"{hours.zfill(2)}:{minutes}"
                        return t
                    
                    start = normalize_time(start)
                    end = normalize_time(end)
                    
                    # Проверяем валидность
                    datetime.strptime(start, "%H:%M")
                    datetime.strptime(end, "%H:%M")
                    
                    return start, end
                    
        return None
        
    except Exception as e:
        logger.error(f"Error parsing time: {e}")
        return None

# FSM States
class Form(StatesGroup):
    waiting_for_date = State()
    waiting_for_start = State()
    waiting_for_end = State()
    waiting_for_revenue_date = State()
    waiting_for_revenue = State()
    waiting_for_tips_date = State()
    waiting_for_tips = State()
    waiting_for_edit_date = State()
    waiting_for_edit_field = State()
    waiting_for_edit_value = State()
    waiting_for_profit_date = State()
    waiting_for_overwrite_confirm = State()
    waiting_for_stats_start = State()
    waiting_for_stats_end = State()
    waiting_for_export_start = State()
    waiting_for_export_end = State()
    waiting_for_week_schedule = State()
    waiting_for_week_confirmation = State()
    waiting_for_quick_today = State()
    waiting_for_shifts_count = State()
    waiting_for_shift_data = State()
    waiting_for_multiple_confirmation = State()

# ВЫБОР ХРАНИЛИЩА
storage_type = os.getenv('STORAGE_TYPE', 'google_sheets').lower()

if storage_type == 'google_sheets':
    try:
        from sheets import add_shift, update_value, get_profit, check_shift_exists
        logger.info("✅ Using Google Sheets storage")
    except Exception as e:
        logger.error(f"❌ Failed to use Google Sheets: {e}")
        # Fallback to SQLite если Google Sheets не работает
        try:
            from database import db_manager as storage
            add_shift = storage.add_shift
            update_value = storage.update_value
            get_profit = storage.get_profit
            check_shift_exists = storage.check_shift_exists
            logger.info("✅ Fallback to SQLite storage")
        except ImportError:
            logger.error("❌ No storage backend available")
            exit(1)
else:
    from database import db_manager as storage
    add_shift = storage.add_shift
    update_value = storage.update_value
    get_profit = storage.get_profit
    check_shift_exists = storage.check_shift_exists
    logger.info("✅ Using SQLite storage")

# Импортируем функции для статистики и экспорта (только для SQLite)
try:
    from database import db_manager
except ImportError:
    db_manager = None

# ВРЕМЕННО ОТКЛЮЧАЕМ ПРОВЕРКУ ДОСТУПА
def check_access(message: types.Message):
    logger.info(f"🔓 Access granted for user: {message.from_user.id}")
    return True

# Команды для уведомлений
@dp.message(Command("test_notification"))
async def test_notification_cmd(msg: types.Message):
    """Тестовая команда для проверки уведомлений"""
    if not check_access(msg): return
        
    await msg.answer("🔔 Отправляю тестовое уведомление...")
    
    # Тест утреннего напоминания
    from notifications import send_shift_reminder
    await send_shift_reminder(bot)
    
    await msg.answer("✅ Тестовое уведомление отправлено!")

@dp.message(Command("notification_status"))
async def notification_status_cmd(msg: types.Message):
    """Статус уведомлений"""
    if not check_access(msg): return
        
    user_id = os.getenv('USER_ID')
    timezone = os.getenv('TIMEZONE', 'Europe/Moscow')
    
    status_text = (
        f"🔔 **Статус уведомлений**\n"
        f"• USER_ID: {user_id or 'Не установлен'}\n"
        f"• Часовой пояс: {timezone}\n"
        f"• Утренние напоминания: 10:00\n"
        f"• Вечерние напоминания: 22:00\n"
        f"• Недельная статистика: Воскресенье 20:00\n"
    )
    
    if not user_id:
        status_text += "\n⚠️ Для работы уведомлений установите USER_ID в настройках"
    
    await msg.answer(status_text)

@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    if not check_access(msg): return
    storage_info = "Google Sheets" if storage_type == "google_sheets" else "SQLite"
    
    # Проверяем статус уведомлений
    user_id = os.getenv('USER_ID')
    notification_status = "✅ Включены" if user_id else "❌ Выключены (нет USER_ID)"
    
    text = (
        "Привет! 🌸\n"
        "Вот что я умею:\n"
        "/add_shift — добавить дату и время смены\n"
        "/add_week — добавить смены на всю неделю 🚀\n"
        "/add_multiple — добавить несколько смен 🆕\n"
        "/today — быстрый ввод за сегодня 🎯\n"
        "/revenue — ввести выручку за день\n"
        "/tips — добавить сумму чаевых 💰\n"
        "/edit — изменить данные\n"
        "/profit — узнать прибыль за день\n"
        "/stats — статистика за период\n"
        "/export — экспорт данных за период\n"
        "/myid — показать мой ID\n"
        "/test_notification — тест уведомлений\n"
        "/notification_status — статус уведомлений\n"
        "/help — показать это сообщение\n"
        f"\n💾 Хранилище: {storage_info}\n"
        f"🔔 Уведомления: {notification_status}\n"
        "💰 Формула прибыли: (часы × 220) + чаевые + (выручка × 0.015)"
    )
    await msg.answer(text)

@dp.message(Command("myid"))
async def show_my_id(msg: types.Message):
    user_id = msg.from_user.id
    first_name = msg.from_user.first_name or "Пользователь"
    await msg.answer(f"👤 {first_name}, ваш ID: `{user_id}`", parse_mode="Markdown")

@dp.message(Command("help"))
async def help_cmd(msg: types.Message):
    await start_cmd(msg)

# ПОШАГОВОЕ ДОБАВЛЕНИЕ НЕСКОЛЬКИХ СМЕН
@dp.message(Command("add_multiple"))
async def add_multiple_step_start(msg: types.Message, state: FSMContext):
    """Начало пошагового добавления нескольких смен"""
    if not check_access(msg): return
    
    await msg.answer(
        "🌸 **Пошаговое добавление смен**\n\n"
        "Сколько смен хочешь добавить, котик? 🐾\n"
        "Введи число от 1 до 10:"
    )
    await state.set_state(Form.waiting_for_shifts_count)

@dp.message(Form.waiting_for_shifts_count)
async def process_shifts_count(msg: types.Message, state: FSMContext):
    """Обработка количества смен"""
    try:
        count = int(clean_user_input(msg.text))
        if count < 1 or count > 10:
            await msg.answer("❌ Много хочешь, котик! Введи число от 1 до 10 🐾")
            return
    except ValueError:
        await msg.answer("❌ Это не похоже на число, пушистик! Введи корректное число 🌸")
        return
    
    await state.update_data(
        shifts_count=count,
        current_shift=1,
        shifts_data=[]
    )
    
    await ask_for_shift_data(msg, state)

async def ask_for_shift_data(msg: types.Message, state: FSMContext):
    """Запрос данных о смене"""
    user_data = await state.get_data()
    current = user_data['current_shift']
    total = user_data['shifts_count']
    
    await msg.answer(
        f"📝 **Смена {current} из {total}**\n\n"
        f"Введи данные в формате:\n"
        f"`<дата> <время>`\n\n"
        f"**Примеры:**\n"
        f"• 15.03.2024 9-18\n"
        f"• 16.03.2024 10:00-19:00\n\n"
        f"Не торопись, всё успеем! 🌸"
    )
    await state.set_state(Form.waiting_for_shift_data)

@dp.message(Form.waiting_for_shift_data)
async def process_shift_data(msg: types.Message, state: FSMContext):
    """Обработка данных смены"""
    user_data = await state.get_data()
    current = user_data['current_shift']
    total = user_data['shifts_count']
    shifts_data = user_data['shifts_data']
    
    input_text = msg.text.strip()
    
    # Разделяем дату и время
    parts = input_text.split()
    if len(parts) < 2:
        await msg.answer("❌ Кажется, чего-то не хватает, котик! Нужно: <дата> <время> 🐾")
        return
    
    date_str = parts[0]
    time_str = ' '.join(parts[1:])
    
    # Проверяем дату
    try:
        datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ 🌸")
        return
    
    # Парсим время
    time_parts = await parse_flexible_time(time_str)
    if not time_parts:
        await msg.answer(
            "❌ Не получилось понять время, котик! 🐾\n"
            "Используй: начало-конец\n"
            "Примеры: 9-18, 10:00-19:00"
        )
        return
    
    start_time, end_time = time_parts
    
    # Проверяем валидность времени
    try:
        datetime.strptime(start_time, "%H:%M")
        datetime.strptime(end_time, "%H:%M")
    except ValueError:
        await msg.answer("❌ Что-то не так со временем, давай попробуем ещё раз? 🌸")
        return
    
    # Добавляем смену в список
    shifts_data.append({
        'date': date_str,
        'start': start_time,
        'end': end_time
    })
    
    await state.update_data(shifts_data=shifts_data)
    
    # Если это не последняя смена, запрашиваем следующую
    if current < total:
        await state.update_data(current_shift=current + 1)
        await ask_for_shift_data(msg, state)
    else:
        # Все смены собраны, показываем итог и добавляем
        await process_all_shifts_collected(msg, state)

async def process_all_shifts_collected(msg: types.Message, state: FSMContext):
    """Обработка собранных смен"""
    user_data = await state.get_data()
    shifts_data = user_data['shifts_data']
    
    # Проверяем существующие смены
    existing_shifts = []
    new_shifts = []
    
    for shift in shifts_data:
        if await check_shift_exists(shift['date']):
            existing_shifts.append(shift)
        else:
            new_shifts.append(shift)
    
    # Формируем сообщение для подтверждения
    confirmation_text = "📋 **Вот какие смены у нас получились:**\n\n"
    
    for i, shift in enumerate(shifts_data, 1):
        status = "⚠️" if shift in existing_shifts else "✅"
        confirmation_text += f"{status} {i}. {shift['date']} {shift['start']}-{shift['end']}\n"
    
    if existing_shifts:
        confirmation_text += f"\n⚠️ **{len(existing_shifts)} смен уже существуют и будут перезаписаны!**"
    
    confirmation_text += "\n\n**Добавляем все смены, котик?** 🐾 (да/нет)"
    
    await state.update_data(
        new_shifts=new_shifts,
        existing_shifts=existing_shifts
    )
    
    await msg.answer(confirmation_text)
    await state.set_state(Form.waiting_for_multiple_confirmation)

@dp.message(Form.waiting_for_multiple_confirmation)
async def process_multiple_confirmation(msg: types.Message, state: FSMContext):
    """Обработка подтверждения добавления нескольких смен"""
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in ['да', 'yes', 'y', 'д']:
        user_data = await state.get_data()
        new_shifts = user_data['new_shifts']
        existing_shifts = user_data['existing_shifts']
        
        # Добавляем новые смены
        added_count = 0
        for shift in new_shifts:
            success = await add_shift(shift['date'], shift['start'], shift['end'])
            if success:
                added_count += 1
            await asyncio.sleep(0.1)
        
        # Перезаписываем существующие смены
        overwritten_count = 0
        for shift in existing_shifts:
            success = await add_shift(shift['date'], shift['start'], shift['end'], reset_financials=True)
            if success:
                overwritten_count += 1
            await asyncio.sleep(0.1)
        
        # Формируем отчет
        report_text = f"✅ **Готово, котик! Все смены добавлены!** 🎉\n\n"
        report_text += f"📊 **Статистика:**\n"
        report_text += f"• Добавлено новых: {added_count} 🌸\n"
        report_text += f"• Перезаписано: {overwritten_count} ✨\n"
        report_text += f"• Всего обработано: {added_count + overwritten_count} 🐾\n"
        
        if added_count + overwritten_count > 0:
            report_text += f"\n🎉 **Ты просто супер! Теперь можно отдохнуть!** 🌟"
        
        await msg.answer(report_text)
        
    elif user_response in ['нет', 'no', 'n', 'н']:
        await msg.answer("❌ Добавление смен отменено, котик! Ничего страшного, всегда можно начать заново 🐾")
    else:
        await msg.answer("Пожалуйста, ответь 'да' или 'нет', пушистик! 🌸")
    
    await state.clear()

# БЫСТРЫЙ ВВОД ЗА СЕГОДНЯ
@dp.message(Command("today"))
async def quick_today_start(msg: types.Message, state: FSMContext):
    """Быстрый ввод данных за сегодня"""
    if not check_access(msg): return
    
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Проверяем есть ли смена на сегодня
    if not await check_shift_exists(today):
        await msg.answer(
            f"❌ На сегодня ({today}) нет смены, котик!\n\n"
            f"Сначала создай смену - введи время в формате:\n"
            f"<начало>-<конец>\n\n"
            f"Примеры:\n"
            f"• 9-18\n"
            f"• 10:00-19:00\n"
            f"• 0900-1800"
        )
        await state.update_data(today_date=today)
        await state.set_state(Form.waiting_for_quick_today)
        return
    
    # Если смена есть, запрашиваем финансовые данные
    await msg.answer(
        f"🎯 **Быстрый ввод данных за {today}:**\n\n"
        f"Введи данные в формате:\n"
        f"<выручка> <чаевые>\n\n"
        f"Пример: 15000 1200\n\n"
        f"Поехали! 🚀"
    )
    await state.update_data(today_date=today, has_shift=True)
    await state.set_state(Form.waiting_for_quick_today)

@dp.message(Form.waiting_for_quick_today)
async def process_quick_today(msg: types.Message, state: FSMContext):
    """Обработка быстрого ввода за сегодня"""
    user_data = await state.get_data()
    today = user_data['today_date']
    has_shift = user_data.get('has_shift', False)
    
    input_text = msg.text.strip()
    
    if has_shift:
        # Обработка финансовых данных
        parts = input_text.split()
        if len(parts) != 2:
            await msg.answer(
                "❌ Неверный формат, котик!\n"
                "Введи: <выручка> <чаевые>\n"
                "Пример: 15000 1200"
            )
            return
        
        revenue, tips = parts
        
        # Проверяем что это числа
        try:
            float(revenue)
            float(tips)
        except ValueError:
            await msg.answer("❌ Оба значения должны быть числами, пушистик!")
            return
        
        # Обновляем данные
        success_revenue = await update_value(today, "выручка", revenue)
        success_tips = await update_value(today, "чай", tips)
        
        if success_revenue and success_tips:
            profit = await get_profit(today)
            await msg.answer(
                f"✅ **Данные за {today} обновлены!** 🎉\n\n"
                f"• Выручка: {revenue}₽\n"
                f"• Чаевые: {tips}₽\n"
                f"• Прибыль: {profit}₽\n\n"
                f"Отличная работа! 🌟"
            )
        else:
            await msg.answer("❌ Ошибка при обновлении данных, котик! Давай попробуем ещё раз? 🐾")
    
    else:
        # Обработка создания смены
        time_parts = await parse_flexible_time(input_text)
        if not time_parts:
            await msg.answer(
                "❌ Неверный формат времени, пушистик!\n"
                "Используй: начало-конец\n"
                "Примеры: 9-18, 10:00-19:00"
            )
            return
        
        start_time, end_time = time_parts
        
        # Проверяем валидность времени
        try:
            datetime.strptime(start_time, "%H:%M")
            datetime.strptime(end_time, "%H:%M")
        except ValueError:
            await msg.answer(
                "❌ Неверный формат времени, котик!\n"
                "Используй ЧЧ:ММ, например: 09:00-18:00"
            )
            return
        
        # Создаем смену
        success = await add_shift(today, start_time, end_time)
        if success:
            await msg.answer(
                f"✅ **Смена на {today} создана!** 🎉\n"
                f"Время: {start_time}-{end_time}\n\n"
                f"Теперь введи финансовые данные:\n"
                f"<выручка> <чаевые>\n\n"
                f"Пример: 15000 1200"
            )
            await state.update_data(has_shift=True)
            # Остаемся в том же состоянии для ввода финансовых данных
        else:
            await msg.answer("❌ Ошибка при создании смены, котик! 🐾")
            await state.clear()
    
    await state.clear()

# ADD SHIFT FLOW
@dp.message(Command("add_shift"))
async def add_shift_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату смены, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_date)

@dp.message(Form.waiting_for_date)
async def process_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем валидность даты
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ (например, 15.03.2024)")
        await state.clear()
        return
    
    # Проверяем, существует ли уже смена с этой датой
    exists = await check_shift_exists(clean_date)
    if exists:
        await state.update_data(date=clean_date, is_overwrite=True)
        await msg.answer(f"❌ Смена на дату {clean_date} уже существует, котик!\n"
                        "Хочешь перезаписать ее? (да/нет)")
        await state.set_state(Form.waiting_for_overwrite_confirm)
    else:
        await state.update_data(date=clean_date, is_overwrite=False)
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00\n"
            "• 0900-1800"
        )
        await state.set_state(Form.waiting_for_start)

# Обработчик подтверждения перезаписи
@dp.message(Form.waiting_for_overwrite_confirm)
async def process_overwrite_confirm(msg: types.Message, state: FSMContext):
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in ['да', 'yes', 'y', 'д']:
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00"
        )
        await state.set_state(Form.waiting_for_start)
    elif user_response in ['нет', 'no', 'n', 'н']:
        await msg.answer("❌ Добавление смены отменено, котик! Используй /add_shift чтобы начать заново 🐾")
        await state.clear()
    else:
        await msg.answer("Пожалуйста, ответь 'да' или 'нет', пушистик! 🌸")

@dp.message(Form.waiting_for_start)
async def process_start(msg: types.Message, state: FSMContext):
    time_input = msg.text.strip()
    
    # Используем умный парсинг времени
    time_parts = await parse_flexible_time(time_input)
    if not time_parts:
        await msg.answer(
            "❌ Неверный формат времени, котик!\n"
            "Используй: начало-конец\n"
            "Примеры: 9-18, 10:00-19:00"
        )
        await state.clear()
        return
    
    start_time, end_time = time_parts
    
    # Проверяем валидность времени
    try:
        datetime.strptime(start_time, "%H:%M")
        datetime.strptime(end_time, "%H:%M")
    except ValueError:
        await msg.answer(
            "❌ Неверный формат времени, пушистик!\n"
            "Используй ЧЧ:ММ, например: 09:00-18:00"
        )
        await state.clear()
        return
        
    await state.update_data(start=start_time, end=end_time)
    
    user_data = await state.get_data()
    date_msg = user_data['date']
    is_overwrite = user_data.get('is_overwrite', False)
    
    success = await add_shift(date_msg, start_time, end_time, reset_financials=is_overwrite)
    
    if success:
        # Если это перезапись, сбрасываем финансовые данные и предлагаем ввести заново
        if is_overwrite:
            await msg.answer(
                f"✅ Смена {date_msg} ({start_time}-{end_time}) перезаписана! 🩷\n\n"
                f"Теперь нужно заново ввести финансовые данные:\n"
                f"1. Введи сумму выручки за этот день:"
            )
            # Сохраняем данные для последующего ввода
            await state.update_data(
                revenue_date=date_msg,
                tips_date=date_msg,
                is_overwrite_flow=True
            )
            await state.set_state(Form.waiting_for_revenue)
        else:
            await msg.answer(f"✅ Смена {date_msg} ({start_time}-{end_time}) добавлена! 🩷\n\nОтличная работа, котик! 🌟")
            await state.clear()
    else:
        await msg.answer("❌ Ошибка при добавлении смены, котик! 🐾")
        await state.clear()

# ПАКЕТНОЕ ДОБАВЛЕНИЕ НА НЕДЕЛЮ
@dp.message(Command("add_week"))
async def add_week_start(msg: types.Message, state: FSMContext):
    """Начало пакетного добавления смен на неделю"""
    if not check_access(msg): return
    
    # Получаем даты текущей недели
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())  # Понедельник
    end_of_week = start_of_week + timedelta(days=6)  # Воскресенье
    
    week_dates = []
    current_date = start_of_week
    while current_date <= end_of_week:
        week_dates.append(current_date.strftime("%d.%m.%Y"))
        current_date += timedelta(days=1)
    
    await state.update_data(week_dates=week_dates)
    
    await msg.answer(
        f"📅 **Пакетное добавление смен на неделю:**\n"
        f"Период: {week_dates[0]} - {week_dates[-1]}\n\n"
        f"Введи время смен в формате:\n"
        f"<начало>-<конец>\n\n"
        f"Примеры:\n"
        f"• 9-18\n"
        f"• 10:00-19:00\n"
        f"• 0900-1800\n\n"
        f"Планируем неделю! 🚀"
    )
    await state.set_state(Form.waiting_for_week_schedule)

@dp.message(Form.waiting_for_week_schedule)
async def process_week_schedule(msg: types.Message, state: FSMContext):
    """Обработка ввода времени для пакетного добавления"""
    time_input = msg.text.strip()
    
    # Парсим время с улучшенной обработкой разных форматов
    time_parts = await parse_flexible_time(time_input)
    if not time_parts:
        await msg.answer(
            "❌ Неверный формат времени, котик!\n"
            "Используй: начало-конец\n"
            "Пример: 9-18, 10:00-19:00"
        )
        return
    
    start_time, end_time = time_parts
    
    # Проверяем валидность времени
    try:
        datetime.strptime(start_time, "%H:%M")
        datetime.strptime(end_time, "%H:%M")
    except ValueError:
        await msg.answer(
            "❌ Неверный формат времени, пушистик!\n"
            "Используй ЧЧ:ММ, например: 09:00-18:00"
        )
        return
    
    user_data = await state.get_data()
    week_dates = user_data['week_dates']
    
    # Проверяем существующие смены
    existing_shifts = []
    new_shifts = []
    
    for date_str in week_dates:
        if await check_shift_exists(date_str):
            existing_shifts.append(date_str)
        else:
            new_shifts.append(date_str)
    
    # Сохраняем данные для подтверждения
    await state.update_data(
        start_time=start_time,
        end_time=end_time,
        new_shifts=new_shifts,
        existing_shifts=existing_shifts
    )
    
    # Формируем сообщение для подтверждения
    confirmation_text = f"📋 **Будут добавлены смены:**\n"
    confirmation_text += f"Время: {start_time}-{end_time}\n\n"
    
    if new_shifts:
        confirmation_text += f"✅ **Новые смены ({len(new_shifts)}):**\n"
        for date in new_shifts:
            confirmation_text += f"• {date}\n"
    
    if existing_shifts:
        confirmation_text += f"\n⚠️ **Уже существуют ({len(existing_shifts)}):**\n"
        for date in existing_shifts[:3]:  # Показываем только первые 3
            confirmation_text += f"• {date}\n"
        if len(existing_shifts) > 3:
            confirmation_text += f"• ... и ещё {len(existing_shifts) - 3}\n"
    
    confirmation_text += f"\n**Добавляем смены, котик?** 🐾 (да/нет)"
    
    await msg.answer(confirmation_text)
    await state.set_state(Form.waiting_for_week_confirmation)

@dp.message(Form.waiting_for_week_confirmation)
async def process_week_confirmation(msg: types.Message, state: FSMContext):
    """Обработка подтверждения пакетного добавления"""
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in ['да', 'yes', 'y', 'д']:
        user_data = await state.get_data()
        start_time = user_data['start_time']
        end_time = user_data['end_time']
        new_shifts = user_data['new_shifts']
        existing_shifts = user_data['existing_shifts']
        
        # Добавляем смены
        added_count = 0
        for date_str in new_shifts:
            success = await add_shift(date_str, start_time, end_time)
            if success:
                added_count += 1
            await asyncio.sleep(0.1)  # Небольшая задержка между запросами
        
        # Формируем отчет
        report_text = f"✅ **Пакетное добавление завершено!** 🎉\n\n"
        report_text += f"📊 **Статистика:**\n"
        report_text += f"• Добавлено смен: {added_count} 🌸\n"
        report_text += f"• Уже существовало: {len(existing_shifts)} ✨\n"
        report_text += f"• Время: {start_time}-{end_time} 🐾\n"
        
        if added_count > 0:
            report_text += f"\n🎉 **Отличная работа! Неделя распланирована!** 🌟"
        else:
            report_text += f"\nℹ️ Все смены на эту неделю уже добавлены, умничка! 💖"
        
        await msg.answer(report_text)
        
    elif user_response in ['нет', 'no', 'n', 'н']:
        await msg.answer("❌ Пакетное добавление отменено, котик! Ничего страшного 🐾")
    else:
        await msg.answer("Пожалуйста, ответь 'да' или 'нет', пушистик! 🌸")
    
    await state.clear()

# REVENUE FLOW - обновленная версия для перезаписи
@dp.message(Command("revenue"))
async def revenue_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_revenue_date)

@dp.message(Form.waiting_for_revenue_date)
async def process_revenue_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾")
        await state.clear()
        return
        
    await state.update_data(revenue_date=clean_date)
    await msg.answer("Введи сумму выручки (только число):")
    await state.set_state(Form.waiting_for_revenue)

@dp.message(Form.waiting_for_revenue)
async def process_revenue(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['revenue_date']
    rev = clean_user_input(msg.text)
    
    # Проверяем, что введено число
    try:
        float(rev)
    except ValueError:
        await msg.answer("❌ Неверный формат числа, пушистик! Введи только цифры (например: 5000)")
        await state.clear()
        return
    
    success = await update_value(date_msg, "выручка", rev)
    if success:
        # Если это поток перезаписи, переходим к вводу чаевых
        if user_data.get('is_overwrite_flow'):
            # Сохраняем выручку в состоянии для финального сообщения
            await state.update_data(revenue=rev)
            await msg.answer(f"✅ Выручка {rev}₽ обновлена! 💰✨\n\nТеперь введи сумму чаевых:")
            await state.set_state(Form.waiting_for_tips)
        else:
            await msg.answer(f"✅ Выручка {rev}₽ обновлена для даты {date_msg}! 💰✨\n\nМолодец, котик! 🌟")
            await state.clear()
    else:
        await msg.answer("❌ Не удалось обновить выручку, котик! 🐾")
        await state.clear()

# TIPS FLOW - обновленная версия для перезаписи
@dp.message(Command("tips"))
async def tips_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_tips_date)

@dp.message(Form.waiting_for_tips_date)
async def process_tips_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾")
        await state.clear()
        return
        
    await state.update_data(tips_date=clean_date)
    await msg.answer("Введи сумму чаевых (число):")
    await state.set_state(Form.waiting_for_tips)

@dp.message(Form.waiting_for_tips)
async def process_tips(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['tips_date']
    tips_amount = clean_user_input(msg.text)
    
    # Проверяем, что введено число
    try:
        float(tips_amount)
    except ValueError:
        await msg.answer("❌ Неверный формат числа, пушистик! Введи только цифры (например: 500)")
        await state.clear()
        return
    
    success = await update_value(date_msg, "чай", tips_amount)
    if success:
        if user_data.get('is_overwrite_flow'):
            # Получаем все данные для финального сообщения
            start = user_data.get('start', '?')
            end = user_data.get('end', '?')
            revenue = user_data.get('revenue', '?')
            
            await msg.answer(
                f"✅ Чаевые {tips_amount}₽ добавлены! ☕️💖\n\n"
                f"🎉 **Все данные за {date_msg} успешно перезаписаны!** 🌟\n"
                f"• Время: {start}-{end}\n"
                f"• Выручка: {revenue}₽\n"
                f"• Чаевые: {tips_amount}₽\n\n"
                f"Отличная работа, котик! 🐾"
            )
        else:
            await msg.answer(f"✅ Чаевые {tips_amount}₽ добавлены для даты {date_msg}! ☕️💖\n\nПушистик, ты лучшая! 🌸")
    
    await state.clear()

# EDIT FLOW
@dp.message(Command("edit"))
async def edit_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Укажи дату, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_edit_date)

@dp.message(Form.waiting_for_edit_date)
async def process_edit_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾")
        await state.clear()
        return
        
    await state.update_data(edit_date=clean_date)
    await msg.answer("Что редактируем, пушистик? (чай, начало, конец, выручка)")
    await state.set_state(Form.waiting_for_edit_field)

@dp.message(Form.waiting_for_edit_field)
async def process_edit_field(msg: types.Message, state: FSMContext):
    field = clean_user_input(msg.text).lower()
    if field not in ["чай", "начало", "конец", "выручка"]:
        await msg.answer("❌ Такого параметра нет, котик! Используй: чай, начало, конец, выручка 🐾")
        await state.clear()
        return
    
    await state.update_data(edit_field=field)
    await msg.answer(f"Введи новое значение для {field}:")
    await state.set_state(Form.waiting_for_edit_value)

@dp.message(Form.waiting_for_edit_value)
async def process_edit_value(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['edit_date']
    field = user_data['edit_field']
    value = clean_user_input(msg.text)
    
    success = await update_value(date_msg, field, value)
    if success:
        await msg.answer(f"✅ {field} изменен на {value} для даты {date_msg}! 🩷\n\nМолодец, котик! 🌟")
    else:
        await msg.answer("❌ Ошибка: не удалось сохранить изменения, пушистик! 🐾")
    
    await state.clear()

# PROFIT FLOW
@dp.message(Command("profit"))
async def profit_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_profit_date)

@dp.message(Form.waiting_for_profit_date)
async def process_profit_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем валидность даты
    try:
        day = datetime.strptime(clean_date, "%d.%m.%Y").date()
        if day > dt.today():
            await msg.answer("❌ Этот день ещё не наступил, котик! 🐾")
            await state.clear()
            return
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ")
        await state.clear()
        return

    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾")
        await state.clear()
        return

    profit_value = await get_profit(clean_date)
    if profit_value is None:
        await msg.answer("❌ Нет данных о прибыли на эту дату, котик! 😿")
        await state.clear()
        return

    try:
        profit_float = float(profit_value)
        logger.info(f"💰 Final profit calculation: {profit_float} for {clean_date}")
    except ValueError:
        logger.error(f"❌ Cannot convert profit to float: {profit_value}")
        profit_float = 0

    # Обновленные сообщения с учетом новой формулы
    if profit_float < 4000:
        text = f"📊 Твоя прибыль за {clean_date}: {profit_float:.2f}₽.\nНе расстраивайся, котик 🐾 — ты отлично поработала! Каждая смена — это опыт! 🌸"
    elif 4000 <= profit_float <= 6000:
        text = f"📊 Твоя прибыль за {clean_date}: {profit_float:.2f}₽.\nНеплохая смена, пушистик 😺 — беги радовать себя чем-то вкусным! Ты это заслужила! 💖"
    else:
        text = f"📊 Твоя прибыль за {clean_date}: {profit_float:.2f}₽.\nТы просто суперстар 🌟 — ещё немного, и миллион твой! Горжусь тобой! 🎉"
    
    await msg.answer(text)
    await state.clear()

# STATS FLOW - только для SQLite
@dp.message(Command("stats"))
async def stats_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    
    if storage_type == 'google_sheets':
        await msg.answer("❌ Статистика временно недоступна при использовании Google Sheets, котик! Используй SQLite хранилище 🐾")
        return
        
    if not db_manager:
        await msg.answer("❌ Модуль статистики недоступен, пушистик! 🐾")
        return
        
    await msg.answer("Введи начальную дату для статистики, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_stats_start)

@dp.message(Form.waiting_for_stats_start)
async def process_stats_start(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
        await state.update_data(stats_start=clean_date)
        await msg.answer("Введи конечную дату, котик! (ДД.ММ.ГГГГ):")
        await state.set_state(Form.waiting_for_stats_end)
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ")
        await state.clear()

@dp.message(Form.waiting_for_stats_end)
async def process_stats_end(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
        user_data = await state.get_data()
        start_date = user_data['stats_start']
        end_date = clean_date
        
        stats = await db_manager.get_statistics(start_date, end_date)
        
        if not stats:
            await msg.answer("❌ Нет данных за указанный период, котик! 🐾")
            await state.clear()
            return
        
        # Форматируем статистику
        text = f"📊 **Статистика за период {start_date} - {end_date}:**\n\n"
        text += f"• Количество смен: {stats['shift_count']} 🌸\n"
        text += f"• Общая выручка: {stats['total_revenue']:.2f}₽ 💰\n"
        text += f"• Общие чаевые: {stats['total_tips']:.2f}₽ ☕️\n"
        text += f"• Общая прибыль: {stats['total_profit']:.2f}₽ 🎉\n"
        text += f"• Средняя выручка за смену: {stats['avg_revenue']:.2f}₽ ✨\n"
        text += f"• Средние чаевые за смену: {stats['avg_tips']:.2f}₽ 💖\n"
        text += f"• Средняя прибыль за смену: {stats['avg_profit']:.2f}₽ 🐾\n\n"
        text += f"**Отличные результаты, котик! Горжусь тобой!** 🌟"
        
        await msg.answer(text)
        
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ")
    
    await state.clear()

# EXPORT FLOW - только для SQLite
@dp.message(Command("export"))
async def export_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    
    if storage_type == 'google_sheets':
        await msg.answer("❌ Экспорт временно недоступен при использовании Google Sheets, котик! Используй SQLite хранилище 🐾")
        return
        
    if not db_manager:
        await msg.answer("❌ Модуль экспорта недоступен, пушистик! 🐾")
        return
        
    await msg.answer("Введи начальную дату для экспорта, котик! (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_export_start)

@dp.message(Form.waiting_for_export_start)
async def process_export_start(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
        await state.update_data(export_start=clean_date)
        await msg.answer("Введи конечную дату, котик! (ДД.ММ.ГГГГ):")
        await state.set_state(Form.waiting_for_export_end)
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ")
        await state.clear()

@dp.message(Form.waiting_for_export_end)
async def process_export_end(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
        user_data = await state.get_data()
        start_date = user_data['export_start']
        end_date = clean_date
        
        shifts = await db_manager.get_shifts_in_period(start_date, end_date)
        
        if not shifts:
            await msg.answer("❌ Нет данных за указанный период, котик! 🐾")
            await state.clear()
            return
        
        # Формируем экспорт
        export_text = f"**Экспорт данных за период {start_date} - {end_date}**\n\n"
        
        total_revenue = 0
        total_tips = 0
        
        for shift in shifts:
            export_text += f"📅 {shift['date']} ({shift['start']}-{shift['end']})\n"
            export_text += f"   Выручка: {shift['revenue']:.2f}₽\n"
            export_text += f"   Чаевые: {shift['tips']:.2f}₽\n"
            export_text += f"   Прибыль: {(shift['revenue'] + shift['tips']):.2f}₽\n\n"
            
            total_revenue += shift['revenue']
            total_tips += shift['tips']
        
        export_text += f"**ИТОГО:**\n"
        export_text += f"Выручка: {total_revenue:.2f}₽ 💰\n"
        export_text += f"Чаевые: {total_tips:.2f}₽ ☕️\n"
        export_text += f"Общая прибыль: {total_revenue + total_tips:.2f}₽ 🎉\n\n"
        export_text += f"**Отличная работа, котик!** 🌟"
        
        # Разбиваем на части если сообщение слишком длинное
        if len(export_text) > 4000:
            parts = [export_text[i:i+4000] for i in range(0, len(export_text), 4000)]
            for part in parts:
                await msg.answer(part)
                await asyncio.sleep(0.5)
        else:
            await msg.answer(export_text)
        
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ")
    
    await state.clear()

@dp.message()
async def echo(message: types.Message):
    """Обработка любых других сообщений"""
    if not check_access(message): return
    await message.answer("Не понимаю эту команду, котик! 😿\nИспользуй /help для списка команд 🐾")

async def main():
    try:
        logger.info("🚀 Starting bot with enhanced features...")
        
        # Настройка уведомлений
        scheduler = setup_scheduler(bot)
        if scheduler:
            logger.info("✅ Notifications scheduler started")
        else:
            logger.warning("⚠️ Notifications scheduler not started - check USER_ID configuration")
        
        # УДАЛЯЕМ ВЕБХУК ПЕРЕД ЗАПУСКОМ POLLING
        logger.info("🗑️ Deleting webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted successfully")
        
        logger.info("✅ Starting polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Останавливаем планировщик при выходе
        if 'scheduler' in locals() and scheduler:
            scheduler.shutdown()
            logger.info("🛑 Scheduler stopped")

# Обработка graceful shutdown
def shutdown_hook():
    logger.info("👋 Bot is shutting down...")

atexit.register(shutdown_hook)

if __name__ == "__main__":
    print("🟢 Bot starting with enhanced features...")
    asyncio.run(main())
