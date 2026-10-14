from datetime import datetime, date
from typing import  List

from sqlalchemy import Column, String, Integer, Text, Date, DateTime, func, BigInteger,UniqueConstraint

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Article(Base):
    __tablename__ = "article"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    tid: int = Column(BigInteger, nullable=False)
    title: str = Column(String(255), nullable=False)
    match_number: str = Column(String(64), index=True)
    publish_date: date = Column(Date, index=True)
    magnet: List[str] = Column(ARRAY(Text))
    edk: List[str] = Column(ARRAY(Text))
    preview_images: List[str] = Column(ARRAY(Text))
    detail_url: str = Column(String(255))
    size: int = Column(BigInteger)
    section: str = Column(String(255), nullable=False, index=True)
    category: str = Column(String(255), index=True)
    website: str = Column(String(32), index=True)
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tid", "website", name="uix_tid_website"),
    )
