# cython: language_level=3
# cython: embedsignature=True
# distutils: language=c++
"""imgui_core.pyx - 核心 ImGui API 绑定

提供与 pyimgui 兼容的 Python API。
"""

from libc.stdlib cimport malloc, free
from libc.string cimport memcpy, strlen
from cpython.bytes cimport PyBytes_AsString

cimport cimgui

# =============================================================================
# 辅助类型和转换
# =============================================================================

cdef class Vec2:
    """2D 向量 - 兼容 pyimgui 的 ImVec2"""
    cdef public float x
    cdef public float y
    
    def __init__(self, float x=0, float y=0):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Vec2({self.x}, {self.y})"
    
    def __iter__(self):
        yield self.x
        yield self.y


cdef class Vec4:
    """4D 向量 - 兼容 pyimgui 的 ImVec4"""
    cdef public float x
    cdef public float y
    cdef public float z
    cdef public float w
    
    def __init__(self, float x=0, float y=0, float z=0, float w=0):
        self.x = x
        self.y = y
        self.z = z
        self.w = w
    
    def __repr__(self):
        return f"Vec4({self.x}, {self.y}, {self.z}, {self.w})"
    
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z
        yield self.w


cdef inline cimgui.ImVec2 _vec2(tuple t):
    """Python tuple -> ImVec2"""
    cdef cimgui.ImVec2 v
    v.x = <float>t[0] if len(t) > 0 else 0
    v.y = <float>t[1] if len(t) > 1 else 0
    return v


cdef inline cimgui.ImVec4 _vec4(tuple t):
    """Python tuple -> ImVec4"""
    cdef cimgui.ImVec4 v
    v.x = <float>t[0] if len(t) > 0 else 0
    v.y = <float>t[1] if len(t) > 1 else 0
    v.z = <float>t[2] if len(t) > 2 else 0
    v.w = <float>t[3] if len(t) > 3 else 0
    return v


cdef inline bytes _to_bytes(s):
    """字符串转 bytes"""
    if isinstance(s, bytes):
        return s
    return s.encode('utf-8')


# =============================================================================
# IO 和 Style 包装类
# =============================================================================

cdef class _IO:
    """ImGuiIO 包装 - 提供属性访问"""
    cdef cimgui.ImGuiIO* _ptr
    
    @staticmethod
    cdef _IO wrap(cimgui.ImGuiIO* ptr):
        cdef _IO obj = _IO.__new__(_IO)
        obj._ptr = ptr
        return obj
    
    @property
    def display_size(self):
        return Vec2(self._ptr.DisplaySize.x, self._ptr.DisplaySize.y)
    
    @display_size.setter
    def display_size(self, value):
        self._ptr.DisplaySize.x = value[0]
        self._ptr.DisplaySize.y = value[1]
    
    @property
    def delta_time(self):
        return self._ptr.DeltaTime
    
    @delta_time.setter
    def delta_time(self, float value):
        self._ptr.DeltaTime = value
    
    @property
    def font_global_scale(self):
        return self._ptr.FontGlobalScale
    
    @font_global_scale.setter
    def font_global_scale(self, float value):
        self._ptr.FontGlobalScale = value
    
    @property
    def fonts(self):
        """返回 FontAtlas"""
        return _FontAtlas.wrap(self._ptr.Fonts)


cdef class _Style:
    """ImGuiStyle 包装 - 提供属性访问"""
    cdef cimgui.ImGuiStyle* _ptr
    
    @staticmethod
    cdef _Style wrap(cimgui.ImGuiStyle* ptr):
        cdef _Style obj = _Style.__new__(_Style)
        obj._ptr = ptr
        return obj
    
    @property
    def alpha(self):
        return self._ptr.Alpha
    
    @alpha.setter
    def alpha(self, float value):
        self._ptr.Alpha = value
    
    @property
    def window_padding(self):
        return Vec2(self._ptr.WindowPadding.x, self._ptr.WindowPadding.y)
    
    @window_padding.setter
    def window_padding(self, value):
        self._ptr.WindowPadding.x = value[0]
        self._ptr.WindowPadding.y = value[1]
    
    @property
    def window_rounding(self):
        return self._ptr.WindowRounding
    
    @window_rounding.setter
    def window_rounding(self, float value):
        self._ptr.WindowRounding = value
    
    @property
    def window_border_size(self):
        return self._ptr.WindowBorderSize
    
    @window_border_size.setter
    def window_border_size(self, float value):
        self._ptr.WindowBorderSize = value
    
    @property
    def child_rounding(self):
        return self._ptr.ChildRounding
    
    @child_rounding.setter
    def child_rounding(self, float value):
        self._ptr.ChildRounding = value
    
    @property
    def child_border_size(self):
        return self._ptr.ChildBorderSize
    
    @child_border_size.setter
    def child_border_size(self, float value):
        self._ptr.ChildBorderSize = value
    
    @property
    def popup_rounding(self):
        return self._ptr.PopupRounding
    
    @popup_rounding.setter
    def popup_rounding(self, float value):
        self._ptr.PopupRounding = value
    
    @property
    def popup_border_size(self):
        return self._ptr.PopupBorderSize
    
    @popup_border_size.setter
    def popup_border_size(self, float value):
        self._ptr.PopupBorderSize = value
    
    @property
    def frame_padding(self):
        return Vec2(self._ptr.FramePadding.x, self._ptr.FramePadding.y)
    
    @frame_padding.setter
    def frame_padding(self, value):
        self._ptr.FramePadding.x = value[0]
        self._ptr.FramePadding.y = value[1]
    
    @property
    def frame_rounding(self):
        return self._ptr.FrameRounding
    
    @frame_rounding.setter
    def frame_rounding(self, float value):
        self._ptr.FrameRounding = value
    
    @property
    def frame_border_size(self):
        return self._ptr.FrameBorderSize
    
    @frame_border_size.setter
    def frame_border_size(self, float value):
        self._ptr.FrameBorderSize = value
    
    @property
    def item_spacing(self):
        return Vec2(self._ptr.ItemSpacing.x, self._ptr.ItemSpacing.y)
    
    @item_spacing.setter
    def item_spacing(self, value):
        self._ptr.ItemSpacing.x = value[0]
        self._ptr.ItemSpacing.y = value[1]
    
    @property
    def item_inner_spacing(self):
        return Vec2(self._ptr.ItemInnerSpacing.x, self._ptr.ItemInnerSpacing.y)
    
    @item_inner_spacing.setter
    def item_inner_spacing(self, value):
        self._ptr.ItemInnerSpacing.x = value[0]
        self._ptr.ItemInnerSpacing.y = value[1]
    
    @property
    def cell_padding(self):
        return Vec2(self._ptr.CellPadding.x, self._ptr.CellPadding.y)
    
    @cell_padding.setter
    def cell_padding(self, value):
        self._ptr.CellPadding.x = value[0]
        self._ptr.CellPadding.y = value[1]
    
    @property
    def indent_spacing(self):
        return self._ptr.IndentSpacing
    
    @indent_spacing.setter
    def indent_spacing(self, float value):
        self._ptr.IndentSpacing = value
    
    @property
    def scrollbar_size(self):
        return self._ptr.ScrollbarSize
    
    @scrollbar_size.setter
    def scrollbar_size(self, float value):
        self._ptr.ScrollbarSize = value
    
    @property
    def scrollbar_rounding(self):
        return self._ptr.ScrollbarRounding
    
    @scrollbar_rounding.setter
    def scrollbar_rounding(self, float value):
        self._ptr.ScrollbarRounding = value
    
    @property
    def grab_min_size(self):
        return self._ptr.GrabMinSize
    
    @grab_min_size.setter
    def grab_min_size(self, float value):
        self._ptr.GrabMinSize = value
    
    @property
    def grab_rounding(self):
        return self._ptr.GrabRounding
    
    @grab_rounding.setter
    def grab_rounding(self, float value):
        self._ptr.GrabRounding = value
    
    @property
    def tab_rounding(self):
        return self._ptr.TabRounding
    
    @tab_rounding.setter
    def tab_rounding(self, float value):
        self._ptr.TabRounding = value


