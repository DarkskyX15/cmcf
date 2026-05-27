# MCMF 编译模型设计

## 概述

MCMF 是一个 **gcc 风格的 clang 工具链封装**。用户像使用 gcc 一样编译 C 代码，内部调用 clang/llvm-link，
最终输出 Minecraft 数据包。

## 编译流水线

```
.c 文件 ──[clang -c -emit-llvm]──▶ .bc 文件
                                        │
多个 .bc ──[llvm-link]─────────────────▶ combined.bc
                                        │
combined.bc ──[llvmlite + IRWalker]────▶ datapack/
```

## CLI 设计（gcc 对标）

| gcc 命令 | MCMF 等效 |
|----------|----------|
| `gcc -c main.c` | `cmcf -c main.c` → `main.bc` |
| `gcc -c main.c -o foo.o` | `cmcf -c main.c -o foo.bc` |
| `gcc main.c utils.c` | `cmcf main.c utils.c` → `./datapack/` |
| `gcc main.o utils.o` | `cmcf main.bc utils.bc` → `./datapack/` |
| `gcc -o prog main.c utils.c` | `cmcf -o mypack/ main.c utils.c` |
| `gcc -I./inc -DDEBUG main.c` | `cmcf -I./inc -DDEBUG main.c` |

**标志**：
- `-c` — 仅编译到 .bc，不生成数据包
- `-o <path>` — 输出路径（-c 时为 bitcode 文件，否则为数据包目录）
- `-O {0,1}` — 优化等级
- `-I <path>` — include 搜索路径
- `-v` — verbose 模式
- `--clang <path>` — 自定义 clang 路径
- `--llvm-link <path>` — 自定义 llvm-link 路径
- `--output-ir <path>` — 导出文本 IR 用于调试

**内部决策**：
- 若传入所有 .c 文件：clang 逐个编译 → llvm-link 合并 → 生成数据包
- 若传入混合 .c/.bc：.c 先编译，再与 .bc 合并
- 若仅传入单个 .bc：跳过 llvm-link，直接生成数据包

## 多文件编译

### 编译阶段（per-file）

```bash
clang -c -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
      -fno-discard-value-names -I <paths> \
      -x c source.c -o source.bc
```

- 每个 `.c` 文件独立编译为 LLVM bitcode (.bc)
- 保留变量名（`-fno-discard-value-names`）
- 保留函数注解（`__attribute__((annotate))`）

### 链接阶段

```bash
llvm-link a.bc b.bc c.bc -o combined.bc
```

- 合并所有 bitcode 文件
- `@llvm.global.annotations`（appending global）被正确合并
- 静态函数不冲突，外部函数自动链接

## 函数入口设计

### cmcf.h 宏定义

用户通过 `#include "cmcf.h"` 引入入口注解宏：

```c
// cmcf.h
#ifndef CMCF_H
#define CMCF_H

#define CMCF_ENTRY_LOAD   __attribute__((annotate("cmcf:entry:load")))
#define CMCF_ENTRY_TICK   __attribute__((annotate("cmcf:entry:tick")))
#define CMCF_ENTRY_EXPORT __attribute__((annotate("cmcf:entry:export")))

#endif
```

### 注解对应关系

| C 声明 | 注解 | Minecraft 映射 |
|--------|------|---------------|
| `CMCF_ENTRY_LOAD void main(void)` | `cmcf:entry:load` | `minecraft:load` 函数标签 |
| `CMCF_ENTRY_TICK void on_tick(void)` | `cmcf:entry:tick` | `minecraft:tick` 函数标签 |
| `CMCF_ENTRY_EXPORT int get_score(int x)` | `cmcf:entry:export` | 暴露的 `.mcfunction`（手动 `/function` 调用） |
| `static void helper(void)` | 无 | `_internal/helper.mcfunction`（仅内部调用） |
| `void normal_func(void)` | 无 | `.mcfunction`（内部调用） |

### 示例

```c
#include "cmcf.h"

CMCF_ENTRY_LOAD void main(void) {
    // 世界加载时执行（minecraft:load 标签）
}

CMCF_ENTRY_TICK void on_tick(void) {
    // 每tick执行（minecraft:tick 标签）
}

CMCF_ENTRY_EXPORT int get_score(int player_id) {
    // 生成暴露的 mcfunction：/function cmcf:get_score
    return 100;
}

static void internal_helper(void) {
    // _internal/internal_helper.mcfunction
}
```

### IR 解析

`IRConverter` 解析 `@llvm.global.annotations` 提取每个函数的注解：

```llvm
@llvm.global.annotations = appending global [2 x { ptr, ptr, ptr, i32, ptr }] [
    { ptr, ptr, ptr, i32, ptr } { ptr @main,
        ptr @.str, ptr @.str.1, i32 1, ptr null },
    { ptr, ptr, ptr, i32, ptr } { ptr @on_tick,
        ptr @.str.2, ptr @.str.3, i32 2, ptr null }
]
```

## 数据包输出结构

```
<datapack>/
├── pack.mcmeta
└── data/
    └── cmcf/
        ├── function/
        │   ├── main.mcfunction              # CMCF_ENTRY_LOAD
        │   ├── on_tick.mcfunction           # CMCF_ENTRY_TICK
        │   ├── get_score.mcfunction         # CMCF_ENTRY_EXPORT
        │   └── _internal/
        │       └── internal_helper.mcfunction  # static 函数
        └── tags/
            └── function/
                ├── load.json                # {"values":["cmcf:main"]}
                └── tick.json                # {"values":["cmcf:on_tick"]}
```

## 构建集成

### Makefile

```makefile
CMCF = cmcf
CFLAGS = -O1 -I./include

BC = main.bc utils.bc

%.bc: %.c cmcf.h
	$(CMCF) -c $(CFLAGS) $<

combined.bc: $(BC)
	$(CMCF) $^ -o $@

mypack/: combined.bc
	$(CMCF) $< -o $@

.PHONY: clean
clean:
	rm -f *.bc combined.bc
	rm -rf mypack/
```

## 已知限制

- 优化等级限制 O0/O1（更高优化会引入不可处理的 IR 指令）
- 向量化始终禁用（`-fno-vectorize -fno-slp-vectorize`）
- 仅支持 C 语言（`-x c`），不支持 C++
- 变量名保留依赖 `-fno-discard-value-names`（优化消除的变量无法恢复）
