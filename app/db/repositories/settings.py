from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Settings


async def get_cf_tokens_for_user(session: AsyncSession, user_id: int) -> list[Settings]:
    result = await session.execute(
        select(Settings).filter(
            Settings.user_id == user_id,
            Settings.name == 'token',
            Settings.group == 'cloudflare',
        )
    )
    return list(result.scalars())


async def get_cf_token_by_id(
    session: AsyncSession, token_id: int, user_id: int
) -> Settings | None:
    result = await session.execute(
        select(Settings).filter(
            Settings.id == token_id,
            Settings.user_id == user_id,
            Settings.name == 'token',
            Settings.group == 'cloudflare',
        )
    )
    return result.scalar()


async def check_token_exists(session: AsyncSession, user_id: int, token: str) -> bool:
    result = await session.execute(
        select(Settings).filter(
            Settings.user_id == user_id,
            Settings.name == 'token',
            Settings.group == 'cloudflare',
            Settings.param == token,
        )
    )
    return result.scalar() is not None


async def add_cf_token(session: AsyncSession, user_id: int, token: str) -> None:
    session.add(Settings(user_id=user_id, name='token', group='cloudflare', param=token))


async def delete_cf_token(session: AsyncSession, token_id: int) -> None:
    await session.execute(delete(Settings).filter(Settings.id == token_id))


async def get_all_cf_tokens(session: AsyncSession) -> list[Settings]:
    result = await session.execute(
        select(Settings).filter(
            Settings.name == 'token',
            Settings.group == 'cloudflare',
        )
    )
    return list(result.scalars())
