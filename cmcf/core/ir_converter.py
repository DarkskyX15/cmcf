from __future__ import annotations

import re
from typing import Optional

import llvmlite.binding as llvm

from cmcf.core.ir_values import (
    IROperand,
    IRConst,
    IRRegister,
    IRFunctionRef,
    IRGlobalRef,
    IRBlockRef,
)
from cmcf.core.ir_instructions import (
    IRInstruction,
    IRParameter,
    IRBlock,
    IRFunction,
    IRModule,
    IRGlobal,
)


class IRConverter:

    @staticmethod
    def convert(module: llvm.ModuleRef) -> IRModule:
        functions = tuple(
            IRConverter._convert_function(f)
            for f in module.functions
        )
        globals = tuple(
            IRConverter._convert_global(g)
            for g in module.global_variables
        )
        ann_map = IRConverter._parse_annotations(module)

        functions = tuple(
            IRConverter._apply_annotations(f, ann_map)
            for f in functions
        )

        return IRModule(
            source_file=module.source_file,
            functions=functions,
            globals=globals,
        )

    @staticmethod
    def _convert_function(func: llvm.ValueRef) -> IRFunction:
        is_decl = func.is_declaration

        params: tuple[IRParameter, ...] = ()
        blocks: tuple[IRBlock, ...] = ()

        if not is_decl:
            params = tuple(
                IRParameter(
                    name=arg.name or str(i),
                    index=i,
                    param_type=IRConverter._extract_param_type(arg),
                )
                for i, arg in enumerate(func.arguments)
            )
            blocks = tuple(
                IRBlock(
                    label=IRConverter._extract_block_label(block),
                    instructions=tuple(
                        IRConverter._convert_instruction(inst)
                        for inst in block.instructions
                    ),
                )
                for block in func.blocks
            )

        return_type = IRConverter._extract_return_type(func) if not is_decl else None
        return IRFunction(
            name=func.name,
            params=params,
            blocks=blocks,
            is_declaration=is_decl,
            return_type=return_type,
        )

    @staticmethod
    def _convert_instruction(inst: llvm.ValueRef) -> IRInstruction:
        result = inst.name if inst.name else None
        if not result and inst.opcode not in ("store", "br", "ret", "switch"):
            result = IRConverter._extract_result_name(inst)

        operands: tuple[IROperand, ...] = tuple(
            IRConverter._convert_operand(op) for op in inst.operands
        )

        predicate = IRConverter._extract_predicate(inst)
        flags = IRConverter._extract_flags(inst)

        return IRInstruction(
            opcode=inst.opcode,
            result=result,
            operands=operands,
            predicate=predicate,
            flags=flags,
        )

    @staticmethod
    def _convert_operand(operand: llvm.ValueRef) -> IROperand:
        if operand.is_constant and operand.value_kind != llvm.ValueKind.function:
            return IRConverter._convert_constant(operand)
        if operand.is_block or operand.value_kind == llvm.ValueKind.basic_block:
            name = operand.name if operand.name else IRConverter._resolve_block_name(operand)
            return IRBlockRef(name=name)
        if operand.is_function or operand.value_kind == llvm.ValueKind.function:
            return IRFunctionRef(name=operand.name)
        if operand.is_global or operand.value_kind == llvm.ValueKind.global_variable:
            return IRGlobalRef(name=operand.name)
        name = operand.name if operand.name else IRConverter._resolve_operand_name(operand)
        return IRRegister(name=name)

    @staticmethod
    def _resolve_block_name(operand: llvm.ValueRef) -> str:
        text = str(operand).strip()
        m = re.match(r"^([\w.]+):", text)
        if m:
            return m.group(1)
        m = re.match(r"label\s+%([\w.]+)", str(operand))
        if m:
            return m.group(1)
        return "?"

    @staticmethod
    def _resolve_operand_name(operand: llvm.ValueRef) -> str:
        text = str(operand).strip()
        m = re.match(r"i\d+\s+(%[\w.]+)", text)
        if m:
            return m.group(1).lstrip("%")
        m = re.match(r"(%[\w.]+)", text)
        if m:
            return m.group(1).lstrip("%")
        return "?"

    @staticmethod
    def _convert_constant(operand: llvm.ValueRef) -> IRConst:
        try:
            val = operand.get_constant_value(signed_int=True)
            return IRConst(value=val, kind="int")
        except Exception:
            pass
        try:
            val = operand.get_constant_value(round_fp=True)
            if isinstance(val, float):
                return IRConst(value=val, kind="float")
            return IRConst(value=val, kind="int")
        except Exception:
            pass
        text = str(operand).strip()
        if text == "null":
            return IRConst(value=None, kind="null")
        if text == "undef":
            return IRConst(value=None, kind="undef")
        if text == "zeroinitializer":
            return IRConst(value=None, kind="zeroinit")
        try:
            val = operand.get_constant_value(signed_int=False)
            return IRConst(value=val, kind="int")
        except Exception:
            pass
        return IRConst(value=text, kind="string")

    @staticmethod
    def _extract_predicate(inst: llvm.ValueRef) -> Optional[str]:
        opcode = inst.opcode
        if opcode not in ("icmp", "fcmp"):
            return None
        text = str(inst).strip()
        parts = text.split()
        for i, part in enumerate(parts):
            if part in ("icmp", "fcmp") and i + 1 < len(parts):
                pred = parts[i + 1]
                if pred not in ("samesign",):
                    return pred
        return None

    @staticmethod
    def _extract_result_name(inst: llvm.ValueRef) -> Optional[str]:
        text = str(inst).strip()
        m = re.match(r"\s*(%[\w.]+)\s*=", text)
        if m:
            return m.group(1).lstrip("%")
        return None

    @staticmethod
    def _extract_block_label(block: llvm.ValueRef) -> str:
        first_line = str(block).strip().split("\n")[0].strip()
        m = re.match(r"^([\w.]+):\s*;?", first_line)
        if m:
            return m.group(1)
        m = re.match(r"^;+\s*(<label>):\s*(\d+)", first_line)
        if m:
            return m.group(2)
        m = re.match(r"^(\d+):\s*;?", first_line)
        if m:
            return m.group(1)
        return first_line[:40] if len(first_line) > 40 else first_line

    @staticmethod
    def _extract_flags(inst: llvm.ValueRef) -> tuple[str, ...]:
        known_flags = {"nsw", "nuw", "exact", "inbounds", "fast",
                       "nnan", "ninf", "nsz", "arcp", "contract",
                       "afn", "reassoc"}
        opcode = inst.opcode
        if opcode in ("icmp", "fcmp", "br", "ret", "call", "phi", "select"):
            return ()
        text = str(inst).strip()
        tokens = text.split()
        flags = tuple(t for t in tokens if t in known_flags)
        return flags

    # -- new methods --------------------------------------------------

    @staticmethod
    def _convert_global(g: llvm.ValueRef) -> IRGlobal:
        text = str(g).strip()
        m = re.match(r"@([\w.]+)\s*=\s*(\S+)\s+(global|constant)\s+(.*)", text, re.DOTALL)
        if m:
            global_type = m.group(4).strip() if m.group(3) == "constant" else f"{m.group(3)} {m.group(4).strip()}"
            is_constant = m.group(3) == "constant"
        else:
            global_type = ""
            is_constant = False

        init = IRConverter._convert_global_init(g)
        return IRGlobal(
            name=g.name,
            global_type=global_type,
            initializer=init,
            is_constant=is_constant,
            linkage=str(g.linkage),
        )

    @staticmethod
    def _convert_global_init(g: llvm.ValueRef) -> IROperand | None:
        try:
            val = g.get_constant_value()
            if isinstance(val, bytes):
                return IRConst(value=val.decode("utf-8", errors="replace"), kind="string")
            if isinstance(val, (int, float)):
                kind = "int" if isinstance(val, int) else "float"
                return IRConst(value=val, kind=kind)
        except Exception:
            pass
        try:
            val = g.get_constant_value(signed_int=True)
            return IRConst(value=val, kind="int")
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_annotations(module: llvm.ModuleRef) -> dict[str, frozenset[str]]:
        result: dict[str, set[str]] = {}
        try:
            ann_global = module.get_global_variable("llvm.global.annotations")
            if ann_global is None:
                return {}
            text = str(ann_global)
            pattern = re.compile(
                r'\{\s*ptr\s+(@[\w.]+),\s*ptr\s+(@[\w.]+),\s*ptr\s+(@[\w.]+),\s*i32\s+(\d+),\s*ptr\s+null\s*\}',
            )
            for m in pattern.finditer(text):
                func_name = m.group(1)
                str_name = m.group(2)
                ann_str = IRConverter._resolve_annotation_string(module, str_name)
                if ann_str:
                    result.setdefault(func_name, set()).add(ann_str)
        except Exception:
            pass
        return {k: frozenset(v) for k, v in result.items()}

    @staticmethod
    def _resolve_annotation_string(module: llvm.ModuleRef, str_name: str) -> str | None:
        try:
            g = module.get_global_variable(str_name.lstrip("@"))
            if g is None:
                return None
            text = str(g)
            m = re.search(r'c"([^"]*)"', text)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    @staticmethod
    def _apply_annotations(func: IRFunction,
                           ann_map: dict[str, frozenset[str]]) -> IRFunction:
        key = f"@{func.name}"
        if key in ann_map:
            return IRFunction(
                name=func.name, params=func.params, blocks=func.blocks,
                is_declaration=func.is_declaration,
                return_type=func.return_type,
                annotations=ann_map[key],
            )
        return func

    @staticmethod
    def _extract_param_type(arg: llvm.ValueRef) -> str:
        text = str(arg).strip()
        m = re.match(r"\s*(\S+)\s+", text)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _extract_return_type(func: llvm.ValueRef) -> str | None:
        text = str(func).strip()
        m = re.match(r"(?:define|declare)\s+\S+\s+(\S+)\s+@", text)
        if m:
            return m.group(1)
        return None
