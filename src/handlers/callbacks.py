from contextlib import suppress

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common import ChangeUserRole, DeleteDomain, CloudFlareTokens, CloudFlareDeleteTokens
from bot.db.models import Users, Domains, Settings
from bot.keyboards import remove_keyboard, confirmation_keyboard
from bot.bot import bot
from bot.config_reader import config

router = Router(name="callbacks-router")

@router.callback_query(ChangeUserRole.filter())
async def change_user_role_callback(callback: CallbackQuery, session: AsyncSession):
    text = callback.data.split(':')
    answer = 'Success'
    if text[1] == 'canceled':
        answer = 'Canceled'
    else:
        sql_user = await session.execute(select(Users).filter(Users.id == callback.message.chat.id))
        user = sql_user.first()
        if not user or user[0].role != 'admin':
            answer = 'access denied'
        else:
            id, role = text[1].split('@')
            if id == config.admin:
                answer = 'access denied'
            else:
                sql = await session.execute(select(Users).filter(Users.id == int(id)))
                if sql.first():
                    await session.execute(update(Users).filter(Users.id == int(id)).values(role = role))
                    await session.commit()
                    msg = ''
                    if role == 'guest':
                        msg = 'Something went wrong, you can no longer add new domains'
                    if role == 'user':
                        msg = 'You can now add new domains\nUse the /add_domain command'
                    if role == 'admin':
                        msg = 'Now you are Administrator, you can manage users\nUse /get_users command'

                    await bot.send_message(int(id), msg)
                else:
                    answer = 'User not found'

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(answer, reply_markup=remove_keyboard())

@router.callback_query(DeleteDomain.filter(F.data == 'canceled'))
async def change_user_role_callback(callback: CallbackQuery):
    with suppress(TelegramBadRequest):
        await callback.message.edit_text('Cancel', reply_markup=remove_keyboard())

@router.callback_query(DeleteDomain.filter())
async def change_user_role_callback(callback: CallbackQuery, session: AsyncSession):
    text = callback.data.split(':')
    id, domain = text[1].split('@')
    domain = domain.replace(';', ':')

    await session.execute(delete(Domains).filter(Domains.user_id == int(id), Domains.domain == domain))
    await session.commit()

    with suppress(TelegramBadRequest):
        await callback.message.edit_text('🫡', reply_markup=remove_keyboard())

@router.callback_query(CloudFlareTokens.filter())
async def remove_cloudflare_token(callback: CallbackQuery, session: AsyncSession):
    token = (await session.execute(select(Settings).filter(Settings.id == int(callback.data[3:]), Settings.user_id == callback.from_user.id, Settings.name == 'token', Settings.group == 'cloudflare'))).scalar()
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(callback.message.text, reply_markup=remove_keyboard())
        if token:
            await callback.message.answer('Are you sure that you want to remove the token? <pre>{}</pre>'.format(token.param[:4] + "*" * (len(token.param) - 4)), reply_markup=confirmation_keyboard(token.id))
        else:
            await callback.message.answer('Token not found')

@router.callback_query(CloudFlareDeleteTokens.filter())
async def remove_cloudflare_token(callback: CallbackQuery, session: AsyncSession):
    id = int(callback.data[4:])
    token = (await session.execute(select(Settings).filter(Settings.id == id, Settings.user_id == callback.from_user.id, Settings.name == 'token', Settings.group == 'cloudflare'))).scalar()
    with suppress(TelegramBadRequest):
        if token:
            await session.execute(delete(Settings).filter(Settings.id == token.id))
            await session.commit()
            await callback.message.edit_text('🫡', reply_markup=remove_keyboard())
        else:
            await callback.message.edit_text(callback.message.text, reply_markup=remove_keyboard())
            await callback.message.answer('Token not found')
