# cython: language_level=3
# cython: embedsignature=True
# distutils: language=c++
"""imgui_backend.pyx - GLFW + OpenGL3 后端绑定

提供 GlfwRenderer 类，与 pyimgui 的 imgui.integrations.glfw.GlfwRenderer 兼容。
"""

cimport cimgui
from cpython.ref cimport PyObject

# GLFW 窗口句柄类型
ctypedef void* GLFWwindow


cdef class GlfwRenderer:
    """GLFW + OpenGL3 渲染器
    
    与 pyimgui 的 imgui.integrations.glfw.GlfwRenderer 兼容。
    
    用法:
        import glfw
        import cimgui_py as imgui
        from cimgui_py.integrations.glfw import GlfwRenderer
        
        # 创建窗口
        window = glfw.create_window(1200, 800, "My App", None, None)
        glfw.make_context_current(window)
        
        # 初始化 ImGui
        imgui.create_context()
        renderer = GlfwRenderer(window)
        
        # 主循环
        while not glfw.window_should_close(window):
            glfw.poll_events()
            renderer.process_inputs()
            
            imgui.new_frame()
            # ... UI 代码 ...
            imgui.render()
            
            glClear(GL_COLOR_BUFFER_BIT)
            renderer.render(imgui.get_draw_data())
            glfw.swap_buffers(window)
        
        renderer.shutdown()
    """
    
    cdef GLFWwindow* _window
    cdef bint _initialized
    
    def __init__(self, window):
        """初始化渲染器
        
        Args:
            window: GLFW 窗口句柄 (来自 glfw.create_window)
        """
        # glfw 模块返回的窗口是一个 ctypes 指针或 capsule
        # 需要转换为 C 指针
        self._window = <GLFWwindow*><size_t>window
        self._initialized = False
        
        # 初始化 GLFW 后端
        if not cimgui.ImGui_ImplGlfw_InitForOpenGL(self._window, True):
            raise RuntimeError("Failed to initialize ImGui GLFW backend")
        
        # 初始化 OpenGL3 后端
        # #version 330 适用于 OpenGL 3.3 Core Profile
        if not cimgui.ImGui_ImplOpenGL3_Init(b"#version 330"):
            cimgui.ImGui_ImplGlfw_Shutdown()
            raise RuntimeError("Failed to initialize ImGui OpenGL3 backend")
        
        self._initialized = True
    
    def process_inputs(self):
        """处理输入事件
        
        在 imgui.new_frame() 之前调用。
        """
        cimgui.ImGui_ImplOpenGL3_NewFrame()
        cimgui.ImGui_ImplGlfw_NewFrame()
    
    def render(self, draw_data):
        """渲染 ImGui 绘制数据
        
        在 imgui.render() 之后、glfw.swap_buffers() 之前调用。
        
        Args:
            draw_data: imgui.get_draw_data() 返回的数据
        """
        # draw_data 是 _DrawData 包装对象
        from cimgui_py.core import _DrawData
        if not isinstance(draw_data, _DrawData):
            raise TypeError("Expected _DrawData from imgui.get_draw_data()")
        
        cdef cimgui.ImDrawData* ptr = (<object>draw_data)._ptr
        cimgui.ImGui_ImplOpenGL3_RenderDrawData(ptr)
    
    def shutdown(self):
        """清理资源
        
        在退出应用前调用。
        """
        if self._initialized:
            cimgui.ImGui_ImplOpenGL3_Shutdown()
            cimgui.ImGui_ImplGlfw_Shutdown()
            self._initialized = False
    
    def refresh_font_texture(self):
        """重建字体纹理
        
        动态添加字体后调用:
            io = imgui.get_io()
            io.fonts.add_font_from_file_ttf("new_font.ttf", 16)
            io.fonts.build()
            renderer.refresh_font_texture()  # 重建 OpenGL 纹理
        """
        # 销毁旧纹理
        cimgui.ImGui_ImplOpenGL3_DestroyFontsTexture()
        # 创建新纹理
        if not cimgui.ImGui_ImplOpenGL3_CreateFontsTexture():
            raise RuntimeError("Failed to create fonts texture")
    
    def __dealloc__(self):
        """析构时自动清理"""
        self.shutdown()
