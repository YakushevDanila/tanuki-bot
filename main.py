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
    if is_admin(user_id):
        # Клавиатура для администратора
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
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
                    KeyboardButton(text="📈 Статистика")
                ],
                [
                    KeyboardButton(text="🔄 Изменить"), 
                    KeyboardButton(text="📤 Экспорт")
                ],
                [
                    KeyboardButton(text="🌙 Неделя"), 
                    KeyboardButton(text="🌸 Помощь")
                ]
            ],
            resize_keyboard=True,
            input_field_placeholder="Выберите действие..."
        )
    else:
        # Клавиатура для обычного пользователя
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
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
                    KeyboardButton(text="🌸 Помощь")
                ]
            ],
            resize_keyboard=True,
            input_field_placeholder="Выберите действие..."
        )
    return keyboard

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

async def cancel_action(message: types.Message, state: FSMContext, text: str = "Действие отменено, котик! 🐾"):
    """Универсальная функция отмены действия"""
    await state.clear()
    await message.answer(
        f"{text}\nВозвращаю в главное меню! 🌸",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# Команды для уведомлений (только для админа)
@dp.message(Command("test_notification"))
async def test_notification_cmd(msg: types.Message):
    """Тестовая команда для проверки уведомлений"""
    if not check_access(msg): return
    
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта команда доступна только администратору, котик! 🐾")
        return
        
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

# Команды управления клавиатурой
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    if not check_access(msg): return
    
    storage_info = "Google Sheets" if storage_type == "google_sheets" else "SQLite"
    
    # Приветственное сообщение в зависимости от прав
    if is_admin(msg.from_user.id):
        text = (
            "Привет, администратор! 🌸\n"
            "У тебя есть доступ ко всем командам!\n\n"
            "📅 **Основные команды:**\n"
            "• Добавить смену - добавить дату и время смены\n"
            "• Выручка - ввести выручку за день\n"
            "• Чаевые - добавить сумму чаевых 💰\n"
            "• Прибыль - узнать прибыль за день\n"
            "• Сегодня - быстрый ввод за сегодня 🎯\n\n"
            "📊 **Расширенные возможности:**\n"
            "• Статистика - статистика за период\n"
            "• Экспорт - экспорт данных\n"
            "• Неделя - добавить смены на неделю\n"
            "• Изменить - изменить данные\n\n"
            f"💾 Хранилище: {storage_info}\n"
            "💰 Формула прибыли: (часы × 220) + чаевые + (выручка × 0.015)"
        )
    else:
        text = (
            "Привет, котик! 🌸\n"
            "Вот что я умею:\n\n"
            "📅 **Основные команды:**\n"
            "• Добавить смену - добавить дату и время смены\n"
            "• Выручка - ввести выручку за день\n"
            "• Чаевые - добавить сумму чаевых 💰\n"
            "• Прибыль - узнать прибыль за день\n"
            "• Сегодня - быстрый ввод за сегодня 🎯\n"
            "• Изменить - изменить данные\n\n"
            f"💾 Хранилище: {storage_info}\n"
            "💰 Формула прибыли: (часы × 220) + чаевые + (выручка × 0.015)"
        )
    
    await msg.answer(text, reply_markup=get_main_keyboard(msg.from_user.id))

@dp.message(Command("keyboard"))
async def show_keyboard(msg: types.Message):
    """Показать клавиатуру"""
    await msg.answer(
        "Вот клавиатура с командами! 🌸",
        reply_markup=get_main_keyboard(msg.from_user.id)
    )

@dp.message(Command("hide"))
async def hide_keyboard(msg: types.Message):
    """Скрыть клавиатуру"""
    await msg.answer(
        "Клавиатура скрыта! 🐾\n"
        "Чтобы вернуть, используй /start или /keyboard",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Command("myid"))
async def show_my_id(msg: types.Message):
    user_id = msg.from_user.id
    first_name = msg.from_user.first_name or "Пользователь"
    role = "👑 Администратор" if is_admin(user_id) else "😺 Котик"
    await msg.answer(f"👤 {first_name}, ваш ID: `{user_id}`\nРоль: {role}", parse_mode="Markdown")

@dp.message(Command("help"))
async def help_cmd(msg: types.Message):
    await start_cmd(msg)

# Обработчики кнопок главного меню
@dp.message(F.text == "🌸 Помощь")
async def help_button(msg: types.Message):
    """Обработка кнопки помощи"""
    await help_cmd(msg)

@dp.message(F.text == "📅 Добавить смену")
async def add_shift_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки добавления смены"""
    await msg.answer(
        "Введи дату смены (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_date)

@dp.message(F.text == "💰 Выручка")
async def revenue_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки выручки"""
    await msg.answer(
        "Введи дату (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_revenue_date)

@dp.message(F.text == "💖 Чаевые")
async def tips_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки чаевых"""
    await msg.answer(
        "Введи дату (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_tips_date)

@dp.message(F.text == "📊 Прибыль")
async def profit_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки прибыли"""
    await msg.answer(
        "Введи дату (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_profit_date)

@dp.message(F.text == "🎯 Сегодня")
async def today_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки сегодня"""
    await quick_today_start(msg, state)

@dp.message(F.text == "🔄 Изменить")
async def edit_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки изменения"""
    await msg.answer(
        "Введи дату для изменения (ДД.ММ.ГГГГ):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(Form.waiting_for_edit_date)

@dp.message(F.text == "📈 Статистика")
async def stats_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки статистики"""
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта функция доступна только администратору, котик! 🐾")
        return
    await stats_start(msg, state)

@dp.message(F.text == "📤 Экспорт")
async def export_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки экспорта"""
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта функция доступна только администратору, котик! 🐾")
        return
    await export_start(msg, state)

@dp.message(F.text == "🌙 Неделя")
async def week_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки добавления недели"""
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта функция доступна только администратору, котик! 🐾")
        return
    await add_week_start(msg, state)

@dp.message(F.text == "❌ Отмена")
async def cancel_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки отмены"""
    await cancel_action(msg, state)

# Обработка быстрых дат
@dp.message(Form.waiting_for_date, F.text == "📅 Сегодня")
@dp.message(Form.waiting_for_revenue_date, F.text == "📅 Сегодня")
@dp.message(Form.waiting_for_tips_date, F.text == "📅 Сегодня")
@dp.message(Form.waiting_for_profit_date, F.text == "📅 Сегодня")
@dp.message(Form.waiting_for_edit_date, F.text == "📅 Сегодня")
async def process_today_date(msg: types.Message, state: FSMContext):
    """Обработка быстрого выбора сегодняшней даты"""
    today = datetime.now().strftime("%d.%m.%Y")
    
    current_state = await state.get_state()
    
    if current_state == Form.waiting_for_date:
        await state.update_data(date=today, is_overwrite=False)
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00\n"
            "• 0900-1800",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Form.waiting_for_start)
    
    elif current_state == Form.waiting_for_revenue_date:
        await state.update_data(revenue_date=today)
        await msg.answer("Введи сумму выручки (только число):", reply_markup=get_cancel_keyboard())
        await state.set_state(Form.waiting_for_revenue)
    
    elif current_state == Form.waiting_for_tips_date:
        await state.update_data(tips_date=today)
        await msg.answer("Введи сумму чаевых (число):", reply_markup=get_cancel_keyboard())
        await state.set_state(Form.waiting_for_tips)
    
    elif current_state == Form.waiting_for_profit_date:
        # Проверяем существование смены
        exists = await check_shift_exists(today)
        if not exists:
            await msg.answer(f"❌ Смена на сегодня ({today}) не найдена, котик!", reply_markup=get_main_keyboard(msg.from_user.id))
            await state.clear()
            return
        
        profit_value = await get_profit(today)
        if profit_value is None:
            await msg.answer("❌ Нет данных о прибыли на сегодня, котик! 😿", reply_markup=get_main_keyboard(msg.from_user.id))
            await state.clear()
            return
        
        await show_profit_result(msg, today, profit_value)
        await state.clear()
    
    elif current_state == Form.waiting_for_edit_date:
        await state.update_data(edit_date=today)
        await msg.answer(
            "Что редактируем, пушистик?",
            reply_markup=get_edit_keyboard()
        )
        await state.set_state(Form.waiting_for_edit_field)

@dp.message(Form.waiting_for_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_revenue_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_tips_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_profit_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_edit_date, F.text == "📅 Вчера")
async def process_yesterday_date(msg: types.Message, state: FSMContext):
    """Обработка быстрого выбора вчерашней даты"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
    
    current_state = await state.get_state()
    
    if current_state == Form.waiting_for_date:
        await state.update_data(date=yesterday, is_overwrite=False)
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00\n"
            "• 0900-1800",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Form.waiting_for_start)
    
    elif current_state == Form.waiting_for_revenue_date:
        await state.update_data(revenue_date=yesterday)
        await msg.answer("Введи сумму выручки (только число):", reply_markup=get_cancel_keyboard())
        await state.set_state(Form.waiting_for_revenue)
    
    elif current_state == Form.waiting_for_tips_date:
        await state.update_data(tips_date=yesterday)
        await msg.answer("Введи сумму чаевых (число):", reply_markup=get_cancel_keyboard())
        await state.set_state(Form.waiting_for_tips)
    
    elif current_state == Form.waiting_for_profit_date:
        # Проверяем существование смены
        exists = await check_shift_exists(yesterday)
        if not exists:
            await msg.answer(f"❌ Смена на вчера ({yesterday}) не найдена, котик!", reply_markup=get_main_keyboard(msg.from_user.id))
            await state.clear()
            return
        
        profit_value = await get_profit(yesterday)
        if profit_value is None:
            await msg.answer("❌ Нет данных о прибыли на вчера, котик! 😿", reply_markup=get_main_keyboard(msg.from_user.id))
            await state.clear()
            return
        
        await show_profit_result(msg, yesterday, profit_value)
        await state.clear()
    
    elif current_state == Form.waiting_for_edit_date:
        await state.update_data(edit_date=yesterday)
        await msg.answer(
            "Что редактируем, пушистик?",
            reply_markup=get_edit_keyboard()
        )
        await state.set_state(Form.waiting_for_edit_field)

# Обработка полей редактирования через кнопки
@dp.message(Form.waiting_for_edit_field, F.text == "🕐 Начало")
@dp.message(Form.waiting_for_edit_field, F.text == "🕘 Конец")
@dp.message(Form.waiting_for_edit_field, F.text == "💰 Выручка")
@dp.message(Form.waiting_for_edit_field, F.text == "💖 Чаевые")
async def process_edit_field_button(msg: types.Message, state: FSMContext):
    """Обработка выбора поля редактирования через кнопки"""
    field_map = {
        "🕐 Начало": "начало",
        "🕘 Конец": "конец", 
        "💰 Выручка": "выручка",
        "💖 Чаевые": "чай"
    }
    
    field = field_map[msg.text]
    await state.update_data(edit_field=field)
    
    field_names = {
        "начало": "время начала (например: 09:00)",
        "конец": "время окончания (например: 18:00)", 
        "выручка": "сумму выручки",
        "чай": "сумму чаевых"
    }
    
    await msg.answer(
        f"Введи новое значение для {field_names[field]}:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(Form.waiting_for_edit_value)

# Основные flow функции (адаптированные под новую систему)
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
            f"• 0900-1800",
            reply_markup=get_cancel_keyboard()
        )
        await state.update_data(today_date=today)
        await state.set_state(Form.waiting_for_quick_today)
        return
    
    # Если смена есть, запрашиваем финансовые данные
    await msg.answer(
        f"🎯 **Быстрый ввод данных за {today}:**\n\n"
        f"Введи данные в формате:\n"
        f"<выручка> <чаевые>\n\n"
        f"Пример: 15000 1200",
        reply_markup=get_cancel_keyboard()
    )
    await state.update_data(today_date=today, has_shift=True)
    await state.set_state(Form.waiting_for_quick_today)

@dp.message(Form.waiting_for_quick_today)
async def process_quick_today(msg: types.Message, state: FSMContext):
    """Обработка быстрого ввода за сегодня"""
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
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
                "Пример: 15000 1200",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        revenue, tips = parts
        
        # Проверяем что это числа
        try:
            float(revenue)
            float(tips)
        except ValueError:
            await msg.answer("❌ Оба значения должны быть числами, пушистик!", reply_markup=get_cancel_keyboard())
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
                f"Отличная работа! 🌟",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
        else:
            await msg.answer("❌ Ошибка при обновлении данных, котик! Давай попробуем ещё раз? 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
    
    else:
        # Обработка создания смены
        time_parts = await parse_flexible_time(input_text)
        if not time_parts:
            await msg.answer(
                "❌ Неверный формат времени, пушистик!\n"
                "Используй: начало-конец\n"
                "Примеры: 9-18, 10:00-19:00",
                reply_markup=get_cancel_keyboard()
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
                "Используй ЧЧ:ММ, например: 09:00-18:00",
                reply_markup=get_cancel_keyboard()
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
                f"Пример: 15000 1200",
                reply_markup=get_cancel_keyboard()
            )
            await state.update_data(has_shift=True)
        else:
            await msg.answer("❌ Ошибка при создании смены, котик! 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
    
    await state.clear()

# ADD SHIFT FLOW
@dp.message(Command("add_shift"))
async def add_shift_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer(
        "Введи дату смены (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_date)

@dp.message(Form.waiting_for_date)
async def process_date(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    clean_date = clean_user_input(msg.text)
    
    # Проверяем валидность даты
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
    except ValueError:
        await msg.answer(
            "❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ (например, 15.03.2024)",
            reply_markup=get_date_keyboard()
        )
        return
    
    # Проверяем, существует ли уже смена с этой датой
    exists = await check_shift_exists(clean_date)
    if exists:
        await state.update_data(date=clean_date, is_overwrite=True)
        await msg.answer(
            f"❌ Смена на дату {clean_date} уже существует, котик!\n"
            "Хочешь перезаписать ее? (да/нет)",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Form.waiting_for_overwrite_confirm)
    else:
        await state.update_data(date=clean_date, is_overwrite=False)
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00\n"
            "• 0900-1800",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Form.waiting_for_start)

# Обработчик подтверждения перезаписи
@dp.message(Form.waiting_for_overwrite_confirm)
async def process_overwrite_confirm(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in ['да', 'yes', 'y', 'д']:
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Form.waiting_for_start)
    elif user_response in ['нет', 'no', 'n', 'н']:
        await cancel_action(msg, state, "❌ Добавление смены отменено, котик!")
    else:
        await msg.answer("Пожалуйста, ответь 'да' или 'нет', пушистик! 🌸", reply_markup=get_cancel_keyboard())

@dp.message(Form.waiting_for_start)
async def process_start(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    time_input = msg.text.strip()
    
    # Используем умный парсинг времени
    time_parts = await parse_flexible_time(time_input)
    if not time_parts:
        await msg.answer(
            "❌ Неверный формат времени, котик!\n"
            "Используй: начало-конец\n"
            "Примеры: 9-18, 10:00-19:00",
            reply_markup=get_cancel_keyboard()
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
            "Используй ЧЧ:ММ, например: 09:00-18:00",
            reply_markup=get_cancel_keyboard()
        )
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
                f"1. Введи сумму выручки за этот день:",
                reply_markup=get_cancel_keyboard()
            )
            # Сохраняем данные для последующего ввода
            await state.update_data(
                revenue_date=date_msg,
                tips_date=date_msg,
                is_overwrite_flow=True
            )
            await state.set_state(Form.waiting_for_revenue)
        else:
            await msg.answer(
                f"✅ Смена {date_msg} ({start_time}-{end_time}) добавлена! 🩷\n\nОтличная работа, котик! 🌟",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
            await state.clear()
    else:
        await msg.answer("❌ Ошибка при добавлении смены, котик! 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
        await state.clear()

# REVENUE FLOW
@dp.message(Form.waiting_for_revenue_date)
async def process_revenue_date(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(
            f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
        await state.clear()
        return
        
    await state.update_data(revenue_date=clean_date)
    await msg.answer("Введи сумму выручки (только число):", reply_markup=get_cancel_keyboard())
    await state.set_state(Form.waiting_for_revenue)

@dp.message(Form.waiting_for_revenue)
async def process_revenue(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    user_data = await state.get_data()
    date_msg = user_data['revenue_date']
    rev = clean_user_input(msg.text)
    
    # Проверяем, что введено число
    try:
        float(rev)
    except ValueError:
        await msg.answer("❌ Неверный формат числа, пушистик! Введи только цифры (например: 5000)", reply_markup=get_cancel_keyboard())
        return
    
    success = await update_value(date_msg, "выручка", rev)
    if success:
        # Если это поток перезаписи, переходим к вводу чаевых
        if user_data.get('is_overwrite_flow'):
            # Сохраняем выручку в состоянии для финального сообщения
            await state.update_data(revenue=rev)
            await msg.answer(f"✅ Выручка {rev}₽ обновлена! 💰✨\n\nТеперь введи сумму чаевых:", reply_markup=get_cancel_keyboard())
            await state.set_state(Form.waiting_for_tips)
        else:
            await msg.answer(
                f"✅ Выручка {rev}₽ обновлена для даты {date_msg}! 💰✨\n\nМолодец, котик! 🌟",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
            await state.clear()
    else:
        await msg.answer("❌ Не удалось обновить выручку, котик! 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
        await state.clear()

# TIPS FLOW
@dp.message(Form.waiting_for_tips_date)
async def process_tips_date(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(
            f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
        await state.clear()
        return
        
    await state.update_data(tips_date=clean_date)
    await msg.answer("Введи сумму чаевых (число):", reply_markup=get_cancel_keyboard())
    await state.set_state(Form.waiting_for_tips)

@dp.message(Form.waiting_for_tips)
async def process_tips(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    user_data = await state.get_data()
    date_msg = user_data['tips_date']
    tips_amount = clean_user_input(msg.text)
    
    # Проверяем, что введено число
    try:
        float(tips_amount)
    except ValueError:
        await msg.answer("❌ Неверный формат числа, пушистик! Введи только цифры (например: 500)", reply_markup=get_cancel_keyboard())
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
                f"Отличная работа, котик! 🐾",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
        else:
            await msg.answer(
                f"✅ Чаевые {tips_amount}₽ добавлены для даты {date_msg}! ☕️💖\n\nПушистик, ты лучшая! 🌸",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
    
    await state.clear()

# EDIT FLOW
@dp.message(Form.waiting_for_edit_date)
async def process_edit_date(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(
            f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
        await state.clear()
        return
        
    await state.update_data(edit_date=clean_date)
    await msg.answer(
        "Что редактируем, пушистик?",
        reply_markup=get_edit_keyboard()
    )
    await state.set_state(Form.waiting_for_edit_field)

@dp.message(Form.waiting_for_edit_field)
async def process_edit_field(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    field = clean_user_input(msg.text).lower()
    if field not in ["чай", "начало", "конец", "выручка"]:
        await msg.answer("❌ Такого параметра нет, котик! Используй: чай, начало, конец, выручка 🐾", reply_markup=get_edit_keyboard())
        return
    
    await state.update_data(edit_field=field)
    await msg.answer(f"Введи новое значение для {field}:", reply_markup=get_cancel_keyboard())
    await state.set_state(Form.waiting_for_edit_value)

@dp.message(Form.waiting_for_edit_value)
async def process_edit_value(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    user_data = await state.get_data()
    date_msg = user_data['edit_date']
    field = user_data['edit_field']
    value = clean_user_input(msg.text)
    
    success = await update_value(date_msg, field, value)
    if success:
        await msg.answer(
            f"✅ {field} изменен на {value} для даты {date_msg}! 🩷\n\nМолодец, котик! 🌟",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
    else:
        await msg.answer("❌ Ошибка: не удалось сохранить изменения, пушистик! 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
    
    await state.clear()

# PROFIT FLOW
@dp.message(Form.waiting_for_profit_date)
async def process_profit_date(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    clean_date = clean_user_input(msg.text)
    
    # Проверяем валидность даты
    try:
        day = datetime.strptime(clean_date, "%d.%m.%Y").date()
        if day > dt.today():
            await msg.answer("❌ Этот день ещё не наступил, котик! 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
            await state.clear()
            return
    except ValueError:
        await msg.answer("❌ Неверный формат даты, пушистик! Используй ДД.ММ.ГГГГ", reply_markup=get_main_keyboard(msg.from_user.id))
        await state.clear()
        return

    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена, котик! Сначала добавь смену через /add_shift 🐾", reply_markup=get_main_keyboard(msg.from_user.id))
        await state.clear()
        return

    profit_value = await get_profit(clean_date)
    if profit_value is None:
        await msg.answer("❌ Нет данных о прибыли на эту дату, котик! 😿", reply_markup=get_main_keyboard(msg.from_user.id))
        await state.clear()
        return

    await show_profit_result(msg, clean_date, profit_value)
    await state.clear()

async def show_profit_result(msg: types.Message, date: str, profit_value: float):
    """Показать результат расчета прибыли"""
    try:
        profit_float = float(profit_value)
        logger.info(f"💰 Final profit calculation: {profit_float} for {date}")
    except ValueError:
        logger.error(f"❌ Cannot convert profit to float: {profit_value}")
        profit_float = 0

    # Обновленные сообщения с учетом новой формулы
    if profit_float < 4000:
        text = f"📊 Твоя прибыль за {date}: {profit_float:.2f}₽.\nНе расстраивайся, котик 🐾 — ты отлично поработала! Каждая смена — это опыт! 🌸"
    elif 4000 <= profit_float <= 6000:
        text = f"📊 Твоя прибыль за {date}: {profit_float:.2f}₽.\nНеплохая смена, пушистик 😺 — беги радовать себя чем-то вкусным! Ты это заслужила! 💖"
    else:
        text = f"📊 Твоя прибыль за {date}: {profit_float:.2f}₽.\nТы просто суперстар 🌟 — ещё немного, и миллион твой! Горжусь тобой! 🎉"
    
    await msg.answer(text, reply_markup=get_main_keyboard(msg.from_user.id))

# ADMIN-ONLY COMMANDS
@dp.message(Command("add_week"))
async def add_week_start(msg: types.Message, state: FSMContext):
    """Начало пакетного добавления смен на неделю"""
    if not check_access(msg): return
    
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта команда доступна только администратору, котик! 🐾")
        return
    
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
        f"Планируем неделю! 🚀",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(Form.waiting_for_week_schedule)

# STATS FLOW - только для админа
@dp.message(Command("stats"))
async def stats_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта команда доступна только администратору, котик! 🐾")
        return
        
    if storage_type == 'google_sheets':
        await msg.answer("❌ Статистика временно недоступна при использовании Google Sheets, котик! Используй SQLite хранилище 🐾")
        return
        
    if not db_manager:
        await msg.answer("❌ Модуль статистики недоступен, пушистик! 🐾")
        return
        
    await msg.answer("Введи начальную дату для статистики (ДД.ММ.ГГГГ):", reply_markup=get_cancel_keyboard())
    await state.set_state(Form.waiting_for_stats_start)

# EXPORT FLOW - только для админа
@dp.message(Command("export"))
async def export_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта команда доступна только администратору, котик! 🐾")
        return
        
    if storage_type == 'google_sheets':
        await msg.answer("❌ Экспорт временно недоступен при использовании Google Sheets, котик! Используй SQLite хранилище 🐾")
        return
        
    if not db_manager:
        await msg.answer("❌ Модуль экспорта недоступен, пушистик! 🐾")
        return
        
    await msg.answer("Введи начальную дату для экспорта (ДД.ММ.ГГГГ):", reply_markup=get_cancel_keyboard())
    await state.set_state(Form.waiting_for_export_start)

# Обработка остальных состояний для админских команд (оставьте как есть из предыдущей версии)
# [Здесь должны быть обработчики Form.waiting_for_week_schedule, Form.waiting_for_stats_start и т.д.]

@dp.message()
async def echo(message: types.Message):
    """Обработка любых других сообщений"""
    if not check_access(message): return
    await message.answer(
        "Не понимаю эту команду, котик! 😿\nИспользуй кнопки ниже или /help для списка команд 🐾",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

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
