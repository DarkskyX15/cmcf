# CMCF 重新设计 — 讨论记录

> **状态**: 讨论完成
> **模块文档**: `docs/arch/` (分功能模块整理，适用于 Code Review)
>
> | # | 文档 | 内容 |
> |---|------|------|
> | 1 | [系统总览](../arch/01-system-overview.md) | 工具拆分、源码结构、文件迁移 |
> | 2 | [配置与数据模型](../arch/02-models-and-config.md) | cmcf.json, module.json, TypedDict |
> | 3 | [模块系统与包管理](../arch/03-module-system.md) | 安装/卸载流程、命名空间隔离 |
> | 4 | [Syscall 机制](../arch/04-syscall.md) | 全局注册、SysCallRegistry |
> | 5 | [Handler 体系与 WalkContext](../arch/05-handler-system.md) | 注册、排序、遍历、FileWriter |
> | 6 | [IR 数据模型与转换](../arch/06-ir-model.md) | IR 结点、操作数、IRConverter |
> | 7 | [编译器前端与树遍历](../arch/07-compiler-frontend.md) | ClangInterface, TreeWalker, 构建流程 |
> | 8 | [C Header 导出](../arch/08-header-export.md) | EXPORT/EXPORT_AS, HeaderExporter |

---

## 1. 工具拆分：`cmcf` + `mcc` + `make`

### 三者分工

| 工具 | 角色 | 职责 |
|------|------|------|
| `cmcf` | 项目管理器 | 脚手架（`init`）、模块安装（`install`/`remove`/`list`）、构建触发（`build`） |
| `mcc` | 编译器 | clang/llvm-link 封装、IR 解析树遍历、datapack + C Header 生成 |
| `make` | 构建自动化 | `.c`→`.bc`→`combined.bc`→`datapack` 的全流程调度 |

### 交付形式

`mcc` 作为 `cmcf` 的子模块 `cmcf/cli/mcc.py`，通过 `console_scripts` 暴露 `mcc` 命令：

```
pyproject.toml
  [project.scripts]
  cmcf = "cmcf.cli.cmcf:main"
  mcc  = "cmcf.cli.mcc:main"
```

### mcc 三个子命令

```bash
mcc compile source.c -o out.bc       # → clang -c -emit-llvm ...
mcc link     a.bc b.bc -o comb.bc    # → llvm-link ...
mcc build    combined.bc -o output/   # → IR walk + datapack + headers
```

对标 gcc 的 `-c` / 链接 / 最终输出。

### 完整调用链

```
cmcf init my_project/
  └→ 生成: .cmcf/cmcf.json, .cmcf/modules.json, src/main.c

cmcf import i32_core
  └→ 复制: handler/ → .cmcf/handler/i32_core/
  └→ 复制: source/ → include/i32_core/ (或 include/<source_alias>/)
  └→ 复制: files.* → .cmcf/<key>/i32_core/
  └→ 更新: .cmcf/modules.json
  └→ 更新: pass.json fingerprint 失效

cmcf build                    ← 生成 makefile + 自动调用 make
  make
    ├→ mcc compile src/main.c -o build/main.bc
    ├→ mcc compile include/i32_core/*.c -o build/
    ├→ mcc link build/*.bc -o build/combined.bc
    └→ mcc build build/combined.bc -o output/
         ├→ importlib 发现 .cmcf/handler/
         ├→ 构建 registry + 排序 (pass.json)
         ├→ IR walk (preflight → handle)
         └→ 写出: data/.../function/..., headers/..., pack.mcmeta
```

### 已确认 ✓

- [x] `mcc` 为 `cmcf/cli/mcc.py` 子模块，与 `cmcf` 共享代码
- [x] `cmcf build` 生成 makefile + 调用 make（makefile 不缓存到磁盘）
- [x] `cmcf.json`、`modules.json` 存放在 `.cmcf/` 内
- [x] `make` 驱动编译/链接流程，`mcc` 作为 makefile 中的工具被调用
- [x] 现有 `cmcf/__main__.py` 中的 clang/llvm-link 逻辑迁移到 `mcc`

---

## 2. 模块系统 (`cmcf/libs/`)

### 设计原则

CMCF 框架本身不含 Minecraft 逻辑，所有功能由模块提供。

### `module.json` 格式

```jsonc
// cmcf/libs/<module_name>/module.json
{
    "name": "i32_core",
    "version": "1.0.0",

    // 元信息（键值随意，仅读取与显示）
    "meta": {
        "description": "Core i32 integer arithmetic and memory operations",
        "author": "cmcf",
        "homepage": "https://github.com/cmcf/i32_core",
        "license": "MIT"
    },

    // 兼容范围（主版本.次版本）
    "pack_format": { "min": [4, 0], "max": [88, 0] },

    "dependencies": {
        "ctrl_core": ">=1.0.0"
    },

    // C 源码（可选，独立字段，留空时不复制）
    "source": "source/",
    "source_alias": "i32",

    // Python Handler（可选，独立字段，留空时忽略）
    "handler": "handler/",

    // 静态文件（key → .cmcf/<key>/<module_name>/）
    "files": {
        "functions": "function/",
        "tags":      "tags/"
    },

    // syscall 注册（签名 → 相对 functions/ 的 mcfunction 路径）
    "syscalls": {
        "printf":   "print.mcfunction",
        "malloc":   "alloc.mcfunction",
        "free":     "free.mcfunction",
        "putchar":  "io/putchar.mcfunction",
        "getchar":  "io/getchar.mcfunction"
    }
}
```

### 字段说明

| 字段 | 必须 | 说明 |
|------|:--:|------|
| `name` | ✓ | 模块唯一标识 |
| `version` | ✓ | 语义化版本 |
| `meta` | 否 | 自由键值，仅读取与显示 |
| `pack_format` | ✓ | `[major, minor]` 格式，min/max |
| `dependencies` | 否 | `"模块名": "版本约束"` |
| `source` | 否 | C 源码目录相对路径；空值不复制 |
| `source_alias` | 否 | 覆盖安装目录名；影响 `#include` 与 makefile 编译路径 |
| `handler` | 否 | Python handler 目录相对路径；空值不复制 |
| `files` | 否 | `key → path` 映射，复制到 `.cmcf/<key>/<module_name>/` |
| `syscalls` | 否 | syscall 签名 → mcfunction 文件名映射 |

### 安装映射

```
cmcf/libs/i32_core/                             →  project/
────────────────────────────────────────────────────────────────
handler:    handler/*                           →  .cmcf/handler/i32_core/*
source:     source/*   + alias="i32"            →  include/i32/*
                        (省略 alias)            →  include/i32_core/*
files:      <key>: <path>/*                     →  .cmcf/<key>/i32_core/*
```

