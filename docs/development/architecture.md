# MCMF 架构设计

## 编译流水线

```
C 源代码 → (clang -x c) → LLVM IR → (mcmf) → mcfunction 数据包
```

- **前端**: ClangInterface 封装 clang 调用，输出 LLVM IR 文本
- **后端**: IRConverter + IRWalker + Handler 系统，解析 IR 并生成数据包

## 模块架构

```
mcmf/
├── config.py                  CompileConfig: 编译配置
├── __main__.py                CLI 入口，组装管线
│
├── core/                      核心层 (无 Minecraft 语义)
│   ├── clang.py               ClangInterface: C 源码→IR 文本
│   ├── ir_converter.py        IRConverter: llvmlite→结构化 IR
│   ├── ir_values.py           IROperand 子类 (5 种)
│   ├── ir_instructions.py     IRInstruction/Block/Function/Module
│   └── ir_visitor.py          IRWalker + WalkReport + InstructionRouter
│
└── mc/                        Minecraft 语义层
    ├── handlers/              指令处理器 (按 opcode 路由)
    │   ├── __init__.py         @register_handler + build_router
    │   ├── base.py             InstructionHandler ABC
    │   ├── memory.py           alloca, load, store, getelementptr
    │   ├── arithmetic.py       add, sub, mul, sdiv/udiv, srem/urem, 位运算
    │   ├── comparison.py       icmp
    │   ├── control_flow.py     br, ret
    │   ├── call.py             call (用户函数/syscall 分类)
    │   └── aggregate.py        phi, select
    └── syscalls/              系统调用框架
        ├── __init__.py         SysCallRegistry + @register_syscall
        └── base.py             SysCallHandler ABC
```

## 编译管线

```
main()
  ├── CompileConfig(source=path)
  ├── ClangInterface(config).compile_to_ir() -> IR text
  ├── IRWalker(ir_text)
  │   ├── llvm.parse_assembly(ir_text)    # llvmlite 解析
  │   ├── IRConverter.convert(llvm_mod)   # → IRModule
  │   └── for func in module.functions:
  │       └── for block in func.blocks:
  │           └── router.handle(inst, ctx)    # 分发到 Handler
  └── 输出 WalkReport (统计 + 诊断)
```

## IR 模型设计

转换层 (IRConverter) 将 llvmlite 的 ValueRef 包装为纯 Python dataclass，
使 Handler 完全不依赖 llvmlite。

### 操作数类型

| IROperand 子类 | 字段 | LLVM IR 对应 |
|----------------|------|-------------|
| IRConst | value, kind | 常量: i32 5, null, undef |
| IRRegister | name | 寄存器: %x, %0, %result |
| IRFunctionRef | name | 函数引用: @printf, @main |
| IRGlobalRef | name | 全局变量: @.str |
| IRBlockRef | name | 基本块标签: entry, 5 |

### 指令结构

```python
IRInstruction(
    opcode="icmp",
    result="8",
    operands=(IRRegister(name="6"), IRRegister(name="7")),
    predicate="sgt",          # icmp/fcmp 谓词 (转换层解析)
    flags=("nsw",),           # nsw/nuw/inbounds 等标志
)
```

## Handler 系统

### 注册机制

```python
from mcmf.mc.handlers import register_handler, InstructionHandler

@register_handler("icmp")
class ComparisonHandler(InstructionHandler):
    def handle(self, inst: IRInstruction, ctx: WalkContext) -> None:
        # 使用 inst.predicate 获取 "sgt" / "eq" 等
        ...
```

### 扩展

用户只需 `import my_module` 触发 `@register_handler` 装饰器执行，
然后 `build_router(report)` 自动发现所有 Handler。

## WalkReport

遍历结束后产出的结构化诊断：

```
=== Walk Report ===
Source:              example/max.cpp
Functions defined:   2 (max, main)
Functions declared:  1 (printf)
Syscalls detected:   1 (printf)
Instruction counts:
  alloca               5
  br                   3
  call                 1
  icmp                 1
  load                 6
  ret                  2
  store                6
Errors:              0
=== Done ===
```
