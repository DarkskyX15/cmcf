from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmcf.core.models import InstalledManifest


@dataclass
class SysCallEntry:
    module: str       # "i32_core"
    file: str         # "print.mcfunction"
    stem: str         # "print"


class SysCallRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, SysCallEntry] = {}

    def register(self, name: str, module: str, file: str) -> None:
        stem = file.rsplit(".", 1)[0] if "." in file else file
        if "/" in stem:
            stem = stem.rsplit("/", 1)[-1]
        self._entries[name] = SysCallEntry(module=module, file=file, stem=stem)

    def lookup(self, name: str) -> SysCallEntry | None:
        return self._entries.get(name)

    @classmethod
    def from_installed_manifest(cls, manifest: InstalledManifest) -> SysCallRegistry:
        reg = cls()
        for module_name, entry in manifest.items():
            for syscall_name, file_path in entry.get("syscalls", {}).items():
                reg.register(syscall_name, module_name, file_path)
        return reg

    def __contains__(self, name: str) -> bool:
        return name in self._entries
