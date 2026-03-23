from textwrap import dedent

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import settings as settings_repo
from app.db.repositories import users as user_repo
from app.keyboards import cancel_reply_keyboard, remove_cloudflare_token
from app.states import STATE_ADD_CLOUD_TOKEN

router = Router(name="commands-cf-router")


def _message_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


@router.message(Command('add_cloud_token'))
async def add_cloud_token(message: Message, session: AsyncSession, role: str):
    if role == 'guest':
        return
    user_id = _message_user_id(message)
    if user_id is None:
        return
    user = await user_repo.get_user(session, user_id)
    if user_repo.is_user_blocked(user):
        return await message.answer(
            'You are blocked ({}) and cannot add Cloudflare tokens.'.format(
                user_repo.user_block_status_text(user)
            )
        )
    await user_repo.set_user_state(session, user_id, STATE_ADD_CLOUD_TOKEN)
    await session.commit()
    await message.answer('Enter cloudflare token', reply_markup=cancel_reply_keyboard())


@router.message(Command('get_cloud_tokens'))
async def get_cloud_tokens(message: Message, session: AsyncSession, role: str):
    if role == 'guest':
        return
    user_id = _message_user_id(message)
    if user_id is None:
        return

    tokens = await settings_repo.get_cf_tokens_for_user(session, user_id)
    if not tokens:
        return await message.answer('Tokens not found')

    msg = ''
    ids = []
    for token in tokens:
        token_param = token.param or ''
        msg += '{id}: <code>{param}</code>\n'.format(
            id=token.id,
            param=token_param[:4] + '*' * max(0, len(token_param) - 4),
        )
        ids.append(token.id)
    msg += '\nSelect the token ID for removal:'

    await message.answer(msg, reply_markup=remove_cloudflare_token(ids))


@router.message(Command('help_create_new_token'))
async def help_create_new_token(message: Message, role: str):
    if role == 'guest':
        return
    msg = '''
    <b>How to create a Cloudflare token</b>

    <b>1.</b> Open:
    <b>Profile</b> -> <b>API Tokens</b> -> <b>Create Token</b>
    <a href="https://dash.cloudflare.com/profile/api-tokens">https://dash.cloudflare.com/profile/api-tokens</a>

    <b>2.</b> Choose template:
    <code>Edit zone DNS</code>

    <b>3.</b> Configure access:
    - <b>Permissions</b>: change <code>Edit</code> to <code>Read</code> (Zone DNS Read)
    - <b>Zone Resources</b>: change <code>Specific zone</code> to <code>All zones</code>

    <b>4.</b> Click <b>Continue to summary</b> and then <b>Create Token</b>
    '''
    await message.answer(dedent(msg), disable_web_page_preview=True)
