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

    def _parse_number(self, value):
        """Parse number from string with various formats"""
        if not value or str(value).strip() == '':
            return 0.0
        
        try:
            # Remove spaces and replace commas with dots
            cleaned = str(value).replace(' ', '').replace(',', '.')
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Could not parse number: {value}")
            return 0.0

    def _calculate_profit(self, hours, revenue, tips):
        """Calculate profit using formula: (hours * 220) + tips + (revenue * 0.015)"""
        try:
            # Parse numbers safely
            hours_val = self._parse_number(hours)
            revenue_val = self._parse_number(revenue)
            tips_val = self._parse_number(tips)
            
            hourly_rate = 220
            revenue_percentage = 0.015
            
            profit = (hours_val * hourly_rate) + tips_val + (revenue_val * revenue_percentage)
            logger.info(f"💰 Profit calculation: ({hours_val}h * {hourly_rate}) + {tips_val} + ({revenue_val} * {revenue_percentage}) = {profit:.2f}")
            return round(profit, 2)
        except Exception as e:
            logger.error(f"❌ Error calculating profit: {e}")
            logger.error(f"❌ Values: hours='{hours}', revenue='{revenue}', tips='{tips}'")
            return 0

    async def _get_row_values(self, row):
        """Get all values from a row with proper error handling"""
        try:
            # Get the entire row to ensure we have all values
            row_data = await asyncio.to_thread(self.worksheet.row_values, row)
            
            # Ensure we have at least 7 columns
            while len(row_data) < 7:
                row_data.append('')
            
            return {
                'date': row_data[0] if len(row_data) > 0 else '',
                'start': row_data[1] if len(row_data) > 1 else '',
                'end': row_data[2] if len(row_data) > 2 else '',
                'hours': row_data[3] if len(row_data) > 3 else '',
                'revenue': row_data[4] if len(row_data) > 4 else '',
                'tips': row_data[5] if len(row_data) > 5 else '',
                'profit': row_data[6] if len(row_data) > 6 else ''
            }
        except Exception as e:
            logger.error(f"❌ Error getting row values: {e}")
            return {
                'date': '', 'start': '', 'end': '', 'hours': '', 
                'revenue': '', 'tips': '', 'profit': ''
            }

    async def add_shift(self, date_msg, start, end, reset_financials=False):
        """Add shift to spreadsheet with optional financial data reset"""
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
                    
                    if reset_financials:
                        # Полностью перезаписываем строку с обнулением финансовых данных
                        new_row = [formatted_date, start, end, hours, '', '', '']
                        await asyncio.to_thread(
                            self.worksheet.update,
                            f'A{row}:G{row}',
                            [new_row],
                            value_input_option=ValueInputOption.user_entered
                        )
                        logger.info(f"📝 Updated existing shift with financial reset: {formatted_date}, hours: {hours}")
                    else:
                        # Обновляем только время и часы
                        await asyncio.to_thread(
                            self.worksheet.update,
                            f'B{row}:D{row}',
                            [[start, end, hours]],
                            value_input_option=ValueInputOption.user_entered
                        )
                        
                        # Пересчитываем прибыль на основе существующих данных
                        row_values = await self._get_row_values(row)
                        
                        revenue = row_values['revenue'] if row_values['revenue'] else "0"
                        tips = row_values['tips'] if row_values['tips'] else "0"
                        
                        profit = self._calculate_profit(hours, revenue, tips)
                        await asyncio.to_thread(
                            self.worksheet.update,
                            f'G{row}',  # G: прибыль
                            [[profit]],
                            value_input_option=ValueInputOption.user_entered
                        )
                        logger.info(f"📝 Updated existing shift: {formatted_date}, hours: {hours}, profit: {profit}")
                else:
                    # Add new record - для новой смены рассчитываем базовую прибыль только от часов
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
        """Update value in spreadsheet with proper profit calculation"""
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
            
            # Get current values BEFORE update
            row_values = await self._get_row_values(row)
            logger.info(f"📊 Current values before update: {row_values}")
            
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

            # Update the field
            await asyncio.to_thread(
                self.worksheet.update,
                f'{column}{row}',
                [[value]],
                value_input_option=ValueInputOption.user_entered
            )
            
            # Get updated values for profit calculation
            await asyncio.sleep(0.5)  # Small delay to ensure update is processed
            updated_values = await self._get_row_values(row)
            
            # Use the updated value for the field we just changed
            if field.lower() == 'выручка':
                revenue = value
                tips = updated_values['tips']
            elif field.lower() == 'чай':
                revenue = updated_values['revenue']
                tips = value
            else:
                revenue = updated_values['revenue']
                tips = updated_values['tips']
            
            # Always use current hours from the row
            hours = updated_values['hours']
            
            logger.info(f"📊 Values for profit calculation: hours='{hours}', revenue='{revenue}', tips='{tips}'")
            
            # Calculate profit with current values
            profit = self._calculate_profit(hours, revenue, tips)
            
            # Update profit cell
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
        """Get profit for date using current data"""
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
            
            # Get all values using our helper function
            row_values = await self._get_row_values(row)
            
            hours = row_values['hours']
            revenue = row_values['revenue']
            tips = row_values['tips']
            
            logger.info(f"📊 Values for profit get: hours='{hours}', revenue='{revenue}', tips='{tips}'")
            
            # Calculate profit using current formula and values
            profit = self._calculate_profit(hours, revenue, tips)
            
            logger.info(f"📊 Profit calculation result: {profit}")
            
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

    async def delete_shift(self, date_msg):
        """Delete shift by date"""
        if not self.initialized:
            logger.error("Google Sheets not initialized")
            return False

        try:
            date_obj = datetime.strptime(date_msg, "%d.%m.%Y").date()
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            cell = await asyncio.to_thread(self.worksheet.find, formatted_date)
            if not cell:
                logger.warning(f"Shift not found for deletion: {formatted_date}")
                return False

            row = cell.row
            
            # Delete the entire row
            await asyncio.to_thread(self.worksheet.delete_rows, row)
            logger.info(f"✅ Deleted shift: {formatted_date}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting shift: {e}")
            return False

    async def get_shift_data(self, date_msg):
        """Get complete shift data for a specific date"""
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
            row_values = await self._get_row_values(row)
            
            return {
                'date': row_values['date'],
                'start': row_values['start'],
                'end': row_values['end'],
                'hours': row_values['hours'],
                'revenue': row_values['revenue'],
                'tips': row_values['tips'],
                'profit': row_values['profit'],
                'is_complete': bool(row_values['revenue'] and row_values['tips'] and 
                                  str(row_values['revenue']).strip() != '' and 
                                  str(row_values['tips']).strip() != '')
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting shift data: {e}")
            return None

    async def get_all_shifts(self):
        """Get all shifts from spreadsheet for schedule view"""
        if not self.initialized:
            logger.error("Google Sheets not initialized")
            return []

        try:
            # Get all records except header
            records = await asyncio.to_thread(self.worksheet.get_all_records)
            shifts = []
            
            for record in records:
                if record.get('Дата'):  # Only include rows with date
                    shifts.append({
                        'date': record.get('Дата', ''),
                        'start': record.get('Начало', ''),
                        'end': record.get('Конец', ''),
                        'hours': record.get('Часы', 0),
                        'revenue': record.get('Выручка', 0),
                        'tips': record.get('Чаевые', 0),
                        'profit': record.get('Прибыль', 0)
                    })
            
            logger.info(f"📊 Retrieved {len(shifts)} shifts from Google Sheets")
            return shifts
            
        except Exception as e:
            logger.error(f"❌ Error getting all shifts: {e}")
            return []

    async def has_shift_today(self, date_msg):
        """Check if shift exists for given date (for notifications)"""
        return await self.check_shift_exists(date_msg)

# Global instance
sheets_manager = GoogleSheetsManager()

# Functions for backward compatibility
async def add_shift(date_msg, start, end, reset_financials=False):
    return await sheets_manager.add_shift(date_msg, start, end, reset_financials)

async def update_value(date_msg, field, value):
    return await sheets_manager.update_value(date_msg, field, value)

async def get_profit(date_msg):
    return await sheets_manager.get_profit(date_msg)

async def check_shift_exists(date_msg):
    return await sheets_manager.check_shift_exists(date_msg)

# New function for deleting shifts
async def delete_shift(date_msg):
    return await sheets_manager.delete_shift(date_msg)

# Function for getting shift data
async def get_shift_data(date_msg):
    return await sheets_manager.get_shift_data(date_msg)

# Function for getting all shifts (for schedule)
async def get_all_shifts():
    return await sheets_manager.get_all_shifts()

# Function for notifications
async def has_shift_today(date_msg):
    """Check if shift exists for today (for notifications)"""
    return await sheets_manager.has_shift_today(date_msg)