### 模块目录结构

```
cmcf/libs/i32_core/
├── module.json
├── handler/                                    # → .cmcf/handler/i32_core/
│   ├── __init__.py
│   ├── arithmetic.py
│   └── memory.py
├── source/                                     # → include/i32/ (alias)
│   ├── i32_core.h
│   ├── i32_core.c
│   └── impl/
│       └── math.c
├── function/                                   # → .cmcf/functions/i32_core/
│   ├── print.mcfunction
│   ├── alloc.mcfunction
│   └── io/
│       ├── putchar.mcfunction
│       └── getchar.mcfunction
└── tags/                                       # → .cmcf/tags/i32_core/
    └── function/
        └── load.json
```

### 安装后项目结构

```
project/my_project/
├── modules.json                     # {"i32_core": "1.0.0", "ctrl_core": "1.0.0"}
├── include/
│   └── i32/                         # source_alias="i32"
│       ├── i32_core.h
│       ├── i32_core.c
│       └── impl/math.c
├── .cmcf/
│   ├── handler/
│   │   ├── i32_core/
│   │   │   ├── __init__.py
│   │   │   ├── arithmetic.py
│   │   │   └── memory.py
│   │   └── ctrl_core/...
│   ├── functions/
│   │   └── i32_core/
│   │       ├── print.mcfunction
│   │       └── io/...
│   ├── tags/
│   │   └── i32_core/
│   │       └── function/load.json
│   └── pass.json
├── src/main.c
└── makefile                         # 含 include/i32/*.c
```

### 纯 mcfunction 模块示例

```jsonc
{
    "name": "vanilla_commands",
    "version": "1.0.0",
    "pack_format": { "min": [4, 0], "max": [88, 0] },
    "files": {
        "functions": "function/",
        "tags":      "tags/"
    },
    "syscalls": {
        "spawn_horse": "entity/spawn_horse.mcfunction"
    }
}
```

### 已确认 ✓

- [x] `source` 和 `handler` 独立可选，空值忽略
- [x] `meta` 自由键值，仅读取与显示
- [x] `pack_format` 使用 `[major, minor]` 格式
- [x] `paths` → `files`，`key → path` 映射到 `.cmcf/<key>/<module_name>/`
- [x] `source_alias` 影响 `#include` 路径和 makefile 编译目录
- [x] `handler` → `.cmcf/handler/<module_name>/`

---

## 3. 包管理器

### 命令设计（方案 D: 子命令命名空间）

```
cmcf repo install <path|name>     → 安装模块到 site_libs（本地仓库）
cmcf repo remove <name>           → 从 site_libs 移除模块
cmcf repo list                    → 列出仓库内可用模块
cmcf repo update                  → 更新仓库内模块

cmcf install <name[:version]>     → 安装模块到当前项目（自动递归依赖）
cmcf remove <name>                → 从当前项目移除模块
```

### 两层模型

```
cmcf repo install ./my_module/   →  site_libs/my_module-1.0.0/   （本地仓库）
cmcf install my_module           →  project/...                  （项目）
```

| 命令 | 目标 | 作用 |
|------|------|------|
| `repo install` | `site_libs/` | 第三方模块安装到 cmcf 本地仓库 |
| `repo remove` | `site_libs/` | 从本地仓库卸载 |
| `repo list` | — | 列出仓库内已安装模块及版本 |
| `install` | `project/` | 从本地仓库复制模块到项目 |
| `remove` | `project/` | 从项目移除模块 |

### 仓库目录

```
cmcf/
├── libs/                          # 内置模块（只读，随 cmcf 更新）
│   ├── m3.json                    # Minecraft Module Manifest（内置注册表）
│   ├── ctrl_core/...
│   └── i32_core/...
└── site_libs/                     # 第三方模块（用户管理）
    ├── m3.json                    # 第三方注册表
    ├── my_module-1.0.0/           # 模块名-版本
    └── my_module-2.0.0-a1b2c3/   # 含短 hash 避免冲突
```

### m3.json 格式

```jsonc
// cmcf/site_libs/m3.json — 三方模块注册表（libs/m3.json 结构相同）
{
    "my_module": {
        "2.0.0": {
            "path": "my_module-2.0.0-a1b2c3",           // 实际文件夹名
            "source": "https://github.com/user/module",  // 安装来源
            "installed_at": "2026-05-29T12:00:00Z",      // 安装时间
            "dependencies": ["i32_core>=1.0.0"]           // 从 module.json 提取
        },
        "1.0.0": {
            "path": "my_module-1.0.0",
            "source": "/home/user/my_module",
            "installed_at": "2026-05-28T08:00:00Z",
            "dependencies": []
        }
    }
}
```

| 字段 | 说明 |
|------|------|
| `path` | `site_libs/` 下的实际文件夹名 |
| `source` | 安装来源路径或 URL |
| `installed_at` | ISO 时间戳，用于清理和审计 |
| `dependencies` | 从 module.json 提取，避免 import 时逐文件解析 |

### `cmcf install <name>` 流程

```
1. 版本选择
   ├─ 指定版本?  cmcf install i32_core@1.0.0
   │     → site_libs 有 → 使用
   │     → libs 有     → 使用
   │     → 都没有     → 报错
   │
   └─ 未指定版本?
         → 遍历 libs + site_libs 中的所有版本
         → 取与项目 pack_format 兼容的最新版本
         → 都没有 → 报错（不考虑降级到不兼容版本）

2. 兼容性检查
   → module.pack_format.min ≤ project.target_format ≤ module.pack_format.max

3. syscall 冲突检查
   → 遍历新模块的所有 syscall 签名
   → 与项目 modules.json 中已安装模块的 syscall 表取交集
   → 交集非空 → 报错列出冲突项，中止

4. 递归安装依赖
   → 遍历 dependencies，对每个依赖递归执行 install 步骤 1-4

5. 文件复制（按 module.json 映射），记录 install_paths
   handler: → .cmcf/handler/<name>/
   source:  → include/<source_alias 或 name>/
   files.*: → .cmcf/<key>/<name>/

6. 更新项目清单 → .cmcf/modules.json:
   {
     "<name>": {
       "version": "1.0.0",
       "install_paths": [                           // 所有安装目录
         ".cmcf/handler/i32_core/",
         ".cmcf/functions/i32_core/",
         ".cmcf/tags/i32_core/",
         "include/i32/"
       ],
       "syscalls": {"printf": "print.mcfunction", ...},  // 完整映射
       "dependencies": {"ctrl_core": ">=1.0.0"}     // 从 module.json 缓存
     }
   }

7. 使 pass.json 失效
   → 删除或标记 fingerprint 过期
```

### `cmcf remove <name>` 流程

