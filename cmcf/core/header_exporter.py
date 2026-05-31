from __future__ import annotations

from typing import TYPE_CHECKING

from cmcf.core.ir_instructions import IRFunction

if TYPE_CHECKING:
    from cmcf.core.context import FileWriter


class HeaderExporter:
    LLVM_TO_C: dict[str, str] = {
        "void": "void", "i1": "_Bool", "i8": "char",
        "i16": "short", "i32": "int", "i64": "long long",
        "float": "float", "double": "double",
        "ptr": "void*", "half": "unsigned short",
    }

    def export(self, func: IRFunction, writer: FileWriter,
               export_as: str | None = None) -> None:
        name = export_as or func.name
        path = f"headers/{name}.h"
        guard = f"CMCF_{name.replace('/', '_').upper()}_H"
        c_params = ", ".join(
            f"{self._to_c(p.param_type)} {p.name}"
            for p in func.params
        )
        c_return = self._to_c(func.return_type) if func.return_type else "void"

        if writer._current_path:  # noqa: SLF001
            writer.push(path)
        else:
            writer.open(path)
        writer.emit(f"#ifndef {guard}")
        writer.emit(f"#define {guard}")
        writer.emit(f"{c_return} {func.name}({c_params});")
        writer.emit("#endif")
        writer.close()

    def _to_c(self, llvm_type: str) -> str:
        return self.LLVM_TO_C.get(llvm_type, llvm_type)
