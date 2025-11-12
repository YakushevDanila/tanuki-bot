from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import asyncio
from datetime import datetime, date as dt, timedelta
import logging
import os
from dotenv import load_dotenv
import atexit
import io
import csv

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

# ID администратора
ADMIN_ID = 462439834

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == ADMIN_ID

def get_main_keyboard(user_id: int):
    """Основная клавиатура в зависимости от прав пользователя"""
    keyboard_buttons = [
        [
            KeyboardButton(text="📅 Добавить смену"), 
            KeyboardButton(text="💰 Выручка")
        ],
        [
            KeyboardButton(text="💖 Чаевые"), 
            KeyboardButton(text="📊 Прибыль")
        ],
        [
            KeyboardButton(text="🎯 Сегодня"), 
            KeyboardButton(text="🔄 Изменить")
        ],
        [
            KeyboardButton(text="🗑️ Удалить"),
            KeyboardButton(text="📅 График")
        ],
        [
            KeyboardButton(text="📅 Неделя"),
            KeyboardButton(text="📤 Экспорт")
        ],
        [
            KeyboardButton(text="🌸 Помощь")
        ]
    ]
    
    # Если пользователь администратор, добавляем кнопку экспорта
    if is_admin(user_id):
        keyboard_buttons.insert(5, [KeyboardButton(text="📊 Статистика")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_onboarding_keyboard():
    """Клавиатура для онбординга"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать пользоваться")],
            [KeyboardButton(text="📚 Подробный обзор")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_date_keyboard():
    """Клавиатура для быстрого выбора даты"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📅 Сегодня"), 
                KeyboardButton(text="📅 Вчера")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )

def get_edit_keyboard():
    """Клавиатура для выбора поля редактирования"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🕐 Начало"), 
                KeyboardButton(text="🕘 Конец")
            ],
            [
                KeyboardButton(text="💰 Выручка"), 
                KeyboardButton(text="💖 Чаевые")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )

def get_delete_confirmation_keyboard():
    """Клавиатура для подтверждения удаления"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Да, удалить"), 
                KeyboardButton(text="❌ Нет, отмена")
            ]
        ],
        resize_keyboard=True
    )

def get_week_confirmation_keyboard():
    """Клавиатура для подтверждения добавления недели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Да, добавить"), 
                KeyboardButton(text="❌ Нет, отмена")
            ]
        ],
        resize_keyboard=True
    )

def get_export_keyboard():
    """Клавиатура для выбора формата экспорта"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 CSV файл"), 
                KeyboardButton(text="📈 Excel файл")
            ],
            [
                KeyboardButton(text="📋 Текстовая сводка"),
                KeyboardButton(text="📅 За период")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )

def get_period_keyboard():
    """Клавиатура для выбора периода"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📅 Неделя"), 
                KeyboardButton(text="📅 Месяц")
            ],
            [
                KeyboardButton(text="📅 Квартал"),
                KeyboardButton(text="📅 Все данные")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )

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
    waiting_for_week_schedule = State()
    waiting_for_week_confirmation = State()
    waiting_for_quick_today = State()
    waiting_for_shifts_count = State()
    waiting_for_shift_data = State()
    waiting_for_multiple_confirmation = State()
    onboarding_step = State()
    waiting_for_delete_date = State()
    waiting_for_delete_confirmation = State()
    waiting_for_export_format = State()
    waiting_for_export_period = State()

# ВЫБОР ХРАНИЛИЩА
storage_type = os.getenv('STORAGE_TYPE', 'google_sheets').lower()

if storage_type == 'google_sheets':
    try:
        from sheets import add_shift, update_value, get_profit, check_shift_exists, delete_shift, get_shift_data, get_all_shifts
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
            delete_shift = storage.delete_shift
            get_shift_data = storage.get_shift_data
            get_all_shifts = storage.get_all_shifts
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
    delete_shift = storage.delete_shift
    get_shift_data = storage.get_shift_data
    get_all_shifts = storage.get_all_shifts
    logger.info("✅ Using SQLite storage")

# ВРЕМЕННО ОТКЛЮЧАЕМ ПРОВЕРКУ ДОСТУПА
def check_access(message: types.Message):
    logger.info(f"🔓 Access granted for user: {message.from_user.id}")
    return True

async def cancel_action(message: types.Message, state: FSMContext, text: str = "Действие отменено, котик! 🐾"):
    """Универсальная функция отмены действия"""
    await state.clear()
    await message.answer(
        f"{text}\nВозвращаю в главное меню! 🌸",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# ФУНКЦИИ ЭКСПОРТА ДАННЫХ
async def generate_csv_file(shifts_data):
    """Генерация CSV файла с данными смен"""
    if not shifts_data:
        return None
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовки
    writer.writerow([
        'Дата', 'День недели', 'Начало', 'Конец', 'Часы', 
        'Выручка', 'Чаевые', 'Прибыль', 'Ставка', 'Процент с выручки'
    ])
    
    # Данные
    for shift in shifts_data:
        try:
            # Расчет дополнительных полей
            hours = shift.get('hours', 0)
            revenue = float(shift.get('revenue', 0) or 0)
            tips = float(shift.get('tips', 0) or 0)
            profit = float(shift.get('profit', 0) or 0)
            
            # Ставка и процент
            rate_income = float(hours) * 220 if hours else 0
            revenue_percent = revenue * 0.015
            
            # День недели
            day_name = get_day_name(datetime.strptime(shift['date'], "%d.%m.%Y").date())
            
            writer.writerow([
                shift['date'],
                day_name,
                shift.get('start', ''),
                shift.get('end', ''),
                shift.get('hours', ''),
                f"{revenue:.2f}",
                f"{tips:.2f}",
                f"{profit:.2f}",
                f"{rate_income:.2f}",
                f"{revenue_percent:.2f}"
            ])
        except Exception as e:
            logger.error(f"Error processing shift for CSV: {shift} - {e}")
            continue
    
    output.seek(0)
    return output

async def generate_text_summary(shifts_data):
    """Генерация текстовой сводки"""
    if not shifts_data:
        return "📊 Нет данных для отображения"
    
    total_shifts = len(shifts_data)
    total_hours = 0
    total_revenue = 0
    total_tips = 0
    total_profit = 0
    total_rate_income = 0
    total_revenue_percent = 0
    
    # Сортируем по дате
    shifts_data.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))
    
    for shift in shifts_data:
        try:
            hours = float(shift.get('hours', 0) or 0)
            revenue = float(shift.get('revenue', 0) or 0)
            tips = float(shift.get('tips', 0) or 0)
            profit = float(shift.get('profit', 0) or 0)
            
            total_hours += hours
            total_revenue += revenue
            total_tips += tips
            total_profit += profit
            total_rate_income += hours * 220
            total_revenue_percent += revenue * 0.015
        except (ValueError, TypeError):
            continue
    
    # Формируем сводку
    summary = f"📊 **СТАТИСТИКА ЗА ВЕСЬ ПЕРИОД**\n\n"
    summary += f"📅 Общее количество смен: {total_shifts}\n"
    summary += f"⏱ Общее время работы: {total_hours:.1f} часов\n"
    summary += f"💰 Общая выручка: {total_revenue:.2f}₽\n"
    summary += f"💖 Общие чаевые: {total_tips:.2f}₽\n"
    summary += f"📊 Общая прибыль: {total_profit:.2f}₽\n\n"
    
    summary += f"**ДЕТАЛИЗАЦИЯ ДОХОДОВ:**\n"
    summary += f"• Почасовой доход: {total_rate_income:.2f}₽\n"
    summary += f"• Процент с выручки: {total_revenue_percent:.2f}₽\n"
    summary += f"• Чаевые: {total_tips:.2f}₽\n\n"
    
    if total_hours > 0:
        avg_hourly = total_profit / total_hours
        summary += f"📈 Средний доход в час: {avg_hourly:.2f}₽\n"
    
    if total_shifts > 0:
        avg_shift = total_profit / total_shifts
        summary += f"📈 Средний доход за смену: {avg_shift:.2f}₽\n"
    
    summary += f"\n🌸 *Отличная работа! Продолжай в том же духе!* 💪"
    
    return summary

async def filter_shifts_by_period(shifts_data, period):
    """Фильтрация смен по периоду"""
    if not shifts_data:
        return []
    
    today = datetime.now().date()
    
    if period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:  # all data
        return shifts_data
    
    filtered_shifts = []
    for shift in shifts_data:
        try:
            shift_date = datetime.strptime(shift['date'], "%d.%m.%Y").date()
            if shift_date >= start_date:
                filtered_shifts.append(shift)
        except ValueError:
            continue
    
    return filtered_shifts

async def export_data(msg: types.Message, format_type: str = "csv", period: str = "all"):
    """Основная функция экспорта данных"""
    try:
        await msg.answer("🔄 Подготавливаю данные для экспорта...")
        
        # Получаем все смены
        all_shifts = await get_all_shifts()
        if not all_shifts:
            await msg.answer("❌ Нет данных для экспорта, котик! 🐾")
            return
        
        # Фильтруем по периоду если нужно
        if period != "all":
            all_shifts = await filter_shifts_by_period(all_shifts, period)
            if not all_shifts:
                await msg.answer(f"❌ Нет данных за выбранный период, котик! 🐾")
                return
        
        period_text = {
            "week": "неделю",
            "month": "месяц", 
            "quarter": "квартал",
            "all": "весь период"
        }.get(period, "весь период")
        
        if format_type == "csv":
            # Генерируем CSV файл
            csv_file = await generate_csv_file(all_shifts)
            if csv_file:
                # Создаем временный файл
                filename = f"смены_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                
                # Конвертируем StringIO в bytes
                csv_content = csv_file.getvalue().encode('utf-8-sig')  # UTF-8 with BOM for Excel
                
                # Создаем временный файл в памяти
                file_to_send = io.BytesIO(csv_content)
                file_to_send.name = filename
                
                await msg.answer_document(
                    document=types.BufferedInputFile(file_to_send.read(), filename=filename),
                    caption=f"📊 Экспорт данных за {period_text} ({len(all_shifts)} смен)\n\nФайл готов для открытия в Excel! 📈"
                )
            else:
                await msg.answer("❌ Ошибка при создании CSV файла, котик! 🐾")
                
        elif format_type == "text":
            # Генерируем текстовую сводку
            summary = await generate_text_summary(all_shifts)
            await msg.answer(summary, parse_mode="Markdown")
            
        elif format_type == "excel":
            # Для Excel можно использовать тот же CSV (Excel отлично открывает CSV)
            csv_file = await generate_csv_file(all_shifts)
            if csv_file:
                filename = f"смены_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                csv_content = csv_file.getvalue().encode('utf-8-sig')
                file_to_send = io.BytesIO(csv_content)
                file_to_send.name = filename
                
                await msg.answer_document(
                    document=types.BufferedInputFile(file_to_send.read(), filename=filename),
                    caption=f"📈 Excel-совместимый файл за {period_text} ({len(all_shifts)} смен)\n\nОткрой в Excel для красивого отображения! ✨"
                )
            else:
                await msg.answer("❌ Ошибка при создании файла, котик! 🐾")
                
    except Exception as e:
        logger.error(f"❌ Error in export_data: {e}")
        await msg.answer("❌ Ошибка при экспорте данных, котик! 🐾")

# ОБРАБОТЧИКИ ЭКСПОРТА
@dp.message(F.text == "📤 Экспорт")
async def export_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки экспорта"""
    await msg.answer(
        "📤 **Экспорт данных**\n\n"
        "Выбери формат экспорта:\n\n"
        "• *📊 CSV файл* - для Excel и анализа\n"
        "• *📈 Excel файл* - CSV с подсказкой для Excel\n" 
        "• *📋 Текстовая сводка* - статистика в сообщении\n"
        "• *📅 За период* - выбери период для экспорта",
        parse_mode="Markdown",
        reply_markup=get_export_keyboard()
    )
    await state.set_state(Form.waiting_for_export_format)

