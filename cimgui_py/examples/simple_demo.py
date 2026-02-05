"""
cimgui_py Simple Demo
使用已绑定的 ImGui 功能展示
"""

import sys
import os
import ctypes

# 添加项目路径 (开发时需要，安装后不需要)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入 cimgui_py - 包的 __init__.py 会处理 DLL 加载顺序
import src.cimgui_py as imgui
from src.cimgui_py import backend

import glfw
from OpenGL import GL as gl

# =============================================================================
# 应用状态
# =============================================================================
class AppState:
    counter = 0
    text_input = "Hello, cimgui_py!"
    checkbox_value = True
    slider_float = 0.5
    slider_int = 50
    color3 = [0.4, 0.7, 0.2]
    combo_current = 0

state = AppState()

# =============================================================================
# UI 绘制
# =============================================================================
def draw_demo_window():
    """演示窗口"""
    # 设置窗口大小（首次使用时）
    imgui.set_next_window_size((600, 500), imgui.ImGuiCond_FirstUseEver)

    if imgui.begin("cimgui_py Demo"):
        # 基础信息
        imgui.text("Welcome to cimgui_py!")
        imgui.text(f"ImGui version: {imgui.get_version()}")
        imgui.separator()

        # 基础控件
        if imgui.collapsing_header("Basic Widgets"):
            # 按钮
            if imgui.button("Click Me!"):
                state.counter += 1
            imgui.same_line()
            imgui.text(f"Counter: {state.counter}")

            # 复选框
            changed, state.checkbox_value = imgui.checkbox("Checkbox", state.checkbox_value)

            # 滑动条
            changed, state.slider_float = imgui.slider_float("Float Slider", state.slider_float, 0.0, 1.0)
            changed, state.slider_int = imgui.slider_int("Int Slider", state.slider_int, 0, 100)

        # 输入框
        if imgui.collapsing_header("Input"):
            changed, state.text_input = imgui.input_text("Text", state.text_input, 256)
            imgui.text(f"You typed: {state.text_input}")

        # 颜色
        if imgui.collapsing_header("Colors"):
            changed, state.color3 = imgui.color_edit3("Color", state.color3)
            # color_button(desc_id, col, flags=0, size=(0,0))
            imgui.color_button("Preview", (*state.color3, 1.0))

        # 树形结构
        if imgui.collapsing_header("Tree"):
            if imgui.tree_node("Root"):
                imgui.text("Leaf 1")
                if imgui.tree_node("Branch"):
                    imgui.text("Leaf 2")
                    imgui.text("Leaf 3")
                    imgui.tree_pop()
                imgui.tree_pop()

        # 表格
        if imgui.collapsing_header("Table"):
            if imgui.begin_table("demo_table", 3):
                imgui.table_setup_column("Name")
                imgui.table_setup_column("Age")
                imgui.table_setup_column("Score")
                imgui.table_headers_row()

                data = [
                    ("Alice", 25, 95.5),
                    ("Bob", 30, 87.3),
                    ("Charlie", 22, 92.1),
                ]

                for name, age, score in data:
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text(name)
                    imgui.table_next_column()
                    imgui.text(str(age))
                    imgui.table_next_column()
                    imgui.text(f"{score:.1f}")

                imgui.end_table()

        # 菜单
        if imgui.collapsing_header("Popup/Menu"):
            if imgui.button("Open Popup"):
                imgui.open_popup("demo_popup")

            if imgui.begin_popup("demo_popup"):
                imgui.text("This is a popup!")
                if imgui.button("Close"):
                    imgui.close_current_popup()
                imgui.end_popup()

    imgui.end()


def main():
    # 初始化 GLFW
    if not glfw.init():
        print("Failed to initialize GLFW")
        return 1

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    window = glfw.create_window(1024, 768, "cimgui_py Demo", None, None)
    if not window:
        print("Failed to create GLFW window")
        glfw.terminate()
        return 1

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    # 创建 ImGui 上下文
    ctx = imgui.create_context()

    # 初始化后端
    window_ptr = ctypes.cast(window, ctypes.c_void_p).value
    backend.glfw_init_for_open_gl(window_ptr, True)
    backend.opengl3_init("#version 330")

    # 设置样式
    imgui.style_colors_dark()

    print("cimgui_py Demo started!")
    print(f"ImGui version: {imgui.get_version()}")

    # 主循环
    while not glfw.window_should_close(window):
        glfw.poll_events()

        backend.opengl3_new_frame()
        backend.glfw_new_frame()
        imgui.new_frame()

        # 显示内置 demo 窗口
        imgui.show_demo_window()

        # 显示我们的 demo
        draw_demo_window()

        # 渲染
        imgui.render()

        w, h = glfw.get_framebuffer_size(window)
        gl.glViewport(0, 0, w, h)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        draw_data = imgui.get_draw_data()
        backend.opengl3_render_draw_data(draw_data._pointer)

        glfw.swap_buffers(window)

    # 清理
    backend.opengl3_shutdown()
    backend.glfw_shutdown()
    imgui.destroy_context(ctx)
    glfw.terminate()

    print("Demo finished!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
