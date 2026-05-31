# 1. 系统总览

> 来源: `docs/development/redesign.md` §1, §10
> 代码: `cmcf/cli/cmcf.py`, `cmcf/cli/mcc.py`, `cmcf/__init__.py`, `pyproject.toml`

---

## 工具拆分

| 工具 | 角色 | 职责 |
|------|------|------|
| `cmcf` | 项目管理器 | 脚手架（`init`）、模块安装（`install`/`remove`）、构建触发（`build`） |
| `mcc` | 编译器 | clang/llvm-link 封装、IR 解析树遍历、datapack + C Header 生成 |

`mcc` 作为 `cmcf` 的子模块 `cmcf/cli/mcc.py`，通过 `console_scripts` 暴露：

```toml
# pyproject.toml
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

### 完整调用链

```
cmcf init my_project/
  └→ 生成: .cmcf/cmcf.json, .cmcf/modules.json, src/main.c

cmcf install i32_core
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

---

## 项目源码结构

```
CMCF/
├── cmcf/
│   ├── __init__.py
│   ├── cli/
│   │   ├── cmcf.py                   # scaffold, repo, install, remove, build
│   │   └── mcc.py                    # compile, link, build
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 # CompileConfig + cmcf.json 解析
│   │   ├── clang.py                  # ClangInterface (C→BC)
│   │   ├── linker.py                 # LinkerInterface (llvm-link)
│   │   ├── ir_converter.py           # llvmlite→结构化IR + annotations提取
│   │   ├── ir_instructions.py        # IR 结点类型
│   │   ├── ir_values.py              # IROperand 子类
│   │   ├── ir_walker.py              # TreeWalker
│   │   ├── handler.py                # @register, Handler, Phase, HandlerCollection
│   │   ├── context.py                # WalkContext, Trace, FileWriter, NameProvider, NodeContext, Registries
│   │   ├── header_exporter.py        # HeaderExporter
│   │   ├── models.py                 # *Manifest TypedDict 定义
│   │   └── syscall_registry.py       # SysCallRegistry, SysCallEntry
│   ├── libs/
│   │   ├── m3.json
│   │   ├── ctrl_core/...
│   │   ├── i32_core/...
│   │   └── echo_test/                # 测试模块
│   └── site_libs/                    # 三方模块仓库
├── example/
├── docs/
│   ├── arch/                         # 模块架构文档
│   └── development/                  # 设计讨论
└── pyproject.toml
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

### 文件迁移对照

| 旧路径 | 新路径 / 动作 |
|--------|--------------|
| `cmcf/__main__.py` | → 拆分为 `cmcf/cli/cmcf.py` + `cmcf/cli/mcc.py` |
| `cmcf/config.py` | → `cmcf/core/config.py`，扩展为 cmcf.json 完整结构 |
| `cmcf/core/ir_visitor.py` | → `cmcf/core/ir_walker.py` |
| `cmcf/core/ir_types.py` | → 删除（未使用） |
| `cmcf/mc/handlers/` | → `cmcf/core/handler.py`（注册器）+ `cmcf/libs/`（handler 实现） |
| `cmcf/mc/syscalls/` | → `cmcf/core/syscall_registry.py` |
| `cmcf/mc/` | → 整个目录删除 |
| `cmcf/lib/` | → 删除（被 `cmcf/libs/` 替代） |
| — | → 新增 `cmcf/core/models.py` |

---

## 已确认 ✓

- `mcc` 为 `cmcf/cli/mcc.py` 子模块，与 `cmcf` 共享代码
- `cmcf build` 生成 makefile + 调用 make（makefile 缓存策略后续决定）
- `cmcf.json`、`modules.json` 存放在 `.cmcf/` 内
- `make` 驱动编译/链接流程，`mcc` 作为 makefile 中的工具被调用
- 现有 `cmcf/__main__.py` 中的 clang/llvm-link 逻辑迁移到 `mcc`
- `core/` 扁平结构，最大文件 < 200 行
- CLI 入口分离为 `cli/cmcf.py` + `cli/mcc.py`
- 旧 `cmcf/lib/` 删除，由 `cmcf/libs/` 替代