```
1. 检查是否存在 ─ 不在 → 报错
2. 遍历已安装模块的 dependencies，检查是否有模块依赖 <name> → 报 warning
3. 遍历 modules[<name>].install_paths → 逐一删除目录/文件
4. 从 .cmcf/modules.json 移除条目
5. 删除 pass.json
```

### `cmcf repo install <path|name>` 流程

```
1. 若 <path> 是本地路径 → 读取 module.json
   若 <name> 是模块名 → 从远程仓库获取（后续扩展）

2. 解析 module.json，提取 name + version

3. 检查 libs/m3.json:
   → 若 name 已存在于 libs → 报错 "内置模块不可覆盖"

4. 将模块目录复制到 site_libs/<name>-<version>[-hash]/

5. 更新 site_libs/m3.json:
   → 若已有同版本 → 覆盖（或报错提示 --force）
   → 添加新版本条目
```

### `cmcf repo remove <name>` 流程

```
1. 查找 site_libs/m3.json 中 <name> 的所有版本
2. 若 libs/m3.json 中也有同名模块 → 不处理 libs 部分
3. 删除 site_libs/<name>-<version>/ 目录
4. 从 site_libs/m3.json 移除条目
```

### 已确认 ✓

- [x] 方案 D：`repo install/remove/list` + `install/remove`
- [x] 两层模型：site_libs（仓库） + project（项目）
- [x] `install <name>` 自动递归安装依赖
- [x] 版本选择：取与项目 pack_format 兼容的最新版本
- [x] `site_libs` 不可覆盖 `libs` 内同名内置模块
- [x] m3.json 字段：path, source, installed_at, dependencies

---

## 4. Syscall 机制

### 全局唯一注册

- syscall 签名在项目级全局唯一（类似 C 的全局函数名）
- `cmcf import` 时检测：若新模块的 syscall 与已安装模块冲突 → 报错中止
- **不需要** `module.json` 声明 `conflicts` 字段 — 同名即冲突

### 注册与映射

Syscall 在 `module.json` 中声明签名与文件的映射：

```jsonc
"syscalls": {
    "printf":   "print.mcfunction",
    "malloc":   "alloc.mcfunction"
}
```

- `printf` → `function/print.mcfunction`
- `malloc` → `function/alloc.mcfunction`

这样 C 代码中的 `printf()` 调用与文件 `print.mcfunction` 解耦。

### 调用解析与 SysCallRegistry

`modules.json` 中的 `syscalls` 存储**完整映射**（名称→文件路径），`mcc build` 时从中构建 `SysCallRegistry` 并挂到 `WalkContext`。

```jsonc
// .cmcf/modules.json
"i32_core": {
    "syscalls": {
        "printf":  "print.mcfunction",
        "malloc":  "alloc.mcfunction",
        "putchar": "io/putchar.mcfunction"
    }
}
```

```python
@dataclass
class SysCallEntry:
    module: str       # "i32_core"
    file: str         # "print.mcfunction"
    stem: str         # "print" (不含 .mcfunction)

class SysCallRegistry:
    _entries: dict[str, SysCallEntry] = {}
    """从 modules.json 构建，key 为 syscall 名称。"""

    def lookup(self, name: str) -> SysCallEntry | None:
        return self._entries.get(name)

    @classmethod
    def from_modules_json(cls, modules_path: Path) -> SysCallRegistry:
        """mcc build 时调用。"""
```

Handler 中使用：
```python
# call handler
syscall = ctx.syscall_registry.lookup(callee_name)
if syscall:
    ctx.emit(f"function {ctx.namespace}:{syscall.module}/{syscall.stem}")
else:
    ctx.emit(f"function {ctx.namespace}:{ctx.project_id}/_internal/{callee_name}")
```

数据流：
```
C: printf("hello")
  → IR: call @printf
    → ctx.syscall_registry.lookup("printf")
      → SysCallEntry(module="i32_core", file="print.mcfunction", stem="print")
        → 生成: function cmcf:i32_core/print
```

### 已确认 ✓

- [x] 全局唯一，install 时冲突检测
- [x] module.json 注册 syscall 签名→文件映射

---

## 5. 模块命名空间隔离（方案 B）

### 输出结构

```
output/<project>/data/<namespace>/function/
├── <user_module>/            ← 用户项目模块名
│   ├── main.mcfunction       ← 导出函数 (CMCF_ENTRY_EXPORT)
│   ├── _internal/
│   │   └── helper.mcfunction ← static / 非导出
│   ├── _load/
│   │   └── on_load.mcfunction
│   └── _tick/
│       └── on_tick.mcfunction
│
├── i32_core/                 ← 安装的模块
│   ├── print.mcfunction      ← syscall
│   ├── alloc.mcfunction      ← syscall
│   ├── _internal/
│   │   └── stack.mcfunction
│   ├── _load/
│   │   └── init.mcfunction
│   └── _tick/
│       └── ...
│
└── ctrl_core/
    └── ...
```

### 函数目录三重分类

| 目录 | 语义 | 对应 C 标注 |
|------|------|------------|
| 根级 | 导出函数 | `CMCF_ENTRY_EXPORT` |
| `_internal/` | 非导出内部函数 | `static` 或无注解 |
| `_load/` | minecraft:load 标签 | `CMCF_ENTRY_LOAD` |
| `_tick/` | minecraft:tick 标签 | `CMCF_ENTRY_TICK` |

### 模块间调用

```
用户 main.c 调用 i32_core 的 printf:
  → function cmcf:i32_core/print

用户 main.c 调用自己的 static helper:
  → function cmcf:my_project/_internal/helper
```

---

## 6. Handler 体系

### 设计原则

- Handler 使用**类**，含 `preflight` + `handle` 双入口方法
- 统一装饰器 `@register`，通过 `node` 参数区分四种 handler 类型
- 状态通过 `WalkContext` 传递
- Mask 模型：反向 preflight 声明意图 → 正向 handle 执行

### 5.1 Handler 基类

```python
class Handler:
    """所有 handler 的基类。"""
    id: ClassVar[str]                      # 唯一标识（由装饰器设置）

    def preflight(self, ctx: WalkContext) -> None:
        """编译前执行一次（反向），向 ctx.flags 添加语义标签，声明执行意图。"""

    def handle(self, node, ctx: WalkContext) -> None:
        """遍历时正向执行。function handler 自行检查 node.annotations 决定是否处理。"""
```

### 5.2 完整 API

