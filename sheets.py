import gspread
from gspread import Worksheet
from gspread.utils import ValueInputOption
import logging
from datetime import datetime
import os
import asyncio

logger = logging.getLogger(__name__)

# Настройка доступа к Google Sheets
def get_google_sheets_client():
    # Получаем данные из переменных окружения
    google_credentials = os.getenv('GOOGLE_CREDENTIALS')
    if not google_credentials:
        logger.error("GOOGLE_CREDENTIALS not found in environment")
        return None

    try:
        # Если переменная окружения содержит JSON, то используем из строки
        from google.oauth2.service_account import Credentials
        import json
        creds_dict = json.loads(google_credentials)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        logger.error(f"Failed to create Google Sheets client: {e}")
        return None

# Инициализация клиента и рабочих листов
client = get_google_sheets_client()
if client:
    try:
        spreadsheet = client.open_by_key(os.getenv('SHEET_ID'))
        shifts_worksheet = spreadsheet.worksheet('Смены')
        logger.info("✅ Google Sheets connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to open worksheet: {e}")
        shifts_worksheet = None
else:
    shifts_worksheet = None

async def check_shift_exists(date_msg):
    """
    Проверяет, существует ли уже смена с указанной датой
    """
    if not shifts_worksheet:
        logger.error("Shifts worksheet not initialized")
        return False

    try:
        # Приводим дату к правильному формату для поиска
        date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        # Ищем дату в первом столбце (столбец с датами)
        cell = await asyncio.to_thread(shifts_worksheet.find, formatted_date)
        
        logger.info(f"🔍 Checked shift existence for {formatted_date}: {'exists' if cell else 'not found'}")
        return cell is not None
        
    except ValueError as e:
        logger.error(f"❌ Invalid date format for {date_msg}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking shift existence for {date_msg}: {e}")
        return False

async def add_shift(date_msg, start, end):
    """
    Добавляет смену в таблицу
    """
    if not shifts_worksheet:
        logger.error("Shifts worksheet not initialized")
        return False

    try:
        # Проверяем валидность даты
        date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        # Проверяем валидность времени
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
        
        # Ищем, есть ли уже смена с этой датой
        existing_cell = await asyncio.to_thread(shifts_worksheet.find, formatted_date)
        
        if existing_cell:
            # Обновляем существующую запись
            row_index = existing_cell.row
            await asyncio.to_thread(
                shifts_worksheet.update,
                f'B{row_index}:C{row_index}',
                [[start, end]],
                value_input_option=ValueInputOption.user_entered
            )
            logger.info(f"📝 Updated existing shift: {formatted_date} {start}-{end}")
        else:
            # Добавляем новую запись
            new_row = [formatted_date, start, end, '', '']  # Дата, начало, конец, выручка, чай
            await asyncio.to_thread(
                shifts_worksheet.append_row,
                new_row,
                value_input_option=ValueInputOption.user_entered
            )
            logger.info(f"✅ Added new shift: {formatted_date} {start}-{end}")
        
        return True
        
    except ValueError as e:
        logger.error(f"❌ Invalid date/time format: {date_msg} {start}-{end}. Error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error adding shift {date_msg} {start}-{end}: {e}")
        return False

async def update_value(date_msg, field, value):
    """
    Обновляет значение в указанной дате и поле (чай, выручка, начало, конец)
    """
    if not shifts_worksheet:
        logger.error("Shifts worksheet not initialized")
        return False

    try:
        # Приводим дату к правильному формату для поиска
        date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        # Ищем дату в первом столбце
        cell = await asyncio.to_thread(shifts_worksheet.find, formatted_date)
        if not cell:
            logger.warning(f"📅 Date not found: {formatted_date}")
            return False

        row_index = cell.row
        
        # Определяем столбец по полю
        column_mapping = {
            'начало': 'B',
            'конец': 'C', 
            'выручка': 'D',
            'чай': 'E'
        }
        
        column_letter = column_mapping.get(field)
        if not column_letter:
            logger.error(f"❌ Unknown field: {field}")
            return False

        # Обновляем ячейку
        await asyncio.to_thread(
            shifts_worksheet.update,
            f'{column_letter}{row_index}',
            value,
            value_input_option=ValueInputOption.user_entered
        )
        
        logger.info(f"📝 Updated {field} for {formatted_date}: {value}")
        return True
        
    except ValueError as e:
        logger.error(f"❌ Invalid date format for {date_msg}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error updating {field} for {date_msg}: {e}")
        return False

async def get_profit(date_msg):
    """
    Получает прибыль для указанной даты
    В данном примере возвращаем выручку как прибыль для простоты
    В реальном приложении здесь должна быть логика расчета прибыли
    """
    if not shifts_worksheet:
        logger.error("Shifts worksheet not initialized")
        return None

    try:
        # Приводим дату к правильному формату для поиска
        date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        # Ищем дату в первом столбце
        cell = await asyncio.to_thread(shifts_worksheet.find, formatted_date)
        if not cell:
            logger.warning(f"📅 Date not found for profit: {formatted_date}")
            return None

        row_index = cell.row
        
        # Получаем выручку (столбец D)
        revenue_cell = await asyncio.to_thread(shifts_worksheet.cell, row_index, 4)  # Столбец D = индекс 4
        revenue = revenue_cell.value if revenue_cell.value else "0"
        
        # Получаем чаевые (столбец E)  
        tips_cell = await asyncio.to_thread(shifts_worksheet.cell, row_index, 5)  # Столбец E = индекс 5
        tips = tips_cell.value if tips_cell.value else "0"
        
        # Расчет прибыли (выручка + чаевые)
        try:
            revenue_float = float(str(revenue).replace(',', '.'))
            tips_float = float(str(tips).replace(',', '.'))
            profit = revenue_float + tips_float
        except ValueError:
            logger.error(f"❌ Invalid number format: revenue={revenue}, tips={tips}")
            return "0"
        
        logger.info(f"💰 Profit for {formatted_date}: {profit} (revenue: {revenue}, tips: {tips})")
        return str(profit)
        
    except ValueError as e:
        logger.error(f"❌ Invalid date format for {date_msg}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error getting profit for {date_msg}: {e}")
        return None

# Ленивая инициализация при импорте
logger.info("Sheets module loaded (lazy initialization)")
