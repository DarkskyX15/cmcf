from __future__ import annotations

from abc import ABC
from dataclasses import dataclass


class IRType(ABC):
    pass


@dataclass(frozen=True)
class VoidType(IRType):
    pass


@dataclass(frozen=True)
class IntegerType(IRType):
    width: int


@dataclass(frozen=True)
class PointerType(IRType):
    pointee: IRType | None = None


@dataclass(frozen=True)
class FunctionType(IRType):
    return_type: IRType
    param_types: tuple[IRType, ...]
    is_vararg: bool = False


@dataclass(frozen=True)
class ArrayType(IRType):
    element_type: IRType
    size: int


I1 = IntegerType(1)
I8 = IntegerType(8)
I32 = IntegerType(32)
I64 = IntegerType(64)
VOID = VoidType()
