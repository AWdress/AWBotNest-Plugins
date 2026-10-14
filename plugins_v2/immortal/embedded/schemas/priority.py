from typing import Optional, List

from pydantic import BaseModel


class PriorityForm(BaseModel):
    priority_name: str
    resolutions: List[str]
    subtitles: List[str]
    mosaic: List[str]
    priority_sort: List[str]
    is_default: bool


class UpdatePriorityForm(PriorityForm):
    id: int
