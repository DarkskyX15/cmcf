from __future__ import annotations

from typing import Type

from cmcf.core.ir_instructions import IRInstruction
from cmcf.core.ir_visitor import WalkContext, WalkReport, InstructionRouter
from cmcf.mc.handlers.base import InstructionHandler


_handler_registry: dict[str, list[Type[InstructionHandler]]] = {}


def register_handler(*opcodes: str):
    def decorator(cls: Type[InstructionHandler]) -> Type[InstructionHandler]:
        cls._handled_opcodes = opcodes  # type: ignore[attr-defined]
        for op in opcodes:
            _handler_registry.setdefault(op, []).append(cls)
        return cls
    return decorator


class FallbackHandler(InstructionHandler):
    def handle(self, inst: IRInstruction, ctx: WalkContext) -> None:
        self.report.errors.append(
            f"unhandled opcode '{inst.opcode}' "
            f"in {ctx.current_function.name if ctx.current_function else '?'}"
        )


def build_router(report: WalkReport) -> InstructionRouter:
    router = InstructionRouter()
    router.set_fallback(FallbackHandler(report))

    for opcode, cls_list in _handler_registry.items():
        for cls in cls_list:
            router.register(opcode, cls(report))

    return router
