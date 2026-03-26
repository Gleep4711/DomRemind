import logging
from asyncio import sleep
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Domains
from app.db.repositories import domains as domain_repo
from app.whois import get_expired_date


DOMAIN_LIMIT = 10


async def add_domains(
    session: AsyncSession,
    user_id: int,
    role: str,
    text: str,
    send_message: Callable[[str], Awaitable[Any]],
) -> None:
    current_domains_count = await domain_repo.count_user_domains(session, user_id)
    limit_enabled = role == 'guest'
    if limit_enabled and current_domains_count >= DOMAIN_LIMIT:
        await send_message(
            'Domain limit reached: <code>{}</code> domains maximum per user.'.format(
                DOMAIN_LIMIT
            )
        )
        return

    domains = text.split('\n')
    msg = ''
    added = False
    added_domains: list[str] = []
    count = 0

    for string in domains:
        count += 1
        d_data = string.split('.')
        if len(d_data) < 2 or not d_data[-2] or not d_data[-1]:
            msg += '<code>{}</code> invalid format\n'.format(string)
            continue

        domain = '{}.{}'.format(d_data[-2], d_data[-1])
        if domain in added_domains:
            msg += '<code>{}</code> already exist\n'.format(domain)
            continue

        if await domain_repo.find_user_domain_link(session, user_id, domain):
            msg += '<code>{}</code> already exist\n'.format(domain)
            continue

        if limit_enabled and current_domains_count + len(added_domains) >= DOMAIN_LIMIT:
            msg += 'Domain limit reached: <code>{}</code> domains maximum per user.\n'.format(
                DOMAIN_LIMIT
            )
            break

        domain_row = await domain_repo.get_domain_by_name(session, domain)
        expires_date = (
            domain_row.expired_date
            if domain_row and domain_row.expired_date
            else await get_expired_date(session, domain)
        )

        if expires_date:
            if expires_date.tzinfo is None:
                expires_date = expires_date.replace(tzinfo=timezone.utc)
            if domain_row is None:
                domain_row = await domain_repo.create_domain(session, domain, expires_date)
            elif domain_row.expired_date is None:
                domain_row.expired_date = expires_date
                domain_row.last_check = datetime.now(timezone.utc)

            await domain_repo.link_user_domain(session, user_id, domain_row.id)
            date_difference = expires_date - datetime.now(timezone.utc)
            msg += '<code>{}</code>: {:%d.%m.%Y} [ {}{} day ]\n'.format(
                domain,
                expires_date,
                '❗️' if date_difference.days < 30 else '',
                date_difference.days,
            )
            added_domains.append(domain)
        else:
            msg += '<code>{}</code> error: domain not added\n'.format(domain)

        if count >= 20 or len(added_domains) >= 10:
            await session.commit()
            await send_message(msg + '... 🏃')
            added_domains = []
            count = 0
            added = True
            msg = ''

        await sleep(1)

    if not msg and not added:
        logging.error('Error: No domains added. User ID: %s Text: %s', user_id, text[:128])
        return

    if msg:
        await session.commit()
        await send_message(msg)
    else:
        await send_message('finish')


async def get_domain_for_deletion(
    session: AsyncSession, user_id: int, domain_name: str
) -> Domains | None:
    return await domain_repo.get_domain_for_user(session, user_id, domain_name)


async def remove_domain(session: AsyncSession, user_id: int, domain_id: int) -> None:
    await domain_repo.unlink_user_domain(session, user_id, domain_id)
    await domain_repo.delete_domain_if_orphan(session, domain_id)
    await session.commit()
