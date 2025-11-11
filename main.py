from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from datetime import datetime, date as dt
import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Функция очистки ввода от временных меток
def clean_user_input(text):
    """
    Очищает пользовательский ввод от временных меток и лишних данных
    Возвращает только первую часть до пробела
    """
    if not text:
        return ""
    
    # Разделяем по пробелам и берем первую часть
    parts = text.strip().split()
    if parts:
        return parts[0]
    return ""

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

# ВРЕМЕННОЕ ХРАНИЛИЩЕ ДАННЫХ (в памяти)
temp_storage = {}

# ЗАГЛУШКИ ДЛЯ GOOGLE SHEETS
logger.info("🔧 Using stub functions - bot working without Google Sheets")

async def add_shift(date_msg, start, end):
    """Добавляет смену во временное хранилище"""
    try:
        clean_date = clean_user_input(date_msg)
        temp_storage[clean_date] = {
            'start': clean_user_input(start),
            'end': clean_user_input(end),
            'revenue': '0',
            'tips': '0'
        }
        logger.info(f"📅 [STUB] Shift added: {clean_date} {start}-{end}")
        logger.info(f"📊 Current storage: {list(temp_storage.keys())}")
        return True
    except Exception as e:
        logger.error(f"❌ Error in add_shift: {e}")
        return False

async def update_value(date_msg, field, value):
    """Обновляет значение во временном хранилище"""
    try:
        clean_date = clean_user_input(date_msg)
        logger.info(f"🔍 Looking for date: {clean_date} in storage: {list(temp_storage.keys())}")
        
        if clean_date not in temp_storage:
            logger.warning(f"❌ Date not found: {clean_date}")
            return False
        
        field_mapping = {
            'выручка': 'revenue',
            'чай': 'tips',
            'начало': 'start', 
            'конец': 'end'
        }
        
        field_key = field_mapping.get(field.lower())
        if not field_key:
            logger.error(f"❌ Unknown field: {field}")
            return False
        
        temp_storage[clean_date][field_key] = clean_user_input(value)
        logger.info(f"📝 [STUB] Updated: {clean_date} {field} = {value}")
        logger.info(f"📊 Current data for {clean_date}: {temp_storage[clean_date]}")
        return True
    except Exception as e:
        logger.error(f"❌ Error in update_value: {e}")
        return False

async def get_profit(date_msg):
    """Рассчитывает прибыль из временного хранилища"""
    try:
        clean_date = clean_user_input(date_msg)
        logger.info(f"🔍 Looking for profit data for: {clean_date} in {list(temp_storage.keys())}")
        
        if clean_date not in temp_storage:
            logger.warning(f"❌ Date not found for profit: {clean_date}")
            return None
        
        data = temp_storage[clean_date]
        revenue_str = data.get('revenue', '0').replace(',', '.')
        tips_str = data.get('tips', '0').replace(',', '.')
        
        logger.info(f"💰 Raw data - revenue: '{revenue_str}', tips: '{tips_str}'")
        
        # Преобразуем в числа
        try:
            revenue = float(revenue_str) if revenue_str else 0
            tips = float(tips_str) if tips_str else 0
        except ValueError as e:
            logger.error(f"❌ Number conversion error: {e}")
            revenue = 0
            tips = 0
        
        profit = revenue + tips
        logger.info(f"✅ Calculated profit: {profit}")
        return str(profit)
    except Exception as e:
        logger.error(f"❌ Error in get_profit: {e}")
        return "0"

async def check_shift_exists(date_msg):
    """Проверяет существование смены во временном хранилище"""
    try:
        clean_date = clean_user_input(date_msg)
        exists = clean_date in temp_storage
        logger.info(f"🔍 Check shift exists {clean_date}: {exists}")
        return exists
    except Exception as e:
        logger.error(f"❌ Error in check_shift_exists: {e}")
        return False

# ВРЕМЕННО ОТКЛЮЧАЕМ ПРОВЕРКУ ДОСТУПА
def check_access(message: types.Message):
    logger.info(f"🔓 Access granted for user: {message.from_user.id}")
    return True

