from abc import ABC, abstractmethod
from app.collect.schema import RawJD, RawTalent


class Fetcher(ABC):
    """采集器抽象。实现类负责代理池/随机延迟/断点续爬。"""
    @abstractmethod
    def fetch(self) -> list[RawJD] | list[RawTalent]:
        ...
