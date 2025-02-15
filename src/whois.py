from whodap import aio_lookup_domain
from dateutil.parser import parse
from pytz import UTC
from whois21 import WHOIS
from asyncio import to_thread

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
    'de', 'dj', 'dk', 'dm', 'do',' dz',
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
        print('\n\nget_expired_date {}\n{}\n\n'.format(domain, e))
        return None


async def get_whois_21(d_data):
    domain = '{}.{}'.format(d_data[-2], d_data[-1])
    try:
        # w = WHOIS(domain)
        w = await to_thread(WHOIS, domain)
    except Exception as e:
        print('whois check {}'.format(domain), e)
        return None
    if not w.success:
        print('\n\nget_whois_21 {}\n{}\n\n'.format(domain, w.error))
        return None
    for key in w.whois_data:
        if key.lower() in records:
            return parse(str(w.whois_data[key])).replace(tzinfo=UTC)
    print('\n\nget_whois_21 not expired date\n{}\n{}\n\n'.format(domain, w.whois_data))
    return None

async def get_whodap(d_data):
    try:
        w = await aio_lookup_domain(domain=d_data[-2], tld=d_data[-1])
        info = w.to_whois_dict()
        expires_date = info['expires_date']
        if not info['expires_date']:
            for ev in w.events:
                if ev.eventAction.lower() in records:
                    expires_date = ev.eventDate
                    break
        return parse(str(expires_date)).replace(tzinfo=UTC)
    except Exception as e:
        print('\n\nget_whodap {}\n{}\n\n'.format(d_data, e))
        return await get_whois_21(d_data)

