# -*- coding: utf-8 -*-
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import json

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Global variable for sheet - will be initialized on first use
_sheet = None

def get_sheets_client():
    """Initialize Google Sheets client using environment variables"""
    try:
        # ТОЛЬКО переменные окружения - убираем fallback на файл
        creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            print("❌ GOOGLE_SHEETS_CREDENTIALS not found in environment")
            return None
            
        print("✅ Using environment variable for credentials")
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        
        client = gspread.authorize(creds)
        print("✅ Google Sheets client authorized successfully")
        return client
    except Exception as e:
        print(f"❌ Error initializing Google Sheets client: {e}")
        return None

def get_sheet():
    """Get the spreadsheet sheet with lazy initialization"""
    global _sheet
    if _sheet is not None:
        return _sheet
        
    try:
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            print("❌ SPREADSHEET_ID not found in environment")
            return None
        
        client = get_sheets_client()
        if not client:
            return None
            
        print(f"✅ Opening spreadsheet with ID: {SPREADSHEET_ID}")
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        _sheet = spreadsheet.sheet1
        print("✅ Sheet accessed successfully")
        return _sheet
    except Exception as e:
        print(f"❌ Error accessing spreadsheet: {e}")
        return None

def ensure_sheet():
    """Ensure sheet is initialized"""
    return get_sheet() is not None

def find_row_by_date(date_str):
    """Find row by date string"""
    sheet = get_sheet()
    if not sheet:
        print("Sheet not available in find_row_by_date")
        return None
    try:
        data = sheet.col_values(1)
        for i, v in enumerate(data):
            if v.strip() == date_str:
                return i + 1
        return None
    except Exception as e:
        print(f"Error finding row: {e}")
        return None

def calculate_hours(start, end):
    """Calculate hours between start and end time"""
    try:
        start_t = datetime.strptime(start.strip(), "%H:%M")
        end_t = datetime.strptime(end.strip(), "%H:%M")
        
        # Handle overnight shifts
        delta = end_t - start_t
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        
        hours = round(delta.total_seconds() / 3600, 2)
        return hours
    except Exception:
        return ""

def calculate_profit(tips, hours, revenue):
    """Calculate total profit"""
    try:
        tips = float(str(tips).replace(",", ".") or 0)
        hours = float(str(hours).replace(",", ".") or 0)
        revenue = float(str(revenue).replace(",", ".") or 0)
        
        # Profit formula: tips + (hours * 220) + (revenue * 0.015)
        profit = tips + (hours * 220) + (revenue * 0.015)
        return round(profit, 2)
    except Exception:
        return ""

def recalc_row(date):
    """Recalculate hours and profit for a row"""
    sheet = get_sheet()
    if not sheet:
        print("Sheet not available in recalc_row")
        return
        
    try:
        headers = sheet.row_values(1)
        row_num = find_row_by_date(date)
        if not row_num:
            return

        values = sheet.row_values(row_num)
        
        # Map headers to column numbers
        cols = {}
        for i, header in enumerate(headers):
            cols[header.lower()] = i + 1

        # Extract values
        start = values[cols.get("начало", 0) - 1] if cols.get("начало") and len(values) >= cols["начало"] else ""
        end = values[cols.get("конец", 0) - 1] if cols.get("конец") and len(values) >= cols["конец"] else ""
        tips = values[cols.get("чай", 0) - 1] if cols.get("чай") and len(values) >= cols["чай"] else ""
        revenue = values[cols.get("выручка", 0) - 1] if cols.get("выручка") and len(values) >= cols["выручка"] else ""

        # Calculate new values
        hours = calculate_hours(start, end)
        profit = calculate_profit(tips, hours, revenue)

        # Update cells
       