# =============================================================================
# Font 相关类
# =============================================================================

cdef class _Font:
    """ImFont 包装"""
    cdef cimgui.ImFont* _ptr
    
    @staticmethod
    cdef _Font wrap(cimgui.ImFont* ptr):
        if ptr == NULL:
            return None
        cdef _Font obj = _Font.__new__(_Font)
        obj._ptr = ptr
        return obj
    
    @property
    def font_size(self):
        return self._ptr.FontSize
    
    @property
    def scale(self):
        return self._ptr.Scale
    
    @scale.setter
    def scale(self, float value):
        self._ptr.Scale = value


cdef class _FontAtlas:
    """ImFontAtlas 包装 - 关键字体 API！"""
    cdef cimgui.ImFontAtlas* _ptr
    
    @staticmethod
    cdef _FontAtlas wrap(cimgui.ImFontAtlas* ptr):
        if ptr == NULL:
            return None
        cdef _FontAtlas obj = _FontAtlas.__new__(_FontAtlas)
        obj._ptr = ptr
        return obj
    
    def add_font_default(self):
        """添加默认字体"""
        cdef cimgui.ImFont* font = cimgui.ImFontAtlas_AddFontDefault(self._ptr, NULL)
        return _Font.wrap(font)
    
    def add_font_from_file_ttf(self, str filename, float size_pixels, 
                                glyph_ranges=None):
        """从 TTF 文件添加字体
        
        Args:
            filename: TTF 文件路径
            size_pixels: 字体大小 (像素)
            glyph_ranges: 字形范围 (可选)
        
        Returns:
            _Font 对象
        """
        cdef bytes b_filename = _to_bytes(filename)
        cdef cimgui.ImWchar* c_ranges = NULL
        cdef list ranges_list
        cdef cimgui.ImWchar* ranges_array = NULL
        
        if glyph_ranges is not None:
            ranges_list = list(glyph_ranges)
            ranges_array = <cimgui.ImWchar*>malloc(len(ranges_list) * sizeof(cimgui.ImWchar))
            for i, r in enumerate(ranges_list):
                ranges_array[i] = <cimgui.ImWchar>r
            c_ranges = ranges_array
        
        cdef cimgui.ImFont* font = cimgui.ImFontAtlas_AddFontFromFileTTF(
            self._ptr, b_filename, size_pixels, NULL, c_ranges
        )
        
        if ranges_array != NULL:
            free(ranges_array)
        
        return _Font.wrap(font)
    
    def build(self):
        """构建字体图集
        
        动态添加字体后调用此方法，然后调用后端的 refresh_font_texture()
        """
        return cimgui.ImFontAtlas_Build(self._ptr)
    
    def clear_fonts(self):
        """清除所有字体"""
        cimgui.ImFontAtlas_ClearFonts(self._ptr)
    
    def clear(self):
        """清除所有数据"""
        cimgui.ImFontAtlas_Clear(self._ptr)
    
    def is_built(self):
        """检查是否已构建"""
        return cimgui.ImFontAtlas_IsBuilt(self._ptr)
    
    def get_tex_data_as_rgba32(self):
        """获取纹理数据 (RGBA32 格式)
        
        Returns:
            tuple: (pixels_bytes, width, height)
        """
        cdef unsigned char* pixels
        cdef int width, height, bytes_per_pixel
        cimgui.ImFontAtlas_GetTexDataAsRGBA32(
            self._ptr, &pixels, &width, &height, &bytes_per_pixel
        )
        # 转换为 Python bytes
        cdef int size = width * height * bytes_per_pixel
        return (bytes(pixels[:size]), width, height)
    
    def set_tex_id(self, tex_id):
        """设置纹理 ID"""
        cimgui.ImFontAtlas_SetTexID(self._ptr, <cimgui.ImTextureID><size_t>tex_id)
    
    # Glyph ranges 快捷方法
    def get_glyph_ranges_default(self):
        """获取默认字形范围"""
        cdef const cimgui.ImWchar* ranges = cimgui.ImFontAtlas_GetGlyphRangesDefault(self._ptr)
        return _glyph_ranges_to_list(ranges)
    
    def get_glyph_ranges_chinese_full(self):
        """获取完整中文字形范围"""
        cdef const cimgui.ImWchar* ranges = cimgui.ImFontAtlas_GetGlyphRangesChineseFull(self._ptr)
        return _glyph_ranges_to_list(ranges)
    
    def get_glyph_ranges_chinese_simplified_common(self):
        """获取常用简体中文字形范围"""
        cdef const cimgui.ImWchar* ranges = cimgui.ImFontAtlas_GetGlyphRangesChineseSimplifiedCommon(self._ptr)
        return _glyph_ranges_to_list(ranges)


cdef list _glyph_ranges_to_list(const cimgui.ImWchar* ranges):
    """将 C 字形范围数组转换为 Python list"""
    cdef list result = []
    cdef int i = 0
    while ranges[i] != 0:
        result.append(ranges[i])
        i += 1
    result.append(0)  # 终止符
    return result


# =============================================================================
# DrawList 包装
# =============================================================================

cdef class _DrawList:
    """ImDrawList 包装"""
    cdef cimgui.ImDrawList* _ptr
    
    @staticmethod
    cdef _DrawList wrap(cimgui.ImDrawList* ptr):
        if ptr == NULL:
            return None
        cdef _DrawList obj = _DrawList.__new__(_DrawList)
        obj._ptr = ptr
        return obj
    
    def add_line(self, p1, p2, col, float thickness=1.0):
        cimgui.ImDrawList_AddLine(self._ptr, _vec2(p1), _vec2(p2), col, thickness)
    
    def add_rect(self, p_min, p_max, col, float rounding=0, int flags=0, float thickness=1.0):
        cimgui.ImDrawList_AddRect(self._ptr, _vec2(p_min), _vec2(p_max), col, rounding, flags, thickness)
    
    def add_rect_filled(self, p_min, p_max, col, float rounding=0, int flags=0):
        cimgui.ImDrawList_AddRectFilled(self._ptr, _vec2(p_min), _vec2(p_max), col, rounding, flags)
    
    def add_circle(self, center, float radius, col, int num_segments=0, float thickness=1.0):
        cimgui.ImDrawList_AddCircle(self._ptr, _vec2(center), radius, col, num_segments, thickness)
    
    def add_circle_filled(self, center, float radius, col, int num_segments=0):
        cimgui.ImDrawList_AddCircleFilled(self._ptr, _vec2(center), radius, col, num_segments)
    
    def add_text(self, pos, col, str text):
        cdef bytes b_text = _to_bytes(text)
        cimgui.ImDrawList_AddText_Vec2(self._ptr, _vec2(pos), col, b_text, NULL)
    
    def add_image(self, tex_id, p_min, p_max, uv_min=(0,0), uv_max=(1,1), col=0xFFFFFFFF):
        cimgui.ImDrawList_AddImage(
            self._ptr, 
            <cimgui.ImTextureID><size_t>tex_id,
            _vec2(p_min), _vec2(p_max),
            _vec2(uv_min), _vec2(uv_max),
            col
        )


