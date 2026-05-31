# CMCF - C to Minecraft Function Compiler

CMCF 是一个将 C 语言编译为 Minecraft 数据包 (mcfunction) 的编译器，利用 LLVM IR 作为中间表示层。CMCF 框架本身不含 Minecraft 逻辑，所有功能由模块提供。

## 工具

| 工具 | 职责 |
|------|------|
| `cmcf` | 项目管理器：脚手架、模块仓库、项目安装/移除、构建触发 |
| `mcc` | 编译器：clang/llvm-link 封装、IR 解析、datapack 生成 |

## 流水线

```
C 源代码 ──[clang]──▶ .bc 文件 ──[llvm-link]──▶ combined.bc ──[mcc build]──▶ datapack/
```

## 前置要求

- Python 3.8+
- [Clang](https://llvm.org/) (C → LLVM IR)
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
# 初始化项目
python -m cmcf.cli.cmcf init my_project

# 进入项目
cd my_project

# 安装模块
python -m cmcf.cli.cmcf install echo_test

# 构建
python -m cmcf.cli.cmcf build

# output/ 目录下即为数据包

# 直接使用 mcc
python -m cmcf.cli.mcc compile input.c -o out.bc
python -m cmcf.cli.mcc link a.bc b.bc -o combined.bc
python -m cmcf.cli.mcc build combined.bc --project .

# 管理本地仓库
python -m cmcf.cli.cmcf repo install /path/to/module
python -m cmcf.cli.cmcf repo list
python -m cmcf.cli.cmcf repo remove module_name
```

## 项目结构

```
CMCF/
├── cmcf/
│   ├── cli/                 # CLI 入口
│   │   ├── cmcf.py          # 脚手架 + 包管理 + 构建
│   │   └── mcc.py           # 编译器 (clang/llvm-link + IR walk)
│   ├── core/                # 框架引擎
│   │   ├── models.py        # JSON 清单 TypedDict
│   │   ├── config.py        # 编译配置
│   │   ├── clang.py         # Clang 接口
│   │   ├── linker.py        # llvm-link 接口
│   │   ├── ir_converter.py  # llvmlite → 结构化 IR
│   │   ├── ir_instructions.py  # IR 结点类型
│   │   ├── ir_values.py     # IROperand 子类
│   │   ├── ir_walker.py     # IR 树遍历器
│   │   ├── handler.py       # Handler 系统
│   │   ├── context.py       # WalkContext
│   │   ├── header_exporter.py  # C Header 导出
│   │   └── syscall_registry.py  # Syscall 注册表
│   ├── libs/                # 内置模块仓库 (只读)
│   │   └── echo_test/       # 测试模块
│   └── site_libs/           # 三方模块仓库
├── example/                 # 测试示例
├── docs/                    # 文档
└── pyproject.toml
```

## 设计文档

- [重构设计文档](docs/development/redesign.md) — 架构设计、模块系统、Handler 体系、包管理器等完整设计
- [架构设计](docs/development/architecture.md)
- [编译模型设计](docs/development/compilation-design.md)
- [LLVM Intrinsic 参考](docs/llvm_intrinsics.md)

## 许可证

MIT
