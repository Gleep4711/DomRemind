from aiogram import Bot
from aiogram.types import BotCommandScopeAllPrivateChats, BotCommand


async def set_ui_commands(bot: Bot):
    """
    Sets bot commands in UI
    :param bot: Bot instance
    """
    commands = [
        BotCommand(command="start", description="Base info"),
        BotCommand(command="add_domain", description="Add a new domain"),
        BotCommand(command="get_domains", description="View all domains")
    ]
    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeAllPrivateChats()
    )
