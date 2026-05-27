from __future__ import annotations

from cmcf.core.ir_instructions import IRInstruction
from cmcf.core.ir_values import IRFunctionRef
from cmcf.core.ir_visitor import WalkContext
from cmcf.mc.handlers import register_handler
from cmcf.mc.handlers.base import InstructionHandler


@register_handler("call")
class CallHandler(InstructionHandler):
    def handle(self, inst: IRInstruction, ctx: WalkContext) -> None:
        if not inst.operands:
            self.report.errors.append(
                f"call with no operands in {ctx.current_function.name}"
            )
            return

        callee = inst.operands[-1]
        if not isinstance(callee, IRFunctionRef):
            self.report.errors.append(
                f"indirect call to {type(callee).__name__} "
                f"in {ctx.current_function.name}"
            )
            return

        if self._is_user_function(callee.name, ctx.module):
            return

        if callee.name not in self.report.syscalls_detected:
            self.report.syscalls_detected.append(callee.name)

    def _is_user_function(self, name: str, module) -> bool:
        return any(
            f.name == name and not f.is_declaration
            for f in module.functions
        )
