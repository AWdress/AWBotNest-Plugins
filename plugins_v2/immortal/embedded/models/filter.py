from datetime import datetime
from typing import List

from sqlalchemy import Column, String, BigInteger, DateTime, func, Text, Boolean

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Filter(Base):
    __tablename__ = "filter"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    filter_name: str = Column(Text, nullable=False)
    keyword: str = Column(Text)
    regex: str = Column(Text)
    resolutions: List[str] = Column(ARRAY(String))
    subtitles: List[str] = Column(ARRAY(String))
    mosaic: List[str] = Column(ARRAY(String))
    min_size: int = Column(BigInteger)
    max_size: int = Column(BigInteger)
    skip_in_library_check: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    enable_pre_download: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    is_default: bool = Column(Boolean, nullable=False)
    create_time: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
