# cimgui_py - Python Bindings for Dear ImGui

基于 cimgui (Dear ImGui 的 C 包装) 的 Cython 绑定。

## 当前状态

✅ **核心绑定已完成！**

- 330 个函数已绑定 (core)
- 26 个后端函数 (GLFW + OpenGL3)
- 445 个常量 (枚举值)
- 7 个类 (IO, Style, Font, DrawList 等)
- 预编译 cimgui.dll (Dear ImGui 1.92.x docking)
- 全自动代码生成系统

## 功能覆盖

| 类别 | 状态 | 说明 |
|------|------|------|
| 窗口控制 | ✅ | `begin`, `end`, `begin_child`, `end_child`, ... |
| 基础 Widgets | ✅ | `button`, `checkbox`, `slider_*`, `input_text`, ... |
| 布局 | ✅ | `same_line`, `separator`, `spacing`, `columns`, ... |
| 菜单 | ✅ | `begin_menu_bar`, `begin_menu`, `menu_item`, ... |
| 表格 | ✅ | `begin_table`, `table_next_row`, `table_setup_column`, ... |
| 弹窗 | ✅ | `begin_popup`, `open_popup`, `close_current_popup`, ... |
| 样式 | ✅ | `push_style_color`, `pop_style_color`, `push_style_var`, ... |
| 树 | ✅ | `tree_node`, `tree_pop`, `collapsing_header`, ... |
| 拖放 | ✅ | `begin_drag_drop_source`, `begin_drag_drop_target`, ... |
| Tab | ✅ | `begin_tab_bar`, `begin_tab_item`, ... |
| 字体 | ✅ | 1.92 新 API: `push_font`, `get_font_baked`, ... |
| GLFW 后端 | ✅ | `glfw_init_for_open_gl`, `glfw_new_frame`, ... (19 函数) |
| OpenGL3 后端 | ✅ | `opengl3_init`, `opengl3_render_draw_data`, ... (7 函数) |

## 安装

```bash
cd cimgui_py
pip install -e .
```

## 构建 (开发)

### 前置条件

- Python 3.10+
- Cython 3.0+
- Visual Studio 2022 (Windows)

### 步骤

1. **生成绑定代码**:
```bash
python codegen/compiler.py -o src
```

2. **编译并安装**:
```bash
pip install -e .
```

3. **验证**:
```python
import imgui
print(len([f for f in dir(imgui) if not f.startswith('_')]))  # ~780
```

## 架构

```
cimgui_py/
├── vendor/cimgui/        # cimgui 源码 (git submodule)
├── lib/
│   ├── cimgui.dll        # 预编译的 cimgui 库
│   └── cimgui.lib
├── codegen/
│   ├── compiler.py       # 代码生成器 (主入口)
│   ├── templates/        # Jinja2 模板
│   │   ├── cimgui.pxd.jinja2      # Cython 声明
│   │   ├── imgui_core.pyx.jinja2  # Cython 实现
│   │   └── imgui.pyi.jinja2       # 类型存根
│   └── config/
│       └── overrides.json  # 函数覆盖配置
├── src/                  # 生成的代码 (git ignored)
│   ├── cimgui.pxd
│   ├── imgui_core.pyx
│   ├── imgui.pyi
│   └── cimgui_py/
│       ├── __init__.py
│       └── core.*.pyd
├── setup.py
└── pyproject.toml
```

## 代码生成系统

本项目使用**全自动**数据驱动的代码生成：

1. **输入**: cimgui 的 `definitions.json`, `structs_and_enums.json`
2. **类型映射**: 内置在 `compiler.py` 中 (无需外部配置)
3. **模板**: Jinja2 模板生成所有绑定代码
4. **输出**: `.pxd`, `.pyx`, `.pyi` 文件

### 自动处理

- ✅ 值类型结构体 (ImVec2, ImVec4, ImRect, ImColor 等)
- ✅ 输出参数 (bool*, int*, float* → 返回 tuple)
- ✅ 数组参数 (float[3], int[4] → 返回 tuple)
- ✅ 字符串数组 (const char*[] → Python list)
- ✅ 函数重载分派 (str vs int 参数)
- ✅ 可选回调 (NULL 安全)

### 手动处理的函数

只有少数函数需要手动实现 (见 `overrides.json`):

- `begin` - 特殊的 closable 参数处理
- `text` - 使用 TextUnformatted 避免格式化问题
- `input_text*` - char* buffer 管理
- `combo`, `list_box` - 字符串数组转换

## 使用示例

```python
import imgui

# 创建上下文
imgui.create_context()

# 主循环
imgui.new_frame()

if imgui.begin("Demo Window"):
    imgui.text("Hello, World!")

    if imgui.button("Click Me"):
        print("Button clicked!")

    changed, value = imgui.slider_float("Speed", 1.0, 0.0, 10.0)
    if changed:
        print(f"New value: {value}")

    imgui.end()

imgui.render()
draw_data = imgui.get_draw_data()
# ... 后端渲染

imgui.destroy_context()
```

## TODO

- [x] GLFW 后端绑定 ✅
- [x] OpenGL3 后端绑定 ✅
- [ ] DrawList 方法绑定
- [ ] 完整的 .pyi 类型存根
