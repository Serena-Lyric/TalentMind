"""Small per-site configuration for the one shared Edge CDP engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

from app.collect.fetchers.job_sites import SITES

City = tuple[str, str]
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BOSS_CITIES: tuple[City, ...] = (
    ('北京', '101010100'), ('上海', '101020100'), ('深圳', '101280600'),
)
_ZHAOPIN_CITIES: tuple[City, ...] = (('北京', '530'), ('上海', '538'), ('深圳', '765'))
_LIEPIN_CITIES: tuple[City, ...] = (('北京', '北京'), ('上海', '上海'), ('深圳', '深圳'))


def _boss_search_url(keyword: str, city: str, page: int) -> str:
    return (
        'https://www.zhipin.com/web/geek/jobs?'
        f'city={quote_plus(city)}&query={quote_plus(keyword)}&page={int(page)}'
    )


@dataclass(frozen=True)
class PlatformDefinition:
    source: str
    label: str
    host_hint: str
    cities: tuple[City, ...]
    profile_dir: Path
    runtime_dir: Path
    search_url: Callable[[str, str, int], str]

    def url(self, keyword: str, city: str, page: int) -> str:
        return self.search_url(keyword, city, page)


PLATFORMS: dict[str, PlatformDefinition] = {
    'boss': PlatformDefinition(
        source='boss', label='BOSS直聘', host_hint='zhipin.com', cities=_BOSS_CITIES,
        profile_dir=_REPO_ROOT / 'data/local/collection/browser_profiles/boss',
        runtime_dir=_REPO_ROOT / 'data/local/collection/runtime/boss', search_url=_boss_search_url,
    ),
    'zhaopin': PlatformDefinition(
        source='zhaopin', label='智联招聘', host_hint='zhaopin.com', cities=_ZHAOPIN_CITIES,
        profile_dir=_REPO_ROOT / 'data/local/collection/browser_profiles/zhaopin',
        runtime_dir=_REPO_ROOT / 'data/local/collection/runtime/zhaopin',
        search_url=SITES['zhaopin'].search_url,
    ),
    'liepin': PlatformDefinition(
        source='liepin', label='猎聘', host_hint='liepin.com', cities=_LIEPIN_CITIES,
        profile_dir=_REPO_ROOT / 'data/local/collection/browser_profiles/liepin',
        runtime_dir=_REPO_ROOT / 'data/local/collection/runtime/liepin',
        search_url=SITES['liepin'].search_url,
    ),
}


@dataclass(frozen=True)
class RuntimeConfig:
    keywords: tuple[str, ...] = ('Python',)
    cities: dict[str, tuple[City, ...]] = field(default_factory=lambda: {
        source: definition.cities for source, definition in PLATFORMS.items()
    })
    pages: int = 1
    detail_limit: int = 1
    max_jobs: int = 1
    page_delay_min: float = 15.0
    page_delay_max: float = 30.0
    switch_interval_min: float = 360.0
    switch_interval_max: float = 720.0
    settle: float = 5.0

    def validate(self) -> None:
        if not self.keywords or any(not isinstance(value, str) or not value.strip() for value in self.keywords):
            raise ValueError('keywords must be a non-empty tuple of strings')
        if type(self.pages) is not int or self.pages < 1:
            raise ValueError('pages must be a positive integer')
        if type(self.detail_limit) is not int or self.detail_limit < 0:
            raise ValueError('detail_limit must be a non-negative integer')
        if type(self.max_jobs) is not int or self.max_jobs < 0:
            raise ValueError('max_jobs must be a non-negative integer')
        if not (15.0 <= self.page_delay_min <= self.page_delay_max <= 30.0):
            raise ValueError('page delays must be within 15..30 seconds')
        if not (360.0 <= self.switch_interval_min <= self.switch_interval_max <= 720.0):
            raise ValueError('switch intervals must be within 360..720 seconds')
        if self.settle < 5.0:
            raise ValueError('settle must be at least 5 seconds')
        for source in PLATFORMS:
            cities = self.cities.get(source)
            if not cities or any(not name or not code for name, code in cities):
                raise ValueError(f'cities missing for {source}')


def get_platform(platform: str) -> PlatformDefinition:
    try:
        return PLATFORMS[platform]
    except KeyError as exc:
        raise ValueError('unsupported collection runtime platform') from exc


def default_runtime_config() -> RuntimeConfig:
    return RuntimeConfig()


def config_from_payload(payload: RuntimeConfig | dict | None) -> RuntimeConfig:
    if isinstance(payload, RuntimeConfig):
        return payload
    if payload is None:
        return default_runtime_config()
    if not isinstance(payload, dict):
        raise ValueError('runtime config must be an object')
    values = dict(payload)
    values['keywords'] = tuple(values.get('keywords') or ())
    values['cities'] = {
        str(platform): tuple((str(city[0]), str(city[1])) for city in cities)
        for platform, cities in (values.get('cities') or {}).items()
    }
    return RuntimeConfig(**values)