# =============================================================================
# Context 和 Frame
# =============================================================================

def create_context():
    """创建 ImGui 上下文"""
    cimgui.igCreateContext(NULL)


def destroy_context():
    """销毁 ImGui 上下文"""
    cimgui.igDestroyContext()


def get_io():
    """获取 IO 对象"""
    return _IO.wrap(cimgui.igGetIO())


def get_style():
    """获取 Style 对象"""
    return _Style.wrap(cimgui.igGetStyle())


def new_frame():
    """开始新帧"""
    cimgui.igNewFrame()


def end_frame():
    """结束帧"""
    cimgui.igEndFrame()


def render():
    """渲染"""
    cimgui.igRender()


cdef class _DrawData:
    """ImDrawData 包装"""
    cdef cimgui.ImDrawData* _ptr
    
    @staticmethod
    cdef _DrawData wrap(cimgui.ImDrawData* ptr):
        cdef _DrawData obj = _DrawData.__new__(_DrawData)
        obj._ptr = ptr
        return obj


def get_draw_data():
    """获取绘制数据"""
    return _DrawData.wrap(cimgui.igGetDrawData())


# =============================================================================
# Window
# =============================================================================

def begin(str name, closable=None, int flags=0):
    """开始窗口
    
    Args:
        name: 窗口名称
        closable: 是否可关闭 (None = 不显示关闭按钮)
        flags: 窗口标志
    
    Returns:
        如果 closable=None: bool (窗口是否展开)
        如果 closable!=None: tuple(expanded, opened)
    """
    cdef bytes b_name = _to_bytes(name)
    cdef cimgui.cppbool opened = True
    cdef cimgui.cppbool expanded
    
    if closable is None:
        expanded = cimgui.igBegin(b_name, NULL, flags)
        return expanded
    else:
        opened = closable
        expanded = cimgui.igBegin(b_name, &opened, flags)
        return (expanded, opened)


def end():
    """结束窗口"""
    cimgui.igEnd()


def begin_child(str label, float width=0, float height=0, 
                border=False, int flags=0):
    """开始子窗口"""
    cdef bytes b_label = _to_bytes(label)
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    # child_flags: border -> ImGuiChildFlags_Border = 1
    cdef int child_flags = 1 if border else 0
    return cimgui.igBeginChild_Str(b_label, size, child_flags, flags)


def end_child():
    """结束子窗口"""
    cimgui.igEndChild()


# =============================================================================
# Widgets: Text
# =============================================================================

def text(str s):
    """显示文本"""
    cdef bytes b = _to_bytes(s)
    cimgui.igText(b)


def text_colored(color, str s):
    """显示彩色文本"""
    cdef bytes b = _to_bytes(s)
    cimgui.igTextColored(_vec4(color), b)


def text_disabled(str s):
    """显示禁用文本"""
    cdef bytes b = _to_bytes(s)
    cimgui.igTextDisabled(b)


def text_wrapped(str s):
    """显示自动换行文本"""
    cdef bytes b = _to_bytes(s)
    cimgui.igTextWrapped(b)


def bullet_text(str s):
    """显示带项目符号的文本"""
    cdef bytes b = _to_bytes(s)
    cimgui.igBulletText(b)


def label_text(str label, str s):
    """显示标签文本"""
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_text = _to_bytes(s)
    cimgui.igLabelText(b_label, b_text)


# =============================================================================
# Widgets: Main
# =============================================================================

def button(str label, width=0, height=0):
    """按钮"""
    cdef bytes b = _to_bytes(label)
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    return cimgui.igButton(b, size)


def small_button(str label):
    """小按钮"""
    cdef bytes b = _to_bytes(label)
    return cimgui.igSmallButton(b)


def invisible_button(str str_id, width, height, int flags=0):
    """不可见按钮"""
    cdef bytes b = _to_bytes(str_id)
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    return cimgui.igInvisibleButton(b, size, flags)


def checkbox(str label, bint state):
    """复选框
    
    Returns:
        tuple(changed, new_state)
    """
    cdef bytes b = _to_bytes(label)
    cdef cimgui.cppbool c_state = state
    cdef bint changed = cimgui.igCheckbox(b, &c_state)
    return (changed, c_state)


def radio_button(str label, bint active):
    """单选按钮"""
    cdef bytes b = _to_bytes(label)
    return cimgui.igRadioButton_Bool(b, active)


def progress_bar(float fraction, size=(-1, 0), str overlay=""):
    """进度条"""
    cdef bytes b = _to_bytes(overlay)
    cimgui.igProgressBar(fraction, _vec2(size), b if overlay else NULL)


def bullet():
    """项目符号"""
    cimgui.igBullet()


def image(tex_id, width, height, uv0=(0,0), uv1=(1,1), 
          tint_col=(1,1,1,1), border_col=(0,0,0,0)):
    """显示图像"""
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    cimgui.igImage(
        <cimgui.ImTextureID><size_t>tex_id,
        size, _vec2(uv0), _vec2(uv1),
        _vec4(tint_col), _vec4(border_col)
    )


def image_button(str str_id, tex_id, width, height, 
                 uv0=(0,0), uv1=(1,1),
                 bg_col=(0,0,0,0), tint_col=(1,1,1,1)):
    """图像按钮"""
    cdef bytes b = _to_bytes(str_id)
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    return cimgui.igImageButton(
        b, <cimgui.ImTextureID><size_t>tex_id,
        size, _vec2(uv0), _vec2(uv1),
        _vec4(bg_col), _vec4(tint_col)
    )


# =============================================================================
# Widgets: Input
# =============================================================================

# 全局缓冲区用于输入文本
cdef char _input_buffer[65536]

def input_text(str label, str value, int buffer_size=256, int flags=0):
    """文本输入
    
    Returns:
        tuple(changed, new_value)
    """
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_value = _to_bytes(value)
    cdef int actual_size = min(buffer_size, 65536)
    
    # 复制当前值到缓冲区
    memcpy(_input_buffer, <char*>b_value, min(len(b_value), actual_size - 1))
    _input_buffer[min(len(b_value), actual_size - 1)] = 0
    
    cdef bint changed = cimgui.igInputText(b_label, _input_buffer, actual_size, flags, NULL, NULL)
    
    return (changed, _input_buffer.decode('utf-8', errors='replace'))


def input_text_multiline(str label, str value, width=0, height=0, 
                          int buffer_size=4096, int flags=0):
    """多行文本输入
    
    Returns:
        tuple(changed, new_value)
    """
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_value = _to_bytes(value)
    cdef int actual_size = min(buffer_size, 65536)
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    
    memcpy(_input_buffer, <char*>b_value, min(len(b_value), actual_size - 1))
    _input_buffer[min(len(b_value), actual_size - 1)] = 0
    
    cdef bint changed = cimgui.igInputTextMultiline(
        b_label, _input_buffer, actual_size, size, flags, NULL, NULL
    )
    
    return (changed, _input_buffer.decode('utf-8', errors='replace'))


