# 4. Syscall 机制

> 来源: `docs/development/redesign.md` §4
> 代码: `cmcf/core/syscall_registry.py`

---

## 全局唯一注册

- syscall 签名在项目级全局唯一（类似 C 的全局函数名）
- `cmcf install` 时检测：若新模块的 syscall 与已安装模块冲突 → 报错中止
- **不需要** `module.json` 声明 `conflicts` 字段 — 同名即冲突

## 注册与映射

Syscall 在 `module.json` 中声明签名与文件的映射：

```jsonc
"syscalls": {
    "printf": "print.mcfunction",
    "malloc": "alloc.mcfunction"
}
```

- `printf` → `function/print.mcfunction`
- `malloc` → `function/alloc.mcfunction`

C 代码中的 `printf()` 调用与文件 `print.mcfunction` 解耦。

## SysCallRegistry

`modules.json` 中的 `syscalls` 存储**完整映射**（名称→文件路径），`mcc build` 时从中构建 `SysCallRegistry` 并挂到 `WalkContext`。

```jsonc
// .cmcf/modules.json — syscalls 以 dict 存储
"i32_core": {
    "syscalls": {
        "printf": "print.mcfunction",
        "malloc": "alloc.mcfunction",
        "putchar": "io/putchar.mcfunction"
    }
}
```

```python
@dataclass
class SysCallEntry:
    module: str       # "i32_core"
    file: str         # "print.mcfunction"
    stem: str         # "print" (不含 .mcfunction)

class SysCallRegistry:
    _entries: dict[str, SysCallEntry] = {}

    def lookup(self, name: str) -> SysCallEntry | None:
        return self._entries.get(name)

    @classmethod
    def from_installed_manifest(cls, manifest: InstalledManifest) -> SysCallRegistry:
        """mcc build 时调用，从 modules.json 构建全量注册表。"""
```

## Handler 中使用

```python
syscall = ctx.registries.syscall.lookup(callee_name)
if syscall:
    ctx.writer.emit(f"function {ctx.namespace}:{syscall.module}/{syscall.stem}")
else:
    ctx.writer.emit(f"function {ctx.namespace}:{ctx.project_id}/_internal/{callee_name}")
```

## 数据流

```
C: printf("hello")
  → IR: call @printf
    → ctx.registries.syscall.lookup("printf")
      → SysCallEntry(module="i32_core", file="print.mcfunction", stem="print")
        → 生成: function cmcf:i32_core/print
```

---

## 已确认 ✓

- 全局唯一，install 时冲突检测
- module.json 注册 syscall 签名→文件映射
- modules.json 以 dict 存储完整映射（方案 C）
- SysCallRegistry 独立类，从 installed manifest 构建
