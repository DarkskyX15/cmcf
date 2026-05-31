# CMCF 实现待办清单

> 从设计文档 `docs/development/redesign.md` 和 Phase 1 实现中提取的未完成项。
> 更新日期: 2026-05-31

---

## 🔴 核心功能缺失

### 1. `path_vars` 默认全集验证

- **来源**: Section 8, 讨论中
- **状态**: 已定义初版默认值，需对照 Minecraft pack_format 各版本官方路径核实
- **文件**: `cmcf/core/config.py` — `DEFAULT_PATH_VARS`
- **当前值**:
  ```python
  DEFAULT_PATH_VARS = {
      "function": "function", "tags": "tags/function",
      "advancement": "advancement", "loot_table": "loot_table",
      "predicate": "predicate", "item_modifier": "item_modifier",
      "recipe": "recipe", "structure": "structure",
      "dimension": "dimension", "dimension_type": "dimension_type",
      "damage_type": "damage_type", "enchantment": "enchantment",
  }
  ```
- **待做**: 查阅 https://minecraft.wiki/w/Data_pack 确认 pack_format 4-88 间的目录名变化，补全所有注册表路径

### 2. module 模式自动生成 `module.json`

- **来源**: 待讨论列表
- **状态**: 路径公式已设计（`{dist}/module/{id}-{version}-{meta_hash}/module.json`），生成逻辑未实现
- **需定义**:
  - 从 `cmcf.json` 的哪些字段提取 `name`/`version`/`pack_format`
  - 如何统计标注了 `CMCF_ENTRY_EXPORT` 的函数→生成 `syscalls` 列表
  - `MetaDict` 如何序列化（直接从 `cmcf.json.meta` 复制？）
  - module.json 的 `dependencies` 是否从 `modules.json` 提取？
- **关联**: Section 8 — `compile.mode` 输出路径公式，Section 7 — C Header 同时生成

### 3. makefile 生成与缓存

- **来源**: Section 1, 待讨论列表
- **状态**: 当前 `cmcf build` 用 Python subprocess 直接调 clang+llvm-link，不生成 makefile
- **决策点**: 保持纯 Python 方案还是改为 makefile+make？
  - 纯 Python: Windows 无需 MSYS2，简单，但不透明
  - makefile+make: 用户可手动 `make`，适合复杂项目，Windows 需额外依赖
- **缓存**: 若用 makefile，是否缓存到 `.cmcf/makefile`？仅 `cmcf install/remove` 时更新？

---

## 🟡 功能部分缺失

### 4. 全局变量 initializer 的 MC 映射

- **来源**: 设计讨论中 — "标记为待定"
- **状态**: `IRGlobal` 已有 `initializer: IROperand | None` 字段，`IRConverter` 已提取
- **未决**: 字符串常量（`@.str = c"hello\00"`）在 MC 中如何表示？
  - 存为 `IRConst(kind="string", value="hello")` → 但 mcfunction 中没有字符串类型
  - 实现时根据用途转换：`printf("hello")` → `tellraw @a "hello"`
  - 由哪个 handler 负责转换？syscall handler 还是 memory handler？
- **关联**: `cmcf/core/ir_converter.py` — `_convert_global_init()`

### 5. `EXPORT_AS` 注解格式

- **来源**: 讨论中 — "具体格式实现时细化"
- **状态**: HeaderExporter 已实现基本解析（`ann.split(":", 3)[2]`）
- **未决**:
  - 路径中允许 `/` 分隔文件夹层级？当前设计支持
  - 是否需要特殊字符转义？
  - 导出路径与 mcfunction 路径的对应关系是否一致？
- **关联**: `cmcf/core/header_exporter.py`

### 6. `--env` CLI 参数

- **来源**: Section 6.10
- **状态**: 设计文档有说明，但 `mcc build` 代码中未实现
- **需要**: 在 `mcc build` 的 argparse 中添加 `--env` 参数，传递给 `_load_handlers()`
- **关联**: `cmcf/cli/mcc.py`

### 7. NameProvider 实现细化

- **来源**: Section 9.3 — "具体实现时再做细化"
- **状态**: 已实现基础方法（`func_file`, `exported_file`, `block_file`, `scoreboard_obj` 等）
- **未决**:
  - 是否需要根据 pack_format 动态调整目录名（如 `"function"` vs `"functions"`）？
  - 当前 `DEFAULT_PATH_VARS` 已含此信息，NameProvider 是否应该读取 path_vars？
  - `scoreboard_obj` 和 `scoreboard_player` 的命名避免与 Minecraft 保留名冲突？
- **关联**: `cmcf/core/context.py`

---

## 🟢 远期/预留

### 8. `cmcf repo install` 远程仓库获取

- **来源**: 待讨论列表
- **状态**: 仅支持本地路径 `repo install /path/to/module`
- **方向**: 支持 URL（`repo install https://github.com/user/module`）或 Git 仓库

### 9. `cmcf install` 错误回滚机制

- **来源**: 待讨论列表
- **状态**: 部分安装失败时不回滚（如 handler 复制完成但 syscall 冲突报错后，handler 文件已写入磁盘）
- **方向**: 事务式安装：先写入临时目录，全部验证通过后原子 rename

### 10. Windows make fallback

- **来源**: 待讨论列表
- **状态**: 当前 `cmcf build` 用 Python subprocess 直接调 clang，不依赖 make
- **决策**: 若未来改为 makefile 方案，需要纯 Python fallback 或推荐 Windows 用户安装 make

### 11. `Registries` 扩展字段

- **来源**: Section 9.5
- **状态**: 预留接口，无实现
  ```python
  @dataclass
  class Registries:
      syscall: SysCallRegistry
      # 未来扩展: variable_mapping, function_table, annotation_index
  ```

### 12. `--export-header` 与 module 模式

- **来源**: Section 7 — "module 模式始终导出 Header，datapack 模式需 `--export-header`"
- **状态**: `mcc build` 代码中 `config.export_header` 可通过 `--export-header` CLI 设置，但 ExportHeaderHandler 未被注册（handler 未实现）
- **关联**: `cmcf/cli/mcc.py`, `cmcf/core/header_exporter.py`

---

## 补充：代码质量

| # | 议题 | 说明 |
|---|------|------|
| 13 | `echo_test` handler 相对导入 | echo.py 使用 `from cmcf.core.handler import ...`（绝对导入），在项目 handler 加载场景下依赖 cmcf 在 PYTHONPATH 上。若模块从 site_libs 安装，需要确认导入路径正确 |
| 14 | cmcf package 安装测试 | 当前所有测试通过 `PYTHONPATH` 设置运行，未测试 `pip install` 后的 console_scripts 行为 |