def input_int(str label, int value, int step=1, int step_fast=100, int flags=0):
    """整数输入
    
    Returns:
        tuple(changed, new_value)
    """
    cdef bytes b = _to_bytes(label)
    cdef int c_value = value
    cdef bint changed = cimgui.igInputInt(b, &c_value, step, step_fast, flags)
    return (changed, c_value)


def input_float(str label, float value, float step=0, float step_fast=0, 
                str format="%.3f", int flags=0):
    """浮点数输入
    
    Returns:
        tuple(changed, new_value)
    """
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_format = _to_bytes(format)
    cdef float c_value = value
    cdef bint changed = cimgui.igInputFloat(b_label, &c_value, step, step_fast, b_format, flags)
    return (changed, c_value)


# =============================================================================
# Widgets: Combo/Listbox
# =============================================================================

def begin_combo(str label, str preview_value, int flags=0):
    """开始下拉框"""
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_preview = _to_bytes(preview_value)
    return cimgui.igBeginCombo(b_label, b_preview, flags)


def end_combo():
    """结束下拉框"""
    cimgui.igEndCombo()


def selectable(str label, selected=False, int flags=0, width=0, height=0):
    """可选择项
    
    Returns:
        tuple(clicked, selected)
    """
    cdef bytes b = _to_bytes(label)
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    cdef cimgui.cppbool c_selected = selected
    cdef bint clicked = cimgui.igSelectable_BoolPtr(b, &c_selected, flags, size)
    return (clicked, c_selected)


# =============================================================================
# Widgets: Sliders & Drags
# =============================================================================

def slider_float(str label, float value, float v_min, float v_max, 
                 str format="%.3f", int flags=0):
    """浮点滑块"""
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_format = _to_bytes(format)
    cdef float c_value = value
    cdef bint changed = cimgui.igSliderFloat(b_label, &c_value, v_min, v_max, b_format, flags)
    return (changed, c_value)


def slider_int(str label, int value, int v_min, int v_max, 
               str format="%d", int flags=0):
    """整数滑块"""
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_format = _to_bytes(format)
    cdef int c_value = value
    cdef bint changed = cimgui.igSliderInt(b_label, &c_value, v_min, v_max, b_format, flags)
    return (changed, c_value)


def drag_float(str label, float value, float v_speed=1.0, 
               float v_min=0, float v_max=0,
               str format="%.3f", int flags=0):
    """浮点拖动"""
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_format = _to_bytes(format)
    cdef float c_value = value
    cdef bint changed = cimgui.igDragFloat(b_label, &c_value, v_speed, v_min, v_max, b_format, flags)
    return (changed, c_value)


def drag_int(str label, int value, float v_speed=1.0, 
             int v_min=0, int v_max=0,
             str format="%d", int flags=0):
    """整数拖动"""
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_format = _to_bytes(format)
    cdef int c_value = value
    cdef bint changed = cimgui.igDragInt(b_label, &c_value, v_speed, v_min, v_max, b_format, flags)
    return (changed, c_value)


# =============================================================================
# Widgets: Trees
# =============================================================================

def tree_node(str label):
    """树节点"""
    cdef bytes b = _to_bytes(label)
    return cimgui.igTreeNode_Str(b)


def tree_node_ex(str label, int flags=0):
    """带标志的树节点"""
    cdef bytes b = _to_bytes(label)
    return cimgui.igTreeNodeEx_Str(b, flags)


def tree_pop():
    """弹出树节点"""
    cimgui.igTreePop()


def collapsing_header(str label, visible=None, int flags=0):
    """折叠标题"""
    cdef bytes b = _to_bytes(label)
    cdef cimgui.cppbool c_visible
    
    if visible is None:
        return cimgui.igCollapsingHeader_TreeNodeFlags(b, flags)
    else:
        c_visible = visible
        result = cimgui.igCollapsingHeader_BoolPtr(b, &c_visible, flags)
        return (result, c_visible)


def set_next_item_open(bint is_open, int cond=0):
    """设置下一项打开状态"""
    cimgui.igSetNextItemOpen(is_open, cond)


# =============================================================================
# Widgets: Tabs
# =============================================================================

def begin_tab_bar(str str_id, int flags=0):
    """开始选项卡栏"""
    cdef bytes b = _to_bytes(str_id)
    return cimgui.igBeginTabBar(b, flags)


def end_tab_bar():
    """结束选项卡栏"""
    cimgui.igEndTabBar()


def begin_tab_item(str label, opened=None, int flags=0):
    """开始选项卡项
    
    Returns:
        如果 opened=None: bool
        否则: tuple(selected, opened)
    """
    cdef bytes b = _to_bytes(label)
    cdef cimgui.cppbool c_opened
    
    if opened is None:
        return (cimgui.igBeginTabItem(b, NULL, flags), True)
    else:
        c_opened = opened
        result = cimgui.igBeginTabItem(b, &c_opened, flags)
        return (result, c_opened)


def end_tab_item():
    """结束选项卡项"""
    cimgui.igEndTabItem()


# =============================================================================
# Widgets: Tables
# =============================================================================

def begin_table(str str_id, int column, int flags=0, 
                outer_size=(0, 0), float inner_width=0):
    """开始表格"""
    cdef bytes b = _to_bytes(str_id)
    return cimgui.igBeginTable(b, column, flags, _vec2(outer_size), inner_width)


def end_table():
    """结束表格"""
    cimgui.igEndTable()


def table_next_row(int row_flags=0, float min_row_height=0):
    """表格下一行"""
    cimgui.igTableNextRow(row_flags, min_row_height)


def table_next_column():
    """表格下一列"""
    return cimgui.igTableNextColumn()


def table_set_column_index(int column_n):
    """设置表格列索引"""
    return cimgui.igTableSetColumnIndex(column_n)


def table_setup_column(str label, int flags=0, float init_width_or_weight=0, 
                       int user_id=0):
    """设置表格列"""
    cdef bytes b = _to_bytes(label)
    cimgui.igTableSetupColumn(b, flags, init_width_or_weight, user_id)


def table_headers_row():
    """表格标题行"""
    cimgui.igTableHeadersRow()


# =============================================================================
# Popups, Modals
# =============================================================================

def begin_popup(str str_id, int flags=0):
    """开始弹出窗口"""
    cdef bytes b = _to_bytes(str_id)
    return cimgui.igBeginPopup(b, flags)


def begin_popup_modal(str name, opened=None, int flags=0):
    """开始模态弹出窗口"""
    cdef bytes b = _to_bytes(name)
    cdef cimgui.cppbool c_opened
    
    if opened is None:
        return cimgui.igBeginPopupModal(b, NULL, flags)
    else:
        c_opened = opened
        result = cimgui.igBeginPopupModal(b, &c_opened, flags)
        return (result, c_opened)


def end_popup():
    """结束弹出窗口"""
    cimgui.igEndPopup()


def open_popup(str str_id, int popup_flags=0):
    """打开弹出窗口"""
    cdef bytes b = _to_bytes(str_id)
    cimgui.igOpenPopup_Str(b, popup_flags)


def close_current_popup():
    """关闭当前弹出窗口"""
    cimgui.igCloseCurrentPopup()


def begin_popup_context_item(str str_id="", int popup_flags=1):
    """开始上下文菜单"""
    cdef bytes b = _to_bytes(str_id) if str_id else b""
    return cimgui.igBeginPopupContextItem(b if str_id else NULL, popup_flags)


def begin_popup_context_window(str str_id="", int popup_flags=1):
    """开始窗口上下文菜单"""
    cdef bytes b = _to_bytes(str_id) if str_id else b""
    return cimgui.igBeginPopupContextWindow(b if str_id else NULL, popup_flags)


