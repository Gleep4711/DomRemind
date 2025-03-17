from asyncio import sleep
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import bot, scheduler
from app.cron import check_cloud_token, pull_all_domains
from app.db.models import Domains, Settings, Users
from app.keyboards import (change_role, delete_domain_inline,
                           remove_cloudflare_token)
from app.whois import get_expired_date

router = Router(name="commands-router")

@router.message(CommandStart())
async def cmd_start(message: Message, role: str, session: AsyncSession):
    """
    Handles /start command
    :param message: Telegram message with "/start" text
    """
    if role == 'guest':
        return await message.answer(
            "Hello! This is a very strange bot.\n"
            "If you don't know what to do, then take it for granted."
        )
    msg = dedent('''
        -- Domains --
        /add_domain Add new domains
        /get_domains Show all domains
        /remove_domains Delete domain

        -- Cloudflare --
        /add_cloud_token Add cloudflare token
        /get_cloud_tokens Show all cloudflare tokens
        /help_create_new_token Instructions for creating a new token
    ''')
    if role == 'admin':
        msg += '\n-- Admin command --\n/get_users List of all users'

    await message.answer(msg)

@router.message(Command('add_domain'))
async def add_domain(message: Message, session: AsyncSession):
    await session.execute(update(Users).filter(Users.id == message.from_user.id).values(state = 'add_domain'))
    await session.commit()
    await message.answer('Enter domains\nYou can enter several domains at once - one domain on one line, no spaces, no commas')

@router.message(Command('get_domains'))
async def get_domains(message: Message, session: AsyncSession):
    date_difference: timedelta

    domains = (await session.execute(select(Domains).filter(Domains.user_id == message.from_user.id).order_by(Domains.expired_date))).scalars()
    msg = ''
    count = 0
    empty = True
    for domain in domains:
        date_difference = domain.expired_date.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        msg += '<code>{}</code> {:%d.%m.%Y} [ {}{} day ]\n'.format(str(domain.domain).ljust(20), domain.expired_date, '❗️' if date_difference.days < 30 else '', date_difference.days)

        count = count + 1
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
    await session.execute(update(Users).filter(Users.id == message.from_user.id).values(state = 'remove_domain'))
    await session.commit()
    await message.answer('Enter the domain you want to delete')


@router.message(Command('get_users'))
async def get_users(message: Message, session: AsyncSession, role: str):
    if role != 'admin':
        return
    users = (await session.execute(select(Users))).scalars()
    users_answer = []
    for user in users:
        # users_answer.append('<code>{}</code> {} {} {}'.format(user.id, user.first_name, user.last_name, user.role))
        user_name = '{} {}'.format(user.first_name, user.last_name).replace('<', '').replace('.', ' ')
        msg = '<code>{}</code> <a href="tg://user?id={}">{}</a> {}'.format(user.id, user.id, user_name, user.role)
        users_answer.append(msg)
        if len(users_answer) >= 10:
            await message.answer('\n'.join(users_answer))
            await sleep(1)
            users_answer = []
    if len(users_answer) > 0:
        await message.answer('\n'.join(users_answer))

@router.message(F.text.regexp(r'^\d*$'))
async def user_id(message: Message, session: AsyncSession, role: str):
    if role != 'admin':
        return
    sql_user = await session.execute(select(Users).filter(Users.id == int(message.text)))
    user = sql_user.first()
    if not user:
        await message.answer('User id not found')

    roles = []
    for key in ['guest', 'user', 'admin']:
        if key != user[0].role:
            roles.append({
                'id': message.text,
                'new_role': key,
            })
    await message.answer('{} {}\n'
                         'Current role: {}\n'
                         '<code>'
                            'Guest - not access\n'
                            'User - access add domain\n'
                            'Admin - access user manager'
                         '</code>'
                         .format(user[0].first_name, user[0].last_name, user[0].role), reply_markup=change_role(roles))

@router.message(Command('add_cloud_token'))
async def add_cloud_token(message: Message, session: AsyncSession, role: str):
    if role == 'guest':
        return
    await session.execute(update(Users).filter(Users.id == message.from_user.id).values(state = 'add_cloud_token'))
    await session.commit()
    await message.answer('Enter cloudflare token')


@router.message(Command('get_cloud_tokens'))
async def get_cloud_tokens(message: Message, session: AsyncSession, role: str):
    if role == 'guest':
        return
    tokens = (await session.execute(select(Settings).filter(Settings.user_id == message.from_user.id, Settings.name == 'token', Settings.group == 'cloudflare'))).scalars()
    token_list = list(tokens)
    if not len(token_list):
        return await message.answer('Tokens not found')

    msg = ''
    ids = []
    for token in token_list:
        msg += '{id}: <code>{param}</code>\n'.format(
            id=token.id,
            param=token.param[:4] + "*" * (len(token.param) - 4),
        )
        ids.append(token.id)
    msg += '\nSelect the token ID for removal:'.format()

    await message.answer(msg, reply_markup=remove_cloudflare_token(ids))


