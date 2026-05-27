from __future__ import annotations

from typing import Optional

from cmcf.mc.syscalls.base import SysCallHandler


_syscall_registry: dict[str, type[SysCallHandler]] = {}


def register_syscall(name: str):
    def decorator(cls: type[SysCallHandler]) -> type[SysCallHandler]:
        cls.name = name
        _syscall_registry[name] = cls
        return cls
    return decorator


class SysCallRegistry:
    def register(self, name: str, handler_cls: type[SysCallHandler]) -> None:
        handler_cls.name = name
        _syscall_registry[name] = handler_cls

    def lookup(self, name: str) -> Optional[type[SysCallHandler]]:
        return _syscall_registry.get(name)

    def list_all(self) -> list[str]:
        return list(_syscall_registry.keys())
