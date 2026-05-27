from __future__ import annotations

from abc import ABC, abstractmethod


class SysCallHandler(ABC):
    name: str

    @abstractmethod
    def describe(self) -> str:
        ...
