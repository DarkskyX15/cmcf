# 5. Handler 体系与 WalkContext

> 来源: `docs/development/redesign.md` §6, §9
> 代码: `cmcf/core/handler.py`, `cmcf/core/context.py`

---

## Handler 体系

### 设计原则

- Handler 使用**类**，含 `preflight` + `handle` 双入口方法
- 统一装饰器 `@register`，通过 `node` 参数区分四种 handler 类型
- 状态通过 `WalkContext` 传递

### Handler 基类

```python
class Handler:
    id: ClassVar[str]

    def preflight(self, ctx: WalkContext) -> None:
        """编译前执行一次（反向），向 ctx.flags 添加语义标签。"""

    def handle(self, node, ctx: WalkContext) -> None:
        """遍历时正向执行。function handler 自行检查 node.annotations。"""
```

### 注册 API

```python
from cmcf.core.handler import register, Handler, Phase

@register(node="module", id="pack_meta", phase=Phase.AFTER)
class PackMetaHandler(Handler): ...

@register(node="function", on="enter", id="load_entry", phase=Phase.CORE)
class LoadEntryHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations and "cmcf:entry:load" in node.annotations: ...

@register(node="block", on="enter", id="block_enter", phase=Phase.MAIN)
class BlockEnterHandler(Handler): ...

@register(node="instruction", on=["add", "sub", "mul"], id="arith",
          phase=Phase.MAIN, before=["icmp_comparison"])
class ArithHandler(Handler): ...
```

### 注册参数规范

| 参数 | `"module"` | `"function"` | `"block"` | `"instruction"` |
|------|:--:|:--:|:--:|:--:|
| `id` | ✓ | ✓ | ✓ | ✓ |
| `on` | ✗ | `"enter"` / `"exit"` / `["enter","exit"]` | `"enter"` / `"exit"` / `["enter","exit"]` | `"add"` / `["add","sub"]` / `"*"` |
| `phase` | ✓ | ✓ | ✓ | ✓ |
| `before` | ✓ | ✓ | ✓ | ✓ |
| `after` | ✓ | ✓ | ✓ | ✓ |

### 函数注解自检

Function handler 在 `handle()` 内自行检查 `node.annotations`（`frozenset[str] | None`）决定是否处理。

```python
# 仅处理 load 入口函数
class LoadEntryHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations and "cmcf:entry:load" in node.annotations: ...

# 仅处理无注解函数（兜底）
class DefaultEnterHandler(Handler):
    def handle(self, node, ctx):
        if node.annotations is None: ...
```

注解由 `IRConverter` 从 `@llvm.global.annotations` 解析。

### Flags 模型

采用冒号分段式标签（如 `"i32_core:scoreboard"`），降低 handler 间耦合。

```
┌─ 编译前（一次性）─────────────────────────────────────┐
│ HandlerCollection.sort()                               │
│ HandlerCollection.preflight(ctx)                       │
│   反向 (AFTER → CORE) 执行所有 handler 的 preflight()  │
│   → 填充 ctx.flags = {"i32_core:scoreboard", ...}      │
└───────────────────────────────────────────────────────┘

┌─ 遍历时（每个结点）───────────────────────────────────┐
│ HandlerCollection.execute(node, ctx)                   │
│   正向 (CORE → AFTER) 执行 handler.handle()            │
│   各 handler 自行检查 ctx.flags 决定是否产出           │
└───────────────────────────────────────────────────────┘
```

### HandlerCollection

```python
class HandlerCollection:
    _sorted: list[Handler]

    def register(self, handler, phase, before, after): ...
    def sort(self, fingerprint, pass_path): ...
    def preflight(self, ctx): ...
    def execute(self, node, ctx): ...
```

### 排序策略

两级排序：
1. 按 phase 分组：CORE (0) < BEFORE (1) < MAIN (2) < AFTER (3)
2. 同 phase 内拓扑排序：`before`/`after` 声明构建有向图

- 循环依赖 → 报 error（不静默）
- 引用了不存在的 handler id → 报 error
- 未声明 before/after → 按注册顺序

### pass.json 缓存

```
pass.json 不存在 → 排序 → 写入
pass.json 存在   → 直接读取

fingerprint = hash(已安装模块列表)
fingerprint ≠ pass.json 中的值 → 重新排序
```

### 注册表结构

