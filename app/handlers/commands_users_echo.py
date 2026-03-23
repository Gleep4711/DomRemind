from asyncio import sleep
from datetime import datetime, timedelta
import logging
from textwrap import dedent

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import bot
from app.config_reader import config
from app.db.repositories import domains as domain_repo
from app.db.repositories import users as user_repo
from app.keyboards import cancel_reply_keyboard, change_role, delete_domain_inline, remove_reply_keyboard
from app.services.cron import verify_and_add_token
from app.services.domain_service import DOMAIN_LIMIT, add_domains as svc_add_domains, get_domain_for_deletion
from app.states import (
    CANCEL_TEXT,
    INPUT_STATES,
    STATE_ADD_CLOUD_TOKEN,
    STATE_ADD_DOMAIN,
    STATE_NONE,
    STATE_REMOVE_DOMAIN,
    STATE_SUPPORT,
)

router = Router(name="commands-users-echo-router")
SUPPORT_COOLDOWN = timedelta(seconds=30)
_support_last_message_at: dict[int, datetime] = {}


def _message_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


def _message_text(message: Message) -> str | None:
    return message.text


@router.message(CommandStart())
async def cmd_start(message: Message, role: str, session: AsyncSession):
    role_str = role.capitalize() if role else 'Guest'
    msg = dedent('''
        <b>Your role:</b> <code>{role}</code>

        <b>Domains</b>
        /add_domain Add new domains
        /get_domains Show all domains
        /remove_domains Delete domain
        /support Contact support
    ''').format(role=role_str)

    if role == 'guest':
        msg += '\n<i>Limit: {} domains per user</i>\n'.format(DOMAIN_LIMIT)

    if role in ['user', 'admin']:
        msg += dedent('''

            <b>Cloudflare</b>
            /add_cloud_token Add cloudflare token
            /get_cloud_tokens Show all cloudflare tokens
            /help_create_new_token Instructions for creating a new token
        ''')

    if role == 'admin':
        msg += dedent('''

            <b>Admin</b>
            /get_users List of all users
            /get_stats Show summary statistics
        ''')

    await message.answer(msg)


@router.message(Command('get_users'))
async def get_users(message: Message, session: AsyncSession, role: str):
    if role != 'admin':
        return

    users = await user_repo.get_all_users(session)
    domain_counts = await domain_repo.get_domain_counts_by_user(session)
    users_answer = []
    for user in users:
        user_name = '{} {}'.format(user.first_name, user.last_name).replace('<', '').replace('.', ' ')
        msg = '<code>{}</code> <a href="tg://user?id={}">{}</a> {} | domains: <code>{}</code>'.format(
            user.id,
            user.id,
            user_name,
            user.role,
            domain_counts.get(user.id, 0),
        )
        if user_repo.is_user_blocked(user):
            msg += ' | blocked: <code>{}</code>'.format(user_repo.user_block_status_text(user))
        users_answer.append(msg)
        if len(users_answer) >= 10:
            await message.answer('\n'.join(users_answer))
            await sleep(1)
            users_answer = []

    if len(users_answer) > 0:
        await message.answer('\n'.join(users_answer))


@router.message(Command('get_stats'))
async def get_stats(message: Message, session: AsyncSession, role: str):
    if role != 'admin':
        return

    users = await user_repo.get_all_users(session)
    domain_stats = await domain_repo.get_domain_statistics(session)
    role_counts: dict[str, int] = {'guest': 0, 'user': 0, 'admin': 0}
    for user in users:
        if user.role:
            role_counts[user.role] = role_counts.get(user.role, 0) + 1

    msg = dedent('''
        <b>General statistics</b>

        <b>Users</b>
        Total: <code>{users_total}</code>
        Guests: <code>{guests}</code>
        Users: <code>{users}</code>
        Admins: <code>{admins}</code>

        <b>Domains</b>
        Unique domains: <code>{total_domains}</code>
        User-domain links: <code>{total_links}</code>
        Users with domains: <code>{users_with_domains}</code>
    ''').format(
        users_total=len(users),
        guests=role_counts.get('guest', 0),
        users=role_counts.get('user', 0),
        admins=role_counts.get('admin', 0),
        total_domains=domain_stats['total_domains'],
        total_links=domain_stats['total_links'],
        users_with_domains=domain_stats['users_with_domains'],
    )
    await message.answer(msg)


