import logging

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings

import httpx

class PydanticSettings(BaseSettings):
    BOT_TOKEN: SecretStr = SecretStr("")
    DB_URL: PostgresDsn = PostgresDsn("postgresql://user:password@localhost/dbname")
    ADMIN: int = 0

    LOGGING: str = "ERROR"


config = PydanticSettings()

logging.basicConfig(
    level=getattr(logging, config.LOGGING.upper(), logging.ERROR),
    format="%(levelname)s: %(filename)s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

# Keep noisy third-party loggers aligned with configured level.
for logger_name in (
    "httpx",
    # "httpcore",
    "requests",
    # "urllib3",
    # "urllib3.connectionpool",
    # "psycopg",
    # "psycopg.pool",
    # "psycopg.connection",
    # "psycopg.cursor",
    # "chardet",
    # "chardet.charsetprober",
    # "charset_normalizer",
    "whois21",
    "log21",
    # "sqlalchemy",
    # "sqlalchemy.engine",
    # "sqlalchemy.engine.Engine",
    # "sqlalchemy.engine.base",
    # "sqlalchemy.pool",
    # "sqlalchemy.pool.base",
    # "sqlalchemy.pool.impl",
    # "sqlalchemy.pool.impl.AsyncAdaptedQueuePool",
    # "sqlalchemy.dialects",
    # "apscheduler",
):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    # if logger_name in ("httpx", "httpcore", "sqlalchemy"):
    #     logger.propagate = False
    for handler in logger.handlers:
        handler.setLevel(logging.ERROR)

# Disable httpx debug logging
for modname in ("main", "_main"):
    mod = getattr(httpx, modname, None)
    if mod and hasattr(mod, "trace"):
        mod.trace = lambda *args, **kwargs: None
        break