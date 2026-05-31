from __future__ import annotations

from typing import TypedDict, NotRequired, Literal


# ======================================================================
# cmcf.json
# ======================================================================

class PackFormat(TypedDict):
    min: list[int]
    max: list[int]


class ProjectSection(TypedDict):
    id: str
    name: NotRequired[str]
    namespace: NotRequired[str]
    version: str
    pack_format: PackFormat
    dist: NotRequired[str]


class CompileSection(TypedDict):
    mode: Literal["datapack", "module"]
    opt_level: NotRequired[int]
    clang_path: NotRequired[str]
    llvm_link_path: NotRequired[str]


class ProjectManifest(TypedDict):
    """cmcf.json 顶层结构"""
    project: ProjectSection
    compile: CompileSection
    path_vars: NotRequired[dict[str, str]]
    files: NotRequired[dict[str, str]]
    meta: NotRequired[dict[str, str]]


# ======================================================================
# module.json
# ======================================================================

class ModuleManifest(TypedDict):
    """单个模块定义"""
    name: str
    version: str
    meta: NotRequired[dict[str, str]]
    pack_format: PackFormat
    dependencies: NotRequired[dict[str, str]]
    source: NotRequired[str]
    source_alias: NotRequired[str]
    handler: NotRequired[str]
    files: NotRequired[dict[str, str]]
    syscalls: NotRequired[dict[str, str]]


# ======================================================================
# modules.json
# ======================================================================

class InstalledModuleEntry(TypedDict):
    """单个已安装模块记录"""
    version: str
    install_paths: list[str]
    syscalls: dict[str, str]
    dependencies: dict[str, str]


InstalledManifest = dict[str, InstalledModuleEntry]


# ======================================================================
# m3.json — Minecraft Mcfunction Module
# ======================================================================

class M3VersionEntry(TypedDict):
    """仓库中某个模块的一个版本"""
    path: str
    source: str
    installed_at: str
    dependencies: dict[str, str]


M3VersionIndex = dict[str, M3VersionEntry]
M3Manifest = dict[str, M3VersionIndex]


# ======================================================================
# pass.json
# ======================================================================

class PassManifest(TypedDict):
    """handler 排序缓存"""
    fingerprint: str
    order: dict[str, list[str]]