@router.message(Command('support'))
async def support(message: Message, session: AsyncSession):
    user_id = _message_user_id(message)
    if user_id is None:
        return

    user = await user_repo.get_user(session, user_id)
    if user_repo.is_user_blocked(user):
        return await message.answer(
            'You are blocked ({}) and cannot use support.'.format(
                user_repo.user_block_status_text(user)
            )
        )

    await user_repo.set_user_state(session, user_id, STATE_SUPPORT)
    await session.commit()
    await message.answer('Write your message for support:', reply_markup=cancel_reply_keyboard())


@router.message(F.text.regexp(r'^\d*$'))
async def user_id_handler(message: Message, session: AsyncSession, role: str):
    if role != 'admin':
        return

    text = _message_text(message)
    if text is None:
        return

    user = await user_repo.get_user(session, int(text))
    if user is None:
        await message.answer('User id not found')
        return

    roles = [
        {'id': text, 'new_role': key}
        for key in ['guest', 'user', 'admin']
        if key != user.role
    ]
    first_name = user.first_name or ''
    last_name = user.last_name or ''

    await message.answer(
        '{} {}\nCurrent role: {}\nBlocked: {}\n'
        '<code>'
        'Guest - access domains only\n'
        'User - access domains and Cloudflare\n'
        'Admin - access user manager'
        '</code>'.format(
            first_name,
            last_name,
            user.role,
            user_repo.user_block_status_text(user),
        ),
        reply_markup=change_role(roles, text, user_repo.is_user_blocked(user)),
    )


@router.message(F.text == CANCEL_TEXT)
async def cancel_input(message: Message, session: AsyncSession, state: str):
    user_id = _message_user_id(message)
    if user_id is None:
        return

    if state not in INPUT_STATES:
        return

    await user_repo.set_user_state(session, user_id, STATE_NONE)
    await session.commit()
    await message.answer('Canceled', reply_markup=remove_reply_keyboard())


@router.message()
async def echo(message: Message, session: AsyncSession, state: str, role: str):
    user_id = _message_user_id(message)
    if user_id is None:
        return

    text = _message_text(message)
    if text is None:
        return

    if state in INPUT_STATES:
        await user_repo.set_user_state(session, user_id, STATE_NONE)
        await session.commit()

    user = await user_repo.get_user(session, user_id)
    blocked = user_repo.is_user_blocked(user)

    if state == STATE_ADD_DOMAIN:
        if blocked:
            return await message.answer(
                'You are blocked ({}) and cannot add domains.'.format(
                    user_repo.user_block_status_text(user)
                ),
                reply_markup=remove_reply_keyboard(),
            )
        await message.answer('running.... 🏃')
        await svc_add_domains(session, user_id, role, text, message.answer)
        return

    if state == STATE_REMOVE_DOMAIN:
        text = _message_text(message)
        if text is None:
            await message.answer('Domain not found')
            return
        domain = await get_domain_for_deletion(session, user_id, text)
        if not domain:
            await message.answer('Domain not found')
            return
        await message.answer(
            '{}'.format(domain.domain),
            reply_markup=delete_domain_inline({'id': str(user_id), 'domain': domain.domain}),
        )
        return

    if state == STATE_ADD_CLOUD_TOKEN:
        if blocked:
            return await message.answer(
                'You are blocked ({}) and cannot add Cloudflare tokens.'.format(
                    user_repo.user_block_status_text(user)
                ),
                reply_markup=remove_reply_keyboard(),
            )
        await verify_and_add_token(session, user_id, text, message.answer, bot)
        return

    if state == STATE_SUPPORT:
        if blocked:
            return await message.answer(
                'You are blocked ({}) and cannot use support.'.format(
                    user_repo.user_block_status_text(user)
                ),
                reply_markup=remove_reply_keyboard(),
            )
        now = datetime.utcnow()
        last_message_at = _support_last_message_at.get(user_id)
        if last_message_at and (now - last_message_at) < SUPPORT_COOLDOWN:
            wait_seconds = int((SUPPORT_COOLDOWN - (now - last_message_at)).total_seconds())
            return await message.answer(
                'Anti-spam: wait {} seconds before next support message.'.format(wait_seconds),
                reply_markup=remove_reply_keyboard(),
            )
        _support_last_message_at[user_id] = now
        await bot.send_message(
            chat_id=config.ADMIN,
            text=(
                '<b>Support request</b>\n'
                'From: <a href="tg://user?id={id}">{id}</a>\n'
                'Role: <code>{role}</code>\n\n'
                '{text}'
            ).format(id=user_id, role=role, text=text),
        )
        await message.answer('Your message has been sent to support.', reply_markup=remove_reply_keyboard())
        return

    logging.error('Error: Unknown command. State: %s Text: %s', state, str(message.text)[:128])
