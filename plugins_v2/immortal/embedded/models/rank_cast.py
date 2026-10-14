from datetime import datetime
from typing import List

from sqlalchemy import Column, String, DateTime, func, BigInteger

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class RankCast(Base):
    __tablename__ = "rank_cast"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    rank_name: str = Column(String(255), nullable=False)
    cast_ids: List[int] = Column(ARRAY(BigInteger), nullable=False)
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
