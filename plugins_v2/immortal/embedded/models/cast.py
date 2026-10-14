from datetime import datetime
from typing import List

from sqlalchemy import Column, String,  DateTime, func, BigInteger

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Cast(Base):
    __tablename__ = "cast"

    id: int = Column(PrimaryKeyInteger, primary_key=True,autoincrement=True, index=True)
    name: str = Column(String(255), nullable=False,unique=True, index=True)
    cn_name: str = Column(String(255))
    former_name: List[str] = Column(ARRAY(String(255)))
    avatar: str = Column(String(255))
    photo: str = Column(String(255))
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
