from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import llvmlite.binding as llvm

from cmcf.core.ir_converter import IRConverter
from cmcf.core.ir_instructions import IRModule, IRFunction, IRBlock
from cmcf.core.ir_values import IRConst, IRRegister, IRFunctionRef, IRGlobalRef, IRBlockRef


@dataclass
class WalkReport:
    source_file: str = ""
    functions_defined: list[str] = field(default_factory=list)
    functions_declared: list[str] = field(default_factory=list)
    syscalls_detected: list[str] = field(default_factory=list)
    instruction_counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class WalkContext:
    module: IRModule
    current_function: IRFunction | None = None
    current_block: IRBlock | None = None


class InstructionRouter:
    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}
        self._fallback = None

    def register(self, opcode: str, handler) -> None:
        self._handlers.setdefault(opcode, []).append(handler)

    def set_fallback(self, handler) -> None:
        self._fallback = handler

    def handle(self, inst, ctx: WalkContext) -> None:
        handlers = self._handlers.get(inst.opcode)
        if handlers:
            for h in handlers:
                h.handle(inst, ctx)
        elif self._fallback:
            self._fallback.handle(inst, ctx)


class IRWalker:
    def __init__(self, ir_source: bytes | str | Path, *, verbose: bool = False) -> None:
        self._ir_source = ir_source
        self._module: IRModule | None = None
        self._verbose = verbose

    def walk(self, router: InstructionRouter, report: WalkReport) -> WalkReport:
        llvm_mod = self._parse(self._ir_source)
        llvm_mod.verify()
        self._module = IRConverter.convert(llvm_mod)

        ctx = WalkContext(module=self._module)

        report.functions_defined = [
            f.name for f in self._module.functions if not f.is_declaration
        ]
        report.functions_declared = [
            f.name for f in self._module.functions if f.is_declaration
        ]

        if self._verbose:
            _debug_header("Module", f"{len(self._module.functions)} function(s)")

        for func in self._module.functions:
            if func.is_declaration:
                if self._verbose:
                    _debug("declare", f"@{func.name}")
                continue
            ctx.current_function = func
            if self._verbose:
                param_str = ", ".join(p.name for p in func.params)
                _debug_header("Function", f"@{func.name}({param_str})")
                _debug_header("  Blocks", f"{len(func.blocks)} block(s)")
            for block in func.blocks:
                ctx.current_block = block
                if self._verbose:
                    _debug("  [" + block.label + "]", "")
                for inst in block.instructions:
                    report.instruction_counts[inst.opcode] = (
                        report.instruction_counts.get(inst.opcode, 0) + 1
                    )
                    if self._verbose:
                        _debug_instruction(inst, ctx.current_function.name)
                    router.handle(inst, ctx)

        ctx.current_function = None
        ctx.current_block = None
        return report

    @staticmethod
    def _parse(source: bytes | str | Path) -> llvm.ModuleRef:
        if isinstance(source, Path):
            data = source.read_bytes()
            return llvm.parse_bitcode(data)
        if isinstance(source, bytes):
            return llvm.parse_bitcode(source)
        return llvm.parse_assembly(source)


def _debug_header(label: str, detail: str) -> None:
    sys.stderr.write(f"\n{'=' * 60}\n")
    sys.stderr.write(f"  {label}: {detail}\n")
    sys.stderr.write(f"{'=' * 60}\n")


def _debug(label: str, detail: str) -> None:
    sys.stderr.write(f"  {label:<30} {detail}\n")


def _debug_instruction(inst, func_name: str) -> None:
    result = inst.result or "(void)"
    pred = f" [{inst.predicate}]" if inst.predicate else ""
    flags = f" {' '.join(inst.flags)}" if inst.flags else ""
    _debug("  > instruction",
           f"{inst.opcode}{pred}{flags} -> {result}")

    for i, op in enumerate(inst.operands):
        _debug_operand(f"      op[{i}]", op, func_name)


def _debug_operand(prefix: str, op, func_name: str) -> None:
    match op:
        case IRConst(kind="int", value=v):
            _debug(prefix, f"const i32 {v}")
        case IRConst(kind=k, value=v):
            _debug(prefix, f"const {k} = {v!r}")
        case IRRegister(name=n):
            _debug(prefix, f"reg %{n}")
        case IRFunctionRef(name=n):
            _debug(prefix, f"func @{n}")
        case IRGlobalRef(name=n):
            _debug(prefix, f"global @{n}")
        case IRBlockRef(name=n):
            _debug(prefix, f"block %{n}")
        case _:
            _debug(prefix, f"? {type(op).__name__}")
