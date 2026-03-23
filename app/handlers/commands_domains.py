from asyncio import sleep
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import domains as domain_repo
from app.db.repositories import users as user_repo
from app.keyboards import cancel_reply_keyboard
from app.services.domain_service import DOMAIN_LIMIT
from app.states import STATE_ADD_DOMAIN, STATE_REMOVE_DOMAIN

router = Router(name="commands-domains-router")


def _message_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


@router.message(Command('add_domain'))
async def add_domain(message: Message, session: AsyncSession, role: str):
    user_id = _message_user_id(message)
    if user_id is None:
        return
    user = await user_repo.get_user(session, user_id)
    if user_repo.is_user_blocked(user):
        return await message.answer(
            'You are blocked ({}) and cannot add domains.'.format(
                user_repo.user_block_status_text(user)
            )
        )
    await user_repo.set_user_state(session, user_id, STATE_ADD_DOMAIN)
    await session.commit()
    msg = (
        'Enter domains\n'
        'You can enter several domains at once - one domain on one line, no spaces, no commas'
    )
    if role == 'guest':
        msg += '\nLimit: <code>{}</code> domains per user'.format(DOMAIN_LIMIT)
    await message.answer(msg, reply_markup=cancel_reply_keyboard())


@router.message(Command('get_domains'))
async def get_domains(message: Message, session: AsyncSession):
    user_id = _message_user_id(message)
    if user_id is None:
        return

    domains = await domain_repo.get_user_domains(session, user_id)
    msg = ''
    count = 0
    empty = True
    for domain in domains:
        if domain.expired_date is None:
            msg += '<code>{}</code> expiration date is unknown\n'.format(str(domain.domain).ljust(20))
            continue

        date_difference = domain.expired_date.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        msg += '<code>{}</code> {:%d.%m.%Y} [ {}{} day ]\n'.format(
            str(domain.domain).ljust(20),
            domain.expired_date,
            '❗️' if date_difference.days < 30 else '',
            date_difference.days,
        )
        count += 1
        if count >= 10:
            empty = False
            await message.answer(msg)
            count = 0
            await sleep(1)
            msg = ''

    if count == 0 and empty:
        return await message.answer('Empty')
    msg += '\nInformation may be out of date for domains that have a lifetime of more than 60 days'
    await message.answer(msg)


@router.message(Command('remove_domains'))
async def remove_domains(message: Message, session: AsyncSession):
    user_id = _message_user_id(message)
    if user_id is None:
        return
    await user_repo.set_user_state(session, user_id, STATE_REMOVE_DOMAIN)
    await session.commit()
    await message.answer('Enter the domain you want to delete', reply_markup=cancel_reply_keyboard())
