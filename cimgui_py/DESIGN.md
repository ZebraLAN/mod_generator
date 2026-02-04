# cimgui_py 设计文档

## 目标

直接绑定 cimgui (Dear ImGui 1.92.5 的 C wrapper)，不考虑 pyimgui 兼容性。

## cimgui API 命名规范

cimgui 的函数命名模式：
- `ig*` - ImGui 全局函数 (如 `igBegin`, `igButton`, `igPushFont`)
- `ImXxx_*` - 结构体方法 (如 `ImFontAtlas_AddFont`, `ImDrawList_AddLine`)
- 重载函数用后缀区分: `_Str`, `_ID`, `_Float`, `_Vec2`, `_Nil` 等

## 1.92 关键 API 变化

### Font System (核心变化)

```c
// PushFont 现在需要 size 参数
void igPushFont(ImFont* font, float font_size_base_unscaled);

// 新增 ImFontBaked - 特定尺寸的字体缓存
ImFontBaked* igGetFontBaked(void);
ImFontBaked* ImFont_GetFontBaked(ImFont* self, float font_size, float density);

// FontAtlas 新增
void ImFontAtlas_RemoveFont(ImFontAtlas* self, ImFont* font);
void ImFontAtlas_CompactCache(ImFontAtlas* self);

// 废弃 (但仍存在供旧后端使用)
// ImFontAtlas_Build, ImFontAtlas_IsBuilt, ImFontAtlas_SetTexID
```

### Texture System (新协议)

```c
// 新的纹理状态机
typedef enum {
    ImTextureStatus_OK,
    ImTextureStatus_Destroyed,
    ImTextureStatus_WantCreate,
    ImTextureStatus_WantUpdates,
    ImTextureStatus_WantDestroy,
} ImTextureStatus;

// ImTextureRef 替代裸 ImTextureID
struct ImTextureRef_c {
    ImTextureData* _TexData;
    ImTextureID _TexID;
};

// 后端标志
ImGuiBackendFlags_RendererHasTextures = 1 << 4

// ImDrawData 现在包含 Textures 列表
ImVector_ImTextureDataPtr* Textures;  // 后端需要处理
```

### Image/Drawing API 变化

```c
// Image 函数现在使用 ImTextureRef_c 而不是 ImTextureID
void igImage(ImTextureRef_c tex_ref, ...);
void ImDrawList_AddImage(ImDrawList* self, ImTextureRef_c tex_ref, ...);
```

## 绑定策略

### 层级结构

```
cimgui_py/
├── src/
│   ├── cimgui.pxd          # C 声明 (从 cimgui.h 提取)
│   ├── imgui.pyx           # 主绑定模块
│   └── backend_glfw_opengl3.pyx  # GLFW+OpenGL3 后端
└── cimgui_py/
    ├── __init__.py         # 导出 API
    └── __init__.pyi        # 类型存根
```

### Python API 设计原则

1. **薄封装**: 尽可能直接暴露 C API
2. **Pythonic 返回值**: 指针参数转 tuple (changed, value)
3. **类型安全**: 使用 typing 注解
4. **无魔法**: 不自动管理生命周期

### 类型映射

| C 类型 | Python 类型 |
|--------|-------------|
| `ImVec2_c` | `tuple[float, float]` 或 `Vec2` 类 |
| `ImVec4_c` | `tuple[float, float, float, float]` 或 `Vec4` 类 |
| `const char*` | `str` (自动 UTF-8 编码) |
| `bool*` | 返回 `tuple[bool, new_value]` |
| `float*` | 返回 `tuple[changed, new_value]` |
| `ImFont*` | `Font` wrapper 类 |
| `ImFontAtlas*` | `FontAtlas` wrapper 类 |
| `ImDrawList*` | `DrawList` wrapper 类 |
| `ImTextureRef_c` | `TextureRef` wrapper 类 |

### 模块划分

1. **Context & Frame**: create_context, new_frame, render, etc.
2. **Window**: begin, end, begin_child, etc.
3. **Layout**: same_line, spacing, indent, etc.
4. **Widgets**: button, text, input_*, slider_*, etc.
5. **Font**: push_font, FontAtlas, Font, FontBaked
6. **Drawing**: DrawList, DrawData
7. **Style**: push_style_color, push_style_var, etc.
8. **Input**: is_key_pressed, is_mouse_clicked, etc.

## 后端实现

### GLFW + OpenGL3

需要实现 `ImGuiBackendFlags_RendererHasTextures` 协议：

```python
class GlfwOpenGL3Backend:
    def render(self, draw_data: DrawData):
        # 1. 处理纹理状态变化
        for tex in draw_data.textures:
            if tex.status == TextureStatus.WantCreate:
                self._create_texture(tex)
            elif tex.status == TextureStatus.WantUpdates:
                self._update_texture(tex)
            elif tex.status == TextureStatus.WantDestroy:
                self._destroy_texture(tex)
        
        # 2. 渲染 draw lists
        for cmd_list in draw_data.cmd_lists:
            ...
```

## 分阶段实现

### Phase 1: 核心框架
- [ ] cimgui.pxd: 结构体和枚举声明
- [ ] cimgui.pxd: 核心函数声明 (Context, Frame, Window)
- [ ] imgui.pyx: 基础封装类 (Vec2, Vec4)
- [ ] imgui.pyx: Context/Frame 函数
- [ ] 编译测试

### Phase 2: Widgets
- [ ] 文本 widgets (text, text_colored, etc.)
- [ ] 按钮 widgets (button, checkbox, radio)
- [ ] 输入 widgets (input_text, input_int, input_float)
- [ ] 滑块 widgets (slider_*, drag_*)

### Phase 3: Font System (1.92 重点)
- [ ] Font wrapper
- [ ] FontBaked wrapper
- [ ] FontAtlas wrapper (add_font, remove_font, compact_cache)
- [ ] push_font(font, size) 新 API

### Phase 4: Drawing & Textures
- [ ] TextureRef / TextureData wrappers
- [ ] DrawList wrapper
- [ ] DrawData wrapper (含 Textures 列表)

### Phase 5: Backend
- [ ] GLFW 输入处理
- [ ] OpenGL3 渲染 (含 RendererHasTextures 协议)
- [ ] 纹理动态创建/更新/销毁

### Phase 6: 完善
- [ ] 类型存根 (.pyi)
- [ ] 文档
- [ ] 测试
