from __future__ import annotations

from abc import ABC, abstractmethod

from cmcf.core.ir_instructions import IRInstruction
from cmcf.core.ir_visitor import WalkContext, WalkReport


class InstructionHandler(ABC):
    def __init__(self, report: WalkReport) -> None:
        self.report = report

    @abstractmethod
    def handle(self, inst: IRInstruction, ctx: WalkContext) -> None:
        ...
