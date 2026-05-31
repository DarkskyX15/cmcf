from __future__ import annotations

import subprocess
from pathlib import Path


class LinkerError(Exception):
    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class LinkerInterface:
    def __init__(self, llvm_link_path: str = "llvm-link") -> None:
        self._path = llvm_link_path

    def link(self, inputs: list[Path], output: Path) -> None:
        cmd = [self._path, "-o", str(output)]
        cmd.extend(str(p) for p in inputs)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise LinkerError(
                f"llvm-link exited with code {result.returncode}",
                stderr=result.stderr,
            )

    @staticmethod
    def is_available(path: str = "llvm-link") -> bool:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
