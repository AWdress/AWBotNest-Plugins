from datetime import datetime

from sqlalchemy import Column,  String, BigInteger, DateTime, func, Text

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Config(Base):
    __tablename__ = "config"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)

    key: str = Column(String(32), unique=True, index=True, nullable=False)
    content: str = Column(Text)
    create_time: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
