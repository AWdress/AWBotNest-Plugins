from datetime import date
from typing import Optional


from pydantic import BaseModel, Field

from ..enums import SubscribeStatus


class SubscribeParam(BaseModel):
    movie_id: int
    filter_id: Optional[int] = None
    priority_id: Optional[int] = None
    pre_download_enabled: Optional[bool] = None
    inherit_pre_download_from_filter: bool = False


class SubscribeUpdateParam(BaseModel):
    subscribe_id: int
    filter_id: Optional[int] = None
    priority_id: Optional[int] = None
    pre_download_enabled: Optional[bool] = None


class CastSubscribeParam(BaseModel):
    cast_id: int
    max_coactors: Optional[int] = Field(default=None, ge=0)
    max_page: Optional[int] = Field(default=None, ge=1)
    replace_max_page: Optional[int] = Field(default=1, ge=1)
    is_single: bool = False
    earliest_release_date: Optional[date] = None
    exclude_vr: bool = False
    filter_id: Optional[int] = None
    priority_id: Optional[int] = None


class CastSubscribeUpdateParam(BaseModel):
    cast_subscribe_id: int
    max_coactors: Optional[int] = Field(default=None, ge=0)
    max_page: Optional[int] = Field(default=None, ge=1)
    replace_max_page: Optional[int] = Field(default=None, ge=1)
    is_single: bool = False
    earliest_release_date: Optional[date] = None
    exclude_vr: bool = False
    filter_id: Optional[int] = None
    priority_id: Optional[int] = None


class GeneralSubscribeParam(BaseModel):
    number_prefix: Optional[str] = None
    publisher: Optional[str] = None
    series: Optional[str] = None
    producer: Optional[str] = None
    genres: Optional[list[str]] = None
    max_coactors: Optional[int] = Field(default=None, ge=0)
    earliest_release_date: Optional[date] = None
    exclude_vr: bool = False
    filter_id: Optional[int] = None
    priority_id: Optional[int] = None


class GeneralSubscribeUpdateParam(BaseModel):
    general_subscribe_id: int
    number_prefix: Optional[str] = None
    publisher: Optional[str] = None
    series: Optional[str] = None
    producer: Optional[str] = None
    genres: Optional[list[str]] = None
    max_coactors: Optional[int] = Field(default=None, ge=0)
    earliest_release_date: Optional[date] = None
    exclude_vr: bool = False
    filter_id: Optional[int] = None
    priority_id: Optional[int] = None


class GeneralSubscribePageParam(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: Optional[str] = None
    status: Optional[SubscribeStatus] = None


class SubscribeCleanupDiagnosticParam(BaseModel):
    include_inactive: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    candidate_types: Optional[list[str]] = None
    movie_id: Optional[int] = None
    subscribe_id: Optional[int] = None
    cast_subscribe_id: Optional[int] = None
    general_subscribe_id: Optional[int] = None


class SubscribePageParam(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)
    keyword: Optional[str] = None
    status: Optional[SubscribeStatus] = None
    release_date_start: Optional[date] = None
    release_date_end: Optional[date] = None


class CastSubscribePageParam(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: Optional[str] = None
    status: Optional[SubscribeStatus] = None
