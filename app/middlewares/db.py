from datetime import datetime, timedelta
from typing import Callable, Awaitable, Dict, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, User
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.models import Users
from app.config_reader import config
from app.bot import bot, scheduler
from app.cron import new_user_notification


class CustomMessage(Message):
    from_user: User


class CustomObject(TelegramObject):
    message: CustomMessage


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: CustomObject,
            data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data['role'] = 'guest'
            data['state'] = ''
            if event.message:
                sql_user = await session.execute(select(Users).filter(Users.id == event.message.from_user.id))
                user = sql_user.first()
                if user:
                    if user[0].role == 'guest':
                        return
                    data['role'] = user[0].role
                    data['state'] = user[0].state
                else:
                    user_data = Users(
                        id=event.message.from_user.id,
                        role='admin' if event.message.from_user.id == config.admin else 'guest',
                        is_bot=event.message.from_user.is_bot,
                        first_name=event.message.from_user.first_name,
                        last_name=event.message.from_user.last_name,
                        username=event.message.from_user.username,
                        is_premium=event.message.from_user.is_premium,
                        language_code=event.message.from_user.language_code,
                        added_to_attachment_menu=event.message.from_user.added_to_attachment_menu,
                        can_join_groups=event.message.from_user.can_join_groups,
                        can_read_all_group_messages=event.message.from_user.can_read_all_group_messages,
                        supports_inline_queries=event.message.from_user.supports_inline_queries,
                    )

                    session.add(user_data)
                    await session.commit()

                    await bot.send_message(chat_id=config.admin, text='New user <code>{}</code> {} {}'.format(
                        event.message.from_user.id,
                        event.message.from_user.first_name,
                        event.message.from_user.last_name
                    ))

                    # scheduler.add_job(
                    #     new_user_notification,
                    #     'date',
                    #     run_date=datetime.now() + timedelta(seconds=5),
                    #     args=(
                    #         bot,
                    #         'New user <code>{}</code> <a href="tg://user?id={}">{} {}</a>'.format(
                    #             event.message.from_user.id,
                    #             event.message.from_user.id,
                    #             event.message.from_user.first_name,
                    #             event.message.from_user.last_name
                    #         )
                    #     )
                    # )

            data['session'] = session
            return await handler(event, data)
