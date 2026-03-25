import asyncio

from aiogram import F
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config_reader import config
from app.handlers import callbacks, commands_cf, commands_domains, commands_users_echo
from app.middlewares import DbSessionMiddleware
from app.ui_commands import set_ui_commands
from app.bot import bot, dp, scheduler
from app.services.cron import notifications, cloudflare_sync
from app.services.iana_sync import sync_iana_zones

async def main():
    engine = create_async_engine(url=str(config.DB_URL))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    # Setup dispatcher and bind routers to it
    dp.message.filter(F.chat.type == 'private')
    dp.update.middleware(DbSessionMiddleware(session_pool=sessionmaker))
    # Automatically reply to all callbacks
    dp.callback_query.middleware(CallbackAnswerMiddleware())


    # Register handlers
    dp.include_router(commands_domains.router)
    dp.include_router(commands_cf.router)
    dp.include_router(commands_users_echo.router)
    dp.include_router(callbacks.router)

    # Set bot commands in UI
    await set_ui_commands(bot)

    # We connect the scheduler of regular tasks
    scheduler.add_job(notifications, 'cron', hour=8, minute=0, args=(bot, sessionmaker), id='notifications')
    scheduler.add_job(cloudflare_sync, 'cron', hour=7, minute=30, args=(bot, sessionmaker), id='cloudflare_sync')
    scheduler.add_job(sync_iana_zones, 'cron', day_of_week='fri', hour=3, minute=0, args=(bot, sessionmaker), id='iana_sync')
    scheduler.start()

    await bot.send_message(chat_id=config.ADMIN, text='Bot is starting...')

    # Run bot
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
