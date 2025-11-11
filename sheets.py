# -*- coding: utf-8 -*-
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
    if delta.total_seconds() < 0:  # åñëè êîíåö ïîñëå ïîëóíî÷è
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
    """Ïåðåñ÷èòàòü ÷àñû, ïðèáûëü, íåäåëþ è ìåñÿö"""
    headers = sheet.row_values(1)
    row = find_row_by_date(date)
    if not row:
        return

    # Ïîëó÷àåì òåêóùèå äàííûå ïî ñòðîêå
    values = sheet.row_values(row)
    cols = {h: i + 1 for i, h in enumerate(headers)}

    start = values[cols["íà÷àëî"] - 1] if "íà÷àëî" in cols and len(values) >= cols["íà÷àëî"] else ""
    end = values[cols["êîíåö"] - 1] if "êîíåö" in cols and len(values) >= cols["êîíåö"] else ""
    tips = values[cols["÷àé"] - 1] if "÷àé" in cols and len(values) >= cols["÷àé"] else ""
    revenue = values[cols["âûðó÷êà"] - 1] if "âûðó÷êà" in cols and len(values) >= cols["âûðó÷êà"] else ""

    hours = calculate_hours(start, end)
    profit = calculate_profit(tips, hours, revenue)
    week, month = get_week_and_month(date)

    # Çàïèñûâàåì ðåçóëüòàòû â òàáëèöó
    if "÷àñû" in cols:
        sheet.update_cell(row, cols["÷àñû"], hours)
    if "ïðèáûëü" in cols:
        sheet.update_cell(row, cols["ïðèáûëü"], profit)
    if "íåäåëÿ" in cols:
        sheet.update_cell(row, cols["íåäåëÿ"], week)
    if "ìåñÿö" in cols:
        sheet.update_cell(row, cols["ìåñÿö"], month)


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
    profit = sheet.cell(row, 7).value  # ñòîëáåö "ïðèáûëü"
    return profit


def has_shift_today(today_str):
    data = sheet.col_values(1)
    return today_str in data

