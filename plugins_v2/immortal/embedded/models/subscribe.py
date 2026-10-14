from datetime import datetime

from sqlalchemy import Column, DateTime, func, BigInteger, String, UniqueConstraint, Boolean
from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Subscribe(Base):
    __tablename__ = "subscribe"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    movie_id: int = Column(BigInteger, nullable=False, unique=True, index=True)
    filter_id: int = Column(BigInteger)
    priority_id: int = Column(BigInteger)
    pre_download_enabled: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    status: str = Column(String, nullable=False, index=True)
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now(), index=True)
