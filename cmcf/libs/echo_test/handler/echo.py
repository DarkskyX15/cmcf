from __future__ import annotations

from cmcf.core.handler import register, Handler
from cmcf.core.ir_instructions import IRInstruction
from cmcf.core.context import WalkContext


@register(node="instruction", on="*", id="echo")
class EchoHandler(Handler):
    def handle(self, node: IRInstruction, ctx: WalkContext) -> None:
        result_str = f" -> {node.result}" if node.result else ""
        pred_str = f" [{node.predicate}]" if node.predicate else ""
        flags_str = f" {' '.join(node.flags)}" if node.flags else ""
        ctx.writer.emit(f"# {node.opcode}{pred_str}{flags_str}{result_str}")
