from __future__ import annotations

from dataclasses import dataclass

from cmcf.core.ir_values import IROperand


@dataclass(frozen=True)
class IRInstruction:
    opcode: str
    result: str | None
    operands: tuple[IROperand, ...]
    predicate: str | None = None
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class IRParameter:
    name: str
    index: int


@dataclass(frozen=True)
class IRBlock:
    label: str
    instructions: tuple[IRInstruction, ...]


@dataclass(frozen=True)
class IRFunction:
    name: str
    params: tuple[IRParameter, ...]
    blocks: tuple[IRBlock, ...]
    is_declaration: bool


@dataclass(frozen=True)
class IRModule:
    source_file: str
    functions: tuple[IRFunction, ...]
