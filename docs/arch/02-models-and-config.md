# 2. 配置与数据模型

> 来源: `docs/development/redesign.md` §8, §11, §2 部分
> 代码: `cmcf/core/models.py`, `cmcf/core/config.py`

---

## cmcf.json 项目配置

```jsonc
// project/.cmcf/cmcf.json
{
    "project": {
        "id": "my_project",          // 必需: 机器标识
        "name": "My Pack",           // 可选→id: pack.mcmeta 显示名
        "namespace": "mypack",       // 可选→id: MC 命名空间
        "version": "1.0.0",
        "pack_format": [88, 1],
        "dist": "./output"           // 输出根目录
    },
    "compile": {
        "mode": "datapack",          // "datapack" | "module"
        "opt_level": 1,
        "clang_path": "clang",
        "llvm_link_path": "llvm-link"
    },
    "path_vars": {},                 // 覆盖默认 MC 路径变量
    "files": {},                     // 静态文件 (key → path)
    "meta": {
        "description": "A custom Minecraft datapack",
        "author": "user"
    }
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `project.id` | 必需，输出目录中的模块/项目标识 |
| `project.name` | 可选→`id`，数据包显示名 |
| `project.namespace` | 可选→`id`，MC 函数命名空间 |
| `project.pack_format` | `[major, minor]`，输出 pack.mcmeta 的格式号 |
| `project.dist` | 输出根目录，默认 `"./output"` |
| `compile.mode` | `"datapack"` 或 `"module"` |
| `compile.opt_level` | 0 或 1，可被 CLI `-O` 覆盖 |
| `compile.clang_path` / `llvm_link_path` | 工具链路径 |
| `path_vars` | 覆盖默认 MC 路径变量 |
| `files` | 静态文件路径映射 |
| `meta` | 自由键值，仅读取与显示 |

### `path_vars` 默认值

cmcf 根据 `project.pack_format` 提供内置默认字典：

```jsonc
{
    "function": "function", "tags": "tags/function",
    "advancement": "advancement", "loot_table": "loot_table",
    "predicate": "predicate", "item_modifier": "item_modifier",
    "recipe": "recipe", "structure": "structure",
    "dimension": "dimension", "dimension_type": "dimension_type",
    "damage_type": "damage_type", "enchantment": "enchantment"
}
```

用户覆盖示例：
```jsonc
"path_vars": { "function": "functions" }
```

### `compile.mode` 与输出路径

#### datapack 模式

```
{project.dist}/datapack/{project.name}/data/{project.namespace}/
├── {path_vars.function}/{project.id}/
│   ├── main.mcfunction
│   ├── _internal/...
│   ├── _load/...
│   └── _tick/...
└── pack.mcmeta
```

#### module 模式

```
{project.dist}/module/{project.id}-{project.version}-{meta_hash}/
├── module.json                  ← 自动生成
├── function/                    ← 导出 + 内部 mcfunction
├── header/                      ← 生成的 C Header
├── <files key1>/                ← 从 project.files 复制
└── <files key2>/...
```

`meta_hash`: SHA256(JSON.stringify(project.meta, sort_keys)) 的 hex 前 8 位。

### CompileConfig

```python
# cmcf/core/config.py
@dataclass
class CompileConfig:
    sources: tuple[Path, ...]
    output: Path | None = None
    compile_only: bool = False
    include_paths: tuple[Path, ...] = ()
    defines: tuple[str, ...] = ()
    verbose: bool = False
    target_format: tuple[int, int] = (88, 1)
    namespace: str = "cmcf"
    project_id: str = ""
    project_name: str = ""
    project_version: str = "0.1.0"
    compile_mode: Literal["datapack", "module"] = "datapack"
    opt_level: Literal[0, 1] = 1
    clang_path: str = "clang"
    llvm_link_path: str = "llvm-link"
    path_vars: dict[str, str] | None = None
    files: dict[str, str] | None = None
    export_header: bool = False

    @classmethod
    def from_manifest(cls, manifest: ProjectManifest) -> CompileConfig:
        ...
