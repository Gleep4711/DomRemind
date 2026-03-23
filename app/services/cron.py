from asyncio import sleep
from datetime import datetime, timezone
import logging
from typing import Any, Awaitable, Callable

import requests
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config_reader import config
from app.db.repositories import domains as domain_repo
from app.db.repositories import settings as settings_repo
from app.whois import get_expired_date


async def notifications(bot: Bot, session_pool: async_sessionmaker[AsyncSession]):
    async with session_pool() as session:
        domains = await domain_repo.get_all_domains(session)
        for domain in domains:
            if domain.last_check is None or domain.expired_date is None or domain.domain is None:
                continue

            last_difference = datetime.now(timezone.utc) - domain.last_check.replace(tzinfo=timezone.utc)
            if last_difference.total_seconds() < 300:
                continue

            date_difference = domain.expired_date.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
            if date_difference.days > 60:
                continue

            expires_date = await get_expired_date(domain.domain)
            if expires_date:
                await domain_repo.update_domain_expiry(session, domain.domain, expires_date)
                await session.commit()
                new_date_difference = expires_date - datetime.now(timezone.utc)
                if new_date_difference.days < 60:
                    msg = '❗️ <code>{}</code> [ {:%d.%m.%Y} ] left: {} day ❗️'.format(
                        domain.domain, domain.expired_date, date_difference.days
                    )
                    await send_message_all_users_with_a_domain(msg, domain.domain, bot, session)
            else:
                msg = '{} check error'.format(domain.domain)
                await send_message_all_users_with_a_domain(msg, domain.domain, bot, session)

            await sleep(1)


async def send_message_all_users_with_a_domain(
    msg: str, domain_name: str, bot: Bot, session: AsyncSession
):
    user_ids = await domain_repo.get_users_for_domain(session, domain_name)
    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            logging.error('Error sending message to user %s for domain %s: %s', user_id, domain_name, e)
            await bot.send_message(
                chat_id=config.ADMIN,
                text='Error send message\nuser id: {}\ndomain: {}'.format(user_id, domain_name),
            )
        await sleep(1)


async def new_user_notification(bot: Bot, msg: str):
    await bot.send_message(chat_id=config.ADMIN, text=msg)


def check_cloud_token(token: str) -> str | bool:
    try:
        response = requests.get(
            'https://api.cloudflare.com/client/v4/user/tokens/verify',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        )
    except Exception as e:
        logging.error('Error verifying Cloudflare token: %s', e)
        return False

    if response.status_code == 200:
        data = response.json()
        if not data['success']:
            return False
        msg = 'The token is successfully added 🎉\n\n'
        for message in data['messages']:
            msg += '\n'.join([f'{key}: <code>{value}</code>' for key, value in message.items()])
            msg += '\n\n'
        return msg

    return False