```
_registry: dict[str, HandlerCollection]
  "module"              → [PackMetaHandler]
  "function.enter"      → [LoadEntryHandler, DefaultEnterHandler]
  "function.exit"       → [DefaultExitHandler]
  "block.enter"         → [BlockEnterHandler]
  "block.exit"          → [BlockExitHandler]
  "instruction.add"     → [ArithHandler]
  "instruction.sub"     → [ArithHandler]
  "instruction.*"       → [EchoHandler]     # 通配符
  ...
```

### 遍历与分发

```
IRModule
  │ _registry["module"].execute(node=module, ctx)
  └→ for func in module.functions:
       │ ctx.trace.annotations = func.annotations
       │ _registry["function.enter"].execute(node=func, ctx)
       └→ for block in func.blocks:
            │ _registry["block.enter"].execute(node=block, ctx)
            └→ for inst in block.instructions:
                 │ key = f"instruction.{inst.opcode}"
                 │ if key in reg: reg[key].execute(...)
                 │ elif "instruction.*" in reg: reg["instruction.*"].execute(...)
            │ _registry["block.exit"].execute(node=block, ctx)
       │ _registry["function.exit"].execute(node=func, ctx)
```

### 动态加载

```python
def _load_handlers(proj_dir: Path) -> None:
    handler_dir = proj_dir / ".cmcf" / "handler"
    sys.path.insert(0, str(handler_dir))
    for module_dir in sorted(handler_dir.iterdir()):
        if module_dir.is_dir():
            importlib.import_module(module_dir.name)
```

每个 handler 模块必须是标准 Python 包，包含 `__init__.py`。

---

## WalkContext

```python
@dataclass
class WalkContext:
    # 配置
    namespace: str
    project_id: str
    target_format: tuple[int, int]
    compile_mode: str

    # I/O
    writer: FileWriter
    header_exporter: HeaderExporter

    # 位置跟踪
    trace: Trace

    # 命名
    namer: NameProvider

    # 查找表
    registries: Registries

    # 作用域临时存储
    module_ctx: NodeContext
    func_ctx: NodeContext
    block_ctx: NodeContext

    # Handler 通信
    flags: set[str]
```

### FileWriter

多文件输出，支持栈式切换：

```python
class FileWriter:
    def open(self, rel_path: str): ...     # 切换文件
    def emit(self, line: str) -> None: ... # 写一行
    def close(self) -> None: ...           # 保存当前文件
    def push(self, rel_path: str) -> None: # 压栈切换
    def pop(self) -> None: ...             # 恢复上一个文件
    def write_all(self) -> None: ...       # 写入磁盘
```

### Trace

```python
@dataclass
class Trace:
    module: IRModule | None = None
    function: IRFunction | None = None
    block: IRBlock | None = None
    instruction: IRInstruction | None = None
    annotations: frozenset[str] | None = None
    module_name: str = ""
    func_name: str = ""
    block_label: str = ""
```

### NameProvider

```python
class NameProvider:
    def func_file(self, module, func) -> str: ...
    def exported_file(self, module, func) -> str: ...
    def block_file(self, module, func, block_label) -> str: ...
    def internal_dir(self) -> str: ...
    def load_dir(self) -> str: ...
    def tick_dir(self) -> str: ...
    def scoreboard_obj(self, var_name) -> str: ...
    def scoreboard_player(self, reg_name) -> str: ...
    def function_ref(self, module, path) -> str: ...
```

### NodeContext

键值对临时存储，进入新作用域时清空。`set`/`get` 自动按 `{module}:{name}` 拼接 key：

```python
class NodeContext:
    def set(self, name, value, module=None): ...
    def get(self, name, default=None, module=None): ...
    def clear(self): ...
```

### Registries

```python
@dataclass
class Registries:
    syscall: SysCallRegistry
    # 未来扩展: variable_mapping, function_table, annotation_index
```

---

## 已确认 ✓

- Handler 使用类，含 `preflight` + `handle` 双方法
- Flags 模型：反向 preflight（编译前一次） → 正向 handle（遍历时）
- Phase 四阶段：CORE/BEFORE/MAIN/AFTER（默认 MAIN）
- before/after 同级拓扑排序（循环依赖/无效引用报 error）
- `HandlerCollection.execute()` 无中央筛选逻辑
- `Handler.filter_tags` 已移除
- pass.json 缓存排序，fingerprint 仅基于模块列表 hash
- `.cmcf/handler/` 加入 `sys.path`，`importlib.import_module("<name>")`
- `FileWriter` 栈接口（`push`/`pop`）
- `Trace.annotations: frozenset[str] | None`
- `NodeContext.set/get(name, module=None)` 自动拼接 key
