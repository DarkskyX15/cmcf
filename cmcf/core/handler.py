from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Callable, ClassVar, Any

# ======================================================================
# Phase
# ======================================================================

class Phase(IntEnum):
    CORE   = 0
    BEFORE = 1
    MAIN   = 2
    AFTER  = 3


# ======================================================================
# Handler
# ======================================================================

class Handler:
    id: ClassVar[str]

    def preflight(self, ctx: Any) -> None:
        """编译前执行一次（反向），向 ctx.flags 添加语义标签。"""

    def handle(self, node: Any, ctx: Any) -> None:
        """遍历时正向执行。"""


# ======================================================================
# Registry
# ======================================================================

def _get_collection(key: str) -> HandlerCollection:
    col = _registry[key]
    col._ensure_key(key)
    return col


@dataclass
class HandlerEntry:
    handler: Handler
    phase: Phase
    before: tuple[str, ...]
    after: tuple[str, ...]


class HandlerCollection:
    def __init__(self) -> None:
        self._entries: dict[str, HandlerEntry] = {}
        self._sorted: list[Handler] = []
        self._sorted_ids: list[str] = []
        self._key: str = ""

    def _ensure_key(self, key: str) -> None:
        if not self._key:
            self._key = key

    def register(self, handler: Handler,
                 phase: Phase = Phase.MAIN,
                 before: tuple[str, ...] = (),
                 after: tuple[str, ...] = ()) -> None:
        self._entries[handler.id] = HandlerEntry(
            handler=handler, phase=phase, before=before, after=after,
        )

    def sort(self, fingerprint: str, pass_path: Path) -> None:
        existing = _read_pass(pass_path)
        if existing and existing.get("fingerprint") == fingerprint:
            order = existing["order"].get(self._key, [])
            if order:
                self._sorted_ids = order
                self._resolve_sorted()
                return

        self._topological_sort()

        existing = existing or {}
        existing["fingerprint"] = fingerprint
        if "order" not in existing:
            existing["order"] = {}
        existing["order"][self._key] = self._sorted_ids
        _write_pass(pass_path, fingerprint, existing["order"])

    def preflight(self, ctx: Any) -> None:
        for h in reversed(self._sorted):
            h.preflight(ctx)

    def execute(self, node: Any, ctx: Any) -> None:
        for h in self._sorted:
            h.handle(node, ctx)

    # -- internals --

    def _topological_sort(self) -> None:
        ids = list(self._entries.keys())
        in_degree: dict[str, int] = {e: 0 for e in ids}
        adj: dict[str, set[str]] = defaultdict(set)

        for eid, entry in self._entries.items():
            for b in entry.before:
                if b in self._entries:
                    adj[eid].add(b)
                    in_degree[b] += 1
            for a in entry.after:
                if a in self._entries:
                    adj[a].add(eid)
                    in_degree[eid] += 1

        queue = [e for e in ids if in_degree[e] == 0]
        sorted_ids: list[str] = []

        while queue:
            eid = queue.pop(0)
            sorted_ids.append(eid)
            for neighbor in adj[eid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        cycle_ids = [e for e, d in in_degree.items() if d > 0]
        if cycle_ids:
            raise RuntimeError(
                f"circular dependency in handler sorting: {cycle_ids}"
            )

        unknown_refs: set[str] = set()
        for e in self._entries.values():
            for b in e.before:
                if b not in self._entries:
                    unknown_refs.add(b)
            for a in e.after:
                if a not in self._entries:
                    unknown_refs.add(a)
        if unknown_refs:
            raise RuntimeError(
                f"handler references unknown id(s): {', '.join(sorted(unknown_refs))}"
            )

        sorted_ids.sort(key=lambda eid: self._entries[eid].phase.value)
        self._sorted_ids = sorted_ids
        self._resolve_sorted()

    def _resolve_sorted(self) -> None:
        self._sorted = [self._entries[eid].handler for eid in self._sorted_ids
                        if eid in self._entries]


_registry: dict[str, HandlerCollection] = defaultdict(HandlerCollection)


def _read_pass(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_pass(path: Path, fingerprint: str, order: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprint": fingerprint, "order": order}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ======================================================================
# register decorator
# ======================================================================

def register(*, node: str,
             on: str | list[str] | None = None,
             id: str,
             phase: Phase = Phase.MAIN,
             before: list[str] | None = None,
             after: list[str] | None = None):
    def decorator(cls: type) -> type:
        handler = cls()
        handler.id = id  # type: ignore[attr-defined]
        before_t = tuple(before or ())
        after_t = tuple(after or ())

        if node == "module":
            _get_collection("module").register(handler, phase, before_t, after_t)
        elif node == "function":
            for pos in _normalize(on or "enter"):
                _get_collection(f"function.{pos}").register(handler, phase, before_t, after_t)
        elif node == "block":
            for pos in _normalize(on or "enter"):
                _get_collection(f"block.{pos}").register(handler, phase, before_t, after_t)
        elif node == "instruction":
            for op in _normalize(on or []):
                _get_collection(f"instruction.{op}").register(handler, phase, before_t, after_t)
        return cls
    return decorator


def _normalize(val: str | list[str]) -> list[str]:
    return [val] if isinstance(val, str) else val


def get_registry() -> dict[str, HandlerCollection]:
    return _registry


def compute_fingerprint(modules_json: Path) -> str:
    try:
        data = modules_json.read_bytes()
    except FileNotFoundError:
        data = b"{}"
    return hashlib.sha256(data).hexdigest()[:16]
