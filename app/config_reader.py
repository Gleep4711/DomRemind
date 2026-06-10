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
)

# Keep noisy third-party loggers aligned with configured level.
for logger_name in (
    "httpx",
    "httpcore",
    "requests",
    "urllib3",
    "urllib3.connectionpool",
    "sqlalchemy",
):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    for handler in logger.handlers:
        handler.setLevel(logging.ERROR)

# Keep misfire warnings ("Run time of job ... was missed by ...") visible
# even when the global level is ERROR.
logging.getLogger("apscheduler").setLevel(logging.WARNING)