```python
from enum import IntEnum
from typing import ClassVar
from cmcf.core.handler import register, Handler

class Phase(IntEnum):
    CORE   = 0   # 基础设施：scoreboard objective 创建、全局变量初始化
    BEFORE = 1   # 前置处理：符号解析、依赖注入
    MAIN   = 2   # 核心逻辑：指令翻译、分支生成（默认）
    AFTER  = 3   # 收尾：文件写出、标签注册、清理

# ── Module 级 ──
@register(node="module", id="pack_meta", phase=Phase.AFTER)
class PackMetaHandler(Handler):
    def preflight(self, ctx): ...
    def handle(self, node, ctx): ...

# ── Function 级 ──
@register(node="function", on="enter",
          id="entry_setup", phase=Phase.CORE)
class EntrySetupHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations and "cmcf:entry:load" in node.annotations:
            ...

@register(node="function", on="enter",
          id="default_enter", phase=Phase.MAIN)
class DefaultEnterHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations is None:    # 仅无注解函数
            ...

@register(node="function", on="exit",
          id="default_exit", phase=Phase.MAIN)
class DefaultExitHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations is None:
            ...

# ── Block 级 ──
@register(node="block", on="enter",
          id="block_enter", phase=Phase.MAIN)
class BlockEnterHandler(Handler):
    def preflight(self, ctx): ...
    def handle(self, node, ctx): ...

@register(node="block", on="exit",
          id="block_finalize", phase=Phase.AFTER)
class BlockExitHandler(Handler):
    def preflight(self, ctx): ...
    def handle(self, node, ctx): ...

# ── Instruction 级 ──
@register(node="instruction", on=["add", "sub", "mul", "sdiv", "udiv"],
          id="arith", phase=Phase.MAIN,
          before=["icmp_comparison"])
class ArithHandler(Handler):
    def preflight(self, ctx): ...
    def handle(self, node, ctx): ...

@register(node="instruction", on="br",
          id="branch", phase=Phase.MAIN, after=["arith"])
class BranchHandler(Handler):
    def preflight(self, ctx): ...
    def handle(self, node, ctx): ...

@register(node="instruction", on=["ret", "switch"],
          id="terminator", phase=Phase.AFTER)
class TerminatorHandler(Handler):
    def preflight(self, ctx): ...
    def handle(self, node, ctx): ...
```

### 5.3 注册参数规范

| 参数 | `"module"` | `"function"` | `"block"` | `"instruction"` |
|------|:--:|:--:|:--:|:--:|
| `id` | ✓ | ✓ | ✓ | ✓ |
| `on` | ✗ | `"enter"` / `"exit"` / `["enter","exit"]` | `"enter"` / `"exit"` / `["enter","exit"]` | `"add"` / `["add","sub"]` |
| `phase` | ✓ | ✓ | ✓ | ✓ |
| `before` | ✓ | ✓ | ✓ | ✓ |
| `after` | ✓ | ✓ | ✓ | ✓ |

### 5.4 函数注解自检

Function handler 在 `handle()` 内自行检查 `node.annotations`（`frozenset[str] | None`）决定是否处理。

```python
# 仅处理 load 入口函数
class LoadEnterHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations and "cmcf:entry:load" in node.annotations:
            ...

# 仅处理无注解函数（兜底）
class DefaultEnterHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations is None:
            ...
```

注解由 `IRConverter` 从 `@llvm.global.annotations` 解析，填充 `IRFunction.annotations: frozenset[str] | None`（`None` = 无注解）。

### 5.5 Flags 模型

采用冒号分段式标签（如 `"struct_core:no_rtti"`），降低 handler 间耦合。

#### 两阶段执行

```
┌─ 编译前（一次性）─────────────────────────────────────┐
│ HandlerCollection.sort()                               │
│   Phase + 拓扑排序 → 写入 pass.json                    │
│ HandlerCollection.preflight(ctx)                       │
│   反向 (AFTER → CORE) 执行所有 handler 的 preflight()  │
│   → 填充 ctx.flags = {"i32_core:scoreboard", ...}      │
│                                                       │
│ → 排序和 flags 全程不变                                │
└───────────────────────────────────────────────────────┘

┌─ 遍历时（每个结点）───────────────────────────────────┐
│ HandlerCollection.execute(node, ctx)                   │
│   正向 (CORE → AFTER) 执行 handler.handle()            │
│   各 handler 自行检查 ctx.flags 决定是否产出           │
│   → 无中央跳过逻辑                                    │
└───────────────────────────────────────────────────────┘
```

#### 示例

```python
class NewArithHandler(Handler):
    def preflight(self, ctx):
        ctx.flags.add("i32_core:scoreboard")   # 声明意图

    def handle(self, node, ctx):
        # 生成 scoreboard players operation ...
        ctx.emit(f"scoreboard players operation %res cmcf += %a cmcf")


class LegacyArithHandler(Handler):
    def preflight(self, ctx):
        if "i32_core:scoreboard" in ctx.flags:
            return  # 新实现已存在，不注册
        ctx.flags.add("legacy:arith")

    def handle(self, node, ctx):
        if "i32_core:scoreboard" in ctx.flags:
            return  # 被跳过
        # 旧实现 ...
```

### 5.6 HandlerCollection 接口

```python
class HandlerCollection:
    _sorted: list[Handler]

    def sort(self, fingerprint: str, pass_path: Path) -> None:
        """编译前：phase + 拓扑排序，读取或写入 pass.json。"""

    def preflight(self, ctx: WalkContext) -> None:
        """编译前：反向执行所有 handler.preflight()，填充 ctx.flags。"""

    def execute(self, node, ctx: WalkContext) -> None:
        """遍历时：正向执行所有 handler.handle()。各 handler 自行判断是否处理当前结点。"""
        for h in self._sorted:
            h.handle(node, ctx)
```

### 5.7 排序策略

#### 两级排序

```
┌─────────────────────────────────────────────┐
│ Step 1: 按 phase 分组                        │
│   CORE (0) < BEFORE (1) < MAIN (2) < AFTER (3) │
├─────────────────────────────────────────────┤
│ Step 2: 同 phase 内拓扑排序                  │
│   before / after 声明构建有向图              │
│   A.before = ["B"] → 边 A → B              │
│   A.after  = ["B"] → 边 B → A              │
│   拓扑排序后: [..., B, A, ...] 或 [..., A, B, ...] │
└─────────────────────────────────────────────┘
```

- 循环依赖 → 报 error（不静默 fallback）
- 引用了不存在的 handler id → 报 error
- 未声明 before/after → 按注册顺序

#### pass.json 缓存

```
pass.json 不存在 → 执行上述排序 → 写入 pass.json
pass.json 存在   → 直接读取

fingerprint = hash(已安装模块列表)   # 仅基于模块列表，不基于 pass 顺序
fingerprint ≠ pass.json 中的值     → 重新排序
```

- corner case：手动修改 `pass.json` 中的 handler 顺序可覆盖排序结果
- 手动修改 `pass.json` 后，**不触发重新排序**（fingerprint 仅基于模块列表）

