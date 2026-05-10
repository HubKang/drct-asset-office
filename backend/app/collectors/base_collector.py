from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCollector(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
