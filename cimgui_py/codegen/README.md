# cimgui Python Binding - 数据驱动编译器

## 架构概述

```
cimgui JSON (source of truth)
        ↓
   ┌────┴────┐
   │compiler.py│ ← config/*.json (设计决策)
   └────┬────┘
        ↓
templates/*.jinja2 → 生成 src/*.{pxd,pyx,pyi}
```

## 核心原则

### 从 cimgui JSON 自动 Derive

| 数据 | 来源 | 说明 |
|------|------|------|
| Public vs Internal API | `location` 字段 | `imgui:440` = public, `imgui_internal:4002` = internal |
| 函数签名 | `argsT`, `ret`, `defaults` | 完整的参数和返回类型 |
| Wrapper 类方法 | `stname` 字段 | `ImFont` → `_Font` 类方法 |
| 结构体字段 | `structs_and_enums.json` | 自动生成属性访问 |
| 枚举值 | `structs_and_enums.json` | 包含 `calc_value` |

### 只配置稳定的设计决策

| 配置 | 文件 | 说明 |
|------|------|------|
| 类型转换 | `type_mapping.json` | C → Python 类型映射 (ImVec2 → tuple 等) |
| 特殊处理 | `overrides.json` | 多返回值函数、手动实现的函数 |

### 不配置易变数据

- ❌ 不手动维护 public/internal 列表
- ❌ 不手动维护方法归属 
- ❌ 不手动追踪函数列表

## 文件结构

```
codegen/
├── compiler.py         # 核心编译器
├── config/
│   ├── type_mapping.json   # 类型转换规则
│   └── overrides.json      # 特殊函数处理
└── templates/
    ├── cimgui.pxd.jinja2       # Cython 声明
    ├── imgui_core.pyx.jinja2   # Cython 实现
    └── imgui.pyi.jinja2        # 类型存根
```

## 使用方法

```bash
# 生成代码
python codegen/compiler.py -o src/

# 查看统计
python codegen/compiler.py --stats
```

## 生成统计 (Dear ImGui 1.92.5)

- Public Functions: 342
- Wrapper Classes: 25 (包含 238 个方法)
- Structs: 127
- Enums: 75

## 添加新的特殊处理

1. 在 `overrides.json` 中添加 skip:
   ```json
   "igNewFunction": {"skip": true}
   ```

2. 在 `imgui_core.pyx.jinja2` 的 "Special Handler Functions" 部分添加手动实现

## 更新 ImGui 版本

1. 更新 cimgui submodule
2. 运行 `python codegen/compiler.py -o src/`
3. 检查是否有新的需要特殊处理的函数
