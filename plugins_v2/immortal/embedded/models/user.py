from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, func

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class User(Base):
    __tablename__ = "user"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    username: str = Column(String(32), unique=True, index=True, nullable=False)
    hashed_password: str = Column(String(128), nullable=False)
    is_active: int = Column(Integer, server_default="1")
    create_time: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), server_onupdate=func.now())
