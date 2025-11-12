from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
import logging
from config import TIMEZONE, USER_ID
import sheets

logger = logging.getLogger(__name__)

async def check_incomplete_shifts():
    """Проверяем смены без выручки или чаевых за последние 7 дней"""
    try:
        if not USER_ID:
            return []

        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).date()
        
        # Ищем смены за последние 7 дней без выручки или чаевых
        incomplete_shifts = []
        
        for days_ago in range(1, 8):  # Проверяем последние 7 дней (исключая сегодня)
            check_date = today - timedelta(days=days_ago)
            date_str = check_date.strftime("%d.%m.%Y")
            
            # Проверяем существование смены
            if await sheets.has_shift_today(date_str):
                # Получаем полные данные смены
                shift_data = await sheets.get_shift_data(date_str)
                if shift_data:
                    revenue = shift_data.get('revenue', '')
                    tips = shift_data.get('tips', '')
                    
                    # Проверяем, заполнены ли выручка и чаевые
                    is_revenue_filled = revenue and str(revenue).strip() != '' and str(revenue) != '0'
                    is_tips_filled = tips and str(tips).strip() != '' and str(tips) != '0'
                    
                    if not is_revenue_filled or not is_tips_filled:
                        incomplete_shifts.append({
                            'date': date_str,
                            'revenue': revenue if is_revenue_filled else None,
                            'tips': tips if is_tips_filled else None,
                            'missing_data': []
                        })
                        
                        if not is_revenue_filled:
                            incomplete_shifts[-1]['missing_data'].append('выручка')
                        if not is_tips_filled:
                            incomplete_shifts[-1]['missing_data'].append('чаевые')
        
        return incomplete_shifts
        
    except Exception as e:
        logger.error(f"❌ Error checking incomplete shifts: {e}")
        return []

async def send_shift_reminder(bot):
    """Напоминание о смене в 10:00 с проверкой незаполненных данных"""
    try:
        if not USER_ID:
            logger.warning("USER_ID not set - skipping reminder")
            return

        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        today_str = today.strftime("%d.%m.%Y")
        
        logger.info(f"🔔 Checking shift for {today_str}...")

        messages = []

        # Проверяем сегодняшнюю смену
        if await sheets.has_shift_today(today_str):
            messages.append(
                f"🌞 Доброе утро, котофей!\n"
                f"Сегодня у тебя смена ({today_str}) 💪\n"
                f"Не забудь взять хорошее настроение и вкусно покушать🫡"
            )
            logger.info(f"✅ Found today's shift: {today_str}")
        else:
            logger.info(f"ℹ️ No shift found for {today_str}")

        # Проверяем незаполненные данные за предыдущие смены
        incomplete_shifts = await check_incomplete_shifts()
        
        if incomplete_shifts:
            # Группируем по датам и показываем только последние 3
            incomplete_dates = []
            for shift in incomplete_shifts[:3]:
                date_str = shift['date']
                missing = " и ".join(shift['missing_data'])
                incomplete_dates.append(f"• {date_str} (нет {missing})")
            
            messages.append(
                f"📝 Внимание!"
                f"Котику пришло напоминание о незаполненных данных:\n"
                f"Обнаружены смены без выручки или чаевых:\n"
                f"{chr(10).join(incomplete_dates)}\n"
                f"\nПожалуйста, заполни данные с помощью команд:\n"
                f"• /revenue — ввести выручку\n"
                f"• /tips — ввести чаевые"
            )
            logger.info(f"⚠️ Found {len(incomplete_shifts)} incomplete shifts")

        if messages:
            message_text = "\n\n".join(messages)
            await bot.send_message(USER_ID, message_text)
            logger.info("✅ Morning reminder sent successfully")
        else:
            logger.info("ℹ️ No reminders to send")
            
    except Exception as e:
        logger.error(f"❌ Error sending shift reminder: {e}")

async def send_evening_prompt(bot):
    """Напоминание вечером в день смены"""
    try:
        if not USER_ID:
            logger.warning("USER_ID not set - skipping evening prompt")
            return

        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).strftime("%d.%m.%Y")
        
        logger.info(f"🔔 Checking evening shift for {today}...")

        if await sheets.has_shift_today(today):
            await bot.send_message(
                USER_ID,
                f"🌙 Привет, работничек!\n"
                f"Надеюсь день прошел отлично!"
                f"Смена {today} подоходит к концу (или уже закончилась) 💫\n"
                f"Пожалуйста, введи данные за день — выручку и чаевые ☕️💰\n"
                f"Используй команды:\n"
                f"→ /revenue — чтобы ввести выручку\n"
                f"→ /tips — чтобы ввести сумму чаевых"
                f"Твой любимый <3"
            )
            logger.info(f"✅ Sent evening reminder for {today}")
        else:
            logger.info(f"ℹ️ No shift found for {today} - no evening reminder sent")
            
    except Exception as e:
        logger.error(f"❌ Error sending evening prompt: {e}")

