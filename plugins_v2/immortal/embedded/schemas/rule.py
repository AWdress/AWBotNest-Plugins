from typing import Optional

from pydantic import BaseModel, Field


class RuleForm(BaseModel):
    id: Optional[int] = None
    website: list[str] = Field(default_factory=lambda: ['ALL'])
    section: list[str] = Field(default_factory=lambda: ['ALL'])
    category: list[str] = Field(default_factory=lambda: ['ALL'])
    regex: Optional[str] = None
    downloader: str
    save_path: str
