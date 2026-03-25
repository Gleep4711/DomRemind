from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Users(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, autoincrement=False)
    role: Mapped[Optional[str]] = mapped_column(String, default='user')
    state: Mapped[Optional[str]] = mapped_column(String, default='')
    is_bot: Mapped[Optional[str]] = mapped_column(String, default='')
    first_name: Mapped[Optional[str]] = mapped_column(String, default='')
    last_name: Mapped[Optional[str]] = mapped_column(String, default='')
    username: Mapped[Optional[str]] = mapped_column(String, default='')
    language_code: Mapped[Optional[str]] = mapped_column(String, default='')
    is_premium: Mapped[Optional[str]] = mapped_column(String, default='')
    added_to_attachment_menu: Mapped[Optional[str]] = mapped_column(String, default='')
    can_join_groups: Mapped[Optional[str]] = mapped_column(String, default='')
    can_read_all_group_messages: Mapped[Optional[str]] = mapped_column(String, default='')
    supports_inline_queries: Mapped[Optional[str]] = mapped_column(String, default='')
    blocked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)

class Domains(Base):
    __tablename__ = 'domains'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, autoincrement=True)
    domain: Mapped[Optional[str]] = mapped_column(String, default='')
    expired_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime)


class UserDomain(Base):
    __tablename__ = 'user_domains'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey('domains.id', ondelete='CASCADE'), primary_key=True)


class Settings(Base):
    __tablename__ = 'settings'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[Optional[str]] = mapped_column(String, default='')
    group: Mapped[Optional[str]] = mapped_column(String, default='')
    param: Mapped[Optional[str]] = mapped_column(String, default='')


class TldZone(Base):
    __tablename__ = 'tld_zones'

    tld: Mapped[str] = mapped_column(String, primary_key=True)
    has_rdap: Mapped[bool] = mapped_column(default=False)
    rdap_url: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
