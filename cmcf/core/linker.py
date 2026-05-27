from __future__ import annotations

import subprocess
from pathlib import Path

from cmcf.config import CompileConfig


class LinkerError(Exception):
    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class LinkerInterface:
    def __init__(self, config: CompileConfig) -> None:
        self._config = config

    def link(self, inputs: list[Path], output: Path) -> None:
        cmd = [self._config.llvm_link_path, "-o", str(output)]
        cmd.extend(str(p) for p in inputs)

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise LinkerError(
                f"llvm-link exited with code {result.returncode}",
                stderr=result.stderr,
            )

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self._config.llvm_link_path, "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
