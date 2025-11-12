from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
import logging
from config import TIMEZONE, USER_ID
import sheets

logger = logging.getLogger(__name__)

async def send_shift_reminder(bot):
    """Напоминание о смене в 10:00"""
    try:
        if not USER_ID:
            logger.warning("USER_ID not set - skipping reminder")
            return

        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).strftime("%d.%m.%Y")
        
        logger.info(f"🔔 Checking shift for {today}...")

        if await sheets.has_shift_today(today):
            await bot.send_message(
                USER_ID,
                f"🌞 Доброе утро!\n"
                f"Сегодня у тебя смена ({today}) 💪\n"
                f"Не забудь взять хорошее настроение и кофеек ☕️"
            )
            logger.info(f"✅ Sent morning reminder for {today}")
        else:
            logger.info(f"ℹ️ No shift found for {today} - no reminder sent")
            
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
                f"🌙 Привет!\n"
                f"Смена {today} подошла к концу (или скоро подойдет) 💫\n"
                f"Пожалуйста, введи данные за день — выручку и чаевые ☕️💰\n"
                f"Используй команды:\n"
                f"→ /revenue — чтобы ввести выручку\n"
                f"→ /tips — чтобы ввести сумму чаевых"
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
        
        # Здесь можно добавить логику для получения статистики за неделю
        # Пока просто отправляем напоминание
        await bot.send_message(
            USER_ID,
            f"📊 Воскресный вечер — время подвести итоги недели!\n"
            f"Период: {start_str} - {end_str}\n"
            f"Используй /stats чтобы посмотреть статистику за эту неделю 📈"
        )
        logger.info(f"✅ Sent weekly summary reminder")
            
    except Exception as e:
        logger.error(f"❌ Error sending weekly summary: {e}")

def setup_scheduler(bot):
    """Настройка планировщика уведомлений"""
    if not USER_ID:
        logger.warning("❌ USER_ID not set - notifications disabled")
        return None

    try:
        tz = pytz.timezone(TIMEZONE)
        scheduler = AsyncIOScheduler(timezone=tz)

        # 10:00 — напоминание о смене
        scheduler.add_job(
            send_shift_reminder, 
            "cron", 
            hour=10, 
            minute=0, 
            args=[bot],
            id="morning_reminder"
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
        logger.info("✅ Scheduler started with 3 jobs:")
        logger.info("   - 10:00 Morning shift reminder")
        logger.info("   - 22:00 Evening data prompt") 
        logger.info("   - 20:00 Sunday weekly summary")
        
        return scheduler
        
    except Exception as e:
        logger.error(f"❌ Failed to setup scheduler: {e}")
        return None
