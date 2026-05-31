# 7. 编译器前端与树遍历

> 来源: `docs/development/redesign.md` §1 部分
> 代码: `cmcf/core/clang.py`, `cmcf/core/linker.py`, `cmcf/core/ir_walker.py`

---

## ClangInterface

C 源码 → LLVM bitcode (.bc)

```python
class ClangInterface:
    def __init__(self, clang_path: str, opt_level: int = 1,
                 include_paths: tuple[Path, ...] = (),
                 defines: tuple[str, ...] = ()): ...

    def compile_to_bc(self, source: Path, output: Path) -> None: ...
```

实际调用的 clang 命令：

```bash
clang -x c -O{0,1} -fno-vectorize -fno-slp-vectorize \
      -fno-discard-value-names \
      -c -emit-llvm -I <paths> -D <defines> \
      -o output.bc source.c
```

关键标志：
- `-fno-vectorize -fno-slp-vectorize` — 禁用向量化（避免生成 MC 不支持的指令）
- `-fno-discard-value-names` — 保留 SSA 变量名
- `-c -emit-llvm` — 输出 bitcode 而非目标文件

---

## LinkerInterface

多个 .bc 文件 → 合并 bitcode

```python
class LinkerInterface:
    def __init__(self, llvm_link_path: str = "llvm-link"): ...

    def link(self, inputs: list[Path], output: Path) -> None: ...
```

实际调用：

```bash
llvm-link a.bc b.bc -o combined.bc
```

---

## TreeWalker

遍历结构化 IR，分发到 Handler。

```python
class TreeWalker:
    def walk(self, bc_path: Path | bytes, ctx: WalkContext) -> None:
        llvm_mod = self._parse(bc_path)
        llvm_mod.verify()
        module = IRConverter.convert(llvm_mod)

        ctx.trace.module = module

        # module-level
        reg["module"].execute(node=module, ctx=ctx)

        for func in module.functions:
            if func.is_declaration: continue

            ctx.trace.function = func
            ctx.trace.annotations = func.annotations
            ctx.func_ctx.clear()

            # function enter
            reg["function.enter"].execute(node=func, ctx=ctx)

            for block in func.blocks:
                ctx.trace.block = block
                ctx.block_ctx.clear()

                # block enter
                reg["block.enter"].execute(node=block, ctx=ctx)

                for inst in block.instructions:
                    ctx.trace.instruction = inst

                    # instruction — opcode 精确匹配或 "*" 通配
                    key = f"instruction.{inst.opcode}"
                    if key in reg:
                        reg[key].execute(node=inst, ctx=ctx)
                    elif "instruction.*" in reg:
                        reg["instruction.*"].execute(node=inst, ctx=ctx)

                # block exit
                reg["block.exit"].execute(node=block, ctx=ctx)

            # function exit
            reg["function.exit"].execute(node=func, ctx=ctx)

        ctx.writer.write_all()

    @staticmethod
    def _parse(source: bytes | Path) -> llvm.ModuleRef:
        """解析 bitcode → llvmlite ModuleRef"""
```

### `mcc build` 完整构建流程

```python
def _cmd_build(args):
    # 1. 加载项目配置
    config = _load_project_config(args)

    # 2. 动态加载 handler（importlib 发现 .cmcf/handler/）
    _load_handlers(proj_dir, config)

    # 3. 对所有 HandlerCollection 排序（pass.json 缓存）
    reg = get_registry()
    fingerprint = compute_fingerprint(modules_path)
    for key, col in reg.items():
        col._ensure_key(key)
        col.sort(fingerprint, pass_path)

    # 4. 构建 WalkContext
    ctx = WalkContext.from_config(config, output_dir)

    # 5. 加载 syscall registry
    ctx.registries.syscall = SysCallRegistry.from_installed_manifest(installed)

    # 6. preflight — 所有 handler 反向执行
    for col in reg.values():
        col.preflight(ctx)

    # 7. walk — 正向遍历 IR 树
    walker = TreeWalker()
    walker.walk(bc, ctx)
```

### `cmcf build` 调用链

```python
def _cmd_build(args):
    # 1. 编译 src/*.c → .bc
    # 2. 编译 include/**/*.c → .bc
    # 3. llvm-link → combined.bc
    # 4. subprocess 调用 mcc build
    mcc_cmd = [sys.executable, "-m", "cmcf.cli.mcc", "build",
               str(combined), "--project", str(proj_dir)]
    sp.run(mcc_cmd, check=True, env=env)
```

---

## 已确认 ✓

- `ClangInterface` 仅支持 bitcode 路径（`compile_to_bc`）
- `LinkerInterface` 封装 `llvm-link`
- `TreeWalker` 遍历 Module→Function→Block→Instruction 四层
- `instruction.*` 通配符捕获所有未精确匹配的 opcode
- `mcc build` 子进程继承 PYTHONPATH
- 构建流程：load handlers → sort → preflight → walk → write
