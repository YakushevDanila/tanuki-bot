import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from config import SPREADSHEET_ID, CREDENTIALS_FILE

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1


def find_row_by_date(date_str):
    data = sheet.col_values(1)
    for i, v in enumerate(data):
        if v.strip() == date_str:
            return i + 1
    return None


def parse_time(t_str):
    try:
        return datetime.strptime(t_str.strip(), "%H:%M")
    except Exception:
        return None


def calculate_hours(start, end):
    start_t = parse_time(start)
    end_t = parse_time(end)
    if not start_t or not end_t:
        return ""
    delta = end_t - start_t
    if delta.total_seconds() < 0:  # если конец после полуночи
        delta += timedelta(days=1)
    hours = round(delta.total_seconds() / 3600, 2)
    return hours


def calculate_profit(tips, hours, revenue):
    try:
        tips = float(str(tips).replace(",", ".") or 0)
        hours = float(str(hours).replace(",", ".") or 0)
        revenue = float(str(revenue).replace(",", ".") or 0)
        profit = tips + (hours * 220) + (revenue * 0.015)
        return round(profit, 2)
    except Exception:
        return ""


def get_week_and_month(date_str):
    try:
        d = datetime.strptime(date_str, "%d.%m.%Y")
        week = d.isocalendar()[1]
        month = d.strftime("%B")
        return week, month
    except Exception:
        return "", ""


def recalc_row(date):
    """Пересчитать часы, прибыль, неделю и месяц"""
    headers = sheet.row_values(1)
    row = find_row_by_date(date)
    if not row:
        return

    # Получаем текущие данные по строке
    values = sheet.row_values(row)
    cols = {h: i + 1 for i, h in enumerate(headers)}

    start = values[cols["начало"] - 1] if "начало" in cols and len(values) >= cols["начало"] else ""
    end = values[cols["конец"] - 1] if "конец" in cols and len(values) >= cols["конец"] else ""
    tips = values[cols["чай"] - 1] if "чай" in cols and len(values) >= cols["чай"] else ""
    revenue = values[cols["выручка"] - 1] if "выручка" in cols and len(values) >= cols["выручка"] else ""

    hours = calculate_hours(start, end)
    profit = calculate_profit(tips, hours, revenue)
    week, month = get_week_and_month(date)

    # Записываем результаты в таблицу
    if "часы" in cols:
        sheet.update_cell(row, cols["часы"], hours)
    if "прибыль" in cols:
        sheet.update_cell(row, cols["прибыль"], profit)
    if "неделя" in cols:
        sheet.update_cell(row, cols["неделя"], week)
    if "месяц" in cols:
        sheet.update_cell(row, cols["месяц"], month)


def add_shift(date, start, end):
    row = [date, start, end, "", "", "", "", "", ""]
    sheet.append_row(row)
    recalc_row(date)


def update_value(date, field, value):
    headers = sheet.row_values(1)
    if field not in headers:
        return False
    col = headers.index(field) + 1
    row = find_row_by_date(date)
    if not row:
        return False
    sheet.update_cell(row, col, value)
    recalc_row(date)
    return True


def get_profit(date):
    row = find_row_by_date(date)
    if not row:
        return None
    profit = sheet.cell(row, 7).value  # столбец "прибыль"
    return profit


def has_shift_today(today_str):
    data = sheet.col_values(1)
    return today_str in data