```
_registry: dict[str, HandlerCollection]

  "module"              → [PackMetaHandler]

  "function.enter"      → [EntrySetupHandler,  DefaultEnterHandler]
  "function.exit"       → [DefaultExitHandler]

  "block.enter"         → [BlockEnterHandler]
  "block.exit"          → [BlockExitHandler]

  "instruction.add"     → [ArithHandler]
  "instruction.sub"     → [ArithHandler]
  "instruction.mul"     → [ArithHandler]
  "instruction.br"      → [BranchHandler]
  "instruction.ret"     → [TerminatorHandler]
  "instruction.switch"  → [TerminatorHandler]
  ...
```

展开逻辑：`@register(node="instruction", on=["add", "sub", "mul"], id="arith")` 将同一个 handler 推入 `"instruction.add"`, `"instruction.sub"`, `"instruction.mul"` 三个 `HandlerCollection`。

### 5.8 遍历与分发

```
IRModule
  │ _registry["module"].execute(node=module, ctx)
  │
  └→ for func in module.functions:
       │ if func.is_declaration: skip
        │ ctx.trace.annotations = func.annotations
        │
       │ _registry["function.enter"].execute(node=func, ctx)
       │
       └→ for block in func.blocks:
            │ ctx.enter_block(block)
            │ _registry["block.enter"].execute(node=block, ctx)
            │
            └→ for inst in block.instructions:
                 │ _registry[f"instruction.{inst.opcode}"].execute(node=inst, ctx)
                 │
            │ _registry["block.exit"].execute(node=block, ctx)
            │ ctx.exit_block(block)
            │
       │ _registry["function.exit"].execute(node=func, ctx)
```

### 5.9 确认 ✓

- [x] Handler 使用类，含 `preflight` + `handle` 双方法
- [x] Flags 模型：反向 preflight（编译前一次） → 正向 handle（遍历时）
- [x] 冒号分段式标签（如 `"i32_core:scoreboard"`）
- [x] `HandlerCollection.sort()` + `preflight()` + `execute()` 三方法
- [x] preflight 仅执行一次，flags 编译前确定且全程不变
- [x] 无中央跳过逻辑——各 handler 自行检查 flags
- [x] Phase 四阶段：CORE/BEFORE/MAIN/AFTER（默认 MAIN）
- [x] before/after 同级拓扑排序（循环依赖/无效引用报 error）
- [x] 函数注解由 handler 自行检查 `node.annotations`（`frozenset[str] | None`）
- [x] `HandlerCollection.execute()` 无中央筛选逻辑，全部 handler 均被调用
- [x] `Handler.filter_tags` 已移除
- [x] pass.json 缓存排序，fingerprint 仅基于模块列表 hash
- [x] Corner case 通过手动修改 pass.json 解决

### 5.10 Handler 加载机制

`mcc build` 执行时，通过 `importlib` 动态加载项目内 `.cmcf/handler/` 目录下的所有模块。

#### 加载逻辑

```python
def _load_handlers(proj_dir: Path) -> None:
    handler_dir = proj_dir / ".cmcf" / "handler"
    sys.path.insert(0, str(handler_dir))    # 将 handler 目录加入搜索路径

    for module_dir in sorted(handler_dir.iterdir()):
        if module_dir.is_dir():
            importlib.import_module(module_dir.name)  # "echo_test", "i32_core"
```

#### 模块结构要求

每个 handler 模块必须是一个标准 Python 包，包含 `__init__.py`：

```
cmcf/libs/<module>/handler/
├── __init__.py          # 可导入 handler 类触发 @register
├── arithmetic.py
└── memory.py
```

```python
# __init__.py
from .arithmetic import AddHandler, SubHandler
from .memory import AllocaHandler
```

`cmcf install` 时通过 `shutil.copytree` 完整复制 handler 目录到 `.cmcf/handler/<module>/`，`__init__.py` 随模块源提供。

#### `--env` 参数（预留）

```bash
mcc build combined.bc --project . --env .cmcf    # 默认
mcc build combined.bc --project . --env .custom  # 自定义 handler 环境目录
```

#### 已确认 ✓

- [x] `.cmcf/handler/` 加入 `sys.path`，直接 `importlib.import_module("<module_name>")`
- [x] 每个 handler 模块提供 `__init__.py`，由模块作者负责
- [x] `cmcf install` 不做额外 `__init__.py` 创建——模块自身保证包结构完整
- [x] 预留 `--env` 参数用于自定义 handler 目录

---

## 7. C Header 导出

### 标注方式

```c
// cmcf.h
#define CMCF_ENTRY_EXPORT    __attribute__((annotate("cmcf:entry:export")))
#define CMCF_ENTRY_EXPORT_AS(path) \
    __attribute__((annotate("cmcf:entry:export:" path)))
```

```c
#include "cmcf.h"

// 函数名即为导出路径
CMCF_ENTRY_EXPORT int get_score(int player_id, int score) {
    return player_id + score;
}

// 自定义导出路径（支持 / 分隔文件夹层级）
CMCF_ENTRY_EXPORT_AS("sub/special_path")
int get_score(int player_id, int score) {
    return player_id + score;
}
```

### 导出模式

| compile.mode | 默认行为 | 显式选项 |
|-------------|---------|---------|
| `"module"` | 始终导出 Header | — |
| `"datapack"` | 不导出 Header | `mcc --export-header` |

### IR 模型扩展

```python
@dataclass(frozen=True)
class IRParameter:
    name: str
    index: int
    param_type: str                       # "i32", "ptr", "float" — 从 llvmlite 提取

@dataclass(frozen=True)
class IRFunction:
    name: str
    params: tuple[IRParameter, ...]
    blocks: tuple[IRBlock, ...]
    is_declaration: bool
    return_type: str | None = None        # "i32" / "void" / None
    annotations: frozenset[str] | None = None   # None=无注解
```

### Header 生成注册

```python
@register(node="function", on="exit",
          id="export_header", phase=Phase.AFTER)
class ExportHeaderHandler(Handler):
    def handle(self, node: IRFunction, ctx: WalkContext) -> None:
        if (ctx.compile_mode == "datapack"
                and not ctx.config.export_header):
            return
        if node.annotations and "cmcf:entry:export" in node.annotations:
            ctx.header_exporter.export(node)
        else:
            # 检查 EXPORT_AS
            for ann in (node.annotations or ()):
                if ann.startswith("cmcf:entry:export:"):
                    ctx.header_exporter.export(node, export_as=ann.split(":", 3)[2])
                    break
```

### `HeaderExporter`

