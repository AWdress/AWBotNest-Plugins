from datetime import datetime

from sqlalchemy import Column, String, BigInteger, DateTime, func, Text, Boolean

from ..core.database import Base
from ..core.portable_types import ARRAY, FALSE_DEFAULT, PrimaryKeyInteger


class Task(Base):
    __tablename__ = "task"

    id: int = Column(PrimaryKeyInteger, primary_key=True, autoincrement=True, index=True)
    task_name: str = Column(String(32), nullable=False)
    task_func: str = Column(String(32), nullable=False)
    task_args: str = Column(Text)
    task_cron: str = Column(String(32), nullable=False)
    enable: bool = Column(Boolean, nullable=True, index=True)
    push_enable: bool = Column(Boolean, nullable=False, server_default=FALSE_DEFAULT)
    push_title_template: str = Column(Text)
    push_message_template: str = Column(Text)
    create_time: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    update_time: datetime = Column(DateTime(timezone=True), onupdate=func.now())
