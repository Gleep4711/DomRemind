from contextlib import suppress
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import ChangeUserRole, DeleteDomain, CloudFlareTokens, CloudFlareDeleteTokens
from app.db.repositories import domains as domain_repo
from app.db.repositories import settings as settings_repo
from app.db.repositories import users as user_repo
from app.keyboards import remove_keyboard, confirmation_keyboard
from app.bot import bot
from app.config_reader import config
from app.services.domain_service import remove_domain

router = Router(name="callbacks-router")

@router.callback_query(ChangeUserRole.filter())
async def change_user_role_callback(callback: CallbackQuery, session: AsyncSession):
    if not callback.data:
        return
    if not isinstance(callback.message, Message):
        return

    text = str(callback.data).split(':')
    answer = 'Success'
    if text[1] == 'canceled':
        answer = 'Canceled'
    else:
        requester = await user_repo.get_user(session, callback.message.chat.id)
        if not requester or requester.role != 'admin':
            answer = 'access denied'
        else:
            action = text[1]
            if action.startswith('r@'):
                _, id, role = action.split('@', maxsplit=2)
                target_id = int(id)
                action_type = 'role'
            elif action.startswith('bd@'):
                _, id = action.split('@', maxsplit=1)
                target_id = int(id)
                role = ''
                action_type = 'block_day'
            elif action.startswith('bp@'):
                _, id = action.split('@', maxsplit=1)
                target_id = int(id)
                role = ''
                action_type = 'block_permanent'
            elif action.startswith('u@'):
                _, id = action.split('@', maxsplit=1)
                target_id = int(id)
                role = ''
                action_type = 'unblock'
            # Backward compatibility for already-rendered keyboards
            elif action.startswith('role:'):
                id, role = action.removeprefix('role:').split('@')
                target_id = int(id)
                action_type = 'role'
            elif action.startswith('block_day:'):
                target_id = int(action.removeprefix('block_day:'))
                role = ''
                action_type = 'block_day'
            elif action.startswith('block_permanent:'):
                target_id = int(action.removeprefix('block_permanent:'))
                role = ''
                action_type = 'block_permanent'
            elif action.startswith('unblock:'):
                target_id = int(action.removeprefix('unblock:'))
                role = ''
                action_type = 'unblock'
            else:
                answer = 'invalid action'
                with suppress(TelegramBadRequest):
                    await callback.message.edit_text(answer, reply_markup=remove_keyboard())
                return

            if target_id == config.ADMIN:
                answer = 'access denied'
            else:
                target_user = await user_repo.get_user(session, target_id)
                if target_user:
                    msg = ''
                    if action_type == 'role':
                        await user_repo.update_user_role(session, target_id, role)
                        if role == 'guest':
                            msg = 'Your role has been changed to guest. You still have access to domains, but Cloudflare features are unavailable.'
                        if role == 'user':
                            msg = 'You can now use domains and Cloudflare features\nUse the /add_domain or /add_cloud_token command'
                        if role == 'admin':
                            msg = 'Now you are Administrator, you can manage users\nUse /get_users command'
                    elif action_type == 'block_day':
                        await user_repo.set_user_blocked_until(
                            session,
                            target_id,
                            datetime.utcnow() + timedelta(days=1),
                        )
                        msg = 'You are blocked for 1 day. Domain deletion and notifications are still available.'
                        answer = 'User blocked for 1 day'
                    elif action_type == 'block_permanent':
                        await user_repo.set_user_blocked_until(
                            session,
                            target_id,
                            user_repo.PERMANENT_BLOCK_UNTIL,
                        )
                        msg = 'You are blocked permanently. Domain deletion and notifications are still available.'
                        answer = 'User blocked permanently'
                    elif action_type == 'unblock':
                        await user_repo.set_user_blocked_until(session, target_id, None)
                        msg = 'You are unblocked.'
                        answer = 'User unblocked'

                    await session.commit()
                    if msg:
                        await bot.send_message(target_id, msg)
                else:
                    answer = 'User not found'

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(answer, reply_markup=remove_keyboard())

@router.callback_query(DeleteDomain.filter(F.data == 'canceled'))
async def canceled(callback: CallbackQuery):
    if not isinstance(callback.message, Message):
        return

    with suppress(TelegramBadRequest):
        await callback.message.edit_text('Cancel', reply_markup=remove_keyboard())

@router.callback_query(DeleteDomain.filter())
async def delete_domain_callback(callback: CallbackQuery, session: AsyncSession):
    if not callback.data:
        return
    if not isinstance(callback.message, Message):
        return

    text = callback.data.split(':')
    id, domain_name = text[1].split('@')
    domain_name = domain_name.replace(';', ':')

    if callback.from_user.id != int(id):
        with suppress(TelegramBadRequest):
            await callback.message.edit_text('access denied', reply_markup=remove_keyboard())
        return

    domain_row = await domain_repo.get_domain_for_user(session, int(id), domain_name)
    if not domain_row:
        with suppress(TelegramBadRequest):
            await callback.message.edit_text('Domain not found', reply_markup=remove_keyboard())
        return

    await remove_domain(session, int(id), domain_row.id)

    with suppress(TelegramBadRequest):
        await callback.message.edit_text('🫡', reply_markup=remove_keyboard())

@router.callback_query(CloudFlareTokens.filter())
async def cloudflare_token(callback: CallbackQuery, session: AsyncSession):
    if not callback.data:
        return
    if not isinstance(callback.message, Message):
        return

    token_id = int(callback.data.split(':', maxsplit=1)[1])
    token = await settings_repo.get_cf_token_by_id(session, token_id, callback.from_user.id)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(callback.message.text or '', reply_markup=remove_keyboard())
        if token:
            token_param = token.param or ''
            masked_token = token_param[:4] + "*" * max(0, len(token_param) - 4)
            await callback.message.answer('Are you sure that you want to remove the token? <pre>{}</pre>'.format(masked_token), reply_markup=confirmation_keyboard(token.id))
        else:
            await callback.message.answer('Token not found')

@router.callback_query(CloudFlareDeleteTokens.filter())
async def delete_cloudflare_token(callback: CallbackQuery, session: AsyncSession):
    if not callback.data:
        return
    if not isinstance(callback.message, Message):
        return

    id = int(callback.data.split(':', maxsplit=1)[1])
    token = await settings_repo.get_cf_token_by_id(session, id, callback.from_user.id)
    with suppress(TelegramBadRequest):
        if token:
            await settings_repo.delete_cf_token(session, token.id)
            await session.commit()
            await callback.message.edit_text('🫡', reply_markup=remove_keyboard())
        else:
            await callback.message.edit_text(callback.message.text or '', reply_markup=remove_keyboard())
            await callback.message.answer('Token not found')
