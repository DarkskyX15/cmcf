from __future__ import annotations

import subprocess
from pathlib import Path

from cmcf.core.config import CompileConfig


class ClangError(Exception):
    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class ClangInterface:
    def __init__(self, clang_path: str, opt_level: int = 1,
                 include_paths: tuple[Path, ...] = (),
                 defines: tuple[str, ...] = ()) -> None:
        self._clang_path = clang_path
        self._opt_level = opt_level
        self._include_paths = include_paths
        self._defines = defines

    def compile_to_bc(self, source: Path, output: Path) -> None:
        cmd = [
            self._clang_path, "-x", "c",
            f"-O{self._opt_level}",
            "-fno-vectorize", "-fno-slp-vectorize",
            "-fno-discard-value-names",
            "-c", "-emit-llvm", "-o", str(output),
        ]
        for inc in self._include_paths:
            cmd.extend(["-I", str(inc)])
        for define in self._defines:
            cmd.extend(["-D", define])
        cmd.append(str(source))

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ClangError(
                f"clang exited with code {result.returncode} for {source.name}",
                stderr=result.stderr,
            )

    @staticmethod
    def is_available(clang_path: str = "clang") -> bool:
        try:
            result = subprocess.run(
                [clang_path, "--version"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @classmethod
    def from_config(cls, config: CompileConfig) -> ClangInterface:
        return cls(
            clang_path=config.clang_path,
            opt_level=config.opt_level,
            include_paths=config.include_paths,
            defines=config.defines,
        )
