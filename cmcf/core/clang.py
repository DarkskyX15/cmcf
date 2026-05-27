from __future__ import annotations

import subprocess
from pathlib import Path

from cmcf.config import CompileConfig


class ClangError(Exception):
    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class ClangInterface:
    def __init__(self, config: CompileConfig) -> None:
        self._config = config

    def compile_to_ir(self) -> str:
        cmd = self._base_cmd() + ["-S", "-emit-llvm", "-o", "-"]
        cmd.append(str(self._config.sources[0]))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise ClangError(
                f"clang exited with code {result.returncode}",
                stderr=result.stderr,
            )

        ir_text = result.stdout
        if self._config.output_ir:
            self._config.output_ir.write_text(ir_text, encoding="utf-8")
        return ir_text

    def compile_to_bc(self, source: Path, output: Path) -> None:
        cmd = self._base_cmd() + ["-c", "-emit-llvm", "-o", str(output)]
        cmd.append(str(source))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise ClangError(
                f"clang exited with code {result.returncode} for {source.name}",
                stderr=result.stderr,
            )

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self._config.clang_path, "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _base_cmd(self) -> list[str]:
        cmd = [
            self._config.clang_path, "-x", "c",
            f"-O{self._config.opt_level}",
            "-fno-vectorize", "-fno-slp-vectorize",
            "-fno-discard-value-names",
        ]
        for inc in self._config.include_paths:
            cmd.extend(["-I", str(inc)])
        for define in self._config.defines:
            cmd.extend(["-D", define])
        return cmd
