from datetime import datetime
from typing import List

from sqlalchemy import Column, String, BigInteger, DateTime, func

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Rule(Base):
    __tablename__ = "rule"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    website: List[str] = Column(ARRAY(String(255)))
    section: List[str] = Column(ARRAY(String(255)), nullable=False)
    category: List[str] = Column(ARRAY(String(255)), nullable=False)
    regex: str = Column(String(255), nullable=False)
    downloader: str = Column(String(255), nullable=False)
    save_path: str = Column(String(255), nullable=False)
    create_time: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
