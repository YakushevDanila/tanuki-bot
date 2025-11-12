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
    onboarding_step = State()

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

# ОНБОРДИНГ - ПЕРВОЕ ЗНАКОМСТВО С БОТОМ
async def start_onboarding(msg: types.Message, state: FSMContext):
    """Запуск онбординга для нового пользователя"""
    welcome_text = (
        "🌸 *Привет, Аня! Рада познакомиться!* 🌸\n\n"
        "Я — твой личный помощник для учета рабочих смен и заработка. "
        "Позволь рассказать, как я могу помочь тебе вести учет твоих финансов!\n\n"
        "💖 *Что я умею:*\n"
        "• Записывать твои смены и рабочее время\n"
        "• Учитывать выручку и чаевые\n"
        "• Автоматически считать прибыль\n"
        "• Показывать статистику и историю\n\n"
        "Хочешь, покажу как это работает? 🐾"
    )
    
    await msg.answer(welcome_text, parse_mode="Markdown", reply_markup=get_onboarding_keyboard())
    await state.set_state(Form.onboarding_step)

@dp.message(Form.onboarding_step, F.text == "🚀 Начать пользоваться")
async def quick_start(msg: types.Message, state: FSMContext):
    """Быстрый старт - сразу к функционалу"""
    await state.clear()
    await msg.answer(
        "Отлично! Давай начнем! 🚀\n\n"
        "Просто нажми на любую кнопку внизу, чтобы попробовать:\n\n"
        "• *📅 Добавить смену* - если хочешь записать новую смену\n"
        "• *🎯 Сегодня* - для быстрого ввода данных за сегодня\n"
        "• *🌸 Помощь* - если забудешь что-то\n\n"
        "Не бойся экспериментировать! Я всегда подскажу! 💖",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(msg.from_user.id)
    )