def is_popup_open(str str_id, int flags=0):
    """检查弹出窗口是否打开"""
    cdef bytes b = _to_bytes(str_id)
    return cimgui.igIsPopupOpen_Str(b, flags)


# =============================================================================
# Menus
# =============================================================================

def begin_menu_bar():
    """开始菜单栏"""
    return cimgui.igBeginMenuBar()


def end_menu_bar():
    """结束菜单栏"""
    cimgui.igEndMenuBar()


def begin_main_menu_bar():
    """开始主菜单栏"""
    return cimgui.igBeginMainMenuBar()


def end_main_menu_bar():
    """结束主菜单栏"""
    cimgui.igEndMainMenuBar()


def begin_menu(str label, enabled=True):
    """开始菜单"""
    cdef bytes b = _to_bytes(label)
    return cimgui.igBeginMenu(b, enabled)


def end_menu():
    """结束菜单"""
    cimgui.igEndMenu()


def menu_item(str label, str shortcut="", selected=False, enabled=True):
    """菜单项
    
    Returns:
        tuple(clicked, selected)
    """
    cdef bytes b_label = _to_bytes(label)
    cdef bytes b_shortcut = _to_bytes(shortcut) if shortcut else b""
    cdef cimgui.cppbool c_selected = selected
    cdef bint clicked = cimgui.igMenuItem_BoolPtr(
        b_label, b_shortcut if shortcut else NULL, &c_selected, enabled
    )
    return (clicked, c_selected)


# =============================================================================
# Layout
# =============================================================================

def separator():
    """分隔线"""
    cimgui.igSeparator()


def same_line(float offset_from_start_x=0, float spacing=-1):
    """同行"""
    cimgui.igSameLine(offset_from_start_x, spacing)


def new_line():
    """新行"""
    cimgui.igNewLine()


def spacing():
    """间距"""
    cimgui.igSpacing()


def dummy(float width, float height):
    """占位"""
    cdef cimgui.ImVec2 size
    size.x = width
    size.y = height
    cimgui.igDummy(size)


def indent(float indent_w=0):
    """缩进"""
    cimgui.igIndent(indent_w)


def unindent(float indent_w=0):
    """取消缩进"""
    cimgui.igUnindent(indent_w)


def begin_group():
    """开始分组"""
    cimgui.igBeginGroup()


def end_group():
    """结束分组"""
    cimgui.igEndGroup()


def set_cursor_pos(pos):
    """设置光标位置"""
    cimgui.igSetCursorPos(_vec2(pos))


def set_cursor_pos_x(float local_x):
    """设置光标 X 位置"""
    cimgui.igSetCursorPosX(local_x)


def set_cursor_pos_y(float local_y):
    """设置光标 Y 位置"""
    cimgui.igSetCursorPosY(local_y)


def get_cursor_pos():
    """获取光标位置"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetCursorPos(&pos)
    return Vec2(pos.x, pos.y)


def get_cursor_pos_x():
    """获取光标 X 位置"""
    return cimgui.igGetCursorPosX()


def get_cursor_pos_y():
    """获取光标 Y 位置"""
    return cimgui.igGetCursorPosY()


def get_cursor_start_pos():
    """获取光标起始位置"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetCursorStartPos(&pos)
    return Vec2(pos.x, pos.y)


def get_cursor_screen_pos():
    """获取光标屏幕位置"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetCursorScreenPos(&pos)
    return Vec2(pos.x, pos.y)


def set_cursor_screen_pos(pos):
    """设置光标屏幕位置"""
    cimgui.igSetCursorScreenPos(_vec2(pos))


def align_text_to_frame_padding():
    """对齐文本到帧内边距"""
    cimgui.igAlignTextToFramePadding()


def get_text_line_height():
    """获取文本行高"""
    return cimgui.igGetTextLineHeight()


def get_text_line_height_with_spacing():
    """获取带间距的文本行高"""
    return cimgui.igGetTextLineHeightWithSpacing()


def get_frame_height():
    """获取帧高度"""
    return cimgui.igGetFrameHeight()


def get_frame_height_with_spacing():
    """获取带间距的帧高度"""
    return cimgui.igGetFrameHeightWithSpacing()


# =============================================================================
# Sizing
# =============================================================================

def push_item_width(float item_width):
    """压入项目宽度"""
    cimgui.igPushItemWidth(item_width)


def pop_item_width():
    """弹出项目宽度"""
    cimgui.igPopItemWidth()


def set_next_item_width(float item_width):
    """设置下一项宽度"""
    cimgui.igSetNextItemWidth(item_width)


def calc_item_width():
    """计算项目宽度"""
    return cimgui.igCalcItemWidth()


def calc_text_size(str text, hide_text_after_double_hash=False, float wrap_width=-1):
    """计算文本大小"""
    cdef bytes b = _to_bytes(text)
    cdef cimgui.ImVec2 size
    cimgui.igCalcTextSize(&size, b, NULL, hide_text_after_double_hash, wrap_width)
    return Vec2(size.x, size.y)


def get_content_region_available():
    """获取可用内容区域"""
    cdef cimgui.ImVec2 size
    cimgui.igGetContentRegionAvail(&size)
    return Vec2(size.x, size.y)


def get_content_region_max():
    """获取最大内容区域"""
    cdef cimgui.ImVec2 size
    cimgui.igGetContentRegionMax(&size)
    return Vec2(size.x, size.y)


def get_window_content_region_min():
    """获取窗口内容区域最小值"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetWindowContentRegionMin(&pos)
    return Vec2(pos.x, pos.y)


def get_window_content_region_max():
    """获取窗口内容区域最大值"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetWindowContentRegionMax(&pos)
    return Vec2(pos.x, pos.y)


# =============================================================================
# Window utilities
# =============================================================================

def set_next_window_pos(pos, int cond=0, pivot=(0, 0)):
    """设置下一窗口位置"""
    cimgui.igSetNextWindowPos(_vec2(pos), cond, _vec2(pivot))


def set_next_window_size(size, int cond=0):
    """设置下一窗口大小"""
    cimgui.igSetNextWindowSize(_vec2(size), cond)


def set_next_window_content_size(size):
    """设置下一窗口内容大小"""
    cimgui.igSetNextWindowContentSize(_vec2(size))


def set_next_window_collapsed(bint collapsed, int cond=0):
    """设置下一窗口折叠状态"""
    cimgui.igSetNextWindowCollapsed(collapsed, cond)


def set_next_window_focus():
    """设置下一窗口焦点"""
    cimgui.igSetNextWindowFocus()


def set_next_window_bg_alpha(float alpha):
    """设置下一窗口背景透明度"""
    cimgui.igSetNextWindowBgAlpha(alpha)


def get_window_pos():
    """获取窗口位置"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetWindowPos(&pos)
    return Vec2(pos.x, pos.y)


def get_window_size():
    """获取窗口大小"""
    cdef cimgui.ImVec2 size
    cimgui.igGetWindowSize(&size)
    return Vec2(size.x, size.y)


def get_window_width():
    """获取窗口宽度"""
    return cimgui.igGetWindowWidth()


def get_window_height():
    """获取窗口高度"""
    return cimgui.igGetWindowHeight()


def is_window_appearing():
    """窗口是否正在出现"""
    return cimgui.igIsWindowAppearing()


