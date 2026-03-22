from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config_reader import config

bot = Bot(config.BOT_TOKEN.get_secret_value())
dp = Dispatcher()
scheduler = AsyncIOScheduler()