```

### 项目结构

```
project/my_project/
├── .cmcf/
│   ├── cmcf.json                 # 项目配置
│   ├── modules.json              # 已安装模块清单
│   ├── handler/                  # Python handler（模块→复制）
│   ├── functions/                # syscall mcfunction（files映射）
│   ├── tags/                     # function tags（files映射）
│   └── pass.json                 # handler 排序缓存
├── include/                      # C 源码（模块→复制）
├── src/
│   └── main.c                    # 用户代码
└── output/                       # 构建输出（dist 默认值）
```

---

## module.json 模块定义

```jsonc
// cmcf/libs/<name>/module.json
{
    "name": "i32_core",
    "version": "1.0.0",
    "meta": {
        "description": "Core i32 integer arithmetic",
        "author": "cmcf"
    },
    "pack_format": { "min": [4, 0], "max": [88, 0] },
    "dependencies": { "ctrl_core": ">=1.0.0" },
    "source": "source/",
    "source_alias": "i32",
    "handler": "handler/",
    "files": { "functions": "function/", "tags": "tags/" },
    "syscalls": {
        "printf": "print.mcfunction",
        "malloc": "alloc.mcfunction"
    }
}
```

| 字段 | 必须 | 说明 |
|------|:--:|------|
| `name` | ✓ | 模块唯一标识 |
| `version` | ✓ | 语义化版本 |
| `meta` | 否 | 自由键值，仅读取与显示 |
| `pack_format` | ✓ | `[major, minor]` 格式，min/max |
| `dependencies` | 否 | `"模块名": "版本约束"` |
| `source` | 否 | C 源码目录相对路径；空值不复制 |
| `source_alias` | 否 | 覆盖安装目录名；影响 `#include` 路径 |
| `handler` | 否 | Python handler 目录相对路径；空值不复制 |
| `files` | 否 | `key → path` 映射，复制到 `.cmcf/<key>/<module_name>/` |
| `syscalls` | 否 | syscall 签名 → mcfunction 文件名映射 |

### modules.json 项目清单

```jsonc
// project/.cmcf/modules.json
{
    "i32_core": {
        "version": "1.0.0",
        "install_paths": [
            ".cmcf/handler/i32_core/",
            ".cmcf/functions/i32_core/",
            "include/i32/"
        ],
        "syscalls": { "printf": "print.mcfunction", "malloc": "alloc.mcfunction" },
        "dependencies": { "ctrl_core": ">=1.0.0" }
    }
}
```

| 字段 | 说明 |
|------|------|
| `version` | 安装的版本号 |
| `install_paths` | list — 所有安装目录，`cmcf remove` 遍历删除 |
| `syscalls` | dict — syscall 签名→文件完整映射，冲突检测 + 调用生成共用 |
| `dependencies` | 从 module.json 缓存，`cmcf remove` 反向依赖检查 |

---

## m3.json 仓库索引

```jsonc
// cmcf/site_libs/m3.json
{
    "my_module": {
        "2.0.0": {
            "path": "my_module-2.0.0-a1b2c3",
            "source": "https://github.com/user/module",
            "installed_at": "2026-05-29T12:00:00Z",
            "dependencies": { "i32_core": ">=1.0.0" }
        }
    }
}
```

| 字段 | 说明 |
|------|------|
| `path` | `site_libs/` 下的实际文件夹名 |
| `source` | 安装来源路径或 URL |
| `installed_at` | ISO 时间戳 |
| `dependencies` | 从 module.json 提取 |

---

## JSON 清单 TypedDict 模型

定义在 `cmcf/core/models.py`，所有类型使用 `*Manifest` 后缀：

| TypedDict | 对应文件 | 说明 |
|-----------|---------|------|
| `ProjectManifest` | `cmcf.json` | 项目配置顶层 |
| `ModuleManifest` | `module.json` | 模块定义 |
| `InstalledManifest` | `modules.json` | `dict[str, InstalledModuleEntry]` |
| `M3Manifest` | `m3.json` | `dict[str, M3VersionIndex]` |
| `PassManifest` | `pass.json` | handler 排序缓存 |

`PackFormat` 复用于 `ProjectManifest` 和 `ModuleManifest`。

---

## 已确认 ✓

- `cmcf.json` 分组：project / compile / path_vars / files / meta
- `project.id` 必需，name/namespace 默认取 id
- `path_vars` 覆盖默认 MC 路径变量
- `compile.mode` 两种：datapack / module
- module 模式自动生成 module.json + C Header，含 meta_hash
- `modules.json` 使用 install_paths (list[str])，remove 遍历删除
- `source` 和 `handler` 独立可选，空值忽略
- `*Manifest` 统一命名
- `M3` = Minecraft Mcfunction Module
