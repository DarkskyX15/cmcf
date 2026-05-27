# MCMF 文档

## 项目简介

MCMF (C to Minecraft Function Compiler) 是一个将 C 编译为 Minecraft mcfunction 数据包的编译器。

**编译流水线**: `C 源代码 → (clang) → LLVM IR → (mcmf) → mcfunction 数据包`

## 文档目录

### 核心文档
- [架构设计](development/architecture.md) - MCMF 架构设计
- [LLVM Intrinsic 参考](llvm_intrinsics.md) - 完整 `llvm.*` intrinsic 分类与处理策略

### 参考文档
- [llvmlite Binding 层文档](refs/llvmlite_docs/) - llvmlite 完整 API 参考
- [LLVM IR 参考](refs/llvm_ir.md) - LLVM IR 语法与指令参考

## 快速开始

```bash
# 分析一个 C 文件
python -m mcmf example/add.cpp -v
```
