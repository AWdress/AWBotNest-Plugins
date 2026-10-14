from typing import Optional

from pydantic import BaseModel, Field


class MovieSearchParam(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: Optional[str] = None


class MovieRecommendParam(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=100)
