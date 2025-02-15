import requests
from asyncio import sleep
from datetime import datetime, timedelta

from aiogram import Bot
from pytz import UTC
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Domains, Settings
from bot.config_reader import config
from bot.whois import get_expired_date


async def notifications(bot: Bot, session_pool:async_sessionmaker[AsyncSession]):
    domain: Domains
    last_difference: timedelta
    date_difference: timedelta

    async with session_pool() as session:
        domains = (await session.execute(select(Domains))).scalars()
        for domain in domains:
            last_difference = datetime.now(UTC) - domain.last_check.replace(tzinfo=UTC)
            if last_difference.total_seconds() < 300:
                continue

            date_difference = domain.expired_date.replace(tzinfo=UTC) - datetime.now(UTC)
            if date_difference.days > 60:
                continue

            expires_date = await get_expired_date(domain.domain)
            if expires_date:
                update_data = {'expired_date': expires_date, 'last_check': datetime.now(UTC)}
                await session.execute(update(Domains).filter(Domains.domain == domain.domain).values(update_data))
                await session.commit()
                new_date_difference = expires_date - datetime.now(UTC)
                if new_date_difference.days < 60:
                    msg = '❗️ <code>{}</code> [ {:%d.%m.%Y} ] left: {} day ❗️'.format(domain.domain, domain.expired_date, date_difference.days)
                    await send_message_all_users_with_a_domain(msg, domain.domain, bot, session)
            else:
                msg = '{} check error'.format(domain.domain)
                await send_message_all_users_with_a_domain(msg, domain.domain, bot, session)

            await sleep(1)

async def send_message_all_users_with_a_domain(msg: str, domain_name: str, bot: Bot, session: AsyncSession):
    domain: Domains

    domains = (await session.execute(select(Domains).filter(Domains.domain == domain_name))).scalars()
    for domain in domains:
        try:
            await bot.send_message(chat_id=domain.user_id, text=msg)
        except:
            await bot.send_message(chat_id=config.admin, text='Error send message\nuser id: {}\ndomain: {}'.format(domain.user_id, domain.domain))
        await sleep(1)

async def new_user_notification(bot: Bot, msg: str):
    await bot.send_message(chat_id=config.admin, text=msg)

async def check_cloud_token(token: str):
    message: dict

    try:
        response = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
    except Exception as e:
        print(e)
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

async def pull_all_domains(token: str, user_id: int, bot: Bot, session: AsyncSession, page = 1):
    try:
        response = requests.get(
            "https://api.cloudflare.com/client/v4/zones?page=" + str(page),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
    except Exception as e:
        print(e)
        await send_error_sync_message(bot=bot, user_id=user_id, token=token)
        return False

    if response.status_code != 200:
        return False

    data = response.json()
    if not data['success']:
        return False

    added_domains = []
    for domain_data in data['result']:
        domain_name = domain_data['name']

        d_data = domain_name.split('.')
        if len(d_data) < 2 or not d_data[-2] or not d_data[-1]:
            continue

        # weed out duplicates
        if domain_name in added_domains:
            continue
        if (await session.execute(select(Domains).filter(Domains.user_id == user_id, Domains.domain == domain_name))).scalar():
            continue

        expires_date = await get_expired_date(domain_name)
        if expires_date:
            session.add(Domains(
                user_id = user_id,
                domain = domain_name,
                expired_date = expires_date,
                last_check = datetime.now(UTC),
            ))
            added_domains.append(domain_name)

            date_difference = expires_date - datetime.now(UTC)
            if date_difference.days < 30:
                msg = '<code>{}</code>: {:%d.%m.%Y} [ {}{} day ]\n'.format(domain_name, expires_date, '❗️', date_difference.days)
                try:
                    await bot.send_message(chat_id=user_id, text=msg)
                except:
                    await bot.send_message(chat_id=config.admin, text='Error send message\nuser id: {}\ntoken: {}\ndomain: {}'.format(user_id, token, domain_name))
        else:
            await bot.send_message(chat_id=user_id, text='Error: Failed to get information about the domain: <code>{}</code>'.format(domain_name))
        await sleep(1)

    if len(added_domains) > 0:
        await session.commit()

    if int(data['result_info']['total_pages']) > 0 and int(data['result_info']['total_pages']) > page:
        await sleep(1)
        await pull_all_domains(
            token=token,
            user_id=user_id,
            bot=bot,
            session=session,
            page=(page + 1),
        )

    return True

async def cloudflare_sync(bot: Bot, session_pool:async_sessionmaker[AsyncSession]):
    async with session_pool() as session:
        tokens = (await session.execute(select(Settings).filter(Settings.name == 'token', Settings.group == 'cloudflare'))).scalars()
        for token in tokens:
            await pull_all_domains(token.param, token.user_id, bot, session)
            await sleep(5)

async def send_error_sync_message(bot: Bot, user_id: int, token: str):
    try:
        await bot.send_message(chat_id=user_id, text='Error sync, token {}...'.format(token[0:4]))
    except:
        await bot.send_message(chat_id=config.admin, text='Error send message\nuser id: {}\ntoken: {}'.format(user_id, token))