```python
class HeaderExporter:
    LLVM_TO_C = {
        "void": "void", "i1": "_Bool", "i8": "char",
        "i16": "short", "i32": "int", "i64": "long long",
        "float": "float", "double": "double",
        "ptr": "void*", "half": "unsigned short",
    }

    def export(self, func: IRFunction, writer: FileWriter,
               export_as: str | None = None) -> None:
        """根据 EXPORT 或 EXPORT_AS 标注导出 C Header。"""
        name = export_as or func.name
        path = f"headers/{name}.h"
        guard = f"CMCF_{name.replace('/', '_').upper()}_H"
        c_params = ", ".join(
            f"{self._to_c(p.param_type)} {p.name}"
            for p in func.params
        )
        c_return = self._to_c(func.return_type) if func.return_type else "void"

        writer.push(path) if writer._current_path else writer.open(path)
        writer.emit(f"#ifndef {guard}")
        writer.emit(f"#define {guard}")
        writer.emit(f"{c_return} {func.name}({c_params});")
        writer.emit(f"#endif")
        writer.close()

    def _to_c(self, llvm_type: str) -> str:
        return self.LLVM_TO_C.get(llvm_type, llvm_type)
```

### 模板输出

```c
// Generated by CMCF — do not edit
#ifndef CMCF_GET_SCORE_H
#define CMCF_GET_SCORE_H
int get_score(int player_id, int score);
#endif
```

### 已确认 ✓

- [x] `EXPORT` + `EXPORT_AS` 两种宏
- [x] module 模式始终导出，datapack 模式需 `--export-header`
- [x] `IRParameter.param_type` + `IRFunction.return_type` + `annotations` 新字段
- [x] `annotations` 类型 `frozenset[str] | None`
- [x] `HeaderExporter` 独立类，含 LLVM→C 类型映射表

---

## 8. `cmcf.json` 项目配置

