from __future__ import annotations

from dataclasses import dataclass, field

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
    param_type: str = ""                  # "i32", "ptr", "float" — 从 llvmlite 提取


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
    return_type: str | None = None        # "i32" / "void" / None
    annotations: frozenset[str] | None = None  # 从 @llvm.global.annotations 提取


@dataclass(frozen=True)
class IRGlobal:
    name: str                              # "@.str", "@counter"
    global_type: str                       # "constant [13 x i8]", "i32"
    initializer: IROperand | None = None   # IRConst or None
    is_constant: bool = False
    linkage: str = ""


@dataclass(frozen=True)
class IRModule:
    source_file: str
    functions: tuple[IRFunction, ...]
    globals: tuple[IRGlobal, ...] = ()
