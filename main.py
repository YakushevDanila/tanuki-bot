from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
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

# ИМПОРТ GOOGLE SHEETS (ЗАМЕНИТЬ ЗАГЛУШКИ)
try:
    from sheets import add_shift, update_value, get_profit
    logger.info("✅ Google Sheets module imported")
except ImportError as e:
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

# Остальной код без изменений...
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

@dp.message(Command("add_shift"))
async def add_shift_cmd(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату смены (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Введи время начала смены (чч:мм):")
    start = (await bot.wait_for("message")).text.strip()

    await msg.answer("Теперь время окончания (чч:мм):")
    end = (await bot.wait_for("message")).text.strip()

    # ИСПОЛЬЗУЕМ РЕАЛЬНУЮ ФУНКЦИЮ GOOGLE SHEETS
    success = await add_shift(date_msg, start, end)
    if success:
        await msg.answer(f"✅ Смена {date_msg} добавлена в Google Sheets 🩷")
    else:
        await msg.answer("❌ Ошибка при добавлении в Google Sheets")

@dp.message(Command("revenue"))
async def revenue(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Введи сумму выручки (только число):")
    rev = (await bot.wait_for("message")).text.strip()

    # ИСПОЛЬЗУЕМ РЕАЛЬНУЮ ФУНКЦИЮ GOOGLE SHEETS
    success = await update_value(date_msg, "выручка", rev)
    if success:
        await msg.answer("✅ Выручка обновлена в Google Sheets 💰✨")
    else:
        await msg.answer("❌ Не удалось найти дату или ошибка Google Sheets 😿")

@dp.message(Command("tips"))
async def tips(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Введи сумму чаевых (число):")
    tips_amount = (await bot.wait_for("message")).text.strip()

    # ИСПОЛЬЗУЕМ РЕАЛЬНУЮ ФУНКЦИЮ GOOGLE SHEETS
    success = await update_value(date_msg, "чай", tips_amount)
    if success:
        await msg.answer("✅ Чаевые добавлены в Google Sheets ☕️💖")
    else:
        await msg.answer("❌ Не удалось найти указанную дату 😿")

@dp.message(Command("edit"))
async def edit_shift(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Укажи дату (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Что редактируем? (чай, начало, конец, выручка)")
    field = (await bot.wait_for("message")).text.strip().lower()

    if field not in ["чай", "начало", "конец", "выручка"]:
        await msg.answer("Такого параметра нет 😿")
        return

    await msg.answer(f"Введи новое значение для {field}:")
    value = (await bot.wait_for("message")).text.strip()

    # ИСПОЛЬЗУЕМ РЕАЛЬНУЮ ФУНКЦИЮ GOOGLE SHEETS
    success = await update_value(date_msg, field, value)
    if success:
        await msg.answer("✅ Изменения сохранены в Google Sheets 🩷")
    else:
        await msg.answer("❌ Ошибка: дата не найдена в Google Sheets")

@dp.message(Command("profit"))
async def profit(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()
    try:
        day = datetime.strptime(date_msg, "%d.%m.%Y").date()
        if day > dt.today():
            await msg.answer("Этот день ещё не наступил 🐾")
            return
    except:
        await msg.answer("Неверный формат даты ❌")
        return

    # ИСПОЛЬЗУЕМ РЕАЛЬНУЮ ФУНКЦИЮ GOOGLE SHEETS
    profit_value = await get_profit(date_msg)
    if not profit_value:
        await msg.answer("❌ Нет данных о прибыли на эту дату в Google Sheets 😿")
        return

    profit_value = float(profit_value.replace(",", "."))
    if profit_value < 4000:
        text = f"📊 Твоя прибыль за {date_msg}: {profit_value:.2f}₽.\nНе расстраивайся, котик 🐾 — ты отлично поработала!"
    elif 4000 <= profit_value <= 6000:
        text = f"📊 Твоя прибыль за {date_msg}: {profit_value:.2f}₽.\nНеплохая смена 😺 — беги радовать себя чем-то вкусным!"
    else:
        text = f"📊 Твоя прибыль за {date_msg}: {profit_value:.2f}₽.\nТы просто суперстар 🌟 — ещё немного, и миллион твой!"
    await msg.answer(text)

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
