from datetime import datetime

from sqlalchemy import Column, String, BigInteger, DateTime, func, Text, Boolean

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Token(Base):
    __tablename__ = "token"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    token_key: str = Column(String(32), nullable=False)
    token_value: str = Column(String(255), nullable=False)
    create_time: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
