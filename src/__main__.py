import asyncio, os

# pre install
os.system('alembic upgrade heads')

# debugging
# os.system('pip install --upgrade pip')
# os.system('pip install -r requirements.txt')

from aiogram import F
from aiogram.types import Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from bot.config_reader import config
from bot.handlers import commands, callbacks
from bot.middlewares import DbSessionMiddleware
from bot.ui_commands import set_ui_commands
from bot.bot import bot, dp, scheduler
from bot.cron import notifications, cloudflare_sync

F: Message

async def main():
    engine = create_async_engine(url=config.db_url, echo=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    # Setup dispatcher and bind routers to it
    dp.message.filter(F.chat.type == 'private')
    dp.update.middleware(DbSessionMiddleware(session_pool=sessionmaker))
    # Automatically reply to all callbacks
    dp.callback_query.middleware(CallbackAnswerMiddleware())


    # Register handlers
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)

    # Set bot commands in UI
    await set_ui_commands(bot)

    # We connect the scheduler of regular tasks
    scheduler.add_job(notifications, 'cron', hour=8, minute=0, args=(bot, sessionmaker))
    scheduler.add_job(cloudflare_sync, 'cron', hour=7, minute=30, args=(bot, sessionmaker))
    scheduler.start()

    # Run bot
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
