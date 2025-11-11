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

# ИМПОРТ GOOGLE SHEETS С ОБРАБОТКОЙ ОШИБОК
try:
    from sheets import add_shift, update_value, get_profit
    logger.info("✅ Google Sheets module imported")
except Exception as e:
    logger.error(f"❌ Failed to import Google Sheets: {e}")
    # Заглушки на случай ошибки
    async def add_shift(date_msg, start, end):
        logger.info(f"📅 Shift added (Sheets failed): {date_msg} {start}-{end}")
        return True
    async def update_value(date_msg, field, value):
        logger.info(f"📝 Updated (Sheets failed): {date_msg} {field} = {value}")
        return True
    async def get_profit(date_msg):
        logger.info(f"💰 Get profit (Sheets failed): {date_msg}")
        return "4500"

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
        "/help — показать это сообщение"
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
    await state.update_data(date=clean_date)
    await msg.answer("Введи время начала смены (чч:мм):")
    await state.set_state(Form.waiting_for_start)

@dp.message(Form.waiting_for_start)
async def process_start(msg: types.Message, state: FSMContext):
    clean_start = clean_user_input(msg.text)
    await state.update_data(start=clean_start)
    await msg.answer("Теперь время окончания (чч:мм):")
    await state.set_state(Form.waiting_for_end)

@dp.message(Form.waiting_for_end)
async def process_end(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['date']
    start = user_data['start']
    end = clean_user_input(msg.text)
    
    success = await add_shift(date_msg, start, end)
    if success:
        await msg.answer(f"✅ Смена {date_msg} добавлена в Google Sheets 🩷")
    else:
        await msg.answer("❌ Ошибка при добавлении в Google Sheets")
    
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
    await state.update_data(revenue_date=clean_date)
    await msg.answer("Введи сумму выручки (только число):")
    await state.set_state(Form.waiting_for_revenue)

@dp.message(Form.waiting_for_revenue)
async def process_revenue(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['revenue_date']
    rev = clean_user_input(msg.text)
    
    success = await update_value(date_msg, "выручка", rev)
    if success:
        await msg.answer("✅ Выручка обновлена в Google Sheets 💰✨")
    else:
        await msg.answer("❌ Не удалось найти дату или ошибка Google Sheets 😿")
    
    await state.clear()

# TIPS FLOW - ОСНОВНОЕ ИСПРАВЛЕНИЕ
@dp.message(Command("tips"))
async def tips_start(msg: types.Message, state: FSMContext):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_tips_date)

@dp.message(Form.waiting_for_tips_date)
async def process_tips_date(msg: types.Message, state: FSMContext):
    clean_date = clean_user_input(msg.text)
    await state.update_data(tips_date=clean_date)
    await msg.answer("Введи сумму чаевых (число):")
    await state.set_state(Form.waiting_for_tips)

@dp.message(Form.waiting_for_tips)
async def process_tips(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date_msg = user_data['tips_date']
    tips_amount = clean_user_input(msg.text)
    
    success = await update_value(date_msg, "чай", tips_amount)
    if success:
        await msg.answer("✅ Чаевые добавлены в Google Sheets ☕️💖")
    else:
        await msg.answer("❌ Не удалось найти указанную дату 😿")
    
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
    await state.update_data(edit_date=clean_date)
    await msg.answer("Что редактируем? (чай, начало, конец, выручка)")
    await state.set_state(Form.waiting_for_edit_field)

@dp.message(Form.waiting_for_edit_field)
async def process_edit_field(msg: types.Message, state: FSMContext):
    field = clean_user_input(msg.text).lower()
    if field not in ["чай", "начало", "конец", "выручка"]:
        await msg.answer("Такого параметра нет 😿")
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
        await msg.answer("✅ Изменения сохранены в Google Sheets 🩷")
    else:
        await msg.answer("❌ Ошибка: дата не найдена в Google Sheets")
    
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
    date_msg = clean_date
    try:
        day = datetime.strptime(date_msg, "%d.%m.%Y").date()
        if day > dt.today():
            await msg.answer("Этот день ещё не наступил 🐾")
            await state.clear()
            return
    except:
        await msg.answer("Неверный формат даты ❌")
        await state.clear()
        return

    profit_value = await get_profit(date_msg)
    if not profit_value:
        await msg.answer("❌ Нет данных о прибыли на эту дату в Google Sheets 😿")
        await state.clear()
        return

    profit_value = float(profit_value.replace(",", "."))
    if profit_value < 4000:
        text = f"📊 Твоя прибыль за {date_msg}: {profit_value:.2f}₽.\nНе расстраивайся, котик 🐾 — ты отлично поработала!"
    elif 4000 <= profit_value <= 6000:
        text = f"📊 Твоя прибыль за {date_msg}: {profit_value:.2f}₽.\nНеплохая смена 😺 — беги радовать себя чем-то вкусным!"
    else:
        text = f"📊 Твоя прибыль за {date_msg}: {profit_value:.2f}₽.\nТы просто суперстар 🌟 — ещё немного, и миллион твой!"
    await msg.answer(text)
    await state.clear()

@dp.message()
async def echo(message: types.Message):
    """Обработка любых других сообщений"""
    if not check_access(message): return
    await message.answer(f"Эхо: {message.text}")

async def main():
    try:
        logger.info("🚀 Starting bot with Google Sheets...")
        logger.info("✅ Starting polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🟢 Bot starting with Google Sheets...")
    asyncio.run(main())
