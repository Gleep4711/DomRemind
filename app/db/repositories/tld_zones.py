from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TldZone


async def upsert_zones(session: AsyncSession, zones: list[dict]) -> None:
    """Bulk-upsert TLD zone records (insert or update on conflict)."""
    if not zones:
        return
    stmt = pg_insert(TldZone).values(zones)
    stmt = stmt.on_conflict_do_update(
        index_elements=[TldZone.tld],
        set_={
            'has_rdap': stmt.excluded.has_rdap,
            'rdap_url': stmt.excluded.rdap_url,
            'updated_at': stmt.excluded.updated_at,
        },
    )
    await session.execute(stmt)


async def get_rdap_tlds(session: AsyncSession) -> set[str]:
    """Return the set of TLD strings that have an RDAP endpoint."""
    result = await session.execute(
        select(TldZone.tld).where(TldZone.has_rdap == True)  # noqa: E712
    )
    return {row[0] for row in result}


async def get_zone_count(session: AsyncSession) -> int:
    result = await session.execute(select(TldZone))
    return len(result.all())


async def get_zone_has_rdap(session: AsyncSession, tld: str) -> bool | None:
    """Return has_rdap for a TLD, or None if zone is absent in DB."""
    result = await session.execute(
        select(TldZone.has_rdap).where(TldZone.tld == tld.lower())
    )
    return result.scalar_one_or_none()
