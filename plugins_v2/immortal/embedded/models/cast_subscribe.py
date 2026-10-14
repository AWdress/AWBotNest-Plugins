from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, String, func

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class CastSubscribe(Base):
    __tablename__ = 'cast_subscribe'

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    cast_id: int = Column(BigInteger, nullable=False, unique=True, index=True)
    max_coactors: int = Column(BigInteger)
    max_page: int = Column(BigInteger)
    replace_max_page: int = Column(BigInteger)
    is_single: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    earliest_release_date: date = Column(Date)
    exclude_vr: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    filter_id: int = Column(BigInteger)
    priority_id: int = Column(BigInteger)
    status: str = Column(String, nullable=False, index=True)
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
