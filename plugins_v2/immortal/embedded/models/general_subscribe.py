from datetime import datetime

from sqlalchemy import Column, Date, DateTime, func, BigInteger, String, Boolean

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class GeneralSubscribe(Base):
    __tablename__ = "general_subscribe"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    number_prefix: str = Column(String(255))
    publisher: str = Column(String(255))
    series: str = Column(String(255))
    producer: str = Column(String(255))
    genres = Column(ARRAY(String))
    max_coactors: int = Column(BigInteger)
    earliest_release_date = Column(Date)
    exclude_vr: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    filter_id: int = Column(BigInteger)
    priority_id: int = Column(BigInteger)
    status: str = Column(String, nullable=False, index=True)
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
