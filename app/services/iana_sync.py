import logging
from datetime import datetime, timezone

from aiogram import Bot
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories import tld_zones as tld_zones_repo
from app.config_reader import config

IANA_RDAP_DNS_URL = 'https://data.iana.org/rdap/dns.json'
IANA_TLD_LIST_URL = 'https://data.iana.org/TLD/tlds-alpha-by-domain.txt'


async def sync_iana_zones(bot: Bot, session_pool: async_sessionmaker[AsyncSession]) -> None:
    """Fetch all TLD zones from IANA and store them in DB."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            rdap_resp = await client.get(IANA_RDAP_DNS_URL)
            rdap_resp.raise_for_status()
            tld_resp = await client.get(IANA_TLD_LIST_URL)
            tld_resp.raise_for_status()
    except Exception as e:
        logging.error('IANA sync failed during HTTP fetch: %s', e)
        return

    # Build tld -> rdap_url mapping from the bootstrap JSON
    rdap_zones: dict[str, str] = {}
    for entry in rdap_resp.json().get('services', []):
        tlds, urls = entry[0], entry[1]
        url = urls[0] if urls else None
        for tld in tlds:
            rdap_zones[tld.lower()] = url if url else ""

    # All officially delegated TLDs from the IANA root zone list
    all_tlds: set[str] = {
        line.strip().lower()
        for line in tld_resp.text.splitlines()
        if line.strip() and not line.startswith('#')
    }

    now = datetime.now(timezone.utc)

    # Merge: start with all official TLDs, add any punycode zones only in RDAP list
    combined = all_tlds | rdap_zones.keys()
    zones = [
        {
            'tld': tld,
            'has_rdap': tld in rdap_zones,
            'rdap_url': rdap_zones.get(tld),
            'updated_at': now,
        }
        for tld in combined
    ]

    async with session_pool() as session:
        await tld_zones_repo.upsert_zones(session, zones)
        await session.commit()

    logging.info(
        'IANA sync complete: %d total zones stored, %d with RDAP',
        len(zones),
        len([z for z in zones if z['has_rdap']]),
    )

    msg = 'IANA sync complete: {} total zones stored, {} with RDAP'.format(
        len(zones),
        len([z for z in zones if z['has_rdap']]),
    )
    await bot.send_message(chat_id=config.ADMIN, text=msg)

