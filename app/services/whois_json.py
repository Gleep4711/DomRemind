import logging
from datetime import datetime, timezone

import httpx
from dateutil.parser import parse

from app.config_reader import config

_API_URL = 'https://whoisjson.com/api/v1/whois'


async def get_expiry_from_whoisjson(domain: str) -> datetime | None:
    """
    Fetch domain expiry date from the WhoisJSON API.

    Returns None when:
    - WHOISJSON_API_KEY is not set in the environment
    - The API returns no expiry data (e.g. .ro domains)
    - Any network or parsing error occurs

    Not integrated into the main lookup flow yet; call explicitly where needed.
    """
    api_key = config.WHOISJSON_API_KEY.get_secret_value()
    if not api_key:
        logging.debug('WHOISJSON_API_KEY not configured, skipping WhoisJSON lookup for %s', domain)
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(_API_URL, params={'domain': domain, 'apikey': api_key})
    except Exception as e:
        logging.error('WhoisJSON request failed for %s: %s', domain, e)
        return None

    if response.status_code != 200:
        logging.error('WhoisJSON returned HTTP %s for %s', response.status_code, domain)
        return None

    try:
        data = response.json()
    except Exception as e:
        logging.error('WhoisJSON invalid JSON response for %s: %s', domain, e)
        return None

    expires_raw = data.get('expires')
    if not expires_raw:
        logging.debug('WhoisJSON: no expiry date in response for %s', domain)
        return None

    try:
        return parse(str(expires_raw)).replace(tzinfo=timezone.utc)
    except Exception as e:
        logging.error('WhoisJSON: failed to parse expiry %r for %s: %s', expires_raw, domain, e)
        return None
