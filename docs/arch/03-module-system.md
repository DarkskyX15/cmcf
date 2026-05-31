# 3. 模块系统与包管理

> 来源: `docs/development/redesign.md` §2, §3, §5
> 代码: `cmcf/cli/cmcf.py` (install/remove/repo 命令), `cmcf/libs/`, `cmcf/site_libs/`

---

## 命令设计（方案 D）

```bash
cmcf repo install <path|name>     → 安装模块到 site_libs（本地仓库）
cmcf repo remove <name>           → 从 site_libs 移除模块
cmcf repo list                    → 列出仓库内可用模块
cmcf repo update                  → 更新仓库内模块

cmcf install <name[:version]>     → 安装模块到当前项目
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
│   ├── m3.json
│   ├── ctrl_core/...
│   └── i32_core/...
└── site_libs/                     # 第三方模块（用户管理）
    ├── m3.json
    └── my_module-1.0.0/
```

---

## 模块安装映射

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
├── handler/              # → .cmcf/handler/i32_core/
│   ├── __init__.py
│   ├── arithmetic.py
│   └── memory.py
├── source/               # → include/i32/ (alias)
│   ├── i32_core.h
│   └── i32_core.c
├── function/             # → .cmcf/functions/i32_core/
│   ├── print.mcfunction
│   └── alloc.mcfunction
└── tags/                 # → .cmcf/tags/i32_core/
    └── function/load.json
```

---

## `cmcf install <name>` 流程

```
1. 版本选择
   ├─ 未指定版本 → 取与项目 pack_format 兼容的最新版本
   └─ 指定版本 → 精确匹配

2. 兼容性检查
   → module.pack_format.min ≤ project.target_format ≤ module.pack_format.max

3. syscall 冲突检查
   → 新模块 syscall 与已安装模块 syscall 取交集
   → 交集非空 → 报错中止

4. 递归安装依赖
   → 遍历 dependencies，对每个依赖递归执行 install

5. 文件复制 + 记录 install_paths
   handler: → .cmcf/handler/<name>/
   source:  → include/<source_alias 或 name>/
   files.*: → .cmcf/<key>/<name>/

6. 更新 .cmcf/modules.json

7. 使 pass.json 失效
```

### `cmcf remove <name>` 流程

```
1. 检查是否存在 → 不在则报错
2. 遍历已安装模块的 dependencies → 反向依赖报 warning
3. 遍历 modules[<name>].install_paths → 逐一删除
4. 从 .cmcf/modules.json 移除条目
5. 删除 pass.json
```

### `cmcf repo install <path>` 流程

```
1. 读取 module.json → 提取 name + version
2. 检查 libs/m3.json → 若同名内置模块 → 报错 "不可覆盖"
3. 复制到 site_libs/<name>-<version>/
4. 更新 site_libs/m3.json
```

---

## 模块命名空间隔离（方案 B）

### 输出结构

```
output/<project>/data/<namespace>/function/
├── <user_module>/
│   ├── main.mcfunction       ← 导出函数
│   ├── _internal/            ← static / 非导出
│   ├── _load/                ← minecraft:load
│   └── _tick/                ← minecraft:tick
├── i32_core/                 ← 安装的模块
│   ├── print.mcfunction      ← syscall
│   ├── _internal/...
│   ├── _load/...
│   └── _tick/...
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

## 已确认 ✓

- 方案 D：`repo install/remove/list` + `install/remove`
- 两层模型：site_libs（仓库） + project（项目）
- `install <name>` 自动递归安装依赖
- 版本选择：取与项目 pack_format 兼容的最新版本
- `site_libs` 不可覆盖 `libs` 内同名内置模块
- `source` 和 `handler` 独立可选，空值忽略
- `source_alias` 影响 `#include` 路径和编译目录
- `handler` → `.cmcf/handler/<module_name>/`
