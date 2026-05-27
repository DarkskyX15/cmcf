# CMCF - C to Minecraft Function Compiler

CMCF 是一个将 C 语言编译为 Minecraft 数据包 (mcfunction) 的编译器，利用 LLVM IR 作为中间表示层。

## 编译流水线

```
.c 文件 ──[clang -c -emit-llvm]──▶ .bc 文件 ──[llvm-link]──▶ combined.bc ──[cmcf]──▶ datapack/
```

- **前端**: clang 将 C 代码编译为 LLVM bitcode
- **链接**: llvm-link 合并多个 bitcode 文件
- **后端**: cmcf 解析 IR，生成 mcfunction 数据包 (Phase 2)

## 开发阶段

### Phase 1 (已完成): IR 分析层 + 工具链集成

- gcc 风格 CLI: `-c`, `-o`, `-O`, `-I`, `-D`
- 多文件编译 + llvm-link 链接
- 变量名保留 (`-fno-discard-value-names`)
- IR 结构化解析 (纯 Python 表示，无 llvmlite 依赖)
- Handler 框架 (`@register_handler`)

### Phase 2 (计划): mcfunction 生成层

TODO:
- mcfunction 命令生成
- 记分板映射 / 符号表管理
- 函数入口注解 (`cmcf.h`)
- 数据包文件生成

## 前置要求

- Python 3.8+
- [Clang](https://llvm.org/) (C → LLVM IR 编译)
- [llvm-link](https://llvm.org/docs/CommandGuide/llvm-link.html) (多文件链接)
- llvmlite (`pip install llvmlite`)

## 安装

```bash
git clone <repository-url>
cd CMCF
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install llvmlite
```

## 使用方法

```bash
# 单文件编译
python -m cmcf input.c

# 多文件编译 (自动链接)
python -m cmcf math.c main.c utils.c

# 指定输出目录
python -m cmcf input.c -o mypack/

# 先编译为 bitcode，再链接
python -m cmcf -c math.c          # → math.bc
python -m cmcf -c main.c          # → main.bc
python -m cmcf math.bc main.bc    # → datapack/

# 优化等级 (O0/O1, 默认 O1)
python -m cmcf input.c -O0

# include 路径和宏定义
python -m cmcf input.c -I ./include -DDEBUG

# verbose 模式
python -m cmcf input.c -v

# 导出 IR 调试
python -m cmcf input.c --output-ir debug.ll

# 自定义工具链路径
python -m cmcf input.c --clang /path/to/clang --llvm-link /path/to/llvm-link
```

### 可用标志

| 标志 | 说明 |
|------|------|
| `-c` | 仅编译到 .bc，不生成数据包 |
| `-o <path>` | 输出路径 (`-c`: .bc 文件，否则: 数据包目录) |
| `-O {0,1}` | 优化等级 (默认 1) |
| `-I <path>` | include 搜索路径 (可重复) |
| `-D <macro>` | 预处理器宏 (可重复) |
| `-v`, `--verbose` | 输出 IR 遍历详情到 stderr |
| `--clang <path>` | 自定义 clang 路径 |
| `--llvm-link <path>` | 自定义 llvm-link 路径 |
| `--output-ir <path>` | 导出合并后的文本 IR |

### Makefile 集成

```makefile
CMCF = python -m cmcf
CFLAGS = -O1 -I./include

BC = math.bc main.bc

%.bc: %.c
	$(CMCF) -c $(CFLAGS) $<

mypack/: $(BC)
	$(CMCF) $(CFLAGS) -o $@ $^
```

## 项目结构

```
CMCF/
├── cmcf/
│   ├── __main__.py                # CLI 入口 (gcc 风格)
│   ├── config.py                  # CompileConfig 编译配置
│   ├── core/                      # 核心层 (无 Minecraft 语义)
│   │   ├── clang.py               # ClangInterface: C→BC 编译
│   │   ├── linker.py              # LinkerInterface: llvm-link 封装
│   │   ├── ir_converter.py        # IRConverter: llvmlite→结构化IR
│   │   ├── ir_instructions.py     # IRInstruction/Block/Function/Module
│   │   ├── ir_types.py            # IRType 类型层次
│   │   ├── ir_values.py           # IROperand 子类 (5种)
│   │   └── ir_visitor.py          # IRWalker + WalkReport + Router
│   └── mc/                        # Minecraft 语义层
│       ├── handlers/              # 指令处理器
│       │   └── ...                # memory, arithmetic, comparison, etc.
│       └── syscalls/              # 系统调用框架
│           └── ...                # SysCallHandler 基类 + Registry
├── example/
│   ├── *.c                        # 单文件测试示例
│   └── multi/                     # 多文件测试示例
├── docs/                          # 文档
└── pyproject.toml
```

## 设计文档

- [架构设计](docs/development/architecture.md)
- [编译模型设计](docs/development/compilation-design.md)
- [LLVM Intrinsic 参考](docs/llvm_intrinsics.md)
- [llvmlite API 参考](docs/refs/llvmlite_docs/)

## 许可证

MIT