@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    if not check_access(msg): return
    text = (
        "Привет! 🌸\n"
        "Вот что я умею:\n"
        "/add_shift — добавить дату и время смены\n"
        "/revenue — ввести выручку за день\n"
        "/tips — добавить сумму чаевых 💰\n"
        "/edit — изменить данные\n"
        "/profit — узнать прибыль за день\n"
        "/myid — показать мой ID\n"
        "/help — показать это сообщение\n"
        "\n"
        "⚠️ Режим тестирования: данные сохраняются в памяти"
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

# ADD SHIFT FLOW
@dp.message(Command("add_shift"))
async def add_shift_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату смены (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_date)

@dp.message(Form.waiting_for_date)
async def process_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем валидность даты
    try:
        datetime.strptime(clean_date, "%d.%m.%Y").date()
    except ValueError:
        await msg.answer("❌ Неверный формат даты. Используй ДД.ММ.ГГГГ (например, 15.03.2024)")
        await state.clear()
        return
    
    # Проверяем, существует ли уже смена с этой датой
    exists = await check_shift_exists(clean_date)
    if exists:
        await state.update_data(date=clean_date)
        await msg.answer(f"❌ Смена на дату {clean_date} уже существует!\n"
                        "Хочешь перезаписать ее? (да/нет)")
        await state.set_state(Form.waiting_for_overwrite_confirm)
    else:
        await state.update_data(date=clean_date)
        await msg.answer("Введи время начала смены (чч:мм):")
        await state.set_state(Form.waiting_for_start)

# Обработчик подтверждения перезаписи
@dp.message(Form.waiting_for_overwrite_confirm)
async def process_overwrite_confirm(msg: types.Message, state: FSMContext):
    user_response = clean_user_input(msg.text).lower()
    
    if user_response in ['да', 'yes', 'y', 'д']:
        await msg.answer("Введи время начала смены (чч:мм):")
        await state.set_state(Form.waiting_for_start)
    elif user_response in ['нет', 'no', 'n', 'н']:
        await msg.answer("❌ Добавление смены отменено. Используй /add_shift чтобы начать заново.")
        await state.clear()
    else:
        await msg.answer("Пожалуйста, ответь 'да' или 'нет'")

@dp.message(Form.waiting_for_start)
async def process_start(msg: types.Message, state: FSMContext):
    clean_start = clean_user_input(msg.text)
    
    # Проверяем валидность времени
    try:
        datetime.strptime(clean_start, "%H:%M")
    except ValueError:
        await msg.answer("❌ Неверный формат времени. Используй чч:мм (например, 09:00)")
        await state.clear()
        return
        
    await state.update_data(start=clean_start)
    await msg.answer("Теперь время окончания (чч:мм):")
    await state.set_state(Form.waiting_for_end)

@dp.message(Form.waiting_for_end)
async def process_end(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['date']
    start = user_data['start']
    end = clean_user_input(msg.text)
    
    # Проверяем валидность времени окончания
    try:
        datetime.strptime(end, "%H:%M")
    except ValueError:
        await msg.answer("❌ Неверный формат времени. Используй чч:мм (например, 18:00)")
        await state.clear()
        return
    
    success = await add_shift(date_msg, start, end)
    if success:
        await msg.answer(f"✅ Смена {date_msg} ({start}-{end}) добавлена 🩷")
    else:
        await msg.answer("❌ Ошибка при добавлении смены")
    
    await state.clear()

# REVENUE FLOW
@dp.message(Command("revenue"))
async def revenue_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_revenue_date)

@dp.message(Form.waiting_for_revenue_date)
async def process_revenue_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена. Сначала добавь смену через /add_shift")
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
        await msg.answer("❌ Неверный формат числа. Введи только цифры (например: 5000)")
        await state.clear()
        return
    
    success = await update_value(date_msg, "выручка", rev)
    if success:
        await msg.answer(f"✅ Выручка {rev}₽ обновлена для даты {date_msg} 💰✨")
    else:
        await msg.answer("❌ Не удалось обновить выручку")
    
    await state.clear()

# TIPS FLOW
@dp.message(Command("tips"))
async def tips_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_tips_date)