@router.message(Command('help_create_new_token'))
async def help_create_new_token(message: Message, session: AsyncSession, role: str):
    if role == 'guest':
        return
    msg = '''
    1. <b>Go to Profile</b> => <b>Api tokens</b> => <b>Create Token</b>
    https://dash.cloudflare.com/profile/api-tokens

    2. Use template "<b>Edit zone DNS</b>"

    3.
    * Permissions - Change "<b>Edit</b>" to "<b>Read</b>" (Zone DNS Read)
    * Zone Resources - Change "<b>Specific zone</b>" to "All zones" (Include All zones)

    <b>Continue to summary</b> and <b>Create Token</b>
    '''

    await message.answer(dedent(msg), disable_web_page_preview=True)


@router.message()
async def echo(message: Message, session: AsyncSession, state: str):
    if state in ['add_domain', 'remove_domain', 'add_cloud_token']:
        await session.execute(update(Users).filter(Users.id == message.from_user.id).values(state = ''))
        await session.commit()

    if state == 'add_domain':
        await message.answer('running.... 🏃')
        await add_domains(message, session)
    elif state == 'remove_domain':
        await delete_domain(message, message.from_user.id, session)
    elif state == 'add_cloud_token':
        await add_token(message, session)

    else:
        print('Error: Unknown command.\nState: "{}"\nText: "{}"'.format(state, str(message.text)[:128]))

async def add_domains(message: Message, session: AsyncSession):
    domains = message.text.split('\n')
    id = message.from_user.id
    msg = ''
    added = False
    added_domains = []
    count = 0
    for string in domains:
        count = count + 1
        # weed out subdomains
        d_data = string.split('.')
        if len(d_data) < 2 or not d_data[-2] or not d_data[-1]:
            msg += '<code>{}</code> invalid format\n'.format(string)
            continue

        # weed out duplicates
        domain = '{}.{}'.format(d_data[-2], d_data[-1])
        if domain in added_domains:
            msg += '<code>{}</code> already exist\n'.format(domain)
            continue

        # check if the domain exists in the database
        sql_domain = await session.execute(select(Domains).filter(Domains.user_id == id, Domains.domain == domain))
        if sql_domain.first():
            msg += '<code>{}</code> already exist\n'.format(domain)
            continue

        expires_date = await get_expired_date(domain)
        if expires_date:
            session.add(Domains(
                user_id = id,
                domain = domain,
                expired_date = expires_date,
                last_check = datetime.now(timezone.utc),
            ))
            date_difference = expires_date - datetime.now(timezone.utc)
            msg += '<code>{}</code>: {:%d.%m.%Y} [ {}{} day ]\n'.format(domain, expires_date, '❗️' if date_difference.days < 30 else '', date_difference.days)
            added_domains.append(domain)
        else:
            msg += '<code>{}</code> error: domain not added\n'.format(domain)

        if count >= 20 or len(added_domains) >= 10:
            await session.commit()
            msg += '... 🏃'
            await message.answer(msg)
            added_domains = []
            count = 0
            added = True
            msg = ''

        await sleep(1)

    if not msg and not added:
        return 'Error'

    if msg:
        await session.commit()
        return await message.answer(msg)
    await message.answer('finish')

async def delete_domain(message: Message, id: int, session: AsyncSession):
    domain: Domains

    domain = (await session.execute(select(Domains).filter(Domains.user_id == id, Domains.domain == message.text))).scalar()
    if not domain:
        return await message.answer('Domain not found')
    await message.answer('{}'.format(domain.domain), reply_markup=delete_domain_inline({'id': str(id), 'domain': domain.domain }))

async def add_token(message: Message, session: AsyncSession):
    token = str(message.text)[:128]
    check_token_in_db = (await session.execute(select(Settings).filter(Settings.user_id == message.from_user.id, Settings.name == 'token', Settings.group == 'cloudflare', Settings.param == token))).scalar()
    if check_token_in_db:
        return await message.answer('Error: This token is already exists')

    await message.answer('Checking... 🕹')
    check_token = await check_cloud_token(message.text)
    if not check_token:
        return await message.answer('Error: token no valid')

    session.add(Settings(user_id=message.from_user.id, name='token', group='cloudflare', param=token))
    await session.commit()
    await message.answer('{}'.format(check_token))

    # scheduler.add_job(pull_all_domains, 'date', run_date=datetime.now() + timedelta(seconds=5), args=(token, message.from_user.id, bot, session))

    await pull_all_domains(token, message.from_user.id, bot, session)
