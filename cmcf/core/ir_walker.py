from __future__ import annotations

from pathlib import Path

import llvmlite.binding as llvm

from cmcf.core.ir_converter import IRConverter
from cmcf.core.ir_instructions import IRModule, IRFunction, IRBlock, IRInstruction
from cmcf.core.handler import get_registry, compute_fingerprint
from cmcf.core.context import WalkContext


class TreeWalker:

    def walk(self, bc_path: Path | bytes, ctx: WalkContext) -> None:
        llvm_mod = self._parse(bc_path)
        llvm_mod.verify()
        module = IRConverter.convert(llvm_mod)

        ctx.trace.module = module

        reg = get_registry()

        # module-level
        col = reg.get("module")
        if col:
            col.execute(node=module, ctx=ctx)

        for func in module.functions:
            if func.is_declaration:
                continue

            ctx.trace.function = func
            ctx.trace.func_name = func.name
            ctx.trace.annotations = func.annotations
            ctx.func_ctx.clear()
            ctx.flags.clear()

            # function enter
            col = reg.get("function.enter")
            if col:
                col.execute(node=func, ctx=ctx)

            for block in func.blocks:
                ctx.trace.block = block
                ctx.trace.block_label = block.label
                ctx.block_ctx.clear()

                # block enter
                col = reg.get("block.enter")
                if col:
                    col.execute(node=block, ctx=ctx)

                for inst in block.instructions:
                    ctx.trace.instruction = inst

                    # instruction
                    key = f"instruction.{inst.opcode}"
                    if key in reg:
                        reg[key].execute(node=inst, ctx=ctx)
                    elif "instruction.*" in reg:
                        reg["instruction.*"].execute(node=inst, ctx=ctx)

                # block exit
                col = reg.get("block.exit")
                if col:
                    col.execute(node=block, ctx=ctx)

            # function exit
            col = reg.get("function.exit")
            if col:
                col.execute(node=func, ctx=ctx)

        ctx.writer.write_all()

    @staticmethod
    def _parse(source: bytes | Path) -> llvm.ModuleRef:
        if isinstance(source, Path):
            return llvm.parse_bitcode(source.read_bytes())
        return llvm.parse_bitcode(source)
