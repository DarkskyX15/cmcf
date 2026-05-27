from __future__ import annotations

from cmcf.core.ir_instructions import IRInstruction
from cmcf.core.ir_visitor import WalkContext
from cmcf.mc.handlers import register_handler
from cmcf.mc.handlers.base import InstructionHandler


@register_handler("add", "sub", "mul", "sdiv", "udiv", "srem", "urem",
                    "and", "or", "xor", "shl", "lshr", "ashr",
                    "trunc", "zext", "sext", "fptoui", "uitofp",
                    "fptosi", "sitofp", "bitcast")
class ArithmeticHandler(InstructionHandler):
    def handle(self, inst: IRInstruction, ctx: WalkContext) -> None:
        pass
