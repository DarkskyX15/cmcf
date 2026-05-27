from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class CompileConfig:
    sources: tuple[Path, ...]
    output: Path | None = None
    compile_only: bool = False
    clang_path: str = "clang"
    llvm_link_path: str = "llvm-link"
    opt_level: Literal[0, 1] = 1
    include_paths: tuple[Path, ...] = ()
    defines: tuple[str, ...] = ()
    verbose: bool = False
    output_ir: Path | None = None
