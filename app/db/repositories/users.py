from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Users


PERMANENT_BLOCK_UNTIL = datetime(9999, 12, 31, 23, 59, 59)


async def get_user(session: AsyncSession, user_id: int) -> Users | None:
    result = await session.execute(select(Users).filter(Users.id == user_id))
    return result.scalar_one_or_none()


async def set_user_state(session: AsyncSession, user_id: int, state: str) -> None:
    await session.execute(update(Users).filter(Users.id == user_id).values(state=state))


async def get_all_users(session: AsyncSession) -> list[Users]:
    result = await session.execute(select(Users))
    return list(result.scalars())


async def update_user_role(session: AsyncSession, user_id: int, role: str) -> None:
    await session.execute(update(Users).filter(Users.id == user_id).values(role=role))


async def set_user_blocked_until(
    session: AsyncSession, user_id: int, blocked_until: datetime | None
) -> None:
    await session.execute(
        update(Users).filter(Users.id == user_id).values(blocked_until=blocked_until)
    )


def is_user_blocked(user: Users | None) -> bool:
    if user is None or user.blocked_until is None:
        return False
    return user.blocked_until > datetime.utcnow()


def user_block_status_text(user: Users | None) -> str:
    if user is None or user.blocked_until is None:
        return 'not blocked'
    if user.blocked_until >= PERMANENT_BLOCK_UNTIL - timedelta(days=1):
        return 'permanent'
    return 'until {}'.format(user.blocked_until.strftime('%d.%m.%Y %H:%M UTC'))
