from asyncio import sleep
from datetime import datetime, timezone
import logging
from typing import Any, Awaitable, Callable

import httpx
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config_reader import config
from app.db.repositories import domains as domain_repo
from app.db.repositories import settings as settings_repo
from app.services.whois_json import get_expiry_from_whoisjson
from app.whois import UNSUPPORTED_ZONES, get_estimated_expiry_for_unsupported, get_expired_date

# Days before estimated expiry at which to notify users of unsupported-zone domains.
# Sorted ascending so threshold-tracking picks the tightest applicable window first.
ESTIMATED_NOTIFICATION_DAYS: tuple[int, ...] = (3, 7, 30)


async def notifications(bot: Bot, session_pool: async_sessionmaker[AsyncSession]):
    '''This function checks the expiration date of the domains and sends notifications to users if the domain is expiring soon.'''

    async with session_pool() as session:
        domains = await domain_repo.get_all_domains(session)
        for domain in domains:
            if domain.expired_date is None or domain.domain is None:
                logging.warning('Skipping domain with missing data: id=%s domain=%s', domain.id, domain.domain)
                continue

            # Anti-spam: skip domains checked in the last 5 minutes.
            if domain.last_check is not None:
                last_difference = datetime.now(timezone.utc) - domain.last_check.replace(tzinfo=timezone.utc)
                if last_difference.total_seconds() < 300:
                    logging.debug(
                        'Skipping recently checked domain: id=%s domain=%s last_check=%s',
                        domain.id, domain.domain, domain.last_check,
                    )
                    continue

            tld = domain.domain.rsplit('.', 1)[-1].lower()

            if tld in UNSUPPORTED_ZONES:
                # Estimated expiry path: send notifications at 30 / 7 / 3 days.
                # last_check is used as a "threshold already notified" marker:
                # if (expired_date - last_check).days <= current_threshold, the
                # notification for that threshold has already been sent.
                days = (domain.expired_date.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days

                current_threshold = next(
                    (t for t in ESTIMATED_NOTIFICATION_DAYS if days <= t), None
                )
                if current_threshold is None:
                    continue  # more than 30 days away

                if domain.last_check is not None:
                    days_at_last_check = (
                        domain.expired_date.replace(tzinfo=timezone.utc)
                        - domain.last_check.replace(tzinfo=timezone.utc)
                    ).days
                    if days_at_last_check <= current_threshold:
                        continue  # already notified for this threshold

                msg = (
                    '⚠️ <code>{}</code> [ {:%d.%m.%Y} ] estimated expiry: {} days '
                    '(zone .{} — date is approximate, based on registration date)'
                ).format(domain.domain, domain.expired_date, days, tld)
                await send_message_all_users_with_a_domain(msg, domain.domain, bot, session)
                await domain_repo.touch_last_check(session, domain.domain)
                await session.commit()
                await sleep(1)
                continue

            # Standard expiry check path.
            if domain.last_check is None:
                continue

            date_difference = domain.expired_date.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
            if date_difference.days > 60:
                continue

            expires_date = await get_expired_date(session, domain.domain)
            if expires_date is None:
                try:
                    await bot.send_message(
                        chat_id=config.ADMIN,
                        text='⚠️ Domain check failed: <code>{}</code>'.format(domain.domain),
                    )
                except Exception:
                    pass
                expires_date = await get_expiry_from_whoisjson(domain.domain)

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


async def check_cloud_token(token: str) -> str | bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
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
    token: str, user_id: int, bot: Bot, session: AsyncSession,
    page: int = 1, _seen: set[str] | None = None,
) -> tuple[int, set[str]] | bool:
    if _seen is None:
        _seen = set()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
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

    added_count = 0
    for domain_data in result_items:
        domain_name: str = domain_data['name']
        _seen.add(domain_name)
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

        if await domain_repo.find_user_domain_link(session, user_id, domain_name):
            logging.debug('Skipping domain already present in DB: user_id=%s domain=%s', user_id, domain_name)
            continue

        tld = domain_name.split('.')[-1].lower()
        domain_row = await domain_repo.get_domain_by_name(session, domain_name)

        if tld in UNSUPPORTED_ZONES:
            if domain_row and domain_row.expired_date:
                expires_date = domain_row.expired_date
                is_estimated = False
            else:
                expires_date = await get_estimated_expiry_for_unsupported(domain_name.split('.'))
                is_estimated = True
        else:
            expires_date = (
                domain_row.expired_date
                if domain_row and domain_row.expired_date
                else await get_expired_date(session, domain_name)
            )
            if expires_date is None:
                expires_date = await get_expiry_from_whoisjson(domain_name)
            is_estimated = False

        if expires_date:
            logging.debug(
                'Domain expiration received: user_id=%s domain=%s expires_date=%s estimated=%s',
                user_id, domain_name, expires_date, is_estimated,
            )
            if domain_row is None:
                domain_row = await domain_repo.create_domain(session, domain_name, expires_date)
            elif domain_row.expired_date is None:
                domain_row.expired_date = expires_date
                domain_row.last_check = datetime.now(timezone.utc)

            await domain_repo.link_user_domain(session, user_id, domain_row.id, source='cloudflare')
            await session.commit()

            added_count += 1

            date_difference = expires_date - datetime.now(timezone.utc)
            logging.debug(
                'Domain added: user_id=%s domain=%s days_left=%s estimated=%s',
                user_id, domain_name, date_difference.days, is_estimated,
            )

            if is_estimated:
                msg = (
                    '⚠️ <code>{}</code> added. Zone .{} has no public expiry data.\n'
                    'Estimated expiry: {:%d.%m.%Y} (~{} days, based on registration date)'
                ).format(domain_name, tld, expires_date, date_difference.days)
                try:
                    await bot.send_message(chat_id=user_id, text=msg)
                except Exception:
                    logging.error(
                        'Failed to send .%s domain notice, notifying admin: user_id=%s domain=%s',
                        tld, user_id, domain_name,
                    )
                    await bot.send_message(
                        chat_id=config.ADMIN,
                        text='Error send message\nuser id: {}\ntoken: {}\ndomain: {}'.format(
                            user_id, token, domain_name
                        ),
                    )
            elif date_difference.days < 30:
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
        sub = await pull_all_domains(
            token=token, user_id=user_id, bot=bot, session=session, page=page + 1, _seen=_seen
        )
        if sub is False:
            return False
        if isinstance(sub, tuple):
            added_count += sub[0]

    logging.debug(
        'pull_all_domains finished: user_id=%s page=%s added_count=%s seen=%s',
        user_id, page, added_count, len(_seen),
    )
    return (added_count, _seen)


