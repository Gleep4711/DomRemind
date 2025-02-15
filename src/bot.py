from aiogram import Bot, Dispatcher
from bot.config_reader import config
from apscheduler.schedulers.asyncio import AsyncIOScheduler

bot = Bot(config.bot_token.get_secret_value(), parse_mode='HTML')
dp = Dispatcher()
scheduler = AsyncIOScheduler()
