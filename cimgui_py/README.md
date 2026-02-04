# cimgui_py - 最小化 Dear ImGui Python 绑定

基于 cimgui (Dear ImGui 的 C 包装) 的 Cython 绑定，专为本项目定制。

## 目标

1. **动态字体加载** - pyimgui 缺失的核心功能
2. **API 兼容** - 尽量兼容 pyimgui 的调用风格
3. **最小化** - 只绑定项目实际使用的 API

## 结构

```
cimgui_py/
├── vendor/
│   └── cimgui/          # cimgui 源码 (git submodule)
├── src/
│   ├── cimgui.pxd       # Cython 声明文件 (C 接口)
│   ├── imgui_core.pyx   # 核心控件绑定
│   ├── imgui_font.pyx   # 字体 API 绑定
│   └── imgui_backend.pyx # GLFW + OpenGL 后端
├── imgui/
│   ├── __init__.py      # 公开 API
│   └── integrations/
│       └── glfw.py      # GlfwRenderer 兼容类
├── setup.py
└── pyproject.toml
```

## 构建

```bash
cd cimgui_py
pip install -e .
```

## 进度

- [ ] 获取 cimgui 源码
- [ ] 基础声明文件 (.pxd)
- [ ] 核心控件 (button, text, input_*, begin/end_*)
- [ ] 样式 API (push/pop_style_*)
- [ ] 字体 API (AddFont*, Build, 纹理重建)
- [ ] GLFW 后端
- [ ] OpenGL3 后端
- [ ] 测试 & 迁移
