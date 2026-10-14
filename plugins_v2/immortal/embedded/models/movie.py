from datetime import datetime, date
from typing import  List

from sqlalchemy import Column, String, Integer, Text, Date, DateTime, func, BigInteger

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Movie(Base):
    __tablename__ = "movie"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    number: str = Column(String(255), nullable=False, unique=True, index=True)
    title: str = Column(Text)
    cn_title: str = Column(Text)
    description: str = Column(Text)
    cn_description: str = Column(Text)
    release_date: date = Column(Date, index=True)
    duration: int = Column(Integer)
    poster: str = Column(String(255))
    banner: str = Column(String(255))
    still_photos: List[str] = Column(ARRAY(Text))
    genres: List[str] = Column(ARRAY(String))
    series: str = Column(String(255))
    producer: str = Column(String(255))
    publisher: str = Column(String(255))
    casts: List[int] = Column(ARRAY(Integer))
    cast_names: List[str] = Column(ARRAY(String(255)))
    create_time: datetime = Column(DateTime(timezone=True), server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