@dp.message(Form.waiting_for_export_format, F.text == "📊 CSV файл")
async def export_csv_handler(msg: types.Message, state: FSMContext):
    """Экспорт в CSV"""
    await export_data(msg, "csv", "all")
    await state.clear()

@dp.message(Form.waiting_for_export_format, F.text == "📈 Excel файл")
async def export_excel_handler(msg: types.Message, state: FSMContext):
    """Экспорт в Excel-совместимый CSV"""
    await export_data(msg, "excel", "all")
    await state.clear()

@dp.message(Form.waiting_for_export_format, F.text == "📋 Текстовая сводка")
async def export_text_handler(msg: types.Message, state: FSMContext):
    """Экспорт текстовой сводки"""
    await export_data(msg, "text", "all")
    await state.clear()

@dp.message(Form.waiting_for_export_format, F.text == "📅 За период")
async def export_period_handler(msg: types.Message, state: FSMContext):
    """Выбор периода для экспорта"""
    await msg.answer(
        "📅 **Выбери период для экспорта:**\n\n"
        "• *Неделя* - данные за последние 7 дней\n"
        "• *Месяц* - данные за последние 30 дней\n"
        "• *Квартал* - данные за последние 90 дней\n"
        "• *Все данные* - полная история смен",
        parse_mode="Markdown",
        reply_markup=get_period_keyboard()
    )
    await state.set_state(Form.waiting_for_export_period)

@dp.message(Form.waiting_for_export_period)
async def export_period_selected(msg: types.Message, state: FSMContext):
    """Обработка выбора периода"""
    period_map = {
        "📅 Неделя": "week",
        "📅 Месяц": "month", 
        "📅 Квартал": "quarter",
        "📅 Все данные": "all"
    }
    
    if msg.text not in period_map:
        await msg.answer("❌ Пожалуйста, выбери период из предложенных вариантов")
        return
    
    period = period_map[msg.text]
    
    await msg.answer(
        f"📤 **Экспорт данных за {period_map[msg.text]}**\n\n"
        "Выбери формат экспорта:",
        reply_markup=get_export_keyboard()
    )
    
    # Сохраняем период в состоянии
    await state.update_data(export_period=period)
    await state.set_state(Form.waiting_for_export_format)

