from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config_reader import config

bot = Bot(config.bot_token.get_secret_value(), parse_mode='HTML')
dp = Dispatcher()
scheduler = AsyncIOScheduler()
