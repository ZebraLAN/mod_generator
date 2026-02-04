# cimgui_py - Python Bindings for Dear ImGui

基于 cimgui (Dear ImGui 的 C 包装) 的 Cython 绑定。

## 当前状态

✅ **核心绑定已完成！**

- 272 个函数已绑定
- 预编译 cimgui.dll (Dear ImGui 1.92.5 docking)
- 数据驱动的代码生成系统

## 功能覆盖

| 类别 | 状态 | 函数 |
|------|------|------|
| 窗口控制 | ✅ | `begin`, `end`, `begin_child`, `end_child`, ... |
| 基础 Widgets | ✅ | `button`, `checkbox`, `slider_*`, `input_text`, ... |
| 布局 | ✅ | `same_line`, `separator`, `spacing`, `columns`, ... |
| 菜单 | ✅ | `begin_menu_bar`, `begin_menu`, `menu_item`, ... |
| 表格 | ✅ | `begin_table`, `table_next_row`, `table_setup_column`, ... |
| 弹窗 | ✅ | `begin_popup`, `open_popup`, `close_current_popup`, ... |
| 样式 | ✅ | `push_style_color`, `pop_style_color`, `push_style_var`, ... |
| 树 | ✅ | `tree_node`, `tree_pop`, ... |
| 拖放 | ✅ | `begin_drag_drop_source`, `begin_drag_drop_target`, ... |
| Tab | ✅ | `begin_tab_bar`, `tab_item_button`, ... |
| 字体 | 🔄 | 待完善 |
| 后端 | 🔄 | GLFW + OpenGL3 待实现 |

## 构建

### 前置条件

- Python 3.10+
- Cython 3.2+
- Visual Studio 2022 (Windows)

### 步骤

1. **预编译的 cimgui.dll 已包含在 `lib/` 目录中**

2. **生成绑定并编译**:
```bash
cd cimgui_py
python codegen/compiler.py   # 生成 Cython 代码
python setup.py build_ext --inplace  # 编译
```

3. **测试**:
```bash
python test_binding.py
```

## 架构

```
cimgui_py/
├── vendor/cimgui/        # cimgui 源码 (git submodule)
├── lib/
│   ├── cimgui.dll        # 预编译的 cimgui 库
│   └── cimgui.lib
├── codegen/
│   ├── compiler.py       # 代码生成器
│   ├── templates/        # Jinja2 模板
│   │   ├── cimgui.pxd.jinja2
│   │   └── imgui_core.pyx.jinja2
│   └── config/
│       ├── type_mapping.json   # 类型映射配置
│       └── overrides.json      # 函数覆盖配置
├── src/
│   ├── cimgui.pxd        # 生成的 Cython 声明
│   ├── imgui_core.pyx    # 生成的 Cython 实现
│   └── cimgui_py/
│       ├── __init__.py
│       └── core.*.pyd    # 编译后的扩展模块
├── setup.py
└── pyproject.toml
```

## 代码生成系统

本项目使用数据驱动的代码生成方式：

1. **输入**: cimgui 提供的 `definitions.json` (函数签名)
2. **配置**: `type_mapping.json` (C → Python 类型映射)
3. **模板**: Jinja2 模板生成 `.pxd` 和 `.pyx` 文件
4. **输出**: 可编译的 Cython 绑定

### 添加新函数

大多数函数会自动生成。若需手动处理：

1. 编辑 `codegen/config/overrides.json` 添加跳过规则
2. 在 `codegen/templates/imgui_core.pyx.jinja2` 中添加手动实现

### 添加新类型映射

编辑 `codegen/config/type_mapping.json`：

```json
{
  "imgui_structs": {
    "MyNewType*": {
      "cython": "MyNewType*",
      "python": "int",
      "conversion": "ptr"
    }
  }
}
```

## 使用示例

```python
import sys
sys.path.insert(0, "src")

import cimgui_py as imgui

# 创建上下文
ctx = imgui.create_context()

# ... 设置 IO (display size 等)
# ... 后端初始化

# 主循环
imgui.new_frame()

if imgui.begin("Demo Window")[0]:
    imgui.text("Hello, World!")
    if imgui.button("Click Me"):
        print("Button clicked!")
    imgui.end()

imgui.render()
# ... 后端渲染

imgui.destroy_context(ctx)
```

## TODO

- [ ] 字体 API (AddFont, Build, GetTexData)
- [ ] GLFW 后端绑定
- [ ] OpenGL3 后端绑定
- [ ] DrawList API
- [ ] 更多 Widget (color picker, plot 等)
- [ ] 类型存根 (.pyi) 生成
