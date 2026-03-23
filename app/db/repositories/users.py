from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Users


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
