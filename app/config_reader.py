from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: SecretStr
    db_url: PostgresDsn
    admin: int

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
    )


config = Settings()
