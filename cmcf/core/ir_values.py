from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Literal


class IROperand(ABC):
    pass


@dataclass(frozen=True)
class IRConst(IROperand):
    value: int | float | str | None
    kind: Literal["int", "float", "string", "null", "undef", "zeroinit"]


@dataclass(frozen=True)
class IRRegister(IROperand):
    name: str


@dataclass(frozen=True)
class IRFunctionRef(IROperand):
    name: str


@dataclass(frozen=True)
class IRGlobalRef(IROperand):
    name: str


@dataclass(frozen=True)
class IRBlockRef(IROperand):
    name: str
