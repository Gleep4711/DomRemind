from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Domains, UserDomain


async def get_user_domains(session: AsyncSession, user_id: int) -> list[Domains]:
    result = await session.execute(
        select(Domains)
        .join(UserDomain, UserDomain.domain_id == Domains.id)
        .filter(UserDomain.user_id == user_id)
        .order_by(Domains.expired_date)
    )
    return list(result.scalars())


async def count_user_domains(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(UserDomain)
        .filter(UserDomain.user_id == user_id)
    )
    return int(result.scalar_one())


async def find_user_domain_link(session: AsyncSession, user_id: int, domain_name: str) -> bool:
    result = await session.execute(
        select(UserDomain)
        .join(Domains, Domains.id == UserDomain.domain_id)
        .filter(UserDomain.user_id == user_id, Domains.domain == domain_name)
    )
    return result.scalar() is not None


async def get_domain_by_name(session: AsyncSession, domain_name: str) -> Domains | None:
    result = await session.execute(select(Domains).filter(Domains.domain == domain_name))
    return result.scalar()


async def create_domain(session: AsyncSession, domain_name: str, expired_date: datetime) -> Domains:
    domain_row = Domains(
        domain=domain_name,
        expired_date=expired_date,
        last_check=datetime.now(timezone.utc),
    )
    session.add(domain_row)
    await session.flush()
    return domain_row


async def link_user_domain(session: AsyncSession, user_id: int, domain_id: int) -> None:
    session.add(UserDomain(user_id=user_id, domain_id=domain_id))


async def get_domain_for_user(
    session: AsyncSession, user_id: int, domain_name: str
) -> Domains | None:
    result = await session.execute(
        select(Domains)
        .join(UserDomain, UserDomain.domain_id == Domains.id)
        .filter(UserDomain.user_id == user_id, Domains.domain == domain_name)
    )
    return result.scalar()


async def unlink_user_domain(session: AsyncSession, user_id: int, domain_id: int) -> None:
    await session.execute(
        delete(UserDomain).filter(
            UserDomain.user_id == user_id,
            UserDomain.domain_id == domain_id,
        )
    )


async def delete_domain_if_orphan(session: AsyncSession, domain_id: int) -> None:
    has_links = (
        await session.execute(select(UserDomain).filter(UserDomain.domain_id == domain_id))
    ).first()
    if not has_links:
        await session.execute(delete(Domains).filter(Domains.id == domain_id))


async def get_all_domains(session: AsyncSession) -> list[Domains]:
    result = await session.execute(select(Domains))
    return list(result.scalars())


async def update_domain_expiry(
    session: AsyncSession, domain_name: str, expires_date: datetime
) -> None:
    await session.execute(
        update(Domains)
        .filter(Domains.domain == domain_name)
        .values(expired_date=expires_date, last_check=datetime.now(timezone.utc))
    )


async def get_users_for_domain(session: AsyncSession, domain_name: str) -> list[int]:
    result = await session.execute(
        select(UserDomain.user_id)
        .join(Domains, Domains.id == UserDomain.domain_id)
        .filter(Domains.domain == domain_name)
    )
    return list(result.scalars())


async def get_domain_counts_by_user(session: AsyncSession) -> dict[int, int]:
    result = await session.execute(
        select(UserDomain.user_id, func.count(UserDomain.domain_id))
        .group_by(UserDomain.user_id)
    )
    return {int(user_id): int(domain_count) for user_id, domain_count in result.all()}


async def get_domain_statistics(session: AsyncSession) -> dict[str, int]:
    total_links = await session.execute(select(func.count()).select_from(UserDomain))
    total_domains = await session.execute(select(func.count()).select_from(Domains))
    users_with_domains = await session.execute(select(func.count(func.distinct(UserDomain.user_id))))
    return {
        'total_links': int(total_links.scalar_one()),
        'total_domains': int(total_domains.scalar_one()),
        'users_with_domains': int(users_with_domains.scalar_one()),
    }
