# -*- coding: utf-8 -*-
"""GLFW 后端集成 - 兼容 pyimgui 的 GlfwRenderer"""

# 尝试导入编译后的后端
try:
    from cimgui_py.backend import GlfwRenderer
except ImportError as e:
    # 未编译时提供占位类
    class GlfwRenderer:
        """GLFW + OpenGL3 渲染器 (未编译)
        
        与 pyimgui 的 imgui.integrations.glfw.GlfwRenderer 兼容。
        """
        
        def __init__(self, window):
            raise ImportError(
                f"cimgui_py 尚未编译。请运行: cd cimgui_py && pip install -e .\n"
                f"原始错误: {e}"
            )
        
        def process_inputs(self):
            raise NotImplementedError()
        
        def render(self, draw_data):
            raise NotImplementedError()
        
        def shutdown(self):
            raise NotImplementedError()
        
        def refresh_font_texture(self):
            raise NotImplementedError()