@dp.message(Form.onboarding_step, F.text == "📚 Подробный обзор")
async def detailed_onboarding(msg: types.Message, state: FSMContext):
    """Подробный обзор функционала"""
    # Шаг 1: Основные функции
    step1_text = (
        "📋 *ОСНОВНЫЕ ФУНКЦИИ:*\n\n"
        "✨ *📅 Добавить смену*\n"
        "Запись рабочего времени. Просто введи дату и время (например: 9-18 или 10:00-19:00)\n\n"
        "✨ *💰 Выручка* \n"
        "Учет дневной выручки. Я запомню сколько ты заработала!\n\n"
        "✨ *💖 Чаевые*\n"
        "Не забудь про чаевые! Они тоже считаются в прибыль 💫\n\n"
        "✨ *📊 Прибыль*\n"
        "Узнай сколько ты заработала за любой день"
    )
    await msg.answer(step1_text, parse_mode="Markdown")
    await asyncio.sleep(2)
    
    # Шаг 2: Умные функции
    step2_text = (
        "🎯 *УМНЫЕ ВОЗМОЖНОСТИ:*\n\n"
        "🚀 *🎯 Сегодня*\n"
        "Быстрый ввод всего за 2 шага! Идеально после рабочего дня\n\n"
        "🔄 *🔄 Изменить*\n"
        "Ошиблась? Не беда! Можешь исправить любые данные\n\n"
        "💫 *Авторасчет прибыли*\n"
        "Я сама посчитаю: (часы × 220) + чаевые + (выручка × 0.015)"
    )
    await msg.answer(step2_text, parse_mode="Markdown")
    await asyncio.sleep(2)
    
    # Шаг 3: Для администратора (если нужно)
    if is_admin(msg.from_user.id):
        step3_text = (
            "👑 *ДОПОЛНИТЕЛЬНО ДЛЯ АДМИНА:*\n\n"
            "📈 *Статистика* - полная аналитика за любой период\n"
            "📤 *Экспорт* - выгрузка всех данных\n"
            "🌙 *Неделя* - планирование смен на всю неделю\n"
            "🔔 *Уведомления* - напоминания о сменах"
        )
        await msg.answer(step3_text, parse_mode="Markdown")
        await asyncio.sleep(2)
    
    # Финальное сообщение
    final_text = (
        "🎉 *Вот и все! Теперь ты знаешь все мои секреты!*\n\n"
        "💡 *Советы для начала:*\n"
        "• Начни с кнопки *🎯 Сегодня* - это самый быстрый способ\n"
        "• Не переживай об ошибках - всё можно исправить\n"
        "• Данные сохраняются автоматически\n"
        "• Я всегда готова помочь! 🐾\n\n"
        "Готова начать? Жми на кнопки ниже! 🌸"
    )
    await msg.answer(final_text, parse_mode="Markdown", reply_markup=get_main_keyboard(msg.from_user.id))
    await state.clear()

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
async def start_cmd(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    
    # Для новых пользователей показываем онбординг
    # Для простоты будем показывать онбординг при каждом /start, но можно добавить логику проверки первого запуска
    await start_onboarding(msg, state)

@dp.message(Command("onboarding"))
async def onboarding_cmd(msg: types.Message, state: FSMContext):
    """Команда для повторного показа онбординга"""
    await start_onboarding(msg, state)

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
    """Расширенная помощь с примерами"""
    help_text = (
        "🌸 *Помощь по командам:*\n\n"
        
        "📅 *ОСНОВНЫЕ КНОПКИ:*\n"
        "• *📅 Добавить смену* - записать рабочее время\n"
        "• *💰 Выручка* - добавить дневную выручку\n" 
        "• *💖 Чаевые* - учесть чаевые\n"
        "• *📊 Прибыль* - узнать заработок за день\n"
        "• *🎯 Сегодня* - быстрый ввод за сегодня\n"
        "• *🔄 Изменить* - исправить данные\n\n"
        
        "💫 *ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:*\n"
        "• *Добавить смену:* \"15.03.2024 9-18\" или \"10:00-19:00\"\n"
        "• *Быстрый ввод:* \"15000 1200\" (выручка и чаевые)\n"
        "• *Формула прибыли:* (часы × 220) + чаевые + (выручка × 0.015)\n\n"
        
        "❓ *НУЖНА ПОМОЩЬ?*\n"
        "Напиши /onboarding для повторного обучения\n"
        "Или просто нажми любую кнопку - я подскажу! 🐾"
    )
    
    await msg.answer(help_text, parse_mode="Markdown", reply_markup=get_main_keyboard(msg.from_user.id))

# Обработчики кнопок главного меню
@dp.message(F.text == "🌸 Помощь")
async def help_button(msg: types.Message):
    """Обработка кнопки помощи"""
    await help_cmd(msg)

@dp.message(F.text == "📅 Добавить смену")
async def add_shift_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки добавления смены"""
    await msg.answer(
        "Отлично! Давай добавим смену! 📅\n\n"
        "Введи дату (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_date)

@dp.message(F.text == "💰 Выручка")
async def revenue_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки выручки"""
    await msg.answer(
        "Записываем выручку! 💰\n\n"
        "Введи дату (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_revenue_date)

@dp.message(F.text == "💖 Чаевые")
async def tips_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки чаевых"""
    await msg.answer(
        "Чаевые - это приятно! 💖\n\n"
        "Введи дату (ДД.ММ.ГГГГ) или выбери быстрый вариант:",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_tips_date)

@dp.message(F.text == "📊 Прибыль")
async def profit_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки прибыли"""
    await msg.answer(
        "Считаем прибыль! 📊\n\n"
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
        "Исправляем данные! 🔄\n\n"
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

# [ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ - те же самые обработчики состояний, что и в предыдущей версии]
# [Добавьте сюда все остальные обработчики из предыдущего кода: process_date, process_start, process_revenue_date, и т.д.]

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

# [ДОБАВЬТЕ ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ИЗ ПРЕДЫДУЩЕЙ ВЕРСИИ...]

@dp.message()
async def echo(message: types.Message):
    """Обработка любых других сообщений"""
    if not check_access(message): return
    
    # Если пользователь просто написал текст без команды, предлагаем помощь
    await message.answer(
        "Не понимаю эту команду, котик! 😿\n\n"
        "Используй кнопки ниже или нажми /help для списка команд 🐾\n"
        "Если запуталась - /onboarding покажет как пользоваться ботом! 🌸",
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
