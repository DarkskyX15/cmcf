# CMCF 文档

## 项目简介

CMCF (C to Minecraft Function Compiler) 是一个将 C 编译为 Minecraft mcfunction 数据包的编译器框架。

**编译流水线**: `C 源代码 → (clang) → LLVM IR → (mcc) → mcfunction 数据包`

**工具链**:
- `cmcf` — 项目脚手架与模块包管理器
- `mcc` — 编译器前端 (IR 解析、Handler 调度、代码生成)

## 文档目录

### 核心文档
- [架构设计](development/architecture.md) — CMCF 架构总览
- [LLVM Intrinsic 参考](llvm_intrinsics.md) — 完整 `llvm.*` intrinsic 分类与处理策略

### 参考文档
- [LLVM IR 参考](refs/llvm_ir.md) — LLVM IR 语法与指令参考

## 快速开始

```bash
# 初始化项目
cmcf init my_project
cd my_project

# 安装模块
cmcf install echo_test

# 构建
cmcf build
```
