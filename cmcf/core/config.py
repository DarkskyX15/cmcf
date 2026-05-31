from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cmcf.core.models import ProjectManifest


@dataclass
class CompileConfig:
    """运行时编译配置，部分字段来自 cmcf.json，部分来自 CLI。"""

    # ── CLI 动态字段 ──
    sources: tuple[Path, ...]
    output: Path | None = None
    compile_only: bool = False
    include_paths: tuple[Path, ...] = ()
    defines: tuple[str, ...] = ()
    verbose: bool = False

    # ── cmcf.json 字段 ──
    target_format: tuple[int, int] = (88, 1)
    namespace: str = "cmcf"
    project_id: str = ""
    project_name: str = ""
    project_version: str = "0.1.0"
    compile_mode: Literal["datapack", "module"] = "datapack"
    opt_level: Literal[0, 1] = 1
    clang_path: str = "clang"
    llvm_link_path: str = "llvm-link"
    path_vars: dict[str, str] | None = None  # None = use built-in defaults
    files: dict[str, str] | None = None
    export_header: bool = False

    @classmethod
    def from_manifest(cls, manifest: ProjectManifest) -> CompileConfig:
        project = manifest["project"]
        compile = manifest["compile"]
        pf = project["pack_format"]
        return cls(
            sources=(),
            output=Path(project.get("dist", "./output")),
            target_format=(pf["min"][0], pf["max"][1]),
            namespace=project.get("namespace", project["id"]),
            project_id=project["id"],
            project_name=project.get("name", project["id"]),
            project_version=project.get("version", "0.1.0"),
            compile_mode=compile.get("mode", "datapack"),
            opt_level=compile.get("opt_level", 1),
            clang_path=compile.get("clang_path", "clang"),
            llvm_link_path=compile.get("llvm_link_path", "llvm-link"),
            path_vars=manifest.get("path_vars"),
            files=manifest.get("files"),
        )


# ── 内置 path_vars 默认值 ──

DEFAULT_PATH_VARS: dict[str, str] = {
    "function": "function",
    "tags": "tags/function",
    "advancement": "advancement",
    "loot_table": "loot_table",
    "predicate": "predicate",
    "item_modifier": "item_modifier",
    "recipe": "recipe",
    "structure": "structure",
    "dimension": "dimension",
    "dimension_type": "dimension_type",
    "damage_type": "damage_type",
    "enchantment": "enchantment",
}