async def cloudflare_sync(bot: Bot, session_pool: async_sessionmaker[AsyncSession]):
    async with session_pool() as session:
        tokens = await settings_repo.get_all_cf_tokens(session)

        # Group tokens by user so we can aggregate all CF domains per user
        # and cleanly unlink domains removed from Cloudflare.
        user_tokens: dict[int, list[str]] = {}
        for token in tokens:
            if token.param is not None:
                user_tokens.setdefault(token.user_id, []).append(token.param)

        for user_id, token_list in user_tokens.items():
            all_cf_domains: set[str] = set()
            for token in token_list:
                result = await pull_all_domains(token, user_id, bot, session)
                if isinstance(result, tuple):
                    all_cf_domains.update(result[1])
                await sleep(5)

            # Unlink CF-sourced domains no longer present in Cloudflare
            await domain_repo.unlink_user_cf_domains_not_in(session, user_id, all_cf_domains)
            await session.commit()


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
    check_result = await check_cloud_token(token)
    if not check_result:
        logging.error('Error: Invalid cloudflare token. User ID: %s', user_id)
        await send_message('Error: token no valid')
        return

    await settings_repo.add_cf_token(session, user_id, token)
    await session.commit()
    await send_message(str(check_result))
    result = await pull_all_domains(token, user_id, bot, session)
    if isinstance(result, tuple):
        await send_message('Sync finished, {} domains added'.format(result[0]))
    elif result is False:
        await send_message('Sync finished with errors')
