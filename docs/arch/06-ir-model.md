# 6. IR 数据模型与转换

> 来源: `docs/development/redesign.md` §7 部分
> 代码: `cmcf/core/ir_instructions.py`, `cmcf/core/ir_values.py`, `cmcf/core/ir_converter.py`

---

## 树结点

```
IRModule                     # 根
├── IRGlobal                 # 全局变量/常量
└── IRFunction               # 函数
    ├── IRParameter          # 参数
    └── IRBlock              # 基本块
        └── IRInstruction     # 指令
            ├── opcode        # str: "add", "br", "icmp"...
            ├── result        # str | None
            ├── predicate     # str | None (icmp/fcmp)
            ├── flags         # tuple[str]: ("nsw", "nuw", "inbounds")
            └── operands      # tuple[IROperand]
```

## 数据结构定义

```python
# cmcf/core/ir_instructions.py

@dataclass(frozen=True)
class IRInstruction:
    opcode: str
    result: str | None
    operands: tuple[IROperand, ...]
    predicate: str | None = None
    flags: tuple[str, ...] = ()

@dataclass(frozen=True)
class IRParameter:
    name: str
    index: int
    param_type: str = ""                  # "i32", "ptr", "float"

@dataclass(frozen=True)
class IRBlock:
    label: str
    instructions: tuple[IRInstruction, ...]

@dataclass(frozen=True)
class IRFunction:
    name: str
    params: tuple[IRParameter, ...]
    blocks: tuple[IRBlock, ...]
    is_declaration: bool
    return_type: str | None = None        # "i32" / "void" / None
    annotations: frozenset[str] | None = None

@dataclass(frozen=True)
class IRGlobal:
    name: str                             # "@.str", "@counter"
    global_type: str                      # "constant [13 x i8]", "i32"
    initializer: IROperand | None = None  # IRConst or None
    is_constant: bool = False
    linkage: str = ""

@dataclass(frozen=True)
class IRModule:
    source_file: str
    functions: tuple[IRFunction, ...]
    globals: tuple[IRGlobal, ...] = ()
```

## 操作数类型

```python
# cmcf/core/ir_values.py

class IROperand(ABC): ...

class IRConst(IROperand):
    value: int | float | str | None
    kind: Literal["int", "float", "string", "null", "undef", "zeroinit"]

class IRRegister(IROperand):
    name: str

class IRFunctionRef(IROperand):
    name: str

class IRGlobalRef(IROperand):
    name: str

class IRBlockRef(IROperand):
    name: str
```

| IROperand 子类 | 字段 | LLVM IR 对应 |
|----------------|------|-------------|
| `IRConst` | value, kind | 常量: `i32 5`, `null`, `undef` |
| `IRRegister` | name | 寄存器: `%x`, `%result` |
| `IRFunctionRef` | name | 函数引用: `@printf` |
| `IRGlobalRef` | name | 全局变量: `@.str` |
| `IRBlockRef` | name | 基本块标签: `%entry` |

## IRConverter

`IRConverter` 将 llvmlite 的 `ModuleRef` 转换为结构化 IR，核心方法：

| 方法 | 职责 |
|------|------|
| `convert(module)` | 入口：遍历 functions + globals + 解析 annotations |
| `_convert_function(func)` | 提取参数、基本块、返回类型 |
| `_convert_instruction(inst)` | 提取 opcode、result、operands、predicate、flags |
| `_convert_operand(op)` | 按 value_kind 分派：const/register/function/global/block |
| `_convert_global(g)` | 提取 IRGlobal 的类型和初始值 |
| `_parse_annotations(module)` | 解析 `@llvm.global.annotations` → `{func_name → frozenset[str]}` |
| `_extract_predicate(inst)` | 从 `str(inst)` 解析 icmp/fcmp 谓词 |
| `_extract_flags(inst)` | 解析 nsw/nuw/inbounds 等标志 |
| `_extract_param_type(arg)` | 从 `str(arg)` 提取参数类型 |
| `_extract_return_type(func)` | 从 `str(func)` 提取返回类型 |

关键处理：
- **opaque pointer**: 通过 `value_kind` + `str()` 解析区分 operand 类型
- **annotations**: `@llvm.global.annotations` 是 appending global，llvm-link 合并后保留完整映射
- **`-fno-discard-value-names`**: 保留 SSA 寄存器名

### 自定义注解支持

用户通过 `__attribute__((annotate))` 标注函数：

```c
__attribute__((annotate("cmcf:entry:export"))) int get_score(int id);
```

`IRConverter._parse_annotations()` 提取注解字符串 → `IRFunction.annotations: frozenset[str] | None`

---


## 已确认 ✓

- IR 模型完全独立于 llvmlite（pure Python dataclasses）
- `IRParameter.param_type` + `IRFunction.return_type` + `annotations` 新字段
- `IRGlobal` 支持全局变量和常量
- `annotations` 类型 `frozenset[str] | None`
- opaque pointer 下通过 `value_kind` 区分 operand
- `-fno-discard-value-names` 保留变量名
