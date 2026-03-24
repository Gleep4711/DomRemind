from asyncio import to_thread
from datetime import timezone
import logging
from typing import Any, cast

from dateutil.parser import parse
from whodap import aio_lookup_domain
from whois21 import WHOIS

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
    'registrar expiration date',
    'registrar registration expiration date',
    'registry expiry date'
]
no_rdap_zones = [
    'ad', 'ae', 'af', 'ag', 'al', 'am', 'ao', 'ar', 'as', 'at', 'au', 'az',
    'ba', 'bd', 'be', 'bg', 'bf', 'bh', 'bi', 'bj', 'bn', 'bo', 'br', 'bs', 'bt', 'bw', 'by', 'bz',
    'ca', 'cat', 'cd', 'cf', 'cg', 'ch', 'ci', 'ck' 'cl', 'cm', 'cn', 'co', 'cr', 'cu', 'cv', 'cy', 'ce',
    'de', 'dj', 'dk', 'dm', 'do', ' dz',
    'ec', 'ee', 'eg', 'es', 'et',
    'fi', 'fj', 'fm', 'fr',
    'ga', 'ge', 'gg', 'gh', 'gi', 'gl', 'gm', 'gr', 'gt', 'gy',
    'hk', 'hn', 'hr', 'ht', 'hu',
    'id', 'ie', 'il', 'im', 'il', 'im', 'in', 'iq', 'is', 'it',
    'je', 'jm', 'jo',
    'ke', 'kh', 'ki', 'kg', 'kr', 'kw', 'kz',
    'la', 'lb', 'li', 'lk', 'ls', 'lt', 'lu', 'lv', 'ly',
    'ma', 'md', 'me', 'mg', 'mk', 'ml', 'mm', 'mn', 'my', 'mu', 'mv', 'mw', 'mx', 'my', 'mz',
    'na', 'ng', 'ni', 'ne', 'nl', 'no', 'np', 'nr', 'nu', 'nz',
    'om',
    'pa', 'pe', 'pg', 'ph', 'pk', 'pl', 'pn,' 'pr', 'ps', 'pt', 'py',
    'qa',
    'ro', 'rs', 'ru', 'rw',
    'sa', 'sb', 'sc', 'se', 'sg', 'sh', 'si', 'sk', 'sl', 'sn', 'so', 'sm', 'sr', 'st', 'sv',
    'td', 'tg', 'th', 'tj', 'tl', 'tm', 'tn', 'to', 'tt', 'tw', 'tz',
    'ua', 'ug', 'uk', 'uy', 'uz',
    'vc', 've', 'vi', 'vn', 'vu',
    'ws',
    'za', 'zm', 'zw'
]


async def get_expired_date(domain):
    d_data = domain.lower().split('.')
    try:
        if d_data[-1] in no_rdap_zones:
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
