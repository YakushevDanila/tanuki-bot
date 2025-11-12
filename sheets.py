import gspread
from gspread import Worksheet
from gspread.utils import ValueInputOption
import logging
from datetime import datetime, timedelta
import os
import asyncio
import json

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self.initialized = False
        self._initialize()

    def _initialize(self):
        """Initialize Google Sheets connection"""
        try:
            # Get environment variables
            google_credentials = os.getenv('GOOGLE_CREDENTIALS')
            sheet_id = os.getenv('SHEET_ID')
            
            if not google_credentials or not sheet_id:
                logger.error("❌ GOOGLE_CREDENTIALS or SHEET_ID not found in environment")
                return

            # Parse JSON credentials
            creds_dict = json.loads(google_credentials)
            
            # Initialize client
            from google.oauth2.service_account import Credentials
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(sheet_id)
            
            # Try to find worksheet
            try:
                self.worksheet = self.spreadsheet.worksheet('Смены')
                logger.info("✅ Found existing 'Смены' worksheet")
                
                # Проверяем структуру колонок
                self._verify_columns_structure()
                
            except gspread.WorksheetNotFound:
                # Create new worksheet if doesn't exist
                self.worksheet = self.spreadsheet.add_worksheet(title='Смены', rows=1000, cols=7)
                # Add headers with correct structure
                headers = ['Дата', 'Начало', 'Конец', 'Часы', 'Выручка', 'Чаевые', 'Прибыль']
                self.worksheet.update('A1:G1', [headers])
                logger.info("✅ Created new 'Смены' worksheet with correct structure")
            
            self.initialized = True
            logger.info("✅ Google Sheets initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Sheets: {e}")
            self.initialized = False

    def _verify_columns_structure(self):
        """Verify and fix columns structure if needed"""
        try:
            headers = self.worksheet.row_values(1)
            expected_headers = ['Дата', 'Начало', 'Конец', 'Часы', 'Выручка', 'Чаевые', 'Прибыль']
            
            if headers != expected_headers:
                logger.warning(f"⚠️ Column structure mismatch. Current: {headers}")
                logger.info("🔄 Updating column structure...")
                
                # Update headers
                self.worksheet.update('A1:G1', [expected_headers])
                logger.info("✅ Column structure updated successfully")
            else:
                logger.info("✅ Column structure is correct")
                
        except Exception as e:
            logger.error(f"❌ Error verifying column structure: {e}")

    def _calculate_hours(self, start_time, end_time):
        """Calculate hours between start and end time"""
        try:
            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")
            
            # Handle overnight shifts
            if end < start:
                end += timedelta(days=1)
            
            duration = end - start
            hours = duration.total_seconds() / 3600
            return round(hours, 2)
        except Exception as e:
            logger.error(f"❌ Error calculating hours: {e}")
            return 0

    def _calculate_profit(self, hours, revenue, tips):
        """Calculate profit using formula: (hours * 220) + tips + (revenue * 0.015)"""
        try:
            # Convert to numbers
            hours_val = float(hours) if hours else 0
            revenue_val = float(str(revenue).replace(',', '.')) if revenue else 0
            tips_val = float(str(tips).replace(',', '.')) if tips else 0
            
            hourly_rate = 220
            revenue_percentage = 0.015
            
            profit = (hours_val * hourly_rate) + tips_val + (revenue_val * revenue_percentage)
            logger.info(f"💰 Profit calculation: ({hours_val}h * {hourly_rate}) + {tips_val} + ({revenue_val} * {revenue_percentage}) = {profit:.2f}")
            return round(profit, 2)
        except Exception as e:
            logger.error(f"❌ Error calculating profit: {e}")
            return 0

    async def add_shift(self, date_msg, start, end):
        """Add shift to spreadsheet"""
        if not self.initialized:
            logger.error("Google Sheets not initialized")
            return False

        try:
            # Validate date
            date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            # Validate time
            datetime.strptime(start, "%H:%M")
            datetime.strptime(end, "%H:%M")
            
            # Calculate hours
            hours = self._calculate_hours(start, end)
            
            # Find existing record
            try:
                cell = await asyncio.to_thread(self.worksheet.find, formatted_date)
                if cell:
                    # Update existing record
                    row = cell.row
                    await asyncio.to_thread(
                        self.worksheet.update,
                        f'B{row}:D{row}',
                        [[start, end, hours]],  # B: начало, C: конец, D: часы
                        value_input_option=ValueInputOption.user_entered
                    )
                    
                    # Recalculate profit
                    revenue_cell = await asyncio.to_thread(self.worksheet.cell, row, 5)  # E: выручка
                    tips_cell = await asyncio.to_thread(self.worksheet.cell, row, 6)     # F: чаевые
                    
                    revenue = revenue_cell.value if revenue_cell.value else "0"
                    tips = tips_cell.value if tips_cell.value else "0"
                    
                    profit = self._calculate_profit(hours, revenue, tips)
                    await asyncio.to_thread(
                        self.worksheet.update,
                        f'G{row}',  # G: прибыль
                        [[profit]],
                        value_input_option=ValueInputOption.user_entered
                    )
                    
                    logger.info(f"📝 Updated existing shift: {formatted_date}, hours: {hours}, profit: {profit}")
                else:
                    # Add new record
                    profit = self._calculate_profit(hours, 0, 0)
                    new_row = [formatted_date, start, end, hours, '', '', profit]
                    await asyncio.to_thread(
                        self.worksheet.append_row,
                        new_row,
                        value_input_option=ValueInputOption.user_entered
                    )
                    logger.info(f"✅ Added new shift: {formatted_date}, hours: {hours}, profit: {profit}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error in sheet operation: {e}")
                return False
                
        except ValueError as e:
            logger.error(f"❌ Invalid date/time format: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error adding shift: {e}")
            return False

    async def update_value(self, date_msg, field, value):
        """Update value in spreadsheet"""
        if not self.initialized:
            logger.error("Google Sheets not initialized")
            return False

        try:
            date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            # Find date
            cell = await asyncio.to_thread(self.worksheet.find, formatted_date)
            if not cell:
                logger.warning(f"Date not found: {formatted_date}")
                return False

            row = cell.row
            
            # Mapping fields to columns
            column_mapping = {
                'начало': 'B',    # Начало
                'конец': 'C',     # Конец
                'выручка': 'E',   # Выручка
                'чай': 'F'        # Чаевые
            }
            
            column = column_mapping.get(field.lower())
            if not column:
                logger.error(f"Unknown field: {field}")
                return False

            await asyncio.to_thread(
                self.worksheet.update,
                f'{column}{row}',
                [[value]],
                value_input_option=ValueInputOption.user_entered
            )
            
            # Recalculate hours if start or end time changed
            if field.lower() in ['начало', 'конец']:
                start_cell = await asyncio.to_thread(self.worksheet.cell, row, 2)  # B: начало
                end_cell = await asyncio.to_thread(self.worksheet.cell, row, 3)    # C: конец
                
                start_time = start_cell.value if start_cell.value else "00:00"
                end_time = end_cell.value if end_cell.value else "00:00"
                
                hours = self._calculate_hours(start_time, end_time)
                await asyncio.to_thread(
                    self.worksheet.update,
                    f'D{row}',  # D: часы
                    [[hours]],
                    value_input_option=ValueInputOption.user_entered
                )
            
            # Get current values for profit calculation
            hours_cell = await asyncio.to_thread(self.worksheet.cell, row, 4)  # D: часы
            revenue_cell = await asyncio.to_thread(self.worksheet.cell, row, 5) # E: выручка
            tips_cell = await asyncio.to_thread(self.worksheet.cell, row, 6)   # F: чаевые
            
            hours = hours_cell.value if hours_cell.value else "0"
            revenue = revenue_cell.value if revenue_cell.value else "0"
            tips = tips_cell.value if tips_cell.value else "0"
            
            profit = self._calculate_profit(hours, revenue, tips)
            await asyncio.to_thread(
                self.worksheet.update,
                f'G{row}',  # G: прибыль
                [[profit]],
                value_input_option=ValueInputOption.user_entered
            )
            
            logger.info(f"✅ Updated {field} for {formatted_date} and recalculated profit: {profit}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating value: {e}")
            return False

    async def get_profit(self, date_msg):
        """Get profit for date using new formula"""
        if not self.initialized:
            logger.error("Google Sheets not initialized")
            return None

        try:
            date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            cell = await asyncio.to_thread(self.worksheet.find, formatted_date)
            if not cell:
                return None

            row = cell.row
            
            # Get all values from correct columns
            hours_cell = await asyncio.to_thread(self.worksheet.cell, row, 4)  # D: часы
            revenue_cell = await asyncio.to_thread(self.worksheet.cell, row, 5) # E: выручка
            tips_cell = await asyncio.to_thread(self.worksheet.cell, row, 6)   # F: чаевые
            profit_cell = await asyncio.to_thread(self.worksheet.cell, row, 7) # G: прибыль
            
            hours = hours_cell.value if hours_cell.value else "0"
            revenue = revenue_cell.value if revenue_cell.value else "0"
            tips = tips_cell.value if tips_cell.value else "0"
            existing_profit = profit_cell.value if profit_cell.value else "0"
            
            # Calculate profit using new formula
            profit = self._calculate_profit(hours, revenue, tips)
            
            # Update profit cell if different
            try:
                existing_profit_float = float(str(existing_profit).replace(',', '.'))
                if abs(existing_profit_float - profit) > 0.01:
                    await asyncio.to_thread(
                        self.worksheet.update,
                        f'G{row}',  # G: прибыль
                        [[profit]],
                        value_input_option=ValueInputOption.user_entered
                    )
                    logger.info(f"📝 Updated profit calculation for {formatted_date}: {profit}")
            except ValueError:
                # If existing profit is not a number, update it
                await asyncio.to_thread(
                    self.worksheet.update,
                    f'G{row}',
                    [[profit]],
                    value_input_option=ValueInputOption.user_entered
                )
            
            return str(profit)
                
        except Exception as e:
            logger.error(f"❌ Error getting profit: {e}")
            return None

    async def check_shift_exists(self, date_msg):
        """Check if shift exists"""
        if not self.initialized:
            logger.error("Google Sheets not initialized")
            return False

        try:
            date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            cell = await asyncio.to_thread(self.worksheet.find, formatted_date)
            return cell is not None
            
        except Exception as e:
            logger.error(f"❌ Error checking shift existence: {e}")
            return False

# Global instance
sheets_manager = GoogleSheetsManager()

# Functions for backward compatibility
async def add_shift(date_msg, start, end):
    return await sheets_manager.add_shift(date_msg, start, end)

async def update_value(date_msg, field, value):
    return await sheets_manager.update_value(date_msg, field, value)

async def get_profit(date_msg):
    return await sheets_manager.get_profit(date_msg)

async def check_shift_exists(date_msg):
    return await sheets_manager.check_shift_exists(date_msg)