async def send_weekly_summary(bot):
    """Еженедельная статистика в воскресенье вечером"""
    try:
        if not USER_ID:
            return

        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        
        # Только по воскресеньям в 20:00
        if now.weekday() != 6:  # 6 = воскресенье
            return

        # Получаем даты за последнюю неделю
        end_date = now.date()
        start_date = end_date - timedelta(days=7)
        
        # Форматируем даты для поиска в таблице
        start_str = start_date.strftime("%d.%m.%Y")
        end_str = end_date.strftime("%d.%m.%Y")
        
        # Проверяем незаполненные данные за неделю
        incomplete_shifts = await check_incomplete_shifts()
        weekly_incomplete = [s for s in incomplete_shifts 
                           if start_date <= datetime.strptime(s['date'], "%d.%m.%Y").date() <= end_date]
        
        message_text = (
            f"📊 Воскресный вечер — в церковь не ходим, но самое время подвести итоги недели!\n"
            f"Период: {start_str} - {end_str}\n"
        )
        
        if weekly_incomplete:
            incomplete_dates = []
            for shift in weekly_incomplete:
                date_str = shift['date']
                missing = " и ".join(shift['missing_data'])
                incomplete_dates.append(f"• {date_str} (нет {missing})")
            
            message_text += (
                f"\n⚠️ Котик, обрати внимание:\n"
                f"Есть незаполненные смены:\n"
                f"{chr(10).join(incomplete_dates)}\n"
                f"Не забудь внести данные до начала новой недели!"
            )
        else:
            message_text += "\n🎉 Все смены за неделю заполнены! Отличная работа!"
        
        message_text += "\n\nИспользуй /stats чтобы посмотреть статистику за эту неделю 📈"
        
        await bot.send_message(USER_ID, message_text)
        logger.info(f"✅ Sent weekly summary reminder with {len(weekly_incomplete)} incomplete shifts")
            
    except Exception as e:
        logger.error(f"❌ Error sending weekly summary: {e}")

async def send_data_completion_reminder(bot):
    """Отдельное напоминание о незаполненных данных (12:00)"""
    try:
        if not USER_ID:
            return

        incomplete_shifts = await check_incomplete_shifts()
        
        if incomplete_shifts:
            # Группируем по датам и показываем до 5
            incomplete_dates = []
            for shift in incomplete_shifts[:5]:
                date_str = shift['date']
                missing = " и ".join(shift['missing_data'])
                incomplete_dates.append(f"• {date_str} (нет {missing})")
            
            await bot.send_message(
                USER_ID,
                f"📋 Напоминание о заполнении данных:\n"
                f"У тебя есть {len(incomplete_shifts)} смен без выручки или чаевых.\n"
                f"Последние даты:\n"
                f"{chr(10).join(incomplete_dates)}\n"
                f"\nКоманды для заполнения:\n"
                f"• /revenue — ввести выручку\n"
                f"• /tips — ввести чаевые\n"
                f"• /edit — изменить другие данные"
            )
            logger.info(f"✅ Sent data completion reminder for {len(incomplete_shifts)} shifts")
        else:
            logger.info("ℹ️ No incomplete shifts - no data completion reminder sent")
            
    except Exception as e:
        logger.error(f"❌ Error sending data completion reminder: {e}")

def setup_scheduler(bot):
    """Настройка планировщика уведомлений"""
    if not USER_ID:
        logger.warning("❌ USER_ID not set - notifications disabled")
        return None

    try:
        tz = pytz.timezone(TIMEZONE)
        scheduler = AsyncIOScheduler(timezone=tz)

        # 10:00 — напоминание о смене + проверка незаполненных данных
        scheduler.add_job(
            send_shift_reminder, 
            "cron", 
            hour=10, 
            minute=0, 
            args=[bot],
            id="morning_reminder"
        )

        # 12:00 — отдельное напоминание о незаполненных данных
        scheduler.add_job(
            send_data_completion_reminder,
            "cron",
            hour=12,
            minute=0,
            args=[bot],
            id="data_completion_reminder"
        )

        # 22:00 — напоминание ввести данные
        scheduler.add_job(
            send_evening_prompt, 
            "cron", 
            hour=22, 
            minute=0, 
            args=[bot],
            id="evening_prompt"
        )

        # 20:00 по воскресеньям — недельная статистика
        scheduler.add_job(
            send_weekly_summary,
            "cron",
            day_of_week="sun",
            hour=20,
            minute=0,
            args=[bot],
            id="weekly_summary"
        )

        scheduler.start()
        logger.info("✅ Scheduler started with 4 jobs:")
        logger.info("   - 10:00 Morning shift reminder + incomplete data check")
        logger.info("   - 12:00 Data completion reminder") 
        logger.info("   - 22:00 Evening data prompt")
        logger.info("   - 20:00 Sunday weekly summary")
        
        return scheduler
        
    except Exception as e:
        logger.error(f"❌ Failed to setup scheduler: {e}")
        return None
