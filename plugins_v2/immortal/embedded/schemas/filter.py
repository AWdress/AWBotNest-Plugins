from typing import Optional, List

from pydantic import BaseModel


class FilterForm(BaseModel):
    filter_name: str
    keyword: str
    regex: Optional[str] = None
    resolutions: Optional[List[str]] = None
    subtitles: Optional[List[str]] = None
    mosaic: Optional[List[str]] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    skip_in_library_check: bool = False
    enable_pre_download: bool = False
    is_default: bool


class UpdateFilterForm(FilterForm):
    id: int
