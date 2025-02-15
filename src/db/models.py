from sqlalchemy import Column, BigInteger, String, DateTime, Sequence

from bot.db.base import Base


class Users(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True, unique=True, autoincrement=False)
    role = Column(String, default='user')
    state = Column(String, default='')
    is_bot = Column(String, default='')
    first_name = Column(String, default='')
    last_name = Column(String, default='')
    username = Column(String, default='')
    language_code = Column(String, default='')
    is_premium = Column(String, default='')
    added_to_attachment_menu = Column(String, default='')
    can_join_groups = Column(String, default='')
    can_read_all_group_messages = Column(String, default='')
    supports_inline_queries = Column(String, default='')

class Domains(Base):
    __tablename__ = 'domains'

    id = Column(BigInteger, primary_key=True, unique=True, autoincrement=True)
    user_id = Column(BigInteger)
    domain = Column(String, default = '')
    expired_date = Column(DateTime, default = '')
    last_check = Column(DateTime, default = '')


class Settings(Base):
    __tablename__ = 'settings'

    id = Column(BigInteger, primary_key=True, unique=True, autoincrement=True)
    user_id = Column(BigInteger)
    name = Column(String, default = '')
    group = Column(String, default = '')
    param = Column(String, default = '')
