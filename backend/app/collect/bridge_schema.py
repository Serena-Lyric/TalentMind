"""Strict wire contract for explicit browser captures."""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "m1-browser-bridge-v1"
MAX_LIST_ITEMS = 5
MAX_DETAIL_CHARS = 100_000
_BOSS_HOSTS = {"zhipin.com", "www.zhipin.com", "m.zhipin.com"}
_HTML_TAG = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


def _is_boss_url(value: str, *, detail: bool | None) -> bool:
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.hostname not in _BOSS_HOSTS:
        return False
    if parts.username or parts.password or parts.port not in (None, 443):
        return False
    if detail is None:
        return True
    if detail:
        return parts.path.startswith("/job_detail/") and parts.path.rstrip("/") != "/job_detail"
    return parts.path.startswith("/web/geek/job")


def _plain_visible_text(value: str, *, field: str) -> str:
    if _HTML_TAG.search(value):
        raise ValueError(f"{field} must be visible text, not HTML")
    return value


class BridgeListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=256)
    company: str = Field(default="", max_length=256)
    salary: str = Field(default="", max_length=128)
    location: str = Field(default="", max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("url")
    @classmethod
    def boss_detail_url(cls, value: str) -> str:
        if not _is_boss_url(value, detail=True):
            raise ValueError("only BOSS HTTPS job-detail URLs are accepted")
        return value

    @field_validator("title", "company", "salary", "location")
    @classmethod
    def visible_text(cls, value: str, info) -> str:
        return _plain_visible_text(value, field=info.field_name)

    @field_validator("tags")
    @classmethod
    def visible_tags(cls, value: list[str]) -> list[str]:
        return [_plain_visible_text(tag, field="tag")[:80] for tag in value if tag.strip()]


class BridgeDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=256)
    company: str = Field(default="", max_length=256)
    salary: str = Field(default="", max_length=128)
    location: str = Field(default="", max_length=128)
    experience: str = Field(default="", max_length=128)
    degree: str = Field(default="", max_length=128)
    description: str = Field(default="", max_length=MAX_DETAIL_CHARS)
    company_info: str = Field(default="", max_length=20_000)
    description_truncated: bool = False
    challenge_detected: bool = False

    @field_validator("url")
    @classmethod
    def boss_detail_url(cls, value: str) -> str:
        if not _is_boss_url(value, detail=True):
            raise ValueError("only BOSS HTTPS job-detail URLs are accepted")
        return value

    @field_validator("title", "company", "salary", "location", "experience", "degree")
    @classmethod
    def visible_text(cls, value: str, info) -> str:
        return _plain_visible_text(value, field=info.field_name)

    @field_validator("description", "company_info")
    @classmethod
    def visible_body(cls, value: str, info) -> str:
        return _plain_visible_text(value, field=info.field_name)


class BridgeCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["m1-browser-bridge-v1"]
    kind: Literal["list", "detail", "blocked"]
    blocked_reason: Literal['security_verification'] | None = None
    page_url: str = Field(min_length=1, max_length=2048)
    items: list[BridgeListItem] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    detail: BridgeDetail | None = None

    @model_validator(mode="after")
    def shape_matches_kind(self):
        if self.kind == 'blocked':
            if (not _is_boss_url(self.page_url, detail=None) or self.blocked_reason is None
                    or self.items or self.detail is not None):
                raise ValueError('blocked capture requires only a BOSS page URL and access reason')
            return self
        if self.blocked_reason is not None:
            raise ValueError('job content cannot carry a blocked-page reason')
        if self.kind == "list":
            if not _is_boss_url(self.page_url, detail=False):
                raise ValueError("list page must be a BOSS HTTPS search page")
            if self.detail is not None or not self.items:
                raise ValueError("list capture requires 1-5 items and no detail")
        else:
            if self.items or self.detail is None:
                raise ValueError("detail capture requires one detail and no list items")
            if _url_key(self.page_url) != _url_key(self.detail.url):
                raise ValueError("detail page URL must match the captured job URL")
        return self


class BridgeSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["boss"] = "boss"
    keyword: str = Field(min_length=1, max_length=80)
    city_name: str = Field(min_length=1, max_length=40)
    city_code: str = Field(min_length=1, max_length=16, pattern=r"^\d+$")
    pages: int = Field(default=1, ge=1, le=1)
    detail_limit: int = Field(default=5, ge=1, le=5)
    max_jobs: int = Field(default=5, ge=1, le=5)

    @field_validator("keyword", "city_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


def _url_key(value: str) -> tuple[str, str, str, str]:
    parts = urlsplit(value)
    return parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query


def validate_capture(payload: dict) -> BridgeCapture:
    return BridgeCapture.model_validate(payload)