def is_window_collapsed():
    """窗口是否折叠"""
    return cimgui.igIsWindowCollapsed()


def is_window_focused(int flags=0):
    """窗口是否获得焦点"""
    return cimgui.igIsWindowFocused(flags)


def is_window_hovered(int flags=0):
    """窗口是否悬停"""
    return cimgui.igIsWindowHovered(flags)


def get_window_draw_list():
    """获取窗口绘制列表"""
    return _DrawList.wrap(cimgui.igGetWindowDrawList())


def get_foreground_draw_list():
    """获取前景绘制列表"""
    return _DrawList.wrap(cimgui.igGetForegroundDrawList_Nil())


def get_background_draw_list():
    """获取背景绘制列表"""
    return _DrawList.wrap(cimgui.igGetBackgroundDrawList_Nil())


# =============================================================================
# Item utilities
# =============================================================================

def is_item_hovered(int flags=0):
    """项目是否悬停"""
    return cimgui.igIsItemHovered(flags)


def is_item_active():
    """项目是否激活"""
    return cimgui.igIsItemActive()


def is_item_focused():
    """项目是否获得焦点"""
    return cimgui.igIsItemFocused()


def is_item_clicked(int mouse_button=0):
    """项目是否被点击"""
    return cimgui.igIsItemClicked(mouse_button)


def is_item_visible():
    """项目是否可见"""
    return cimgui.igIsItemVisible()


def is_item_edited():
    """项目是否被编辑"""
    return cimgui.igIsItemEdited()


def is_item_activated():
    """项目是否被激活"""
    return cimgui.igIsItemActivated()


def is_item_deactivated():
    """项目是否被取消激活"""
    return cimgui.igIsItemDeactivated()


def is_item_deactivated_after_edit():
    """项目是否在编辑后被取消激活"""
    return cimgui.igIsItemDeactivatedAfterEdit()


def is_any_item_hovered():
    """是否有任何项目悬停"""
    return cimgui.igIsAnyItemHovered()


def is_any_item_active():
    """是否有任何项目激活"""
    return cimgui.igIsAnyItemActive()


def is_any_item_focused():
    """是否有任何项目获得焦点"""
    return cimgui.igIsAnyItemFocused()


def get_item_rect_min():
    """获取项目矩形最小值"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetItemRectMin(&pos)
    return Vec2(pos.x, pos.y)


def get_item_rect_max():
    """获取项目矩形最大值"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetItemRectMax(&pos)
    return Vec2(pos.x, pos.y)


def get_item_rect_size():
    """获取项目矩形大小"""
    cdef cimgui.ImVec2 size
    cimgui.igGetItemRectSize(&size)
    return Vec2(size.x, size.y)


def set_item_allow_overlap():
    """允许项目重叠"""
    cimgui.igSetItemAllowOverlap()


# =============================================================================
# Tooltips
# =============================================================================

def set_tooltip(str text):
    """设置工具提示"""
    cdef bytes b = _to_bytes(text)
    cimgui.igSetTooltip(b)


def begin_tooltip():
    """开始工具提示"""
    cimgui.igBeginTooltip()


def end_tooltip():
    """结束工具提示"""
    cimgui.igEndTooltip()


# =============================================================================
# Style
# =============================================================================

def push_style_color(int idx, *args):
    """压入样式颜色
    
    用法:
        push_style_color(COLOR_TEXT, r, g, b, a)
        push_style_color(COLOR_TEXT, (r, g, b, a))
        push_style_color(COLOR_TEXT, 0xRRGGBBAA)
    """
    cdef cimgui.ImVec4 col
    cdef cimgui.ImU32 u32_col
    
    if len(args) == 1:
        if isinstance(args[0], (tuple, list)):
            col = _vec4(tuple(args[0]))
            cimgui.igPushStyleColor_Vec4(idx, col)
        else:
            u32_col = args[0]
            cimgui.igPushStyleColor_U32(idx, u32_col)
    elif len(args) == 4:
        col.x = args[0]
        col.y = args[1]
        col.z = args[2]
        col.w = args[3]
        cimgui.igPushStyleColor_Vec4(idx, col)
    else:
        raise ValueError("push_style_color expects (idx, r, g, b, a) or (idx, color_tuple) or (idx, u32)")


def pop_style_color(int count=1):
    """弹出样式颜色"""
    cimgui.igPopStyleColor(count)


def push_style_var_float(int idx, float val):
    """压入样式变量 (float)"""
    cimgui.igPushStyleVar_Float(idx, val)


def push_style_var_vec2(int idx, val):
    """压入样式变量 (vec2)"""
    cimgui.igPushStyleVar_Vec2(idx, _vec2(val))


def push_style_var(int idx, val):
    """压入样式变量 (自动检测类型)"""
    if isinstance(val, (tuple, list)):
        push_style_var_vec2(idx, val)
    else:
        push_style_var_float(idx, val)


def pop_style_var(int count=1):
    """弹出样式变量"""
    cimgui.igPopStyleVar(count)


def get_color_u32(idx_or_color, float alpha_mul=1.0):
    """获取颜色 U32"""
    if isinstance(idx_or_color, int):
        return cimgui.igGetColorU32_Col(idx_or_color, alpha_mul)
    elif isinstance(idx_or_color, (tuple, list)):
        return cimgui.igGetColorU32_Vec4(_vec4(tuple(idx_or_color)))
    else:
        return cimgui.igGetColorU32_U32(idx_or_color)


def get_color_u32_rgba(float r, float g, float b, float a):
    """获取 RGBA 颜色 U32"""
    cdef cimgui.ImVec4 col
    col.x = r
    col.y = g
    col.z = b
    col.w = a
    return cimgui.igGetColorU32_Vec4(col)


# =============================================================================
# Font
# =============================================================================

def push_font(font):
    """压入字体"""
    if font is None:
        cimgui.igPushFont(NULL)
    elif isinstance(font, _Font):
        cimgui.igPushFont((<_Font>font)._ptr)
    else:
        raise TypeError("Expected _Font or None")


def pop_font():
    """弹出字体"""
    cimgui.igPopFont()


def get_font():
    """获取当前字体"""
    return _Font.wrap(cimgui.igGetFont())


def get_font_size():
    """获取字体大小"""
    return cimgui.igGetFontSize()


# =============================================================================
# ID
# =============================================================================

def push_id(id_val):
    """压入 ID"""
    if isinstance(id_val, str):
        cimgui.igPushID_Str(_to_bytes(id_val))
    elif isinstance(id_val, int):
        cimgui.igPushID_Int(id_val)
    else:
        raise TypeError("Expected str or int")


def pop_id():
    """弹出 ID"""
    cimgui.igPopID()


def get_id(str str_id):
    """获取 ID"""
    cdef bytes b = _to_bytes(str_id)
    return cimgui.igGetID_Str(b)


# =============================================================================
# Scrolling
# =============================================================================

def get_scroll_x():
    """获取水平滚动"""
    return cimgui.igGetScrollX()


def get_scroll_y():
    """获取垂直滚动"""
    return cimgui.igGetScrollY()


def set_scroll_x(float scroll_x):
    """设置水平滚动"""
    cimgui.igSetScrollX_Float(scroll_x)


def set_scroll_y(float scroll_y):
    """设置垂直滚动"""
    cimgui.igSetScrollY_Float(scroll_y)


def get_scroll_max_x():
    """获取最大水平滚动"""
    return cimgui.igGetScrollMaxX()


