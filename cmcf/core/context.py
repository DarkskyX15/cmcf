from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cmcf.core.config import CompileConfig, DEFAULT_PATH_VARS
from cmcf.core.ir_instructions import (
    IRModule, IRFunction, IRBlock, IRInstruction,
)
from cmcf.core.syscall_registry import SysCallRegistry
from cmcf.core.header_exporter import HeaderExporter


# ======================================================================
# FileWriter
# ======================================================================

class FileWriter:
    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root
        self._current_path: Path | None = None
        self._current_buffer: list[str] = []
        self._completed: dict[Path, list[str]] = {}
        self._stack: list[tuple[Path, list[str]]] = []

    def open(self, rel_path: str) -> None:
        if self._current_path is not None:
            self._completed[self._current_path] = self._current_buffer
        self._current_path = Path(rel_path)
        self._current_buffer = []

    def emit(self, line: str) -> None:
        if self._current_path is None:
            self.open("main.mcfunction")
        self._current_buffer.append(line)

    def close(self) -> None:
        if self._current_path is not None:
            self._completed[self._current_path] = self._current_buffer
            self._current_path = None
            self._current_buffer = []

    def push(self, rel_path: str) -> None:
        self._stack.append((self._current_path or Path(), self._current_buffer))
        self._current_path = Path(rel_path)
        self._current_buffer = []

    def pop(self) -> None:
        self.close()
        if self._stack:
            self._current_path, self._current_buffer = self._stack.pop()

    def write_all(self) -> None:
        self.close()
        for file_path, lines in self._completed.items():
            full = self._output_root / file_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ======================================================================
# Trace
# ======================================================================

@dataclass
class Trace:
    module: IRModule | None = None
    function: IRFunction | None = None
    block: IRBlock | None = None
    instruction: IRInstruction | None = None
    annotations: frozenset[str] | None = None
    module_name: str = ""
    func_name: str = ""
    block_label: str = ""


# ======================================================================
# NameProvider
# ======================================================================

class NameProvider:
    def __init__(self, config: CompileConfig) -> None:
        self._pid = config.project_id
        self._ns = config.namespace
        pv = dict(DEFAULT_PATH_VARS)
        if config.path_vars:
            pv.update(config.path_vars)
        self._pv = pv
        self._tf = config.target_format

    def func_file(self, module: str, func: str) -> str:
        return f"{module}/_internal/{func}.mcfunction"

    def exported_file(self, module: str, func: str) -> str:
        return f"{module}/{func}.mcfunction"

    def block_file(self, module: str, func: str, block_label: str) -> str:
        return f"{module}/_internal/{func}/{block_label}.mcfunction"

    def internal_dir(self) -> str:
        return "_internal"

    def load_dir(self) -> str:
        return "_load"

    def tick_dir(self) -> str:
        return "_tick"

    def scoreboard_obj(self, var_name: str) -> str:
        return f"cmcf_var_{var_name}"

    def scoreboard_player(self, reg_name: str) -> str:
        return f"$cmcf.{reg_name}"

    def function_ref(self, module: str, path: str) -> str:
        return f"{self._ns}:{module}/{path}"


# ======================================================================
# NodeContext
# ======================================================================

class NodeContext:
    def __init__(self, source_module: str = "") -> None:
        self._data: dict[str, Any] = {}
        self._source_module = source_module

    def set(self, name: str, value: Any, module: str | None = None) -> None:
        key = f"{module or self._source_module}:{name}"
        self._data[key] = value

    def get(self, name: str, default: Any = None, module: str | None = None) -> Any:
        key = f"{module or self._source_module}:{name}"
        return self._data.get(key, default)

    def clear(self) -> None:
        self._data.clear()


# ======================================================================
# Registries
# ======================================================================

@dataclass
class Registries:
    syscall: SysCallRegistry


# ======================================================================
# WalkContext
# ======================================================================

@dataclass
class WalkContext:
    namespace: str
    project_id: str
    target_format: tuple[int, int]
    compile_mode: str

    writer: FileWriter
    namer: NameProvider
    header_exporter: HeaderExporter
    registries: Registries

    trace: Trace = field(default_factory=Trace)
    flags: set[str] = field(default_factory=set)

    module_ctx: NodeContext = field(default_factory=NodeContext)
    func_ctx: NodeContext = field(default_factory=NodeContext)
    block_ctx: NodeContext = field(default_factory=NodeContext)

    @classmethod
    def from_config(cls, config: CompileConfig, output_dir: Path) -> WalkContext:
        writer = FileWriter(output_dir)
        namer = NameProvider(config)
        header_export = HeaderExporter()
        syscall_reg = SysCallRegistry()
        registries = Registries(syscall=syscall_reg)
        return cls(
            namespace=config.namespace,
            project_id=config.project_id,
            target_format=config.target_format,
            compile_mode=config.compile_mode,
            writer=writer,
            namer=namer,
            header_exporter=header_export,
            registries=registries,
        )
