# LLVM Intrinsic 参考

> 基于 `docs/refs/llvm_ir.md` 中 LLVM 语言参考手册的完整 intrinsic 目录整理。
> 标记了在 CMCF 项目（纯整数 C，`-fno-vectorize`）中可能出现的 intrinsic。

## 目录

- [第一类：一定会出现](#第一类一定会出现)
- [第二类：溢出检测](#第二类溢出检测)
- [第三类：饱和算术](#第三类饱和算术)
- [第四类：浮点相关](#第四类浮点相关)
- [第五类：向量专用](#第五类向量专用)
- [第六类：平台/GC/特殊用途](#第六类平台gc特殊用途)

---

## 第一类：一定会出现

在 C 代码 `-O0`/`-O1` 下可能触发的 intrinsic。优先级从高到低。

### 高优先级

| Intrinsic | 触发条件 | IR 示例 |
|-----------|----------|---------|
| `llvm.smax.*` | `a > b ? a : b` 模式 | `call i32 @llvm.smax.i32(i32 %a, i32 %b)` |
| `llvm.smin.*` | `a < b ? a : b` 模式 | 同上 |
| `llvm.umax.*` | 无符号比较优化 | 同上 |
| `llvm.umin.*` | 无符号比较优化 | 同上 |
| `llvm.memcpy.*` | 结构体拷贝、数组复制 | `call void @llvm.memcpy.p0.p0.i64(ptr %d, ptr %s, i64 %n, i1 false)` |
| `llvm.memmove.*` | 可能重叠的内存复制 | 同上 |
| `llvm.memset.*` | 数组/结构体清零初始化 | `call void @llvm.memset.p0.i64(ptr %d, i8 0, i64 %n, i1 false)` |

### 中优先级

| Intrinsic | 触发条件 |
|-----------|----------|
| `llvm.abs.*` | `abs()` 调用或取绝对值模式 |
| `llvm.scmp.*` | 有符号三路比较 |
| `llvm.ucmp.*` | 无符号三路比较 |

### 低优先级

| Intrinsic | 触发条件 | 处理策略 |
|-----------|----------|---------|
| `llvm.lifetime.start.*` | -O1 变量作用域开始标记 | **忽略**（无运行时语义） |
| `llvm.lifetime.end.*` | -O1 变量作用域结束标记 | **忽略** |
| `llvm.assume` | 编译器推断的断言 | **忽略** |
| `llvm.expect.*` | `__builtin_expect()` | **忽略** |
| `llvm.expect.with.probability` | branch probability | **忽略** |
| `llvm.stackprotector` | `-fstack-protector`（默认不开启） | **忽略** |
| `llvm.stackguard` | `-fstack-protector` | **忽略** |
| `llvm.va_start` | `va_list` / `printf(...)` 可变参数 | 通过 syscall 间接处理 |
| `llvm.va_end` | 同上 | 通过 syscall 间接处理 |
| `llvm.va_copy` | 同上 | 通过 syscall 间接处理 |
| `llvm.trap` | `abort()`, `__builtin_trap()` | 可注册为 syscall |
| `llvm.debugtrap` | 调试陷阱 | **忽略** |
| `llvm.ubsantrap` | UBSan 陷阱 | **忽略** |
| `llvm.objectsize.*` | `__builtin_object_size()` | **忽略** |
| `llvm.donothing` | 编译器占位 | **忽略** |
| `llvm.sideeffect` | 优化屏障 | **忽略** |

---

## 第二类：溢出检测

需 `-ftrapv` 或显式调用 `__builtin_*_overflow()` 才会出现。

| Intrinsic | 说明 |
|-----------|------|
| `llvm.sadd.with.overflow.*` | 有符号加法 + 溢出标志 |
| `llvm.uadd.with.overflow.*` | 无符号加法 + 溢出标志 |
| `llvm.ssub.with.overflow.*` | 有符号减法 + 溢出标志 |
| `llvm.usub.with.overflow.*` | 无符号减法 + 溢出标志 |
| `llvm.smul.with.overflow.*` | 有符号乘法 + 溢出标志 |
| `llvm.umul.with.overflow.*` | 无符号乘法 + 溢出标志 |

---

## 第三类：饱和算术

标准 C 不触发，需嵌入式扩展或显式调用。

| Intrinsic | 说明 |
|-----------|------|
| `llvm.sadd.sat.*` | 有符号饱和加法 |
| `llvm.uadd.sat.*` | 无符号饱和加法 |
| `llvm.ssub.sat.*` | 有符号饱和减法 |
| `llvm.usub.sat.*` | 无符号饱和减法 |
| `llvm.sshl.sat.*` | 有符号饱和左移 |
| `llvm.ushl.sat.*` | 无符号饱和左移 |
| `llvm.smul.fix.*` | 有符号定点乘法 |
| `llvm.umul.fix.*` | 无符号定点乘法 |
| `llvm.smul.fix.sat.*` | 有符号饱和定点乘法 |
| `llvm.umul.fix.sat.*` | 无符号饱和定点乘法 |
| `llvm.sdiv.fix.*` | 有符号定点除法 |
| `llvm.udiv.fix.*` | 无符号定点除法 |
| `llvm.sdiv.fix.sat.*` | 有符号饱和定点除法 |
| `llvm.udiv.fix.sat.*` | 无符号饱和定点除法 |
| `llvm.fptoui.sat.*` | 浮点→无符号整数（饱和） |
| `llvm.fptosi.sat.*` | 浮点→有符号整数（饱和） |

---

## 第四类：浮点相关

纯整数 C 代码**不会出现**。约 40 个 intrinsic：

### 数学函数

`llvm.sqrt.*`, `llvm.powi.*`, `llvm.sin.*`, `llvm.cos.*`, `llvm.tan.*`,
`llvm.asin.*`, `llvm.acos.*`, `llvm.atan.*`, `llvm.atan2.*`,
`llvm.sinh.*`, `llvm.cosh.*`, `llvm.tanh.*`, `llvm.sincos.*`, `llvm.sincospi.*`,
`llvm.modf.*`, `llvm.pow.*`, `llvm.exp.*`, `llvm.exp2.*`, `llvm.exp10.*`,
`llvm.ldexp.*`, `llvm.frexp.*`, `llvm.log.*`, `llvm.log10.*`, `llvm.log2.*`

### 浮点运算

`llvm.fma.*` (fused multiply-add), `llvm.fmuladd.*`, `llvm.fabs.*`,
`llvm.copysign.*`, `llvm.canonicalize.*`

### 浮点比较

`llvm.maxnum.*`, `llvm.minnum.*`, `llvm.maximum.*`, `llvm.minimum.*`,
`llvm.maximumnum.*`, `llvm.minimumnum.*`

### 浮点舍入

`llvm.floor.*`, `llvm.ceil.*`, `llvm.trunc.*`, `llvm.rint.*`, `llvm.nearbyint.*`,
`llvm.round.*`, `llvm.roundeven.*`, `llvm.lround.*`, `llvm.llround.*`,
`llvm.lrint.*`, `llvm.llrint.*`, `llvm.fptrunc.round`

### 浮点分类

`llvm.is.fpclass`

### 浮点转换

`llvm.convert.to.arbitrary.fp`, `llvm.convert.from.arbitrary.fp`

---

## 第五类：向量专用

全部由 `-fno-vectorize -fno-slp-vectorize` 消除。

### 向量 reduce 系列（~25 个）

`llvm.vector.reduce.add.*`, `llvm.vector.reduce.fadd.*`, `llvm.vector.reduce.mul.*`,
`llvm.vector.reduce.fmul.*`, `llvm.vector.reduce.and.*`, `llvm.vector.reduce.or.*`,
`llvm.vector.reduce.xor.*`, `llvm.vector.reduce.smax.*`, `llvm.vector.reduce.smin.*`,
`llvm.vector.reduce.umax.*`, `llvm.vector.reduce.umin.*`, `llvm.vector.reduce.fmax.*`,
`llvm.vector.reduce.fmin.*`, `llvm.vector.reduce.fmaximum.*`, `llvm.vector.reduce.fminimum.*`

### 向量操作系列（~20 个）

`llvm.vector.insert`, `llvm.vector.extract`, `llvm.vector.reverse`,
`llvm.vector.deinterleave2/3/4/5/6/7/8`, `llvm.vector.interleave2/3/4/5/6/7/8`,
`llvm.vector.splice.left`, `llvm.vector.splice.right`, `llvm.stepvector`

### VP (Vector Predicated) 系列（~137 个）

所有 `llvm.vp.*` 变体：`llvm.vp.add.*`, `llvm.vp.sub.*`, `llvm.vp.mul.*`,
`llvm.vp.sdiv.*`, `llvm.vp.udiv.*`, `llvm.vp.srem.*`, `llvm.vp.urem.*`,
`llvm.vp.ashr.*`, `llvm.vp.lshr.*`, `llvm.vp.shl.*`, `llvm.vp.and.*`,
`llvm.vp.or.*`, `llvm.vp.xor.*`, `llvm.vp.abs.*`, `llvm.vp.smax.*`,
`llvm.vp.smin.*`, `llvm.vp.umax.*`, `llvm.vp.umin.*`, `llvm.vp.fadd.*`,
`llvm.vp.fsub.*`, `llvm.vp.fmul.*`, `llvm.vp.fdiv.*`, `llvm.vp.frem.*`,
`llvm.vp.fneg.*`, `llvm.vp.fabs.*`, `llvm.vp.sqrt.*`, `llvm.vp.fma.*`,
`llvm.vp.fmuladd.*`, `llvm.vp.select.*`, `llvm.vp.merge.*`, `llvm.vp.load`,
`llvm.vp.load.ff`, `llvm.vp.store`, `llvm.vp.gather`, `llvm.vp.scatter`,
`llvm.vp.trunc.*`, `llvm.vp.zext.*`, `llvm.vp.sext.*`, `llvm.vp.fptrunc.*`,
`llvm.vp.fpext.*`, `llvm.vp.fptoui.*`, `llvm.vp.fptosi.*`, `llvm.vp.uitofp.*`,
`llvm.vp.sitofp.*`, `llvm.vp.ptrtoint.*`, `llvm.vp.inttoptr.*`,
`llvm.vp.fcmp.*`, `llvm.vp.icmp.*`, `llvm.vp.reduce.*` (18 个),
`llvm.vp.ceil.*`, `llvm.vp.floor.*`, `llvm.vp.rint.*`, `llvm.vp.nearbyint.*`,
`llvm.vp.round.*`, `llvm.vp.roundeven.*`, `llvm.vp.roundtozero.*`,
`llvm.vp.lrint.*`, `llvm.vp.llrint.*`, `llvm.vp.bitreverse.*`,
`llvm.vp.bswap.*`, `llvm.vp.ctpop.*`, `llvm.vp.ctlz.*`, `llvm.vp.cttz.*`,
`llvm.vp.cttz.elts.*`, `llvm.vp.sadd.sat.*`, `llvm.vp.uadd.sat.*`,
`llvm.vp.ssub.sat.*`, `llvm.vp.usub.sat.*`, `llvm.vp.fshl.*`, `llvm.vp.fshr.*`,
`llvm.vp.is.fpclass.*`

### Masked 内存操作系列（8 个）

`llvm.masked.load.*`, `llvm.masked.store.*`, `llvm.masked.gather.*`,
`llvm.masked.scatter.*`, `llvm.masked.expandload.*`, `llvm.masked.compressstore.*`

### 其他向量相关

`llvm.experimental.vp.splice`, `llvm.experimental.vp.reverse`,
`llvm.experimental.vp.strided.load`, `llvm.experimental.vp.strided.store`,
`llvm.experimental.cttz.elts`, `llvm.experimental.get.vector.length`,
`llvm.experimental.vector.histogram.*`, `llvm.experimental.vector.extract.last.active`,
`llvm.experimental.vector.compress.*`, `llvm.experimental.vector.match.*`,
`llvm.matrix.transpose.*`, `llvm.matrix.multiply.*`,
`llvm.matrix.column.major.load.*`, `llvm.matrix.column.major.store.*`,
`llvm.get.active.lane.mask.*`, `llvm.vscale`

---

## 第六类：平台/GC/特殊用途

标准 C 代码**不会触发**。

### 垃圾回收 (GC)

`llvm.gcroot`, `llvm.gcread`, `llvm.gcwrite`,
`llvm.experimental.gc.statepoint`, `llvm.experimental.gc.result`,
`llvm.experimental.gc.relocate`, `llvm.experimental.gc.get.pointer.base`,
`llvm.experimental.gc.get.pointer.offset`

### 栈/帧操作

`llvm.returnaddress`, `llvm.addressofreturnaddress`, `llvm.sponentry`,
`llvm.stackaddress`, `llvm.frameaddress`, `llvm.stacksave`, `llvm.stackrestore`,
`llvm.localescape`, `llvm.localrecover`

### 寄存器操作

`llvm.read_register`, `llvm.read_volatile_register`, `llvm.write_register`

### Objective-C 系列（17 个）

`llvm.objc.autorelease`, `llvm.objc.autoreleasePoolPop`, `llvm.objc.autoreleasePoolPush`,
`llvm.objc.autoreleaseReturnValue`, `llvm.objc.copyWeak`, `llvm.objc.destroyWeak`,
`llvm.objc.initWeak`, `llvm.objc.loadWeak`, `llvm.objc.loadWeakRetained`,
`llvm.objc.moveWeak`, `llvm.objc.release`, `llvm.objc.retain`,
`llvm.objc.retainAutorelease`, `llvm.objc.retainAutoreleaseReturnValue`,
`llvm.objc.retainAutoreleasedReturnValue`, `llvm.objc.retainBlock`,
`llvm.objc.storeStrong`, `llvm.objc.storeWeak`

### Windows SEH 异常处理（4 个）

`llvm.seh.try.begin`, `llvm.seh.try.end`, `llvm.seh.scope.begin`, `llvm.seh.scope.end`

### 指针认证 (ARM PAC)

`llvm.ptrauth.sign`, `llvm.ptrauth.auth`, `llvm.ptrauth.blend`

### CFI 类型检查

`llvm.type.test`, `llvm.type.checked.load`, `llvm.type.checked.load.relative`

### 性能分析

`llvm.instrprof.increment`, `llvm.instrprof.increment.step`, `llvm.instrprof.callsite`,
`llvm.instrprof.timestamp`, `llvm.instrprof.cover`, `llvm.instrprof.value.profile`,
`llvm.instrprof.mcdc.parameters`, `llvm.instrprof.mcdc.tvbitmap.update`

### Pre-allocated call

`llvm.call.preallocated.setup`, `llvm.call.preallocated.arg`, `llvm.call.preallocated.teardown`

### 其他专有 intrinsic

`llvm.swift.async.context.addr`, `llvm.thread.pointer`,
`llvm.threadlocal.address`, `llvm.structured.gep`, `llvm.get.dynamic.area.offset`,
`llvm.prefetch`, `llvm.pcmarker`, `llvm.readcyclecounter`, `llvm.readsteadycounter`,
`llvm.clear_cache`, `llvm.init.trampoline`, `llvm.adjust.trampoline`,
`llvm.invariant.start`, `llvm.invariant.end`, `llvm.launder.invariant.group`,
`llvm.strip.invariant.group`, `llvm.var.annotation`, `llvm.ptr.annotation.*`,
`llvm.annotation.*`, `llvm.codeview.annotation`, `llvm.ssa.copy`,
`llvm.arithmetic.fence`, `llvm.load.relative`, `llvm.is.constant.*`,
`llvm.ptrmask`, `llvm.fake.use`, `llvm.reloc.none`,
`llvm.experimental.deoptimize`, `llvm.experimental.guard`,
`llvm.experimental.widenable.condition`, `llvm.allow.ubsan.check`,
`llvm.allow.runtime.check`, `llvm.cond.loop`, `llvm.looptrap`,
`llvm.get.rounding`, `llvm.set.rounding`, `llvm.get.fpenv`, `llvm.set.fpenv`,
`llvm.reset.fpenv`, `llvm.get.fpmode`, `llvm.set.fpmode`, `llvm.reset.fpmode`

### 约束浮点系列（~40 个，`-ffp-model=strict` 触发）

全部 `llvm.experimental.constrained.*`：`fadd`, `fsub`, `fmul`, `fdiv`, `frem`,
`fma`, `fptoui`, `fptosi`, `uitofp`, `sitofp`, `fptrunc`, `fpext`, `fcmp`, `fcmps`,
`fmuladd`, `sqrt`, `pow`, `powi`, `ldexp`, `sin`, `cos`, `tan`, `asin`, `acos`,
`atan`, `atan2`, `sinh`, `cosh`, `tanh`, `exp`, `exp2`, `log`, `log10`, `log2`,
`rint`, `lrint`, `llrint`, `nearbyint`, `maxnum`, `minnum`, `maximum`, `minimum`,
`ceil`, `floor`, `round`, `roundeven`, `lround`, `llround`, `trunc`

### 调试信息（`-g` 标志触发）

`llvm.dbg.value`, `llvm.dbg.declare`, `llvm.dbg.addr`, `llvm.dbg.label`,
`llvm.dbg.assign` — 均通过 metadata 参数调用，非普通函数调用。**完全忽略**。

### 循环元数据（非函数调用）

`llvm.loop.*` 系列是元数据附加，不是 `call @llvm.*` 指令。**完全忽略**。

### 内存原子操作

`llvm.memcpy.element.unordered.atomic`, `llvm.memmove.element.unordered.atomic`,
`llvm.memset.element.unordered.atomic`

### DebugInfo 保留 intrinsic

`llvm.preserve.array.access.index`, `llvm.preserve.union.access.index`,
`llvm.preserve.struct.access.index`, `llvm.protected.field.ptr`,
`llvm.experimental.noalias.scope.decl`

---

## 总结

LLVM 语言参考手册中记录的全部 `llvm.*` intrinsic 约 **450+ 个**。
对于 CMCF 项目的纯整数 C 代码（`-O0`/`-O1`，`-fno-vectorize`）：

| 类别 | 数量 | 处理 |
|------|------|------|
| 需要关注 | ~10 个 | smax/min/umax/min/abs/memcpy/memmove/memset |
| 直接忽略 | ~440+ 个 | 浮点/向量/平台/GC/调试 |