def get_scroll_max_y():
    """获取最大垂直滚动"""
    return cimgui.igGetScrollMaxY()


def set_scroll_here_x(float center_x_ratio=0.5):
    """设置滚动到此处 (X)"""
    cimgui.igSetScrollHereX(center_x_ratio)


def set_scroll_here_y(float center_y_ratio=0.5):
    """设置滚动到此处 (Y)"""
    cimgui.igSetScrollHereY(center_y_ratio)


# =============================================================================
# Mouse
# =============================================================================

def is_mouse_down(int button):
    """鼠标按钮是否按下"""
    return cimgui.igIsMouseDown_Nil(button)


def is_mouse_clicked(int button, bint repeat=False):
    """鼠标按钮是否点击"""
    return cimgui.igIsMouseClicked_Bool(button, repeat)


def is_mouse_released(int button):
    """鼠标按钮是否释放"""
    return cimgui.igIsMouseReleased_Nil(button)


def is_mouse_double_clicked(int button):
    """鼠标按钮是否双击"""
    return cimgui.igIsMouseDoubleClicked(button)


def is_mouse_hovering_rect(r_min, r_max, bint clip=True):
    """鼠标是否悬停在矩形区域"""
    return cimgui.igIsMouseHoveringRect(_vec2(r_min), _vec2(r_max), clip)


def get_mouse_pos():
    """获取鼠标位置"""
    cdef cimgui.ImVec2 pos
    cimgui.igGetMousePos(&pos)
    return Vec2(pos.x, pos.y)


def is_mouse_dragging(int button, float lock_threshold=-1):
    """鼠标是否拖动"""
    return cimgui.igIsMouseDragging(button, lock_threshold)


def get_mouse_drag_delta(int button=0, float lock_threshold=-1):
    """获取鼠标拖动增量"""
    cdef cimgui.ImVec2 delta
    cimgui.igGetMouseDragDelta(&delta, button, lock_threshold)
    return Vec2(delta.x, delta.y)


def reset_mouse_drag_delta(int button=0):
    """重置鼠标拖动增量"""
    cimgui.igResetMouseDragDelta(button)


# =============================================================================
# Keyboard
# =============================================================================

def is_key_down(int key):
    """键是否按下"""
    return cimgui.igIsKeyDown_Nil(key)


def is_key_pressed(int key, bint repeat=True):
    """键是否被按下"""
    return cimgui.igIsKeyPressed_Bool(key, repeat)


def is_key_released(int key):
    """键是否释放"""
    return cimgui.igIsKeyReleased_Nil(key)


# =============================================================================
# Clipboard
# =============================================================================

def get_clipboard_text():
    """获取剪贴板文本"""
    cdef const char* text = cimgui.igGetClipboardText()
    if text == NULL:
        return ""
    return text.decode('utf-8', errors='replace')


def set_clipboard_text(str text):
    """设置剪贴板文本"""
    cdef bytes b = _to_bytes(text)
    cimgui.igSetClipboardText(b)


# =============================================================================
# 常量 - 与 pyimgui 兼容
# =============================================================================

# Color indices
COLOR_TEXT = cimgui.ImGuiCol_Text
COLOR_TEXT_DISABLED = cimgui.ImGuiCol_TextDisabled
COLOR_WINDOW_BACKGROUND = cimgui.ImGuiCol_WindowBg
COLOR_CHILD_BACKGROUND = cimgui.ImGuiCol_ChildBg
COLOR_POPUP_BACKGROUND = cimgui.ImGuiCol_PopupBg
COLOR_BORDER = cimgui.ImGuiCol_Border
COLOR_BORDER_SHADOW = cimgui.ImGuiCol_BorderShadow
COLOR_FRAME_BACKGROUND = cimgui.ImGuiCol_FrameBg
COLOR_FRAME_BACKGROUND_HOVERED = cimgui.ImGuiCol_FrameBgHovered
COLOR_FRAME_BACKGROUND_ACTIVE = cimgui.ImGuiCol_FrameBgActive
COLOR_TITLE_BACKGROUND = cimgui.ImGuiCol_TitleBg
COLOR_TITLE_BACKGROUND_ACTIVE = cimgui.ImGuiCol_TitleBgActive
COLOR_TITLE_BACKGROUND_COLLAPSED = cimgui.ImGuiCol_TitleBgCollapsed
COLOR_MENUBAR_BACKGROUND = cimgui.ImGuiCol_MenuBarBg
COLOR_SCROLLBAR_BACKGROUND = cimgui.ImGuiCol_ScrollbarBg
COLOR_SCROLLBAR_GRAB = cimgui.ImGuiCol_ScrollbarGrab
COLOR_SCROLLBAR_GRAB_HOVERED = cimgui.ImGuiCol_ScrollbarGrabHovered
COLOR_SCROLLBAR_GRAB_ACTIVE = cimgui.ImGuiCol_ScrollbarGrabActive
COLOR_CHECK_MARK = cimgui.ImGuiCol_CheckMark
COLOR_SLIDER_GRAB = cimgui.ImGuiCol_SliderGrab
COLOR_SLIDER_GRAB_ACTIVE = cimgui.ImGuiCol_SliderGrabActive
COLOR_BUTTON = cimgui.ImGuiCol_Button
COLOR_BUTTON_HOVERED = cimgui.ImGuiCol_ButtonHovered
COLOR_BUTTON_ACTIVE = cimgui.ImGuiCol_ButtonActive
COLOR_HEADER = cimgui.ImGuiCol_Header
COLOR_HEADER_HOVERED = cimgui.ImGuiCol_HeaderHovered
COLOR_HEADER_ACTIVE = cimgui.ImGuiCol_HeaderActive
COLOR_SEPARATOR = cimgui.ImGuiCol_Separator
COLOR_SEPARATOR_HOVERED = cimgui.ImGuiCol_SeparatorHovered
COLOR_SEPARATOR_ACTIVE = cimgui.ImGuiCol_SeparatorActive
COLOR_RESIZE_GRIP = cimgui.ImGuiCol_ResizeGrip
COLOR_RESIZE_GRIP_HOVERED = cimgui.ImGuiCol_ResizeGripHovered
COLOR_RESIZE_GRIP_ACTIVE = cimgui.ImGuiCol_ResizeGripActive
COLOR_TAB = cimgui.ImGuiCol_Tab
COLOR_TAB_HOVERED = cimgui.ImGuiCol_TabHovered
COLOR_TAB_ACTIVE = cimgui.ImGuiCol_TabActive
COLOR_TAB_UNFOCUSED = cimgui.ImGuiCol_TabUnfocused
COLOR_TAB_UNFOCUSED_ACTIVE = cimgui.ImGuiCol_TabUnfocusedActive
COLOR_PLOT_LINES = cimgui.ImGuiCol_PlotLines
COLOR_PLOT_LINES_HOVERED = cimgui.ImGuiCol_PlotLinesHovered
COLOR_PLOT_HISTOGRAM = cimgui.ImGuiCol_PlotHistogram
COLOR_PLOT_HISTOGRAM_HOVERED = cimgui.ImGuiCol_PlotHistogramHovered
COLOR_TABLE_HEADER_BACKGROUND = cimgui.ImGuiCol_TableHeaderBg
COLOR_TABLE_BORDER_STRONG = cimgui.ImGuiCol_TableBorderStrong
COLOR_TABLE_BORDER_LIGHT = cimgui.ImGuiCol_TableBorderLight
COLOR_TABLE_ROW_BACKGROUND = cimgui.ImGuiCol_TableRowBg
COLOR_TABLE_ROW_BACKGROUND_ALT = cimgui.ImGuiCol_TableRowBgAlt
COLOR_TEXT_SELECTED_BACKGROUND = cimgui.ImGuiCol_TextSelectedBg
COLOR_DRAG_DROP_TARGET = cimgui.ImGuiCol_DragDropTarget
COLOR_NAV_HIGHLIGHT = cimgui.ImGuiCol_NavHighlight
COLOR_NAV_WINDOWING_HIGHLIGHT = cimgui.ImGuiCol_NavWindowingHighlight
COLOR_NAV_WINDOWING_DIM_BACKGROUND = cimgui.ImGuiCol_NavWindowingDimBg
COLOR_MODAL_WINDOW_DIM_BACKGROUND = cimgui.ImGuiCol_ModalWindowDimBg
COLOR_COUNT = cimgui.ImGuiCol_COUNT

