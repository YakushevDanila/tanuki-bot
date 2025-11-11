from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
from datetime import datetime, date as dt

from config import BOT_TOKEN, ALLOWED_USER_ID
import sheets
from scheduler import setup_scheduler

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def check_access(message: types.Message):
    return message.from_user.id == ALLOWED_USER_ID


@dp.message(Command("привет"))
async def greet(msg: types.Message):
    if not check_access(msg): return
    text = (
        "Привет, Аня 🌸\n"
        "Вот что я умею:\n"
        "/добавить_смену — добавить дату и время смены\n"
        "/выручка — ввести выручку за день\n"
        "/чай — добавить сумму чаевых 💰\n"
        "/редактировать_график — изменить данные\n"
        "/прибыль — узнать прибыль за день"
    )
    await msg.answer(text)


@dp.message(Command("добавить_смену"))
async def add_shift(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату смены (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Введи время начала смены (чч:мм):")
    start = (await bot.wait_for("message")).text.strip()

    await msg.answer("Теперь время окончания (чч:мм):")
    end = (await bot.wait_for("message")).text.strip()

    sheets.add_shift(date_msg, start, end)
    await msg.answer(f"Смена {date_msg} добавлена 🩷")


@dp.message(Command("выручка"))
async def revenue(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Введи сумму выручки (только число):")
    rev = (await bot.wait_for("message")).text.strip()

    if sheets.update_value(date_msg, "выручка", rev):
        await msg.answer("Выручка обновлена 💰✨")
    else:
        await msg.answer("Не удалось найти дату 😿")


@dp.message(Command("чай"))
async def tips(msg: types.Message):
    if not check_access(msg): return
    await msg.answer("Введи дату (ДД.ММ.ГГГГ):")
    date_msg = (await bot.wait_for("message")).text.strip()

    await msg.answer("Введи сумму чаевых (число):")
    tips = (await bot.wait_for("message")).text.strip()

    if sheets.update_value(date_msg, "чай", tips):
        await msg.answer("Чаевые добавлены ☕️💖")
    else:
        await msg.answer("Не удалось найти указанную дату 😿")


@dp.message(Command("редактировать_график"))
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

    if sheets.update_value(date_msg, field, value):
        await msg.answer("Изменения сохранены 🩷")
    else:
        await msg.answer("Ошибка: дата не найдена ❌")


@dp.message(Command("прибыль"))
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

    profit = sheets.get_profit(date_msg)
    if not profit:
        await msg.answer("Нет данных о прибыли на эту дату 😿")
        return

    profit = float(profit.replace(",", "."))
    if profit < 4000:
        text = f"Твоя прибыль за {date_msg}: {profit:.2f}₽.\nНе расстраивайся, котик 🐾 — ты отлично поработала!"
    elif 4000 <= profit <= 6000:
        text = f"Твоя прибыль за {date_msg}: {profit:.2f}₽.\nНеплохая смена 😺 — беги радовать себя чем-то вкусным!"
    else:
        text = f"Твоя прибыль за {date_msg}: {profit:.2f}₽.\nТы просто суперстар 🌟 — ещё немного, и миллион твой!"
    await msg.answer(text)


async def main():
    setup_scheduler(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())