### 完整格式

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
        "opt_level": 1,              // 0 | 1
        "clang_path": "clang",
        "llvm_link_path": "llvm-link"
    },

    "path_vars": {},                 // 覆盖默认 MC 路径变量

    "files": {},                     // 静态文件 (key → path)

    "meta": {
        "description": "A custom Minecraft datapack",
        "author": "user",
        "homepage": "https://github.com/user/my_project",
        "license": "MIT"
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
| `path_vars` | 覆盖默认 MC 路径变量（适应不同 pack_format 的目录命名变化） |
| `files` | 静态文件路径映射 |
| `meta` | 自由键值，仅读取与显示 |

### `path_vars` 默认值

cmcf 根据 `project.pack_format` 提供内置默认字典，用户在 `path_vars` 中显式声明的键会覆盖默认值。

```jsonc
// cmcf 内置默认（pack_format [88,0] 及以上）
{
    "function":     "function",
    "tags":         "tags/function",
    "advancement":  "advancement",
    "loot_table":   "loot_table",
    "predicate":    "predicate",
    "item_modifier": "item_modifier",
    "recipe":       "recipe",
    "structure":    "structure",
    "dimension":    "dimension",
    "dimension_type": "dimension_type",
    "damage_type":  "damage_type",
    "enchantment":  "enchantment"
}
```

```jsonc
// 覆盖示例 — 兼容旧版 MC
"path_vars": {
    "function": "functions",
    "tags":     "tags/functions"
}
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

`files` 静态文件：
```
{project.dist}/datapack/{project.name}/data/{project.namespace}/
　　{path_vars[<key>]}/{project.id}/
```

#### module 模式

```
{project.dist}/module/{project.id}-{project.version}-{meta_hash}/
├── module.json                  ← 自动生成
├── function/                    ← 导出 + 内部 mcfunction
│   ├── main.mcfunction
│   ├── _internal/...
│   ├── _load/...
│   └── _tick/...
├── header/                      ← 生成的 C Header (仅导出函数)
│   ├── main.h
│   └── get_score.h
├── <files key1>/                ← 从 project.files 复制
└── <files key2>/...
```

`meta_hash`: SHA256(JSON.stringify(project.meta, sort_keys)) 的 hex 前 8 位。

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

### `modules.json` 格式

```jsonc
// project/.cmcf/modules.json
{
    "i32_core": {
        "version": "1.0.0",
        "install_paths": [
            ".cmcf/handler/i32_core/",
            ".cmcf/functions/i32_core/",
            ".cmcf/tags/i32_core/",
            "include/i32/"
        ],
        "syscalls": {"printf": "print.mcfunction", "malloc": "alloc.mcfunction",
                     "free": "free.mcfunction", "putchar": "io/putchar.mcfunction",
                     "getchar": "io/getchar.mcfunction"},
        "dependencies": {"ctrl_core": ">=1.0.0"}
    },
    "ctrl_core": {
        "version": "1.0.0",
        "install_paths": [
            ".cmcf/handler/ctrl_core/",
            ".cmcf/functions/ctrl_core/",
            "include/ctrl/"
        ],
        "syscalls": {},
        "dependencies": {}
    }
}
```

| 字段 | 说明 |
|------|------|
| `version` | 安装的版本号 |
| `install_paths` | list — 所有安装目录，`cmcf remove` 遍历删除 |
| `syscalls` | dict — syscall 签名→文件完整映射，冲突检测 + 调用生成共用 |
| `dependencies` | 从 module.json 缓存，`cmcf remove` 反向依赖检查 |

### 已确认 ✓

- [x] `cmcf.json` 分组：project / compile / path_vars / files / meta
- [x] `project.id` 必需，name/namespace 默认取 id
- [x] `path_vars` 覆盖默认 MC 路径变量，适应不同 pack_format
- [x] `compile.mode` 两种：datapack / module
- [x] module 模式自动生成 module.json + C Header，含 meta_hash
- [x] `modules.json` 使用 install_paths (list[str])，remove 遍历删除
- [x] `cmcf build` 生成 makefile + 调用 make（makefile 是否缓存后续决定）

---

## 9. WalkContext — Handler 运行时上下文

`WalkContext` 是 Handler 所有生成功能的来源，在 `mcc build` 时构建并注入遍历器。

### 总览

```python
@dataclass
class WalkContext:
    # === 配置（只读） ===
    namespace: str                              # MC 命名空间
    project_id: str                             # 项目/模块标识
    target_format: tuple[int, int]              # pack_format

    # === I/O ===
    writer: FileWriter                          # 多文件输出
    header_exporter: HeaderExporter             # C Header 导出

    # === 当前位置（只读，由 TreeWalker 维护） ===
    trace: Trace                                # 当前 Module/Function/Block/Instruction

    # === 命名 ===
    namer: NameProvider                         # 文件/变量/scoreboard 命名规则

    # === 查找表 ===
    registries: Registries                      # syscall + 未来扩展

    # === 作用域临时存储（进入新作用域时 clear） ===
    module_ctx: NodeContext                      # IRModule 级
    func_ctx: NodeContext                        # IRFunction 级
    block_ctx: NodeContext                       # IRBlock 级

    # === Handler 通信（preflight 填充，handle 读取） ===
    flags: set[str]
```

### 9.1 `FileWriter` — 多文件输出

管理多个输出文件，支持栈式切换。

```python
class FileWriter:
    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root
        self._current_path: Path | None = None
        self._current_buffer: list[str] = []
        self._completed: dict[Path, list[str]] = {}

    def open(self, rel_path: str) -> None:
        """快速切换：保存当前缓冲到 _completed，切换到新文件。"""

    def emit(self, line: str) -> None:
        """向当前文件写一行命令。"""

    def close(self) -> None:
        """保存当前文件到 _completed，清空 current。"""

    # ── 栈接口（备用） ──
    def push(self, rel_path: str) -> None:
        """把当前文件压栈，切换到新文件（保留恢复点）。"""

    def pop(self) -> None:
        """恢复到 push 之前的文件（继续写入）。"""

    def write_all(self) -> None:
        """Disk write for all _completed。"""
```

**使用场景**：
```
BlockHandler(enter)  → writer.open("func/entry.mcfunction")
  ArithHandler       → writer.emit("scoreboard players ...")
  BranchHandler      → writer.emit("execute if ... run function ...")
BlockHandler(exit)   → writer.close()

BlockHandler(enter)  → writer.open("func/loop.mcfunction")
  ...
BlockHandler(exit)   → writer.close()
```

### 9.2 `Trace` — 位置跟踪

```python
@dataclass
class Trace:
    """当前遍历位置（只读），由 TreeWalker 维护。"""
    module: IRModule | None = None
    function: IRFunction | None = None
    block: IRBlock | None = None
    instruction: IRInstruction | None = None
    annotations: frozenset[str] | None = None      # 当前函数注解
    module_name: str = ""                  # 当前 cmcf 模块名（如 "i32_core"）
    func_name: str = ""                    # 当前函数名（如 "main"）
    block_label: str = ""                  # 当前基本块标签（如 "entry"）
```

### 9.3 `NameProvider` — 命名规则

```python
class NameProvider:
    def __init__(self, project_id: str, namespace: str,
                 path_vars: dict[str, str],
                 target_format: tuple[int, int]) -> None: ...

    # ── mcfunction 文件路径 ──
    def func_file(self, module: str, func: str) -> str:
        """相对路径: "{module}/_internal/{func}.mcfunction" """

    def exported_file(self, module: str, func: str) -> str:
        """相对路径: "{module}/{func}.mcfunction" """

    def block_file(self, module: str, func: str, block_label: str) -> str:
        """相对路径: "{module}/_internal/{func}/{block_label}.mcfunction" """

    # ── 目录路径 ──
    def internal_dir(self) -> str: ...
    def load_dir(self) -> str: ...
    def tick_dir(self) -> str: ...

    # ── scoreboard ──
    def scoreboard_obj(self, var_name: str) -> str:
        """记分板目标名: "cmcf_var_{var_name}" """

    def scoreboard_player(self, reg_name: str) -> str:
        """记分板虚拟玩家名: "$cmcf.{reg_name}" """

    # ── Minecraft 引用 ──
    def function_ref(self, module: str, path: str) -> str:
        """完整 function 引用: "cmcf:i32_core/print" """
```

### 9.4 `NodeContext` — 作用域临时存储

键值对临时存储，进入新作用域时清空。`set`/`get` 自动按 `{module}:{name}` 拼接 key 避免不同 cmcf 模块间冲突。

```python
class NodeContext:
    _data: dict[str, Any] = {}
    _source_module: str = ""           # 当前 handler 所属的 cmcf 模块名

    def set(self, name: str, value: Any, module: str | None = None) -> None:
        key = f"{module or self._source_module}:{name}"
        self._data[key] = value

    def get(self, name: str, default: Any = None, module: str | None = None) -> Any:
        key = f"{module or self._source_module}:{name}"
        return self._data.get(key, default)

    def clear(self) -> None:
        self._data.clear()
```

Handler 使用示例：
```python
# handler 所属模块为 "i32_core" → _source_module = "i32_core"
ctx.func_ctx.set("local_vars", ["a", "b"])
# → key: "i32_core:local_vars"

# 显式跨模块访问
ctx.func_ctx.set("result", 42, module="ctrl_core")
# → key: "ctrl_core:result"
ctx.func_ctx.get("result", module="ctrl_core")
# → 42
```

### 9.5 `Registries` — 查找表

```python
@dataclass
class Registries:
    syscall: SysCallRegistry
    # 未来扩展: variable_mapping, function_table, annotation_index
```

### 9.6 已确认 ✓

- [x] `FileWriter` 栈接口（`push`/`pop`），备用
- [x] `NodeContext.set/get(name, module=None)` 自动拼接 `{module}:{name}`
- [x] `Trace.annotations: frozenset[str] | None` 替代单个 `annotation`
- [x] `HeaderExporter` 独立类，挂载到 `WalkContext.header_exporter`
- [x] `NameProvider` 统一文件/变量/scoreboard/Minecraft 引用命名
- [x] `module_ctx` / `func_ctx` / `block_ctx` 进入新作用域时 clear
- [x] `flags` 用于 handler 间通信

---

## 10. CMCF 项目源码结构

### 设计原则

- 框架 **不含 Minecraft 逻辑** — 所有语义由 `libs/` 模块提供
- CLI 入口分离 — `cmcf` 脚手架 + `mcc` 编译器，共处 `cli/`
- `core/` 扁平结构 — 按职责拆分，最大文件 < 200 行

### 目录树

```
CMCF/
├── cmcf/
│   ├── __init__.py
│   │
│   ├── cli/                          # CLI 入口
│   │   ├── cmcf.py                   # scaffold, repo, install, remove, build
│   │   └── mcc.py                    # compile, link, build
│   │
│   ├── core/                         # 框架引擎（无 Minecraft 语义）
│   │   ├── __init__.py
│   │   ├── config.py                 # CompileConfig + cmcf.json 解析
│   │   ├── clang.py                  # ClangInterface (C→BC)
│   │   ├── linker.py                 # LinkerInterface (llvm-link)
│   │   ├── ir_converter.py           # llvmlite→结构化IR + annotations提取
│   │   ├── ir_instructions.py        # IRModule/Function/Block/Instruction/Parameter
│   │   ├── ir_values.py              # IROperand 子类 (5种)
│   │   ├── ir_walker.py              # TreeWalker（原 ir_visitor）
│   │   ├── handler.py                # @register, Handler, Phase, HandlerCollection
│   │   ├── context.py                # WalkContext, Trace, FileWriter,
│   │   │                             #   NameProvider, NodeContext, Registries
│   │   ├── header_exporter.py        # HeaderExporter (→ C Header)
│   │   ├── models.py                 # *Manifest TypedDict 定义
│   │   └── syscall_registry.py       # SysCallRegistry, SysCallEntry
│   │
│   ├── libs/                         # 内置模块仓库（只读，随 cmcf 更新）
│   │   ├── m3.json
│   │   ├── ctrl_core/
│   │   │   ├── module.json
│   │   │   ├── handler/...
│   │   │   ├── source/...
│   │   │   └── function/...
│   │   └── i32_core/
│   │       ├── module.json
│   │       ├── handler/...
│   │       ├── source/...
│   │       └── function/...
│   │   └── echo_test/                 # 测试模块（含 __init__.py 包结构）
│   │       ├── module.json
│   │       ├── handler/
│   │       │   ├── __init__.py
│   │       │   └── echo.py
│   │       └── source/...
│   │
│   └── site_libs/                    # 三方模块仓库（可写）
│       ├── m3.json
│       └── .keep
│
├── project/                          # 用户项目模板
├── output/                           # 构建输出示例
├── example/                          # 测试示例
│   ├── *.c                           # 10 单文件测试
│   └── multi/                        # 多文件测试
├── docs/                             # 文档
├── pyproject.toml
└── README.md
```

### 文件迁移对照

| 旧路径 | 新路径 / 动作 |
|--------|--------------|
| `cmcf/__main__.py` | → 拆分为 `cmcf/cli/cmcf.py` + `cmcf/cli/mcc.py` |
| `cmcf/config.py` | → `cmcf/core/config.py`，扩展为 cmcf.json 完整结构 |
| `cmcf/core/ir_visitor.py` | → `cmcf/core/ir_walker.py` |
| `cmcf/core/ir_instructions.py` | → 保留，IRParameter + IRFunction 新增字段 |
| `cmcf/core/ir_types.py` | → 删除（未使用） |
| `cmcf/mc/handlers/__init__.py` | → `cmcf/core/handler.py`（注册器 + HandlerCollection） |
| `cmcf/mc/handlers/base.py` | → 合并入 `cmcf/core/handler.py` |
| `cmcf/mc/handlers/{arithmetic,...}.py` | → 删除，迁移到 `cmcf/libs/i32_core/handler/` |
| `cmcf/mc/syscalls/` | → `cmcf/core/syscall_registry.py` |
| `cmcf/mc/` | → **整个目录删除** |
| `cmcf/lib/` | → 删除（被 `cmcf/libs/` 替代） |
| — | → **新增** `cmcf/core/models.py` |

### `pyproject.toml` console_scripts

```toml
[project.scripts]
cmcf = "cmcf.cli.cmcf:main"
mcc  = "cmcf.cli.mcc:main"
```

### core/ 模块依赖关系

```
config                ← 无依赖
clang                 ← config
linker                ← config
ir_converter          ← ir_instructions, ir_values
ir_walker             ← ir_converter, handler, context
handler               ← ir_instructions
context               ← ir_instructions, ir_values, syscall_registry, header_exporter
syscall_registry      ← 无依赖
header_exporter       ← ir_instructions, context.FileWriter
models                ← 无依赖
```

### 已确认 ✓

- [x] `mc/` 目录完全移除，Minecraft 语义由 `libs/` 模块提供
- [x] `core/` 扁平结构，最大文件 < 200 行
- [x] CLI 入口分离为 `cli/cmcf.py` + `cli/mcc.py`
- [x] 旧 `cmcf/lib/` 删除，由 `cmcf/libs/` 替代
- [x] 无用的 `ir_types.py` 删除
- [x] 新增 `cmcf/core/models.py` — 所有 JSON 清单 TypedDict 定义

---

## 11. JSON 清单模型 (`models.py`)

所有 JSON 文件的 TypedDict 定义集中在 `cmcf/core/models.py`。

### 11.1 `ProjectManifest` — cmcf.json

```python
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
```

### 11.2 `ModuleManifest` — module.json

```python
class ModuleManifest(TypedDict):
    """单个模块定义"""
    name: str
    version: str
    meta: NotRequired[dict[str, str]]
    pack_format: PackFormat              # 复用
    dependencies: NotRequired[dict[str, str]]
    source: NotRequired[str]
    source_alias: NotRequired[str]
    handler: NotRequired[str]
    files: NotRequired[dict[str, str]]
    syscalls: NotRequired[dict[str, str]]
```

### 11.3 `InstalledManifest` — modules.json

```python
class InstalledModuleEntry(TypedDict):
    """单个已安装模块记录"""
    version: str
    install_paths: list[str]
    syscalls: dict[str, str]
    dependencies: dict[str, str]

InstalledManifest = dict[str, InstalledModuleEntry]
```

### 11.4 `M3Manifest` — m3.json

> **M**inecraft **M**cfunction **M**odule

```python
class M3VersionEntry(TypedDict):
    """仓库中某个模块的一个版本"""
    path: str
    source: str
    installed_at: str
    dependencies: dict[str, str]

M3VersionIndex = dict[str, M3VersionEntry]   # {version → entry}
M3Manifest = dict[str, M3VersionIndex]        # {module_name → version_index}
```

### 11.5 `PassManifest` — pass.json

```python
class PassManifest(TypedDict):
    """handler 排序缓存"""
    fingerprint: str
    order: dict[str, list[str]]
```

### 11.6 完整 import

```python
# cmcf/core/models.py
from typing import TypedDict, NotRequired, Literal
```

### 与 `CompileConfig` 的关系

- `ProjectManifest` 等 TypedDict 是 JSON 文件的静态视图（`json.load` → TypedDict）
- `cmcf/core/config.py` 中的 `CompileConfig` dataclass 是运行时对象，持有 `Path` 引用等非 JSON 字段
- 转换：`CompileConfig.from_manifest(manifest: ProjectManifest)` → 运行时配置

### 已确认 ✓

- [x] 五种 `*Manifest` 统一命名
- [x] `M3` = Minecraft Mcfunction Module
- [x] `InstalledManifest` 独立 TypedDict（不复用 M3Manifest — 结构不同）
- [x] `PackFormat` 复用于 `ProjectManifest` 和 `ModuleManifest`

| 优先级 | 议题 |
|--------|------|
| 🔴 | module 模式自动生成 module.json 具体逻辑 |
| 🟡 | `cmcf repo install` 远程仓库获取（URL/Git） |
| 🟡 | `cmcf install` 错误回滚机制 |
| 🟡 | makefile 模板结构 + 缓存策略 |
| 🟢 | Windows 上 make fallback 方案 |
| 🟢 | compile_to_ir() (文本IR) 的保留/移除 |