# Обновляем обработчики форматов для учета периода
@dp.message(Form.waiting_for_export_format, F.text == "📊 CSV файл")
async def export_csv_with_period(msg: types.Message, state: FSMContext):
    """Экспорт в CSV с учетом периода"""
    user_data = await state.get_data()
    period = user_data.get('export_period', 'all')
    await export_data(msg, "csv", period)
    await state.clear()

@dp.message(Form.waiting_for_export_format, F.text == "📈 Excel файл")
async def export_excel_with_period(msg: types.Message, state: FSMContext):
    """Экспорт в Excel с учетом периода"""
    user_data = await state.get_data()
    period = user_data.get('export_period', 'all')
    await export_data(msg, "excel", period)
    await state.clear()

@dp.message(Form.waiting_for_export_format, F.text == "📋 Текстовая сводка")
async def export_text_with_period(msg: types.Message, state: FSMContext):
    """Экспорт текстовой сводки с учетом периода"""
    user_data = await state.get_data()
    period = user_data.get('export_period', 'all')
    await export_data(msg, "text", period)
    await state.clear()

# КОМАНДА СТАТИСТИКИ (только для админа)
@dp.message(F.text == "📊 Статистика")
async def statistics_button(msg: types.Message):
    """Обработка кнопки статистики (только для админа)"""
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта функция доступна только администратору, котик! 🐾")
        return
    
    await export_data(msg, "text", "all")

# Остальной код остается без изменений (онбординг, обработчики команд и т.д.)
# ... [здесь должен быть весь остальной код из предыдущего примера] ...

# Обновленная функция помощи
@dp.message(Command("help"))
async def help_cmd(msg: types.Message):
    """Расширенная помощь с примерами"""
    help_text = (
        "🌸 *Помощь по командам:*\n\n"
        
        "📅 *ОСНОВНЫЕ КНОПКИ:*\n"
        "• *📅 Добавить смену* - записать рабочее время\n"
        "• *💰 Выручка* - добавить дневную выручку\n" 
        "• *💖 Чаевые* - учесть чаевые\n"
        "• *📊 Прибыль* - узнать заработок за день\n"
        "• *🎯 Сегодня* - быстрый ввод за сегодня\n"
        "• *🔄 Изменить* - исправить данные\n"
        "• *🗑️ Удалить* - удалить смену (осторожно!)\n"
        "• *📅 График* - посмотреть смены на неделю\n"
        "• *📅 Неделя* - добавить смены на всю неделю\n"
        "• *📤 Экспорт* - выгрузить данные в файл\n\n"
        
        "💫 *ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:*\n"
        "• *Добавить смену:* \"15.03.2024 9-18\" или \"10:00-19:00\"\n"
        "• *Быстрый ввод:* \"15000 1200\" (выручка и чаевые)\n"
        "• *Формула прибыли:* (часы × 220) + чаевые + (выручка × 0.015)\n\n"
        
        "📊 *ЭКСПОРТ ДАННЫХ:*\n"
        "• CSV файл - для анализа в Excel\n"
        "• Текстовая сводка - статистика в сообщении\n"
        "• За период - данные за неделю/месяц/квартал\n\n"
        
        "❓ *НУЖНА ПОМОЩЬ?*\n"
        "Напиши /onboarding для повторного обучения\n"
        "Или просто нажми любую кнопку - я подскажу! 🐾"
    )
    
    await msg.answer(help_text, parse_mode="Markdown", reply_markup=get_main_keyboard(msg.from_user.id))

# Добавляем обработчик отмены для состояний экспорта
@dp.message(Form.waiting_for_export_format, F.text == "❌ Отмена")
@dp.message(Form.waiting_for_export_period, F.text == "❌ Отмена")
async def cancel_export(msg: types.Message, state: FSMContext):
    """Отмена экспорта"""
    await cancel_action(msg, state, "Экспорт отменен, котик! 🐾")

# Функция get_day_name (должна быть уже в коде)
def get_day_name(date_obj):
    """Получить название дня недели на русском"""
    try:
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        return days[date_obj.weekday()]
    except Exception as e:
        logger.error(f"Error getting day name for {date_obj}: {e}")
        return "День"

# Остальной код (main, запуск бота и т.д.) остается без изменений
# ... [остальной код из предыдущего примера] ...

async def main():
    try:
        logger.info("🚀 Starting bot with export features...")
        
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
    print("🟢 Bot starting with export features...")
    asyncio.run(main())