# Style variables
STYLE_ALPHA = cimgui.ImGuiStyleVar_Alpha
STYLE_DISABLED_ALPHA = cimgui.ImGuiStyleVar_DisabledAlpha
STYLE_WINDOW_PADDING = cimgui.ImGuiStyleVar_WindowPadding
STYLE_WINDOW_ROUNDING = cimgui.ImGuiStyleVar_WindowRounding
STYLE_WINDOW_BORDER_SIZE = cimgui.ImGuiStyleVar_WindowBorderSize
STYLE_WINDOW_MIN_SIZE = cimgui.ImGuiStyleVar_WindowMinSize
STYLE_WINDOW_TITLE_ALIGN = cimgui.ImGuiStyleVar_WindowTitleAlign
STYLE_CHILD_ROUNDING = cimgui.ImGuiStyleVar_ChildRounding
STYLE_CHILD_BORDER_SIZE = cimgui.ImGuiStyleVar_ChildBorderSize
STYLE_POPUP_ROUNDING = cimgui.ImGuiStyleVar_PopupRounding
STYLE_POPUP_BORDER_SIZE = cimgui.ImGuiStyleVar_PopupBorderSize
STYLE_FRAME_PADDING = cimgui.ImGuiStyleVar_FramePadding
STYLE_FRAME_ROUNDING = cimgui.ImGuiStyleVar_FrameRounding
STYLE_FRAME_BORDER_SIZE = cimgui.ImGuiStyleVar_FrameBorderSize
STYLE_ITEM_SPACING = cimgui.ImGuiStyleVar_ItemSpacing
STYLE_ITEM_INNER_SPACING = cimgui.ImGuiStyleVar_ItemInnerSpacing
STYLE_INDENT_SPACING = cimgui.ImGuiStyleVar_IndentSpacing
STYLE_CELL_PADDING = cimgui.ImGuiStyleVar_CellPadding
STYLE_SCROLLBAR_SIZE = cimgui.ImGuiStyleVar_ScrollbarSize
STYLE_SCROLLBAR_ROUNDING = cimgui.ImGuiStyleVar_ScrollbarRounding
STYLE_GRAB_MIN_SIZE = cimgui.ImGuiStyleVar_GrabMinSize
STYLE_GRAB_ROUNDING = cimgui.ImGuiStyleVar_GrabRounding
STYLE_TAB_ROUNDING = cimgui.ImGuiStyleVar_TabRounding
STYLE_BUTTON_TEXT_ALIGN = cimgui.ImGuiStyleVar_ButtonTextAlign
STYLE_SELECTABLE_TEXT_ALIGN = cimgui.ImGuiStyleVar_SelectableTextAlign

# Window flags
WINDOW_NONE = cimgui.ImGuiWindowFlags_None
WINDOW_NO_TITLE_BAR = cimgui.ImGuiWindowFlags_NoTitleBar
WINDOW_NO_RESIZE = cimgui.ImGuiWindowFlags_NoResize
WINDOW_NO_MOVE = cimgui.ImGuiWindowFlags_NoMove
WINDOW_NO_SCROLLBAR = cimgui.ImGuiWindowFlags_NoScrollbar
WINDOW_NO_SCROLL_WITH_MOUSE = cimgui.ImGuiWindowFlags_NoScrollWithMouse
WINDOW_NO_COLLAPSE = cimgui.ImGuiWindowFlags_NoCollapse
WINDOW_ALWAYS_AUTO_RESIZE = cimgui.ImGuiWindowFlags_AlwaysAutoResize
WINDOW_NO_BACKGROUND = cimgui.ImGuiWindowFlags_NoBackground
WINDOW_NO_SAVED_SETTINGS = cimgui.ImGuiWindowFlags_NoSavedSettings
WINDOW_NO_MOUSE_INPUTS = cimgui.ImGuiWindowFlags_NoMouseInputs
WINDOW_MENU_BAR = cimgui.ImGuiWindowFlags_MenuBar
WINDOW_HORIZONTAL_SCROLLING_BAR = cimgui.ImGuiWindowFlags_HorizontalScrollbar
WINDOW_NO_FOCUS_ON_APPEARING = cimgui.ImGuiWindowFlags_NoFocusOnAppearing
WINDOW_NO_BRING_TO_FRONT_ON_FOCUS = cimgui.ImGuiWindowFlags_NoBringToFrontOnFocus
WINDOW_ALWAYS_VERTICAL_SCROLLBAR = cimgui.ImGuiWindowFlags_AlwaysVerticalScrollbar
WINDOW_ALWAYS_HORIZONTAL_SCROLLBAR = cimgui.ImGuiWindowFlags_AlwaysHorizontalScrollbar
WINDOW_ALWAYS_USE_WINDOW_PADDING = cimgui.ImGuiWindowFlags_AlwaysUseWindowPadding
WINDOW_NO_NAV_INPUTS = cimgui.ImGuiWindowFlags_NoNavInputs
WINDOW_NO_NAV_FOCUS = cimgui.ImGuiWindowFlags_NoNavFocus
WINDOW_UNSAVED_DOCUMENT = cimgui.ImGuiWindowFlags_UnsavedDocument
WINDOW_NO_NAV = cimgui.ImGuiWindowFlags_NoNav
WINDOW_NO_DECORATION = cimgui.ImGuiWindowFlags_NoDecoration
WINDOW_NO_INPUTS = cimgui.ImGuiWindowFlags_NoInputs

# Hovered flags
HOVERED_NONE = cimgui.ImGuiHoveredFlags_None
HOVERED_CHILD_WINDOWS = cimgui.ImGuiHoveredFlags_ChildWindows
HOVERED_ROOT_WINDOW = cimgui.ImGuiHoveredFlags_RootWindow
HOVERED_ANY_WINDOW = cimgui.ImGuiHoveredFlags_AnyWindow
HOVERED_ALLOW_WHEN_BLOCKED_BY_POPUP = cimgui.ImGuiHoveredFlags_AllowWhenBlockedByPopup
HOVERED_ALLOW_WHEN_BLOCKED_BY_ACTIVE_ITEM = cimgui.ImGuiHoveredFlags_AllowWhenBlockedByActiveItem
HOVERED_ALLOW_WHEN_OVERLAPPED = cimgui.ImGuiHoveredFlags_AllowWhenOverlapped
HOVERED_ALLOW_WHEN_DISABLED = cimgui.ImGuiHoveredFlags_AllowWhenDisabled
HOVERED_RECT_ONLY = cimgui.ImGuiHoveredFlags_RectOnly
