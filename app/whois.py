import logging
from asyncio import to_thread
from datetime import datetime, timezone
from typing import Any, cast

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from whodap import aio_lookup_domain
from whois21 import WHOIS

from app.db.repositories import tld_zones as tld_zones_repo

# TLDs where the registry WHOIS server never publishes expiry dates.
# Domains in these zones are tracked with an estimated expiry (creation + 1 year).
UNSUPPORTED_ZONES: frozenset[str] = frozenset(['ro'])

records = [
    'expires    on',
    'expires on',
    'expires_on',
    'expire',
    'paid-till',
    'paid_till',
    'free-date',
    'free_date',
    'expiration date',
    'expiration',
    'registrar expiration',
    'registrar expiration date',
    'registrar registration expiration date',
    'registry expiry date'
]

# Legacy fallback for zones that are not found in DB.
no_rdap_zones: frozenset[str] = frozenset([
    'ad', 'ae', 'af', 'ag', 'al', 'am', 'ao', 'ar', 'as', 'at', 'au', 'az',
    'ba', 'bd', 'be', 'bg', 'bf', 'bh', 'bi', 'bj', 'bn', 'bo', 'br', 'bs', 'bt', 'bw', 'by', 'bz',
    'ca', 'cat', 'cd', 'cf', 'cg', 'ch', 'ci', 'ck', 'cl', 'cm', 'cn', 'co', 'cr', 'cu', 'cv', 'cy',
    'de', 'dj', 'dk', 'dm', 'do', 'dz',
    'ec', 'ee', 'eg', 'es', 'et',
    'fi', 'fj', 'fm', 'fr',
    'ga', 'ge', 'gg', 'gh', 'gi', 'gl', 'gm', 'gr', 'gt', 'gy',
    'hk', 'hn', 'hr', 'ht', 'hu',
    'id', 'ie', 'il', 'im', 'in', 'iq', 'is', 'it',
    'je', 'jm', 'jo',
    'ke', 'kh', 'ki', 'kg', 'kr', 'kw', 'kz',
    'la', 'lb', 'li', 'lk', 'ls', 'lt', 'lu', 'lv', 'ly',
    'ma', 'md', 'me', 'mg', 'mk', 'ml', 'mm', 'mn', 'mu', 'mv', 'mw', 'mx', 'my', 'mz',
    'na', 'ng', 'ni', 'ne', 'nl', 'no', 'np', 'nr', 'nu', 'nz',
    'om',
    'pa', 'pe', 'pg', 'ph', 'pk', 'pl', 'pn', 'pr', 'ps', 'pt', 'py',
    'qa',
    'ro', 'rs', 'ru', 'rw',
    # IDN ccTLDs without RDAP (ACE form); .рф = xn--p1ai
    'xn--p1ai',
    'sa', 'sb', 'sc', 'se', 'sg', 'sh', 'si', 'sk', 'sl', 'sn', 'so', 'sm', 'sr', 'st', 'sv',
    'td', 'tg', 'th', 'tj', 'tl', 'tm', 'tn', 'to', 'tt', 'tw', 'tz',
    'ua', 'ug', 'uk', 'uy', 'uz',
    'vc', 've', 'vi', 'vn', 'vu',
    'ws',
    'za', 'zm', 'zw',
])

async def get_expired_date(session: AsyncSession, domain: str):
    # Normalize IDN (e.g. Cyrillic) domains to ACE/Punycode before any lookup.
    # WHOIS servers and RDAP only accept ASCII labels
    try:
        domain = '.'.join(
            label.encode('idna').decode('ascii')
            for label in domain.lower().split('.')
        )
    except (UnicodeError, UnicodeDecodeError):
        logging.warning('IDNA encoding failed for domain %r; proceeding as-is', domain)

    d_data = domain.lower().split('.')
    tld = d_data[-1]
    try:
        zone_has_rdap = await tld_zones_repo.get_zone_has_rdap(session, tld)
        if zone_has_rdap is None:
            use_whois = tld in no_rdap_zones
        else:
            use_whois = not zone_has_rdap
        if use_whois:
            return await get_whois_21(d_data)
        else:
            return await get_whodap(d_data)
    except Exception as e:
        logging.error(f"Error getting expired date for domain {domain}: {e}")
        return None


async def get_whois_21(d_data):
    domain = '{}.{}'.format(d_data[-2], d_data[-1])
    try:
        # w = WHOIS(domain)
        w = await to_thread(WHOIS, domain)
    except Exception as e:
        logging.error(f"Error checking whois for domain {domain}: {e}")
        return None
    if not w.success:
        logging.error(f"WHOIS check failed for domain {domain}: {w.error}")
        return None
    for key in w.whois_data:
        if key.lower() in records:
            return parse(str(w.whois_data[key])).replace(tzinfo=timezone.utc)
    logging.error(f"WHOIS check did not return an expiration date for domain {domain}: {w.whois_data}")
    return None


_creation_records = [
    'registered on',
    'registered',
    'created on',
    'creation date',
    'created',
    'domain registration date',
]


async def get_estimated_expiry_for_unsupported(d_data: list[str]) -> 'datetime | None':
    """Return creation_date + 1 year for zones that never publish expiry via WHOIS/RDAP."""
    domain = '{}.{}'.format(d_data[-2], d_data[-1])
    try:
        w = await to_thread(WHOIS, domain)
    except Exception as e:
        logging.error('WHOIS error for unsupported zone %s: %s', domain, e)
        return None
    if not w.success:
        logging.error('WHOIS failed for unsupported zone %s: %s', domain, w.error)
        return None
    for key in w.whois_data:
        if key.lower() in _creation_records:
            try:
                create_date = parse(str(w.whois_data[key])).replace(tzinfo=timezone.utc)
                return create_date + relativedelta(years=1)
            except Exception as e:
                logging.error('Cannot parse creation date for %s from %r: %s', domain, w.whois_data[key], e)
    logging.error('No creation date field found in WHOIS for %s: %s', domain, list(w.whois_data.keys()))
    return None


async def get_whodap(d_data):
    try:
        w = await aio_lookup_domain(domain=d_data[-2], tld=d_data[-1])
        info = cast(dict[str, Any], w.to_whois_dict())
        expires_date = info.get('expires_date')
        if not expires_date:
            events = w.events
            if isinstance(events, (list, tuple)):
                for ev in events:
                    if ev.eventAction.lower() in records:
                        expires_date = ev.eventDate
                        break
        if not expires_date:
            return await get_whois_21(d_data)
        return parse(str(expires_date)).replace(tzinfo=timezone.utc)
    except Exception as e:
        logging.error(f"Error getting whodap data for domain {d_data}: {e}")
        return await get_whois_21(d_data)
