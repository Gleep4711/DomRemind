import logging

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings


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
    "httpcore",
    "requests",
    "urllib3",
    "urllib3.connectionpool",
    "psycopg",
    "psycopg.pool",
    "psycopg.connection",
    "psycopg.cursor",
    "chardet",
    "chardet.charsetprober",
    "charset_normalizer",
    "whois21",
    "log21",
    "sqlalchemy",
    "apscheduler",
):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    for handler in logger.handlers:
        handler.setLevel(logging.ERROR)
