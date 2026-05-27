from __future__ import annotations

from cmcf.core.ir_instructions import IRInstruction
from cmcf.core.ir_visitor import WalkContext
from cmcf.mc.handlers import register_handler
from cmcf.mc.handlers.base import InstructionHandler


@register_handler("phi", "select")
class AggregateHandler(InstructionHandler):
    def handle(self, inst: IRInstruction, ctx: WalkContext) -> None:
        pass
