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
    # Теперь у всех пользователей одинаковые права
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
                KeyboardButton(text="🗑️ Удалить"),
                KeyboardButton(text="📅 График")
            ],
            [
                KeyboardButton(text="📅 Неделя"),
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
        "Узнай сколько ты заработала за любой день\n\n"
        "✨ *🗑️ Удалить*\n"
        "Удали ошибочную смену (будь осторожна! ❤️)\n\n"
        "✨ *📅 График*\n"
        "Посмотри все запланированные смены на неделю"
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
        "📅 *📅 График на неделю*\n"
        "Добавь сразу все рабочие дни одним сообщением!\n\n"
        "💫 *Авторасчет прибыли*\n"
        "Я сама посчитаю: (часы × 220) + чаевые + (выручка × 0.015)"
    )
    await msg.answer(step2_text, parse_mode="Markdown")
    await asyncio.sleep(2)
    
    # Финальное сообщение
    final_text = (
        "🎉 *Вот и все! Теперь ты знаешь все мои секреты!*\n\n"
        "💡 *Советы для начала:*\n"
        "• Начни с кнопки *🎯 Сегодня* - это самый быстрый способ\n"
        "• Используй *📅 График* для планирования недели\n"
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
        "• *🔄 Изменить* - исправить данные\n"
        "• *🗑️ Удалить* - удалить смену (осторожно!)\n"
        "• *📅 График* - посмотреть смены на неделю\n"
        "• *📅 Неделя* - добавить смены на всю неделю\n\n"
        
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

@dp.message(F.text == "🗑️ Удалить")
async def delete_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки удаления"""
    await msg.answer(
        "Удаляем смену! 🗑️\n\n"
        "Введи дату смены для удаления (ДД.ММ.ГГГГ):",
        reply_markup=get_date_keyboard()
    )
    await state.set_state(Form.waiting_for_delete_date)

@dp.message(F.text == "📅 График")
async def schedule_button(msg: types.Message):
    """Обработка кнопки графика"""
    try:
        await msg.answer("🔄 Загружаю график смен...", reply_markup=ReplyKeyboardRemove())
        await show_schedule(msg)
    except Exception as e:
        logger.error(f"❌ Error in schedule_button: {e}")
        await msg.answer(
            "❌ Не удалось загрузить график смен, котик! 😿\n"
            "Попробуй еще раз или напиши разработчику! 🐾",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )

@dp.message(F.text == "📅 Неделя")
async def week_button(msg: types.Message, state: FSMContext):
    """Обработка кнопки добавления недели"""
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
@dp.message(Form.waiting_for_delete_date, F.text == "📅 Сегодня")
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
    
    elif current_state == Form.waiting_for_delete_date:
        await process_delete_date_with_data(msg, state, today)

@dp.message(Form.waiting_for_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_revenue_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_tips_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_profit_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_edit_date, F.text == "📅 Вчера")
@dp.message(Form.waiting_for_delete_date, F.text == "📅 Вчера")
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
    
    elif current_state == Form.waiting_for_delete_date:
        await process_delete_date_with_data(msg, state, yesterday)

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

# ОБРАБОТКА УДАЛЕНИЯ СМЕН
@dp.message(Form.waiting_for_delete_date)
async def process_delete_date(msg: types.Message, state: FSMContext):
    """Обработка ввода даты для удаления"""
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

    await process_delete_date_with_data(msg, state, clean_date)

async def process_delete_date_with_data(msg: types.Message, state: FSMContext, date_str: str):
    """Обработка удаления смены с данными"""
    # Проверяем существование смены
    exists = await check_shift_exists(date_str)
    if not exists:
        await msg.answer(
            f"❌ Смена на дату {date_str} не найдена, котик!",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
        await state.clear()
        return

    # Получаем данные смены
    shift_data = await get_shift_data(date_str)
    if not shift_data:
        await msg.answer(
            f"❌ Не удалось загрузить данные смены на {date_str}",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
        await state.clear()
        return

    # Сохраняем дату в состоянии и показываем подтверждение
    await state.update_data(delete_date=date_str, shift_data=shift_data)
    
    # Формируем сообщение с данными смены
    shift_info = (
        f"📅 *Дата:* {shift_data['date']}\n"
        f"🕐 *Время:* {shift_data['start']} - {shift_data['end']}\n"
        f"⏱ *Часы:* {shift_data['hours']}\n"
    )
    
    # Добавляем финансовые данные если они есть
    if shift_data.get('revenue') and str(shift_data['revenue']).strip():
        shift_info += f"💰 *Выручка:* {shift_data['revenue']}₽\n"
    if shift_data.get('tips') and str(shift_data['tips']).strip():
        shift_info += f"💖 *Чаевые:* {shift_data['tips']}₽\n"
    if shift_data.get('profit') and str(shift_data['profit']).strip():
        shift_info += f"📊 *Прибыль:* {shift_data['profit']}₽\n"
    
    shift_info += "\n❌ *Ты уверена, что хочешь удалить эту смену?*\n"
    shift_info += "Это действие нельзя отменить! 😿"
    
    await msg.answer(shift_info, parse_mode="Markdown", reply_markup=get_delete_confirmation_keyboard())
    await state.set_state(Form.waiting_for_delete_confirmation)

@dp.message(Form.waiting_for_delete_confirmation)
async def process_delete_confirmation(msg: types.Message, state: FSMContext):
    """Обработка подтверждения удаления"""
    if msg.text == "❌ Нет, отмена":
        await cancel_action(msg, state, "Удаление отменено, котик! 🐾")
        return
        
    if msg.text != "✅ Да, удалить":
        await msg.answer(
            "Пожалуйста, выбери вариант подтверждения:",
            reply_markup=get_delete_confirmation_keyboard()
        )
        return
        
    user_data = await state.get_data()
    date_to_delete = user_data['delete_date']
    
    success = await delete_shift(date_to_delete)
    if success:
        await msg.answer(
            f"✅ Смена на {date_to_delete} удалена! 💔\n\n"
            f"Не переживай, котик! Всегда можно добавить новую смену! 🌸",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
    else:
        await msg.answer(
            f"❌ Не удалось удалить смену на {date_to_delete}\n"
            f"Попробуй еще раз или напиши разработчику! 🐾",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )
    
    await state.clear()

# ПОКАЗ ГРАФИКА НА НЕДЕЛЮ - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def show_schedule(msg: types.Message):
    """Показать график смен на ближайшие дни"""
    try:
        logger.info(f"🔄 Loading schedule for user: {msg.from_user.id}")
        
        # Получаем все смены
        all_shifts = await get_all_shifts()
        logger.info(f"📊 Retrieved {len(all_shifts) if all_shifts else 0} shifts from storage")
        
        if not all_shifts:
            await msg.answer(
                "📅 У тебя пока нет запланированных смен, котик! 🐾\n\n"
                "Хочешь добавить первую смену? Нажми кнопку *📅 Добавить смену* или *📅 Неделя* для планирования недели! 🌸",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
            return

        # Фильтруем смены за последние 7 дней и следующие 14 дней
        today = datetime.now().date()
        start_date = today - timedelta(days=7)
        end_date = today + timedelta(days=14)
        
        logger.info(f"📅 Filtering shifts from {start_date} to {end_date}")
        
        relevant_shifts = []
        skipped_shifts = 0
        
        for shift in all_shifts:
            try:
                if not shift or 'date' not in shift:
                    skipped_shifts += 1
                    continue
                    
                shift_date = datetime.strptime(shift['date'], "%d.%m.%Y").date()
                if start_date <= shift_date <= end_date:
                    relevant_shifts.append(shift)
            except ValueError as e:
                logger.warning(f"⚠️ Skipped shift with invalid date format: {shift.get('date')} - {e}")
                skipped_shifts += 1
                continue
            except Exception as e:
                logger.warning(f"⚠️ Error processing shift: {shift} - {e}")
                skipped_shifts += 1
                continue
        
        logger.info(f"✅ Found {len(relevant_shifts)} relevant shifts, skipped {skipped_shifts}")

        if not relevant_shifts:
            await msg.answer(
                "📅 В ближайшие дни у тебя нет запланированных смен, котик! 🐾\n\n"
                "Хочешь добавить смены? Нажми кнопку *📅 Добавить смену* или *📅 Неделя* для планирования недели! 🌸",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(msg.from_user.id)
            )
            return

        # Сортируем смены по дате
        relevant_shifts.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))

        # Формируем сообщение
        schedule_text = "📅 *Твой график смен:*\n\n"
        
        current_date = None
        for shift in relevant_shifts:
            try:
                shift_date = datetime.strptime(shift['date'], "%d.%m.%Y").date()
                
                # Добавляем заголовок дня
                if shift_date != current_date:
                    day_name = get_day_name(shift_date)
                    date_prefix = "🟢" if shift_date == today else ("🟡" if shift_date == today + timedelta(days=1) else "⚪️")
                    schedule_text += f"\n{date_prefix} *{day_name}, {shift['date']}*\n"
                    current_date = shift_date
                
                # Формируем информацию о смене
                time_info = f"🕐 {shift.get('start', '?')}-{shift.get('end', '?')} ({shift.get('hours', '?')}ч)"
                
                # Добавляем финансовую информацию если есть
                financial_info = ""
                if shift.get('revenue') and str(shift['revenue']).strip() and shift['revenue'] not in ['0', '0.0', '']:
                    try:
                        revenue_val = float(shift['revenue'])
                        if revenue_val > 0:
                            financial_info += f" | 💰 {revenue_val:.0f}₽"
                    except (ValueError, TypeError):
                        pass
                
                if shift.get('tips') and str(shift['tips']).strip() and shift['tips'] not in ['0', '0.0', '']:
                    try:
                        tips_val = float(shift['tips'])
                        if tips_val > 0:
                            financial_info += f" | 💖 {tips_val:.0f}₽"
                    except (ValueError, TypeError):
                        pass
                
                if shift.get('profit') and str(shift['profit']).strip() and shift['profit'] not in ['0', '0.0', '']:
                    try:
                        profit_val = float(shift['profit'])
                        if profit_val > 0:
                            financial_info += f" | 📊 {profit_val:.0f}₽"
                    except (ValueError, TypeError):
                        pass
                
                schedule_text += f"   {time_info}{financial_info}\n"
                
            except Exception as e:
                logger.error(f"❌ Error formatting shift {shift}: {e}")
                continue

        schedule_text += f"\n📊 *Всего смен: {len(relevant_shifts)}*"
        if skipped_shifts > 0:
            schedule_text += f"\n⚠️ *Пропущено: {skipped_shifts}*"
        schedule_text += f"\n🌸 *Отличная работа, котик! Ты справишься!* 💪"

        # Если сообщение слишком длинное, разбиваем на части
        if len(schedule_text) > 4000:
            parts = []
            current_part = ""
            for line in schedule_text.split('\n'):
                if len(current_part + line + '\n') > 4000:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await msg.answer(part, parse_mode="Markdown", reply_markup=get_main_keyboard(msg.from_user.id))
                else:
                    await msg.answer(part, parse_mode="Markdown")
                await asyncio.sleep(0.5)
        else:
            await msg.answer(schedule_text, parse_mode="Markdown", reply_markup=get_main_keyboard(msg.from_user.id))

    except Exception as e:
        logger.error(f"❌ Error showing schedule: {e}", exc_info=True)
        await msg.answer(
            "❌ Не удалось загрузить график смен, котик! 😿\n"
            "Возможно, проблема с данными. Попробуй добавить новую смену или обратись к разработчику! 🐾",
            reply_markup=get_main_keyboard(msg.from_user.id)
        )

def get_day_name(date_obj):
    """Получить название дня недели на русском"""
    try:
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        return days[date_obj.weekday()]
    except Exception as e:
        logger.error(f"Error getting day name for {date_obj}: {e}")
        return "День"

# ДОБАВЛЕНИЕ ГРАФИКА НА НЕДЕЛЮ (доступно всем)
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
        f"📅 **Планирование недели:**\n"
        f"Период: {week_dates[0]} - {week_dates[-1]}\n\n"
        f"Введи время смен в формате:\n"
        f"<начало>-<конец>\n\n"
        f"*Примеры:*\n"
        f"• 9-18\n"
        f"• 10:00-19:00\n"
        f"• 0900-1800\n\n"
        f"Это время будет установлено для всех рабочих дней недели! 🚀",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(Form.waiting_for_week_schedule)

@dp.message(Form.waiting_for_week_schedule)
async def process_week_schedule(msg: types.Message, state: FSMContext):
    """Обработка ввода времени для пакетного добавления"""
    if msg.text == "❌ Отмена":
        await cancel_action(msg, state)
        return
        
    time_input = msg.text.strip()
    
    # Парсим время с улучшенной обработкой разных форматов
    time_parts = await parse_flexible_time(time_input)
    if not time_parts:
        await msg.answer(
            "❌ Неверный формат времени, котик!\n"
            "Используй: начало-конец\n"
            "Пример: 9-18, 10:00-19:00",
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
        confirmation_text += f"✅ *Новые смены ({len(new_shifts)}):*\n"
        for date in new_shifts:
            day_name = get_day_name(datetime.strptime(date, "%d.%m.%Y").date())
            confirmation_text += f"• {day_name}, {date}\n"
    
    if existing_shifts:
        confirmation_text += f"\n⚠️ *Уже существуют ({len(existing_shifts)}):*\n"
        for date in existing_shifts[:3]:  # Показываем только первые 3
            day_name = get_day_name(datetime.strptime(date, "%d.%m.%Y").date())
            confirmation_text += f"• {day_name}, {date}\n"
        if len(existing_shifts) > 3:
            confirmation_text += f"• ... и ещё {len(existing_shifts) - 3}\n"
        
        confirmation_text += "\n*Существующие смены будут перезаписаны!*"
    
    confirmation_text += "\n\n*Добавляем смены на неделю, котик?* 🐾"
    
    await msg.answer(confirmation_text, parse_mode="Markdown", reply_markup=get_week_confirmation_keyboard())
    await state.set_state(Form.waiting_for_week_confirmation)

@dp.message(Form.waiting_for_week_confirmation)
async def process_week_confirmation(msg: types.Message, state: FSMContext):
    """Обработка подтверждения пакетного добавления"""
    # Расширенная проверка ответов для ДА
    yes_responses = ['да', 'yes', 'y', 'д', 'ДА', 'Да', 'дА', 'lf', 'LF', 'Lf', 'конечно', 'ага', 'угу']
    # Расширенная проверка ответов для НЕТ  
    no_responses = ['нет', 'no', 'n', 'н', 'НЕТ', 'Нет', 'нЕТ', 'ytn', 'YTN', 'Ytn', 'не', 'отмена']
    
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in yes_responses:
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
        
        # Перезаписываем существующие смены
        overwritten_count = 0
        for date_str in existing_shifts:
            success = await add_shift(date_str, start_time, end_time, reset_financials=True)
            if success:
                overwritten_count += 1
            await asyncio.sleep(0.1)
        
        # Формируем отчет
        report_text = f"✅ **Планирование недели завершено!** 🎉\n\n"
        report_text += f"📊 *Статистика:*\n"
        report_text += f"• Добавлено смен: {added_count} 🌸\n"
        report_text += f"• Перезаписано: {overwritten_count} ✨\n"
        report_text += f"• Всего обработано: {added_count + overwritten_count} 🐾\n"
        report_text += f"• Время: {start_time}-{end_time} 🕐\n"
        
        if added_count + overwritten_count > 0:
            report_text += f"\n🎉 *Отличная работа! Неделя распланирована!* 🌟\n"
            report_text += f"Теперь можешь посмотреть график в разделе *📅 График*!"
        else:
            report_text += f"\nℹ️ Все смены на эту неделю уже добавлены, умничка! 💖"
        
        await msg.answer(report_text, parse_mode="Markdown", reply_markup=get_main_keyboard(msg.from_user.id))
        
    elif user_response in no_responses:
        await cancel_action(msg, state, "❌ Планирование недели отменено, котик!")
    else:
        await msg.answer(
            "Пожалуйста, ответь *Да* или *Нет*, пушистик! 🌸\n\n"
            "*Примеры ответов:*\n"
            "• Да, конечно, ага, угу ✅\n"  
            "• Нет, не надо, отмена ❌",
            parse_mode="Markdown",
            reply_markup=get_week_confirmation_keyboard()
        )
    
    await state.clear()

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
        
    # Расширенная проверка ответов для ДА
    yes_responses = ['да', 'yes', 'y', 'д', 'ДА', 'Да', 'дА', 'lf', 'LF', 'Lf', 'конечно', 'ага', 'угу']
    # Расширенная проверка ответов для НЕТ  
    no_responses = ['нет', 'no', 'n', 'н', 'НЕТ', 'Нет', 'нЕТ', 'ytn', 'YTN', 'Ytn', 'не', 'отмена']
    
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in yes_responses:
        await msg.answer(
            "Введи время смены в формате:\n"
            "<начало>-<конец>\n\n"
            "Примеры:\n"
            "• 9-18\n"
            "• 10:00-19:00",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Form.waiting_for_start)
    elif user_response in no_responses:
        await cancel_action(msg, state, "❌ Добавление смены отменено, котик!")
    else:
        await msg.answer(
            "Пожалуйста, ответь *Да* или *Нет*, пушистик! 🌸\n\n"
            "*Примеры ответов:*\n"
            "• Да, конечно, ага, угу ✅\n"  
            "• Нет, не надо, отмена ❌",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

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

# Команда для отладки графика
@dp.message(Command("debug_schedule"))
async def debug_schedule_cmd(msg: types.Message):
    """Команда для отладки графика"""
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Эта команда только для администратора")
        return
        
    try:
        all_shifts = await get_all_shifts()
        debug_info = f"🔧 *Отладочная информация:*\n\n"
        debug_info += f"• Всего смен: {len(all_shifts) if all_shifts else 0}\n"
        
        if all_shifts:
            # Покажем первые 3 смены для примера
            for i, shift in enumerate(all_shifts[:3]):
                debug_info += f"\n*Смена {i+1}:*\n"
                for key, value in shift.items():
                    debug_info += f"  {key}: {value}\n"
        
        await msg.answer(debug_info, parse_mode="Markdown")
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка отладки: {e}")

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