@dp.message(Form.waiting_for_tips_date)
async def process_tips_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена. Сначала добавь смену через /add_shift")
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
        await msg.answer("❌ Неверный формат числа. Введи только цифры (например: 500)")
        await state.clear()
        return
    
    success = await update_value(date_msg, "чай", tips_amount)
    if success:
        await msg.answer(f"✅ Чаевые {tips_amount}₽ добавлены для даты {date_msg} ☕️💖")
    else:
        await msg.answer("❌ Не удалось добавить чаевые")
    
    await state.clear()

# EDIT FLOW
@dp.message(Command("edit"))
async def edit_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Укажи дату (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_edit_date)

@dp.message(Form.waiting_for_edit_date)
async def process_edit_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена. Сначала добавь смену через /add_shift")
        await state.clear()
        return
        
    await state.update_data(edit_date=clean_date)
    await msg.answer("Что редактируем? (чай, начало, конец, выручка)")
    await state.set_state(Form.waiting_for_edit_field)

@dp.message(Form.waiting_for_edit_field)
async def process_edit_field(msg: types.Message, state: FSMContext):
    field = clean_user_input(msg.text).lower()
    if field not in ["чай", "начало", "конец", "выручка"]:
        await msg.answer("❌ Такого параметра нет. Используй: чай, начало, конец, выручка")
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
        await msg.answer(f"✅ {field} изменен на {value} для даты {date_msg} 🩷")
    else:
        await msg.answer("❌ Ошибка: не удалось сохранить изменения")
    
    await state.clear()

# PROFIT FLOW
@dp.message(Command("profit"))
async def profit_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_profit_date)

@dp.message(Form.waiting_for_profit_date)
async def process_profit_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    
    # Проверяем валидность даты
    try:
        day = datetime.strptime(clean_date, "%d.%m.%Y").date()
        if day > dt.today():
            await msg.answer("❌ Этот день ещё не наступил 🐾")
            await state.clear()
            return
    except ValueError:
        await msg.answer("❌ Неверный формат даты. Используй ДД.ММ.ГГГГ")
        await state.clear()
        return

    # Проверяем существование смены
    exists = await check_shift_exists(clean_date)
    if not exists:
        await msg.answer(f"❌ Смена на дату {clean_date} не найдена. Сначала добавь смену через /add_shift")
        await state.clear()
        return

    profit_value = await get_profit(clean_date)
    if profit_value is None:
        await msg.answer("❌ Нет данных о прибыли на эту дату 😿")
        await state.clear()
        return

    try:
        profit_float = float(profit_value.replace(",", "."))
    except ValueError:
        profit_float = 0

    if profit_float < 4000:
        text = f"📊 Твоя прибыль за {clean_date}: {profit_float:.2f}₽.\nНе расстраивайся, котик 🐾 — ты отлично поработала!"
    elif 4000 <= profit_float <= 6000:
        text = f"📊 Твоя прибыль за {clean_date}: {profit_float:.2f}₽.\nНеплохая смена 😺 — беги радовать себя чем-то вкусным!"
    else:
        text = f"📊 Твоя прибыль за {clean_date}: {profit_float:.2f}₽.\nТы просто суперстар 🌟 — ещё немного, и миллион твой!"
    
    await msg.answer(text)
    await state.clear()

@dp.message()
async def echo(message: types.Message):
    """Обработка любых других сообщений"""
    if not check_access(message): return
    await message.answer("Не понимаю эту команду 😿\nИспользуй /help для списка команд")

async def main():
    try:
        logger.info("🚀 Starting bot with temporary storage...")
        
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

if __name__ == "__main__":
    print("🟢 Bot starting with temporary storage...")
    asyncio.run(main())
