import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN
from handlers import router
from utils import send_weekly_report
from database import db

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Подключаем router
    dp.include_router(router)
    
    # Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week=4, hour=18, minute=0),
        args=[bot]
    )
    scheduler.start()
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        await bot.session.close()
        if db.connection:
            db.connection.close()
        scheduler.shutdown()

if __name__ == '__main__':
    asyncio.run(main())