async def pull_all_domains(
    token: str, user_id: int, bot: Bot, session: AsyncSession, page: int = 1
):
    try:
        response = requests.get(
            'https://api.cloudflare.com/client/v4/zones?page=' + str(page),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        )
    except Exception as e:
        logging.error('Error pulling domains for user %s with token %s: %s', user_id, token, e)
        await send_error_sync_message(bot=bot, user_id=user_id, token=token)
        return False

    if response.status_code != 200:
        logging.error(
            'Cloudflare request failed with non-200: user_id=%s page=%s status_code=%s',
            user_id, page, response.status_code,
        )
        return False

    data: dict = response.json()
    if not data['success']:
        logging.error(
            'Cloudflare response marked unsuccessful: user_id=%s page=%s errors=%s',
            user_id, page, data.get('errors'),
        )
        return False

    result_items = data.get('result', [])
    total_pages_raw = data.get('result_info', {}).get('total_pages', 0)
    logging.debug(
        'Cloudflare page parsed: user_id=%s page=%s items=%s total_pages=%s',
        user_id, page, len(result_items), total_pages_raw,
    )

    added_domains: list[str] = []
    for domain_data in result_items:
        domain_name: str = domain_data['name']
        logging.debug('Processing domain from Cloudflare: user_id=%s domain=%s', user_id, domain_name)

        d_data = domain_name.split('.')
        if len(d_data) < 2 or not d_data[-2] or not d_data[-1]:
            logging.error('Skipping domain with invalid format: user_id=%s domain=%s', user_id, domain_name)
            await bot.send_message(
                chat_id=user_id,
                text='Error sync, invalid domain format: <code>{}</code>'.format(domain_name),
            )
            await bot.send_message(
                chat_id=config.ADMIN,
                text='Error sync, invalid domain format\nuser id: {}\ndomain: {}'.format(user_id, domain_name),
            )
            continue

        if domain_name in added_domains:
            logging.debug('Skipping duplicate domain in current batch: user_id=%s domain=%s', user_id, domain_name)
            continue

        if await domain_repo.find_user_domain_link(session, user_id, domain_name):
            logging.debug('Skipping domain already present in DB: user_id=%s domain=%s', user_id, domain_name)
            continue

        domain_row = await domain_repo.get_domain_by_name(session, domain_name)
        expires_date = (
            domain_row.expired_date
            if domain_row and domain_row.expired_date
            else await get_expired_date(domain_name)
        )

        if expires_date:
            logging.debug(
                'Domain expiration received: user_id=%s domain=%s expires_date=%s',
                user_id, domain_name, expires_date,
            )
            if domain_row is None:
                domain_row = await domain_repo.create_domain(session, domain_name, expires_date)
            elif domain_row.expired_date is None:
                domain_row.expired_date = expires_date
                domain_row.last_check = datetime.now(timezone.utc)

            await domain_repo.link_user_domain(session, user_id, domain_row.id)
            await session.commit()

            added_domains.append(domain_name)

            date_difference = expires_date - datetime.now(timezone.utc)
            logging.debug(
                'Domain added: user_id=%s domain=%s days_left=%s',
                user_id, domain_name, date_difference.days,
            )
            if date_difference.days < 30:
                msg = '<code>{}</code>: {:%d.%m.%Y} [ {}{} day ]\n'.format(
                    domain_name, expires_date, '❗️', date_difference.days
                )
                try:
                    await bot.send_message(chat_id=user_id, text=msg)
                except Exception:
                    logging.error(
                        'Failed to send expiry alert, notifying admin: user_id=%s domain=%s',
                        user_id, domain_name,
                    )
                    await bot.send_message(
                        chat_id=config.ADMIN,
                        text='Error send message\nuser id: {}\ntoken: {}\ndomain: {}'.format(
                            user_id, token, domain_name
                        ),
                    )
        else:
            logging.debug('Expiration date not found, notifying user: user_id=%s domain=%s', user_id, domain_name)
            await bot.send_message(
                chat_id=user_id,
                text='Error: Failed to get information about the domain: <code>{}</code>'.format(domain_name),
            )

        await sleep(1)

    total_pages = int(total_pages_raw)
    if total_pages > 0 and total_pages > page:
        logging.debug(
            'Fetching next Cloudflare page: user_id=%s current_page=%s total_pages=%s',
            user_id, page, total_pages,
        )
        await sleep(1)
        await pull_all_domains(token=token, user_id=user_id, bot=bot, session=session, page=(page + 1))

    logging.debug(
        'pull_all_domains finished: user_id=%s page=%s added_count=%s',
        user_id, page, len(added_domains),
    )
    return True


async def cloudflare_sync(bot: Bot, session_pool: async_sessionmaker[AsyncSession]):
    async with session_pool() as session:
        tokens = await settings_repo.get_all_cf_tokens(session)
        for token in tokens:
            if token.param is None:
                continue
            await pull_all_domains(token.param, token.user_id, bot, session)
            await sleep(5)


async def send_error_sync_message(bot: Bot, user_id: int, token: str):
    try:
        await bot.send_message(chat_id=user_id, text='Error sync, token {}...'.format(token[0:4]))
    except Exception:
        await bot.send_message(
            chat_id=config.ADMIN,
            text='Error send message\nuser id: {}\ntoken: {}'.format(user_id, token),
        )


async def verify_and_add_token(
    session: AsyncSession,
    user_id: int,
    token_text: str,
    send_message: Callable[[str], Awaitable[Any]],
    bot: Bot,
) -> None:
    token = token_text[:128]
    if await settings_repo.check_token_exists(session, user_id, token):
        logging.error('Error: This token already exists. User ID: %s', user_id)
        await send_message('Error: This token is already exists')
        return

    await send_message('Checking... 🕹')
    check_result = check_cloud_token(token)
    if not check_result:
        logging.error('Error: Invalid cloudflare token. User ID: %s', user_id)
        await send_message('Error: token no valid')
        return

    await settings_repo.add_cf_token(session, user_id, token)
    await session.commit()
    await send_message(str(check_result))
    await pull_all_domains(token, user_id, bot, session)
