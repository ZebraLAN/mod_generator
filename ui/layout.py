# -*- coding: utf-8 -*-
"""ImGui 布局系统 - 支持自动布局

==============================================================================
容器类型与间距概念 - 理解 ImGui 布局的关键
==============================================================================

ImGui 与 CSS 的核心区别:
  - CSS: 每个元素可以有 margin/padding，由 Box Model 决定
  - ImGui: 间距来源于 **样式变量** (WindowPadding, FramePadding, ItemSpacing)

三种容器类型:
  1. Window/Child (begin_child) - 有自己的 WindowPadding，有独立滚动/裁剪
  2. Group (begin_group)        - 仅逻辑分组，无 padding，用于测量/对齐
  3. Table (begin_table)        - 有 CellPadding，用于多列布局

布局 helpers 使用的容器:
  - ly.card(), ly.scroll_y(), ly.fixed_size() → Child (有 padding)
  - ly.hstack(), ly.vstack(), ly.auto_hcenter() → Group (无 padding)
  - ly.grid() → Table (有 cell padding)

样式作用时机:
  - tw.p_* 设置 WindowPadding + FramePadding
  - tw.bg_* 设置 Child 背景 (ChildBg) 或 Frame 背景 (FrameBg)
  - 样式必须在容器 **创建之前** 设置！

正确模式:
    with tw.bg_abyss_800 | tw.p_4:       # 先设置样式
        with ly.card("my_card"):          # 再创建容器
            imgui.text("内容")            # 内容有 16px padding

错误模式:
    with ly.card("my_card"):              # 容器已创建
        with tw.bg_abyss_800 | tw.p_4:    # 太晚了！样式无法影响容器
            imgui.text("内容")

==============================================================================

自动布局 API:
    from ui import layout as ly
    from ui import tw

    # 自动水平居中 - 不需要手算宽度！
    with ly.auto_hcenter("welcome_buttons"):
        with tw.btn_primary:
            if ly.btn("新建", 40, 9):
                ...
        ly.same_line(4)
        with tw.btn_secondary:
            if ly.btn("打开", 40, 9):
                ...

    # 自动垂直居中
    with ly.auto_vcenter("welcome_content"):
        ly.text_center("Title")
        ly.gap_y(4)
        ly.text_center("Subtitle")

    # 完全自动居中
    with ly.auto_center("welcome_page"):
        # ... 内容 ...

手动布局 API (需要知道尺寸):
    ly.hcenter_start(336)  # 手动指定宽度
    ly.vcenter_start(200)  # 手动指定高度
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from contextlib import contextmanager
import inspect
import os

import imgui

from ui.state import dpi_scale
from ui.styles import StyleContext

if TYPE_CHECKING:
    pass


# =============================================================================
# 自动布局缓存
# =============================================================================

import inspect

# 缓存每个布局 ID 的尺寸 (width, height)
_size_cache: dict[str, tuple[float, float]] = {}

# 尺寸变化阈值 - 小于此值不更新缓存，避免浮点抖动
_SIZE_THRESHOLD = 0.5


def _get_cached_size(layout_id: str) -> tuple[float, float] | None:
    """获取缓存的尺寸"""
    return _size_cache.get(layout_id)


def _set_cached_size(layout_id: str, width: float, height: float) -> None:
    """设置缓存的尺寸（带抖动过滤）

    只有当尺寸变化超过阈值时才更新，避免浮点精度导致的抖动
    """
    cached = _size_cache.get(layout_id)

    # 向下取整以确保稳定（不会在 225/226 之间交替）
    new_w = int(width)
    new_h = int(height)

    if cached:
        # 检查变化是否超过阈值
        dw = abs(cached[0] - new_w)
        dh = abs(cached[1] - new_h)
        if dw < _SIZE_THRESHOLD and dh < _SIZE_THRESHOLD:
            return  # 变化太小，不更新

    _size_cache[layout_id] = (new_w, new_h)


def clear_layout_cache() -> None:
    """清除布局缓存 (窗口大小变化时可能需要)"""
    _size_cache.clear()


def _auto_id() -> str:
    """自动生成唯一 ID (类似 gensym)

    使用调用栈的文件路径:行号:字节码偏移:函数名组合作为唯一标识
    这样即使同一行有多个调用也能区分
    """
    # 跳过 _auto_id 和调用它的函数 (auto_hcenter 等)
    frame = inspect.currentframe()
    try:
        # 往上跳 2 层: _auto_id -> auto_xxx -> 用户代码
        caller = frame.f_back.f_back

        # 组合多个标识以确保唯一性
        filename = caller.f_code.co_filename
        lineno = caller.f_lineno
        # 字节码偏移量 - 比列号更可靠，因为 Python 不直接提供列号
        lasti = caller.f_lasti
        # 函数名或代码块名称
        func_name = caller.f_code.co_name

        # 使用相对路径避免 ID 过长（只保留文件名）
        import os
        short_name = os.path.basename(filename)

        return f"{short_name}:{lineno}:{lasti}:{func_name}"
    finally:
        del frame


# =============================================================================
# 自动居中 Context Managers
# =============================================================================

@contextmanager
def auto_hcenter(layout_id: str | None = None):
    """自动水平居中 - 使用上一帧的尺寸，无需手算宽度

    原理:
        1. 第一帧: 正常渲染，测量 group 宽度并缓存
        2. 后续帧: 使用缓存的宽度计算居中位置

    Args:
        layout_id: 可选。不提供则自动生成 (基于调用位置)

    用法:
        with ly.auto_hcenter():  # ID 自动生成
            imgui.button("A")
            imgui.same_line()
            imgui.button("B")
    """
    lid = layout_id or _auto_id()
    cached = _get_cached_size(lid)

    window_width = imgui.get_window_width()
    if cached:
        # 有缓存，使用缓存的宽度居中
        # 取整避免亚像素抖动
        x = int((window_width - cached[0]) / 2)
        imgui.set_cursor_pos_x(x)

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        # 更新缓存
        size = imgui.get_item_rect_size()
        _set_cached_size(lid, size.x, size.y)


@contextmanager
def auto_vcenter(layout_id: str | None = None):
    """自动垂直居中 - 使用上一帧的尺寸，无需手算高度

    Args:
        layout_id: 可选。不提供则自动生成
    """
    lid = layout_id or _auto_id()
    cached = _get_cached_size(lid)

    if cached:
        window_height = imgui.get_window_height()
        # 取整避免亚像素抖动
        y = int((window_height - cached[1]) / 2)
        imgui.set_cursor_pos_y(y)

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        size = imgui.get_item_rect_size()
        _set_cached_size(lid, size.x, size.y)


@contextmanager
def auto_center(layout_id: str | None = None):
    """自动完全居中 - 水平和垂直都自动

    Args:
        layout_id: 可选。不提供则自动生成
    """
    lid = layout_id or _auto_id()
    cached = _get_cached_size(lid)

    window_width = imgui.get_window_width()
    window_height = imgui.get_window_height()
    if cached:
        # 取整避免亚像素抖动
        x = int((window_width - cached[0]) / 2)
        y = int((window_height - cached[1]) / 2)
        imgui.set_cursor_pos((x, y))

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        size = imgui.get_item_rect_size()
        _set_cached_size(lid, size.x, size.y)


# =============================================================================
# 尺寸转换
# =============================================================================

def sz(n: float) -> float:
    """Tailwind 单位转 DPI 缩放像素

    sz(40) = 160px at 1x DPI
    sz(9)  = 36px at 1x DPI

    用于需要精确像素值的场景:
        imgui.button("OK", width=sz(40), height=sz(9))
    """
    return n * 4 * dpi_scale()


def sz_raw(n: float) -> float:
    """Tailwind 单位转像素 (无 DPI 缩放)

    用于需要原始像素的场景
    """
    return n * 4


# =============================================================================
# Tailwind 风格间距函数
# =============================================================================

def gap_y(n: float) -> None:
    """添加垂直间距

    Args:
        n: Tailwind 单位 (4 = 16px, 6 = 24px)
    """
    px = n * 4 * dpi_scale()
    imgui.dummy(0, px)


def gap_x(n: float) -> None:
    """添加水平间距 (配合 same_line)

    Args:
        n: Tailwind 单位 (4 = 16px)
    """
    px = n * 4 * dpi_scale()
    imgui.same_line(spacing=px)


def gap_y_px(px: float) -> None:
    """添加垂直间距 (精确像素)"""
    imgui.dummy(0, px * dpi_scale())


def gap_x_px(px: float) -> None:
    """添加水平间距 (精确像素)"""
    imgui.same_line(spacing=px * dpi_scale())


def same_line(gap: float = 0) -> None:
    """移动到同一行下一位置

    Args:
        gap: Tailwind 单位间距 (4 = 16px)
    """
    imgui.same_line(spacing=gap * 4 * dpi_scale())


# =============================================================================
# 按钮 Helper
# =============================================================================

def btn(label: str, w: float = 0, h: float = 0) -> bool:
    """[DEPRECATED] 绘制按钮 - 请改用 (tw.btn_* | tw.btn_md)(imgui.button)(label)

    推荐新写法:
        if (tw.btn_primary | tw.btn_md)(imgui.button)("确定"):
            do_something()

    旧写法 (仍可用但不推荐):
        with tw.btn_primary:
            if ly.btn("确定", 40, 9):
                do_something()

    Args:
        label: 按钮文字
        w: 宽度 (Tailwind 单位, 40 = 160px)
        h: 高度 (Tailwind 单位, 9 = 36px)

    Returns:
        bool: 是否点击
    """
    width = w * 4 * dpi_scale() if w > 0 else 0
    height = h * 4 * dpi_scale() if h > 0 else 0
    return imgui.button(label, width=width, height=height)


# =============================================================================
# 居中文本
# =============================================================================

def text_center(content: str, style: StyleContext | None = None, cache_id: str | None = None) -> None:
    """水平居中绘制文本

    Args:
        content: 文本内容
        style: 样式上下文
        cache_id: 缓存 ID，用于多帧尺寸稳定。如果不提供则使用 content 作为 ID
    """
    window_width = imgui.get_window_width()
    cache_key = cache_id or f"text_center:{content}"

    # 获取缓存的真实宽度
    cached = _get_cached_size(cache_key)
    if cached:
        # 使用缓存的实际宽度居中
        imgui.set_cursor_pos_x(int((window_width - cached[0]) / 2))
    else:
        # 首帧：使用预计算宽度（可能不准确）
        text_size = imgui.calc_text_size(content)
        imgui.set_cursor_pos_x(int((window_width - text_size.x) / 2))

    # 渲染文本
    if style:
        with style:
            imgui.text(content)
    else:
        imgui.text(content)

    # 测量实际渲染宽度并缓存
    actual_size = imgui.get_item_rect_size()
    _set_cached_size(cache_key, int(actual_size.x), int(actual_size.y))


def text_right(content: str, style: StyleContext | None = None, margin: float = 0, cache_id: str | None = None) -> None:
    """右对齐绘制文本

    Args:
        content: 文本内容
        style: 样式上下文
        margin: 右边距（Tailwind 单位）
        cache_id: 缓存 ID，用于多帧尺寸稳定。如果不提供则使用 content 作为 ID
    """
    window_width = imgui.get_window_width()
    margin_px = margin * 4 * dpi_scale()
    cache_key = cache_id or f"text_right:{content}"

    # 获取缓存的真实宽度
    cached = _get_cached_size(cache_key)
    if cached:
        # 使用缓存的实际宽度右对齐
        imgui.set_cursor_pos_x(int(window_width - cached[0] - margin_px))
    else:
        # 首帧：使用预计算宽度（可能不准确）
        text_size = imgui.calc_text_size(content)
        imgui.set_cursor_pos_x(int(window_width - text_size.x - margin_px))

    # 渲染文本
    if style:
        with style:
            imgui.text(content)
    else:
        imgui.text(content)

    # 测量实际渲染宽度并缓存
    actual_size = imgui.get_item_rect_size()
    _set_cached_size(cache_key, int(actual_size.x), int(actual_size.y))


# =============================================================================
# 图标 + 文字标签
# =============================================================================

def icon_label(
    icon_char: str,
    text: str,
    gap: float = 2,
    icon_style: StyleContext | None = None,
    text_style: StyleContext | None = None,
) -> None:
    """渲染图标 + 文字标签

    Args:
        icon_char: FA 图标字符
        text: 标签文字
        gap: 图标与文字间距 (Tailwind 单位)
        icon_style: 图标样式
        text_style: 文字样式

    用法:
        ly.icon_label(FA_GEM, "项目名称", icon_style=tw.text_crystal_400)
    """
    if icon_style:
        with icon_style:
            imgui.text(icon_char)
    else:
        imgui.text(icon_char)
    same_line(gap)
    if text_style:
        with text_style:
            imgui.text(text)
    else:
        imgui.text(text)


# =============================================================================
# 居中容器
# =============================================================================

@contextmanager
def hcenter(width: float):
    """水平居中容器

    Args:
        width: 内容宽度 (像素)
    """
    window_width = imgui.get_window_width()
    imgui.set_cursor_pos_x((window_width - width * dpi_scale()) / 2)
    yield


@contextmanager
def vcenter(height: float):
    """垂直居中容器

    Args:
        height: 内容高度 (像素)
    """
    window_height = imgui.get_window_height()
    imgui.set_cursor_pos_y((window_height - height * dpi_scale()) / 2)
    yield


@contextmanager
def center(width: float, height: float):
    """完全居中容器"""
    window_width = imgui.get_window_width()
    window_height = imgui.get_window_height()
    imgui.set_cursor_pos((
        (window_width - width * dpi_scale()) / 2,
        (window_height - height * dpi_scale()) / 2
    ))
    yield


def vcenter_start(content_height: float) -> None:
    """设置垂直居中起点 (非 context manager)"""
    window_height = imgui.get_window_height()
    imgui.set_cursor_pos_y((window_height - content_height * dpi_scale()) / 2)


def hcenter_start(content_width: float) -> None:
    """设置水平居中起点 (非 context manager)"""
    window_width = imgui.get_window_width()
    imgui.set_cursor_pos_x((window_width - content_width * dpi_scale()) / 2)


# =============================================================================
# 水平行布局
# =============================================================================

@contextmanager
def row(gap: float = 0):
    """水平行容器 - 子元素水平排列

    Args:
        gap: 子元素间距 (Tailwind 单位, 4 = 16px)

    用法:
        with ly.row(gap=4):
            imgui.button("A")
            imgui.button("B")
    """
    gap_px = gap * 4 * dpi_scale()
    style = imgui.get_style()
    original_spacing = style.item_spacing

    imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (gap_px, original_spacing.y))
    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        imgui.pop_style_var()


@contextmanager
def col(gap: float = 0):
    """垂直列容器 - 子元素垂直排列

    Args:
        gap: 子元素间距 (Tailwind 单位)
    """
    gap_px = gap * 4 * dpi_scale()
    style = imgui.get_style()
    original_spacing = style.item_spacing

    imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (original_spacing.x, gap_px))
    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        imgui.pop_style_var()


# =============================================================================
# 便捷函数
# =============================================================================

def next_line() -> None:
    """强制换行"""
    imgui.new_line()


def divider(char: str = "━", count: int = 32, style: StyleContext | None = None) -> None:
    """居中分隔线"""
    text_center(char * count, style)


def hr(color: tuple[float, float, float, float] | None = None) -> None:
    """水平分隔线

    Args:
        color: 可选的 RGBA 颜色。None 则使用默认颜色
    """
    if color:
        imgui.push_style_color(imgui.COLOR_SEPARATOR, *color)
        imgui.separator()
        imgui.pop_style_color()
    else:
        imgui.separator()


# =============================================================================
# 可交互容器 (Interactive Containers)
# =============================================================================

class CardState:
    """Card 交互状态"""
    __slots__ = ('clicked', 'hovered')

    def __init__(self):
        self.clicked = False
        self.hovered = False


@contextmanager
def card(
    label: str,
    height: float = 0,
    *,
    flags: int = 0,
):
    """可交互卡片容器 - 纯布局组件，样式通过外部 tw tokens 控制

    ⚠️ 容器类型: Child Window (begin_child)
       - 有自己的 WindowPadding (由外部 tw.p_* 控制)
       - 有自己的背景色 (由外部 tw.bg_* 控制)
       - 可以滚动和裁剪内容

    样式必须在 card 之前设置，因为 begin_child 在进入时就读取样式。

    Args:
        label: 唯一标识符
        height: 高度 (Tailwind 单位)。0 表示自适应内容
        flags: 额外的 child window flags

    Yields:
        CardState 对象，包含 clicked 和 hovered 属性

    用法:
        # ✅ 正确：样式在 card 外部
        with tw.bg_abyss_800 | tw.child_rounded_md | tw.p_2:
            with ly.card("my_card", height=12) as state:
                imgui.text("Card content")  # 有 8px 内边距

        # ❌ 错误：样式在 card 内部 (不起作用)
        with ly.card("my_card"):
            with tw.bg_abyss_800:  # 太晚了！
                imgui.text("Content")
        with tw.bg_abyss_800 | tw.child_rounded_md | tw.p_2:
            with ly.card("my_card", height=12) as state:
                imgui.text("Card content")

        if state.clicked:
            do_something()

        # 动态边框 (选中状态)
        border_style = tw.child_border_crystal_500 if is_active else tw.noop
        with tw.bg_abyss_800 | tw.child_rounded_md | border_style:
            with ly.card("project_header", height=12) as state:
                ...
    """
    h = sz(height) if height > 0 else 0
    avail_width = imgui.get_content_region_available().x

    state = CardState()

    # Child window flags
    child_flags = imgui.WINDOW_NO_SCROLLBAR | flags
    if height == 0:
        child_flags |= imgui.WINDOW_ALWAYS_AUTO_RESIZE

    imgui.begin_child(label, width=avail_width, height=h, border=False, flags=child_flags)
    try:
        yield state
    finally:
        imgui.end_child()

        # 检测交互状态
        state.hovered = imgui.is_item_hovered()
        state.clicked = imgui.is_item_clicked()


# Panel 高度缓存 (用于背景绘制)
_panel_height_cache: dict[str, float] = {}


def clear_panel_cache() -> None:
    """清除面板高度缓存"""
    _panel_height_cache.clear()


@contextmanager
def panel(
    label: str,
    bg_color: tuple[float, float, float, float],
    padding: float = 4,
    rounding: float = 2,
):
    """带样式的自动高度面板 - 背景 + padding + 圆角

    ⚠️ 容器类型: Group (begin_group) - 真正的自动高度

    与 card() 的区别:
       - card() 使用 begin_child()，height=0 时会填满剩余空间
       - panel() 使用 begin_group()，高度由内容决定

    实现原理:
        1. 使用高度缓存 (第一帧可能略有闪烁)
        2. 先绘制背景矩形
        3. 用 Group 包裹内容
        4. 更新高度缓存供下一帧使用

    Args:
        label: 唯一标识符 (用于缓存高度)
        bg_color: 背景色 RGBA tuple
        padding: 内边距 (Tailwind 单位，默认 4 = 16px)
        rounding: 圆角 (Tailwind 单位，默认 2 = 8px)

    用法:
        from ui.tw import ABYSS_800

        with ly.panel("my_panel", ABYSS_800, padding=4, rounding=2):
            imgui.text("自动高度面板")
            imgui.text("背景会正确绘制在内容后面")
    """
    pad = sz(padding)
    round_px = sz(rounding)
    avail_width = imgui.get_content_region_available().x

    # 记录面板起始位置 (屏幕坐标)
    panel_start = imgui.get_cursor_screen_pos()

    # 获取缓存的高度 (首次渲染默认为一个合理值)
    cached_height = _panel_height_cache.get(label, sz(20))

    # 计算面板尺寸
    panel_width = avail_width
    panel_height = cached_height + pad * 2

    # 先绘制背景
    draw_list = imgui.get_window_draw_list()
    r, g, b, a = bg_color
    color_u32 = imgui.get_color_u32_rgba(r, g, b, a)

    bg_x1 = panel_start.x
    bg_y1 = panel_start.y
    bg_x2 = panel_start.x + panel_width
    bg_y2 = panel_start.y + panel_height

    draw_list.add_rect_filled(bg_x1, bg_y1, bg_x2, bg_y2, color_u32, round_px)

    # 添加 padding 偏移
    cursor = imgui.get_cursor_pos()
    imgui.set_cursor_pos((cursor.x + pad, cursor.y + pad))

    # 限制内容宽度 (总宽度 - 2*padding)
    content_width = avail_width - pad * 2

    imgui.begin_group()
    try:
        # 将 content_width 通过 push_item_width 传递给内部
        imgui.push_item_width(content_width)
        yield content_width  # 返回可用内容宽度
    finally:
        imgui.pop_item_width()
        imgui.end_group()

        # 获取实际内容高度并更新缓存
        group_size = imgui.get_item_rect_size()
        actual_height = group_size.y
        _panel_height_cache[label] = actual_height

        # 推进 cursor 到面板底部 + padding
        imgui.dummy(0, pad)


# =============================================================================
# 复合组件 (Widgets)
# ⚠️ 注意: 以下组件是设计体系建立之前实现的，未来可能需要重新设计
# TODO: 考虑迁移到 widgets.py 并使用 tw/styles 系统重构
# =============================================================================

def window_size() -> tuple[float, float]:
    """获取当前窗口尺寸"""
    return imgui.get_window_width(), imgui.get_window_height()


def content_region() -> tuple[float, float]:
    """获取可用内容区域尺寸"""
    avail = imgui.get_content_region_available()
    return avail.x, avail.y


def scaled(px: float) -> float:
    """返回 DPI 缩放后的像素值"""
    return px * dpi_scale()


# =============================================================================
# [DEPRECATED] 便捷 spacing 函数 - 请使用 gap_y(n) 代替
# =============================================================================
def sp_0(): gap_y(0)
def sp_1(): gap_y(1)
def sp_2(): gap_y(2)
def sp_3(): gap_y(3)
def sp_4(): gap_y(4)
def sp_5(): gap_y(5)
def sp_6(): gap_y(6)
def sp_8(): gap_y(8)
def sp_10(): gap_y(10)
def sp_12(): gap_y(12)
def sp_16(): gap_y(16)


@contextmanager
def auto_right(layout_id: str | None = None):
    """自动右对齐容器 - 内容自动靠右显示

    原理:
        1. 第一帧: 正常渲染，测量 group 宽度并缓存
        2. 后续帧: 使用缓存的宽度计算右对齐位置

    Args:
        layout_id: 可选。不提供则自动生成 (基于调用位置)

    用法:
        with ly.auto_right():
            imgui.button("设置")
    """
    lid = layout_id or _auto_id()
    cached = _get_cached_size(lid)

    # 在 same_line 之前获取内容区域信息
    content_region_width = imgui.get_content_region_available().x
    start_x = imgui.get_cursor_pos_x()

    if cached and cached[0] > 0:
        # 有缓存，计算精确的右对齐位置
        target_x = start_x + content_region_width - cached[0]
        imgui.same_line()
        imgui.set_cursor_pos_x(target_x)
    else:
        # 第一帧无缓存，先正常渲染
        imgui.same_line()

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        # 更新缓存
        size = imgui.get_item_rect_size()
        _set_cached_size(lid, size.x, size.y)


# =============================================================================
# Flex 布局原语 - hstack / vstack / spacer
# =============================================================================

# Debug 模式：显示 slot 边界框
FLEX_DEBUG = False
_flex_debug_logged: set[str] = set()  # 避免重复打印

# 缓存 hstack 的行高和各 slot 高度 {hstack_id: (max_height, [slot_heights])}
_hstack_height_cache: dict[str, tuple[float, list[float]]] = {}


def _hstack_id_from_caller() -> str:
    """从调用位置生成稳定的 hstack ID

    使用调用栈的文件名:行号作为唯一标识，确保每帧相同位置的 hstack 有相同 ID
    需要跳过 @contextmanager 包装层
    """
    frame = inspect.currentframe()
    try:
        # 往上跳: _hstack_id_from_caller -> hstack -> contextmanager wrapper -> 用户代码
        # 需要找到不在 contextlib.py 的帧
        f = frame.f_back
        while f:
            filename = f.f_code.co_filename
            if 'contextlib' not in filename and 'layout.py' not in filename:
                return f"hstack:{filename}:{f.f_lineno}"
            f = f.f_back
        return "hstack:unknown"
    finally:
        del frame


class _FlexContext:
    """Flex 布局上下文 - 管理子元素布局"""

    def __init__(self, direction: str, gap: float, align: str, hstack_id: str | None = None):
        self.direction = direction  # 'h' or 'v'
        self.gap = gap
        self.align = align  # 'start', 'center', 'end'
        self._first_item = True
        self._gap_px = gap * 4 * dpi_scale()
        self._spacer_used = False  # spacer() 调用后跳过下一次 same_line

        # hstack 垂直对齐支持
        self._hstack_id = hstack_id
        self._slot_index = 0
        self._slot_heights: list[float] = []  # 本帧测量的高度
        self._start_y = 0.0  # hstack 起始 Y 位置

    def next_item(self):
        """在下一个子元素前调用，处理间距"""
        if self._first_item:
            self._first_item = False
        elif self._spacer_used:
            # spacer 已经做了 same_line，跳过
            self._spacer_used = False
        else:
            if self.direction == 'h':
                imgui.same_line(spacing=self._gap_px)
            else:
                imgui.dummy(0, self._gap_px)

    def get_slot_y_offset(self) -> float:
        """获取当前 slot 的 Y 偏移量（用于垂直对齐）"""
        if self.direction != 'h' or self.align == 'start' or not self._hstack_id:
            return 0.0

        # 从缓存获取上一帧的数据
        cached = _hstack_height_cache.get(self._hstack_id)
        if not cached:
            return 0.0

        max_height, slot_heights = cached
        if self._slot_index >= len(slot_heights):
            return 0.0

        slot_height = slot_heights[self._slot_index]

        if self.align == 'center':
            return (max_height - slot_height) / 2
        elif self.align == 'end':
            return max_height - slot_height

        return 0.0

    def record_slot_height(self, height: float):
        """记录当前 slot 的高度"""
        self._slot_heights.append(height)
        self._slot_index += 1

    def finalize(self):
        """hstack 结束时调用，更新缓存"""
        if self._hstack_id and self._slot_heights:
            max_h = max(self._slot_heights) if self._slot_heights else 0
            _hstack_height_cache[self._hstack_id] = (max_h, self._slot_heights.copy())


# 线程局部的 flex 上下文栈
_flex_stack: list[_FlexContext] = []


def _current_flex() -> _FlexContext | None:
    """获取当前 flex 上下文"""
    return _flex_stack[-1] if _flex_stack else None


def item():
    """标记一个 flex 子项 - 在每个子元素前调用以应用间距

    用法 (传统方式):
        with ly.hstack(gap=2):
            ly.item(); imgui.text("A")
            ly.item(); imgui.text("B")

    推荐使用 slot() 替代:
        with ly.hstack(gap=2):
            with ly.slot():
                imgui.text("A")
            with ly.slot():
                imgui.text("B")
    """
    ctx = _current_flex()
    if ctx:
        ctx.next_item()


@contextmanager
def slot():
    """Flex 槽位 - 包装子元素，自动处理间距和对齐

    比 item() 更优雅的写法，使用 with 块明确元素边界。
    在 hstack 中支持垂直对齐 (align='center'/'end')。

    用法:
        with ly.hstack(gap=2, align='center'):
            with ly.slot():
                imgui.text("A")  # 会垂直居中
            with ly.slot():
                imgui.text("B")
                imgui.text("(副标题)")  # 多个元素在同一槽位

        # 支持嵌套
        with ly.vstack(gap=3):
            with ly.slot():
                with ly.hstack(gap=1):
                    with ly.slot():
                        imgui.text("嵌套内容")
    """
    ctx = _current_flex()
    if ctx:
        ctx.next_item()  # 这里会调用 same_line()，会重置 Y 位置

    # same_line() 之后再记录起始位置和应用偏移
    start_screen_pos = imgui.get_cursor_screen_pos()
    start_y = imgui.get_cursor_pos_y()

    # 应用 Y 偏移（基于上一帧缓存）
    # 必须在 same_line() 之后应用！
    y_offset = 0.0
    if ctx and ctx.direction == 'h' and ctx.align != 'start':
        y_offset = ctx.get_slot_y_offset()
        if y_offset > 0:
            imgui.set_cursor_pos_y(start_y + y_offset)

    # 用 Group 包装内容，使 slot 内的多个元素作为一个整体
    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()

        # 测量并记录 slot 高度
        slot_size = imgui.get_item_rect_size()
        if ctx and ctx.direction == 'h':
            ctx.record_slot_height(slot_size.y)

        # Debug: 绘制边界框（无条件）
        if FLEX_DEBUG:
            draw_list = imgui.get_window_draw_list()
            item_min = imgui.get_item_rect_min()
            item_max = imgui.get_item_rect_max()

            # 绘制 slot 实际边界（红色）
            draw_list.add_rect(
                item_min.x, item_min.y,
                item_max.x, item_max.y,
                imgui.get_color_u32_rgba(1, 0, 0, 0.8), 0, 0, 1
            )

            # 如果有缓存，绘制 max_height 参考线（绿色）
            if ctx and ctx._hstack_id:
                cached = _hstack_height_cache.get(ctx._hstack_id)
                if cached:
                    max_height = cached[0]
                    ref_top = start_screen_pos.y
                    ref_bottom = start_screen_pos.y + max_height
                    draw_list.add_rect(
                        item_min.x + 2, ref_top,
                        item_max.x - 2, ref_bottom,
                        imgui.get_color_u32_rgba(0, 1, 0, 0.5), 0, 0, 1
                    )


@contextmanager
def hstack(gap: float = 2, align: str = "center"):
    """水平 Flex 容器 - 子元素水平排列，支持垂直对齐

    ⚠️ 容器类型: Group (begin_group)
       - 无自己的 padding（仅逻辑分组）
       - 无自己的背景
       - gap 通过 same_line(spacing) 实现，不是 ItemSpacing

    Args:
        gap: 子元素间距 (Tailwind 单位, 2 = 8px)
        align: 垂直对齐方式
            - 'start': 顶部对齐 (默认 ImGui 行为)
            - 'center': 垂直居中 ⭐ 推荐用于图标+文字
            - 'end': 底部对齐

    用法 (推荐 - 使用 slot):
        # 图标和文字垂直居中对齐
        with ly.hstack(gap=2, align='center'):
            with ly.slot():
                with tw.text_xl:
                    imgui.text(FA_ICON)
            with ly.slot():
                imgui.text("文字")

    用法 (传统 - 使用 item，不支持对齐):
        with ly.hstack(gap=2):
            ly.item(); icon("sword")
            ly.item(); imgui.text("武器")
    """
    hstack_id = _hstack_id_from_caller() if align != 'start' else None
    ctx = _FlexContext('h', gap, align, hstack_id)
    _flex_stack.append(ctx)

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        ctx.finalize()  # 更新高度缓存
        _flex_stack.pop()


@contextmanager
def vstack(gap: float = 2, align: str = "start"):
    """垂直 Flex 容器 - 子元素垂直排列

    ⚠️ 容器类型: Group (begin_group)
       - 无自己的 padding（仅逻辑分组）
       - 无自己的背景
       - gap 通过 dummy 实现，不是 ItemSpacing

    Args:
        gap: 子元素间距 (Tailwind 单位)
        align: 水平对齐 ('start', 'center', 'end') - 目前未实现

    用法:
        with ly.vstack(gap=1):
            ly.item(); imgui.text("项目名称")
            ly.item(); imgui.text("v1.0 · 作者")
    """
    ctx = _FlexContext('v', gap, align)
    _flex_stack.append(ctx)

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        _flex_stack.pop()


def spacer():
    """弹性空间 - 用于实现 justify-between 效果

    在 hstack 中自动推算剩余空间，将后续元素推到右侧。
    spacer 之后的 slot 会被推到右边缘。

    用法:
        with ly.hstack():
            with ly.slot():
                imgui.text("左侧")
            ly.spacer()
            with ly.slot():
                imgui.text("右侧")  # 会被推到最右边
    """
    ctx = _current_flex()
    if not ctx or ctx.direction != 'h':
        return  # 仅在 hstack 中有效

    # 标记 spacer 已使用，下一个 slot 不需要再 same_line
    ctx._spacer_used = True

    # 获取剩余空间，用 same_line 跳到右侧
    # 注意：后续的 slot 会使用 auto_right_slot 机制
    avail = imgui.get_content_region_available().x
    if avail > 0:
        imgui.same_line(spacing=avail)


# =============================================================================
# 可交互列表项 - list_item
# =============================================================================

class ListItemState:
    """列表项交互状态"""
    __slots__ = ('clicked', 'hovered', 'double_clicked')

    def __init__(self):
        self.clicked = False
        self.hovered = False
        self.double_clicked = False


# 缓存每个 list_item 的上一帧状态 (hovered, height)
_list_item_cache: dict[str, tuple[bool, float]] = {}


@contextmanager
def list_item(
    item_id: str,
    selected: bool = False,
    *,
    padding_x: float = 3,
    padding_y: float = 2,
    rounding: float = 1,
    bg_color: tuple | None = None,
    selected_color: tuple | None = None,
    hover_color: tuple | None = None,
):
    """可交互列表项 - 统一处理背景、padding、hover/selected 状态

    内置缓存机制：使用上一帧的 hover 状态决定背景色，避免闪烁。

    Args:
        item_id: 唯一标识符
        selected: 是否选中
        padding_x: 水平内边距 (Tailwind 单位)
        padding_y: 垂直内边距 (Tailwind 单位)
        rounding: 圆角 (Tailwind 单位)
        bg_color: 默认背景色 (None = 透明)
        selected_color: 选中时背景色
        hover_color: 悬停时背景色

    Yields:
        ListItemState - 包含 clicked, hovered, double_clicked

    用法:
        with ly.list_item("item_1", selected=is_active,
                          selected_color=tw.CRYSTAL_600,
                          hover_color=tw.ABYSS_700) as state:
            imgui.text("物品名称")

        if state.clicked:
            select_item(1)
    """
    # 导入主题色默认值
    from ui import tw as _tw

    # 使用默认颜色
    if selected_color is None:
        selected_color = _tw.CRYSTAL_600
    if hover_color is None:
        hover_color = _tw.ABYSS_700

    avail_width = imgui.get_content_region_available().x
    px = sz(padding_x)
    py = sz(padding_y)

    # 获取上一帧缓存
    was_hovered, cached_height = _list_item_cache.get(item_id, (False, 0))

    # 确定背景颜色
    if selected and selected_color:
        color = selected_color
    elif was_hovered and hover_color:
        color = hover_color
    elif bg_color:
        color = bg_color
    else:
        color = None

    # 记录起始位置
    start_screen = imgui.get_cursor_screen_pos()
    start_cursor = imgui.get_cursor_pos()

    # ===== 1. 先画背景（用缓存的高度）=====
    if color and cached_height > 0:
        draw_list = imgui.get_window_draw_list()
        draw_list.add_rect_filled(
            start_screen.x, start_screen.y,
            start_screen.x + avail_width, start_screen.y + cached_height,
            imgui.get_color_u32_rgba(*color),
            rounding=sz(rounding),
        )

    # ===== 2. 设置内容位置（加 padding）=====
    imgui.set_cursor_pos((start_cursor.x + px, start_cursor.y + py))

    # 创建状态对象
    state = ListItemState()

    imgui.begin_group()
    try:
        yield state
    finally:
        imgui.end_group()

        # 测量内容
        content_height = imgui.get_item_rect_size().y
        row_height = content_height + py * 2

        # ===== 3. 放置交互按钮 =====
        imgui.set_cursor_pos(start_cursor)
        imgui.invisible_button(f"##{item_id}_btn", avail_width, row_height)
        state.hovered = imgui.is_item_hovered()
        state.clicked = imgui.is_item_clicked()
        state.double_clicked = imgui.is_mouse_double_clicked(0) and state.hovered

        # 缓存这一帧的状态
        _list_item_cache[item_id] = (state.hovered, row_height)

        # 恢复光标
        imgui.set_cursor_pos((start_cursor.x, start_cursor.y + row_height))

        # 鼠标样式
        if state.hovered:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)


# =============================================================================
# 折叠面板 - collapsible
# =============================================================================

# 折叠状态存储
_collapsible_states: dict[str, bool] = {}


class CollapsibleState:
    """折叠面板状态"""
    __slots__ = ('is_open', 'header_clicked', 'header_hovered')

    def __init__(self, is_open: bool):
        self.is_open = is_open
        self.header_clicked = False
        self.header_hovered = False


@contextmanager
def collapsible(
    panel_id: str,
    *,
    default_open: bool = True,
    header_padding_x: float = 3,
    header_padding_y: float = 2,
    header_rounding: float = 1,
    header_bg: tuple | None = None,
    header_hover: tuple | None = None,
    content_indent: float = 0,
    content_gap: float = 1,
):
    """可折叠面板 - 包含可点击头部和可折叠内容区

    Args:
        panel_id: 唯一标识符
        default_open: 默认是否展开
        header_padding_x/y: 头部内边距
        header_rounding: 头部圆角
        header_bg: 头部背景色
        header_hover: 头部悬停背景色
        content_indent: 内容区左侧缩进
        content_gap: 头部与内容间距

    Yields:
        CollapsibleState - 包含 is_open, header_clicked, header_hovered

    用法:
        with ly.collapsible("weapons", header_bg=tw.ABYSS_800) as panel:
            # 头部内容（始终显示）
            with panel.header:
                with ly.hstack(gap=2):
                    ly.item(); imgui.text(FA_CHEVRON_DOWN if panel.is_open else FA_CHEVRON_RIGHT)
                    ly.item(); imgui.text("武器")
                    ly.spacer()
                    ly.item(); imgui.text("(6)")

            # 折叠内容（仅展开时显示）
            if panel.is_open:
                for weapon in weapons:
                    ...
    """
    from ui import tw as _tw

    # 初始化状态
    if panel_id not in _collapsible_states:
        _collapsible_states[panel_id] = default_open

    is_open = _collapsible_states[panel_id]

    # 使用默认颜色
    if header_bg is None:
        header_bg = _tw.ABYSS_800
    if header_hover is None:
        header_hover = _tw.ABYSS_700

    # 创建面板对象
    class Panel:
        def __init__(self):
            self.is_open = is_open
            self.header_clicked = False
            self.header_hovered = False

        @contextmanager
        def header(self):
            """头部区域"""
            with list_item(
                f"{panel_id}_header",
                selected=False,
                padding_x=header_padding_x,
                padding_y=header_padding_y,
                rounding=header_rounding,
                bg_color=header_bg,
                hover_color=header_hover,
            ) as state:
                yield
                self.header_clicked = state.clicked
                self.header_hovered = state.hovered

            # 点击头部切换展开状态
            if self.header_clicked:
                _collapsible_states[panel_id] = not is_open
                self.is_open = not is_open

    panel = Panel()

    try:
        yield panel
    finally:
        pass


# =============================================================================
# 图标按钮 - icon_btn
# =============================================================================

def icon_btn(
    icon: str,
    btn_id: str,
    *,
    size: float = 7,
    tooltip_text: str | None = None,
    disabled: bool = False,
    style = None,
) -> bool:
    """图标按钮 - 统一尺寸和样式

    Args:
        icon: Font Awesome 图标字符
        btn_id: 按钮唯一 ID（不含 ##）
        size: 按钮尺寸 (Tailwind 单位, 7 = 28px)
        tooltip_text: 悬停提示
        disabled: 是否禁用
        style: StyleContext 样式

    Returns:
        bool: 是否点击

    用法:
        if ly.icon_btn(FA_PLUS, "add_weapon", tooltip_text="添加武器"):
            add_weapon()
    """
    from ui import styles as _styles

    btn_size = sz(size)
    clicked = False

    # 应用样式
    ctx = style if style else _styles.noop()
    if disabled:
        ctx = ctx | _styles.disabled()

    with ctx:
        if imgui.button(f"{icon}##{btn_id}", btn_size, btn_size) and not disabled:
            clicked = True

    if tooltip_text and imgui.is_item_hovered():
        imgui.set_tooltip(tooltip_text)

    return clicked


# =============================================================================
# 双槽行布局 - split_row (左右两端对齐)
# =============================================================================

# 缓存 split_row 的状态 (was_hovered, row_height, right_width, left_height)
_split_row_cache: dict[str, tuple[bool, float, float, float]] = {}


class SplitRowState:
    """双槽行交互状态"""
    __slots__ = ('clicked', 'hovered', 'row_height')

    def __init__(self):
        self.clicked = False
        self.hovered = False
        self.row_height = 0.0


class _RightSlotContext:
    """右侧槽位 - 使用缓存实现右对齐 + 垂直居中"""

    def __init__(self, parent: 'SplitRowContext'):
        self._parent = parent

    def __enter__(self):
        # 使用缓存的右侧宽度和行高计算位置
        cached = _split_row_cache.get(self._parent.row_id)
        cached_right_width = cached[2] if cached else 0
        cached_row_height = cached[1] if cached else 0

        if cached_right_width > 0 and cached_row_height > 0:
            # 有缓存：精确右对齐 + 垂直居中
            right_x = (self._parent._start_cursor.x + self._parent._avail_width
                      - cached_right_width - self._parent._px)
            # 垂直居中于整行
            right_y = self._parent._start_cursor.y + (cached_row_height - self._parent._right_height) / 2
            # 首次右侧高度未知，使用 padding
            if self._parent._right_height == 0:
                right_y = self._parent._start_cursor.y + self._parent._py
            imgui.set_cursor_pos((right_x, right_y))
        else:
            # 首帧：放在最右边（可能不精确）
            imgui.same_line()

        imgui.begin_group()
        return self

    def __exit__(self, *args):
        imgui.end_group()
        size = imgui.get_item_rect_size()
        self._parent._right_width = size.x
        self._parent._right_height = size.y


class SplitRowContext:
    """双槽行上下文管理器 - 支持左右两端对齐"""

    def __init__(
        self,
        row_id: str,
        padding_x: float,
        padding_y: float,
        hover_color: tuple | None,
        bg_color: tuple | None,
    ):
        self.row_id = row_id
        self._px = sz(padding_x)
        self._py = sz(padding_y)
        self._hover_color = hover_color
        self._bg_color = bg_color

        # 运行时记录
        self._start_cursor = None
        self._start_screen = None
        self._avail_width = 0.0
        self._left_height = 0.0
        self._right_width = 0.0
        self._right_height = 0.0

        # 状态输出
        self.state = SplitRowState()

    @property
    def left(self):
        """左侧槽位 - 垂直居中"""
        @contextmanager
        def _ctx():
            # 获取缓存：计算垂直居中偏移
            cached = _split_row_cache.get(self.row_id)
            if cached and cached[1] > 0 and cached[3] > 0:
                # 有缓存：精确垂直居中（取整避免抖动）
                cached_row_height = cached[1]
                cached_left_height = cached[3]
                y_offset = int((cached_row_height - cached_left_height) / 2)
            else:
                # 首帧：使用 padding 作为偏移
                y_offset = self._py

            imgui.set_cursor_pos((
                self._start_cursor.x + self._px,
                self._start_cursor.y + y_offset
            ))
            imgui.begin_group()
            try:
                yield
            finally:
                imgui.end_group()
                self._left_height = imgui.get_item_rect_size().y

        return _ctx()

    @property
    def right(self):
        """右侧槽位 - 自动右对齐"""
        return _RightSlotContext(self)

    def __enter__(self):
        # 记录起始位置
        self._start_cursor = imgui.get_cursor_pos()
        self._start_screen = imgui.get_cursor_screen_pos()
        self._avail_width = imgui.get_content_region_available().x

        # 获取上一帧缓存
        cached = _split_row_cache.get(self.row_id)
        was_hovered = cached[0] if cached else False
        cached_height = cached[1] if cached else 0

        # 确定背景颜色
        color = None
        if was_hovered and self._hover_color:
            color = self._hover_color
        elif self._bg_color:
            color = self._bg_color

        # ===== 先画背景（用缓存的高度）=====
        if color and cached_height > 0:
            draw_list = imgui.get_window_draw_list()
            draw_list.add_rect_filled(
                self._start_screen.x, self._start_screen.y,
                self._start_screen.x + self._avail_width,
                self._start_screen.y + cached_height,
                imgui.get_color_u32_rgba(*color),
            )

        return self

    def __exit__(self, *args):
        # 计算行高（取整避免抖动）
        content_height = max(self._left_height, self._right_height)
        row_height = int(content_height + self._py * 2)
        self.state.row_height = row_height

        # ===== 放置交互按钮 =====
        # 只覆盖左侧区域，不覆盖右侧按钮（避免吞掉右侧按钮的 hover）
        clickable_width = self._avail_width - self._right_width - self._px
        imgui.set_cursor_pos(self._start_cursor)
        imgui.invisible_button(f"##{self.row_id}_row_btn", clickable_width, row_height)
        self.state.hovered = imgui.is_item_hovered()
        self.state.clicked = imgui.is_item_clicked()

        # 缓存这一帧的状态 (hovered, height, right_width, left_height)
        _split_row_cache[self.row_id] = (
            self.state.hovered,
            row_height,
            self._right_width,
            self._left_height,
        )

        # 恢复光标到下一行
        imgui.set_cursor_pos((self._start_cursor.x, self._start_cursor.y + row_height))

        # 鼠标样式
        if self.state.hovered:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)


@contextmanager
def split_row(
    row_id: str,
    *,
    padding_x: float = 3,
    padding_y: float = 1.5,
    hover_color: tuple | None = None,
    bg_color: tuple | None = None,
):
    """双槽行布局 - 左右两端对齐，自动处理 hover 背景

    高级原语：创建带左右两部分的可交互行。自动处理：
    - hover 背景（带缓存，不闪烁）
    - 左右两端对齐（右侧内容自动靠右）
    - 行高自动计算
    - 交互状态检测

    Args:
        row_id: 唯一标识符
        padding_x: 水平内边距 (Tailwind 单位)
        padding_y: 垂直内边距 (Tailwind 单位)
        hover_color: 悬停背景色
        bg_color: 默认背景色

    Yields:
        SplitRowContext - 包含 left, right 槽位和 state

    用法:
        with ly.split_row("section_weapons", hover_color=tw.ABYSS_600) as row:
            with row.left:
                imgui.text("武器 (3)")

            with row.right:
                ly.icon_btn(FA_PLUS, "add")

        if row.state.clicked:
            toggle_section()
    """
    ctx = SplitRowContext(row_id, padding_x, padding_y, hover_color, bg_color)
    with ctx:
        yield ctx


# =============================================================================
# 简化的右对齐原语
# =============================================================================

def push_right(content_width: float) -> None:
    """将光标移到右对齐位置

    用于在行内将后续内容右对齐。

    Args:
        content_width: 后续内容的宽度 (Tailwind 单位)

    用法:
        imgui.text("左侧内容")
        ly.push_right(5)  # 后续内容宽 20px
        ly.icon_btn(FA_PLUS, "add")
    """
    avail = imgui.get_content_region_available().x
    width_px = sz(content_width)
    cursor = imgui.get_cursor_pos()
    imgui.set_cursor_pos_x(cursor.x + avail - width_px)


def right_aligned(content_width: float):
    """右对齐容器上下文

    Args:
        content_width: 内容宽度 (Tailwind 单位)

    用法:
        with ly.right_aligned(10):
            ly.icon_btn(FA_PLUS, "add")
            ly.same_line(1)
            ly.icon_btn(FA_TRASH, "del")
    """
    @contextmanager
    def _ctx():
        push_right(content_width)
        imgui.begin_group()
        try:
            yield
        finally:
            imgui.end_group()

    return _ctx()


# =============================================================================
# 自动尺寸的右对齐
# =============================================================================

# auto_right_slot 是 auto_right 的别名，保留向后兼容
auto_right_slot = auto_right


def clear_list_item_cache():
    """清除 list_item 缓存"""
    _list_item_cache.clear()


def set_collapsible_state(panel_id: str, is_open: bool):
    """设置折叠面板状态"""
    _collapsible_states[panel_id] = is_open


def get_collapsible_state(panel_id: str, default: bool = True) -> bool:
    """获取折叠面板状态"""
    return _collapsible_states.get(panel_id, default)


# =============================================================================
# Context Menu - 右键菜单原语
# =============================================================================

@contextmanager
def context_menu(menu_id: str):
    """样式化右键菜单

    自动应用暗黑主题样式：
    - ABYSS_800 背景
    - 圆角边框
    - 统一内边距

    Args:
        menu_id: 菜单唯一标识符

    Yields:
        bool: 菜单是否打开

    用法:
        with ly.context_menu("item_ctx") as opened:
            if opened:
                if ly.menu_item("复制", icon=FA_COPY):
                    copy_item()
                ly.menu_separator()
                if ly.menu_item("删除", icon=FA_TRASH, danger=True):
                    delete_item()
    """
    from ui import tw as _tw
    from ui.styles import window_padding, frame_padding, popup_rounding, popup_border

    # 菜单样式
    menu_style = (
        _tw.bg_abyss_800 |
        _tw.border_abyss_600 |
        window_padding(2, 2) |
        frame_padding(8, 4) |
        popup_rounding(4) |
        popup_border(1)
    )

    with menu_style:
        opened = imgui.begin_popup_context_item(menu_id)
        try:
            yield opened
        finally:
            if opened:
                imgui.end_popup()


def menu_item(
    label: str,
    *,
    icon: str | None = None,
    shortcut: str | None = None,
    danger: bool = False,
    disabled: bool = False,
) -> bool:
    """样式化菜单项

    Args:
        label: 菜单项文字
        icon: 可选图标 (Font Awesome)
        shortcut: 可选快捷键提示
        danger: 是否为危险操作（红色）
        disabled: 是否禁用

    Returns:
        bool: 是否点击

    用法:
        if ly.menu_item("复制", icon=FA_COPY):
            copy_item()
        if ly.menu_item("删除", icon=FA_TRASH, danger=True):
            delete_item()
    """
    from ui import tw as _tw

    # 构建显示文本
    if icon:
        display_text = f"{icon}  {label}"
    else:
        display_text = f"    {label}"  # 无图标时留空位对齐

    # 应用颜色样式
    if disabled:
        text_style = _tw.text_parchment_600
    elif danger:
        text_style = _tw.text_blood_400
    else:
        text_style = _tw.text_parchment_200

    with text_style:
        clicked, _ = imgui.menu_item(display_text, shortcut or "", False, not disabled)

    return clicked


def menu_separator():
    """菜单分隔线"""
    from ui import tw as _tw

    # 添加一点垂直间距
    imgui.dummy(0, 2)

    # 绘制分隔线
    draw_list = imgui.get_window_draw_list()
    cursor_screen = imgui.get_cursor_screen_pos()
    avail_width = imgui.get_content_region_available().x

    color = imgui.get_color_u32_rgba(*_tw.ABYSS_600)
    draw_list.add_line(
        cursor_screen.x, cursor_screen.y,
        cursor_screen.x + avail_width, cursor_screen.y,
        color, 1.0
    )

    imgui.dummy(0, 4)


# =============================================================================
# Grid 布局 - 多列网格
# =============================================================================

@contextmanager
def grid(cols: int = 2, gap: float = 4, row_gap: float | None = None):
    """多列网格布局

    ⚠️ 容器类型: Table (begin_table)
       - 有自己的 CellPadding (由 gap 参数控制)
       - 无背景色（Table 本身透明）
       - 样式通过 tw.* 作用于内部的 Frame 控件

    使用 ImGui Table 实现 CSS Grid 风格的多列布局。

    Args:
        cols: 列数 (默认 2)
        gap: 列间距 (Tailwind 单位)
        row_gap: 行间距 (Tailwind 单位，默认等于 gap)

    用法:
        with ly.grid(cols=2, gap=4):
            with ly.grid_item():
                imgui.text("Label 1")
            with ly.grid_item():
                imgui.input_text("##input1", ...)

            with ly.grid_item():
                imgui.text("Label 2")
            with ly.grid_item():
                imgui.input_text("##input2", ...)
    """
    gap_px = sz(gap)
    row_gap_px = sz(row_gap) if row_gap is not None else gap_px

    # 使用 Table 实现 grid
    flags = (
        imgui.TABLE_SIZING_STRETCH_SAME |
        imgui.TABLE_NO_BORDERS_IN_BODY
    )

    # 设置 cell padding
    imgui.push_style_var(imgui.STYLE_CELL_PADDING, (gap_px / 2, row_gap_px / 2))

    if imgui.begin_table("##grid", cols, flags):
        try:
            yield
        finally:
            imgui.end_table()
            imgui.pop_style_var()
    else:
        imgui.pop_style_var()
        yield  # 表格创建失败也要 yield


@contextmanager
def grid_item(span: int = 1):
    """Grid 单元格

    Args:
        span: 跨越的列数 (目前 ImGui Table 不直接支持 colspan)

    用法:
        with ly.grid(cols=2):
            with ly.grid_item():
                imgui.text("Cell 1")
    """
    imgui.table_next_column()
    yield


def grid_row():
    """开始新的 grid 行（通常不需要手动调用，grid_item 会自动换行）"""
    imgui.table_next_row()


# =============================================================================
# 表单布局 - form_row
# =============================================================================

@contextmanager
def form_row(
    label: str,
    label_width: float = 25,
    *,
    label_style=None,
    required: bool = False,
    help_text: str | None = None,
):
    """表单行 - 左侧标签 + 右侧输入

    标准的两列表单布局，自动处理标签宽度和对齐。

    Args:
        label: 标签文本
        label_width: 标签宽度 (Tailwind 单位，25 = 100px)
        label_style: 标签样式 (StyleContext)
        required: 是否显示必填标记 *
        help_text: 帮助文本 (悬停显示)

    Yields:
        输入区域

    用法:
        with ly.form_row("名称", required=True):
            _, value = imgui.input_text("##name", value)

        with ly.form_row("描述", help_text="简短描述此物品"):
            _, value = imgui.input_text_multiline("##desc", value)
    """
    from ui import tw as _tw

    label_w = sz(label_width)
    avail = imgui.get_content_region_available().x

    imgui.begin_group()

    # 标签区域
    style = label_style or _tw.text_parchment_400
    with style:
        imgui.text(label)
        if required:
            imgui.same_line(spacing=2)
            with _tw.text_blood_400:
                imgui.text("*")
        if help_text:
            imgui.same_line(spacing=4)
            with _tw.text_parchment_600:
                imgui.text("(?)")
            if imgui.is_item_hovered():
                imgui.set_tooltip(help_text)

    # 设置输入区域宽度
    imgui.same_line(position=label_w)
    imgui.push_item_width(avail - label_w)

    try:
        yield
    finally:
        imgui.pop_item_width()
        imgui.end_group()


@contextmanager
def form_section(title: str, *, gap: float = 3):
    """表单分区 - 带标题的表单区域

    Args:
        title: 分区标题
        gap: 标题与内容间距

    用法:
        with ly.form_section("基本信息"):
            with ly.form_row("名称"):
                ...
            with ly.form_row("类型"):
                ...
    """
    from ui import tw as _tw

    with _tw.text_parchment_200:
        imgui.text(title)
    gap_y(gap)

    yield


# =============================================================================
# 滚动区域 - scroll_y / scroll_x
# =============================================================================

@contextmanager
def scroll_y(height: float, *, border: bool = False):
    """垂直滚动区域

    ⚠️ 容器类型: Child Window (begin_child)
       - 有自己的 WindowPadding (外部 tw.p_* 控制)
       - 内容超出会显示滚动条
       - 样式必须在 scroll_y 之前设置

    Args:
        height: 区域高度 (Tailwind 单位)
        border: 是否显示边框

    用法:
        # 带内边距的滚动区域
        with tw.p_2:
            with ly.scroll_y(height=50):  # 200px 高
                for item in long_list:
                    imgui.text(item)  # 有 8px 内边距
    """
    h = sz(height)
    w = imgui.get_content_region_available().x

    imgui.begin_child(
        "##scroll_y",
        width=w,
        height=h,
        border=border,
        flags=imgui.WINDOW_ALWAYS_VERTICAL_SCROLLBAR
    )
    try:
        yield
    finally:
        imgui.end_child()


@contextmanager
def scroll_x(width: float = 0, height: float = 0, *, border: bool = False):
    """水平滚动区域

    Args:
        width: 区域宽度 (0 = 自动)
        height: 区域高度 (0 = 自动)
        border: 是否显示边框

    用法:
        with ly.scroll_x():
            with ly.hstack(gap=2):
                for img in images:
                    draw_thumbnail(img)
    """
    w = sz(width) if width > 0 else 0
    h = sz(height) if height > 0 else 0

    imgui.begin_child(
        "##scroll_x",
        width=w,
        height=h,
        border=border,
        flags=imgui.WINDOW_HORIZONTAL_SCROLLBAR
    )
    try:
        yield
    finally:
        imgui.end_child()


# =============================================================================
# 固定尺寸容器
# =============================================================================

@contextmanager
def fixed_width(width: float):
    """固定宽度容器

    Args:
        width: 宽度 (Tailwind 单位)

    用法:
        with ly.fixed_width(60):  # 240px
            imgui.text("固定宽度内容")
    """
    w = sz(width)
    imgui.begin_group()
    imgui.push_item_width(w)
    try:
        yield
    finally:
        imgui.pop_item_width()
        imgui.end_group()


@contextmanager
def fixed_height(height: float):
    """固定高度容器 (使用 child window)

    Args:
        height: 高度 (Tailwind 单位)
    """
    h = sz(height)
    w = imgui.get_content_region_available().x

    imgui.begin_child("##fixed_h", width=w, height=h, border=False)
    try:
        yield
    finally:
        imgui.end_child()


@contextmanager
def fixed_size(width: float, height: float):
    """固定尺寸容器

    Args:
        width: 宽度 (Tailwind 单位)
        height: 高度 (Tailwind 单位)
    """
    w = sz(width)
    h = sz(height)

    imgui.begin_child("##fixed", width=w, height=h, border=False)
    try:
        yield
    finally:
        imgui.end_child()


# =============================================================================
# 比例分割布局
# =============================================================================

@contextmanager
def split_h(left_ratio: float = 0.5, gap: float = 4):
    """水平分割 - 左右两栏

    Args:
        left_ratio: 左侧占比 (0.0 ~ 1.0)
        gap: 中间间距 (Tailwind 单位)

    Yields:
        (left_ctx, right_ctx) 两个 context manager

    用法:
        with ly.split_h(0.3) as (left, right):
            with left:
                draw_sidebar()
            with right:
                draw_main_content()
    """
    gap_px = sz(gap)
    avail = imgui.get_content_region_available().x
    left_w = (avail - gap_px) * left_ratio
    right_w = (avail - gap_px) * (1 - left_ratio)

    @contextmanager
    def left_region():
        imgui.begin_child("##split_left", width=left_w, height=0, border=False)
        try:
            yield
        finally:
            imgui.end_child()

    @contextmanager
    def right_region():
        imgui.same_line(spacing=gap_px)
        imgui.begin_child("##split_right", width=right_w, height=0, border=False)
        try:
            yield
        finally:
            imgui.end_child()

    yield (left_region(), right_region())


@contextmanager
def split_v(top_ratio: float = 0.5, gap: float = 4):
    """垂直分割 - 上下两栏

    Args:
        top_ratio: 上方占比 (0.0 ~ 1.0)
        gap: 中间间距 (Tailwind 单位)

    用法:
        with ly.split_v(0.3) as (top, bottom):
            with top:
                draw_header()
            with bottom:
                draw_content()
    """
    gap_px = sz(gap)
    avail = imgui.get_content_region_available()
    top_h = (avail.y - gap_px) * top_ratio
    bottom_h = (avail.y - gap_px) * (1 - top_ratio)

    @contextmanager
    def top_region():
        imgui.begin_child("##split_top", width=avail.x, height=top_h, border=False)
        try:
            yield
        finally:
            imgui.end_child()

    @contextmanager
    def bottom_region():
        gap_y(gap / 4)  # 转换回 tailwind 单位
        imgui.begin_child("##split_bottom", width=avail.x, height=bottom_h, border=False)
        try:
            yield
        finally:
            imgui.end_child()

    yield (top_region(), bottom_region())


# =============================================================================
# 条件渲染 Helpers
# =============================================================================

@contextmanager
def visible_if(condition: bool):
    """条件渲染 - 仅当条件为真时渲染内容

    比 if 语句更优雅，且保持缩进一致。

    用法:
        with ly.visible_if(has_items):
            draw_items_list()

        with ly.visible_if(is_loading):
            draw_spinner()
    """
    if condition:
        yield True
    else:
        yield False
        return  # 不执行 with 块


@contextmanager
def hidden_if(condition: bool):
    """条件隐藏 - 当条件为真时隐藏内容

    visible_if 的反向版本。

    用法:
        with ly.hidden_if(is_empty):
            draw_content()
    """
    if not condition:
        yield True
    else:
        yield False
        return


# =============================================================================
# 对齐容器
# =============================================================================

@contextmanager
def align_bottom():
    """底部对齐 - 将内容推到容器底部

    需要在固定高度容器内使用。

    用法:
        with ly.fixed_height(50):
            imgui.text("顶部内容")
            with ly.align_bottom():
                ly.btn("底部按钮", 20, 8)
    """
    # 测量内容高度，然后放置到底部
    # 使用缓存机制
    lid = _auto_id()
    cached = _get_cached_size(lid)

    avail = imgui.get_content_region_available()
    if cached and cached[1] > 0:
        # 有缓存，计算底部位置
        offset_y = avail.y - cached[1]
        if offset_y > 0:
            imgui.dummy(0, offset_y)

    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()
        size = imgui.get_item_rect_size()
        _set_cached_size(lid, size.x, size.y)


# =============================================================================
# Wrap 布局 - 自动换行
# =============================================================================

class WrapContext:
    """Wrap 布局上下文"""

    def __init__(self, gap_x: float, gap_y: float, max_width: float):
        self._gap_x = sz(gap_x)
        self._gap_y = sz(gap_y)
        self._max_width = max_width
        self._current_x = 0.0
        self._row_height = 0.0
        self._first_item = True

    def next(self):
        """在下一个子元素前调用"""
        if self._first_item:
            self._first_item = False
            return

        # 检查是否需要换行
        # 这需要预知下一个元素的宽度，ImGui 不支持
        # 所以这里只能在 same_line 后检查
        imgui.same_line(spacing=self._gap_x)


@contextmanager
def wrap(gap_x: float = 2, gap_y: float = 2):
    """自动换行容器

    注意：由于 ImGui 的 immediate mode 特性，完美的 wrap 需要预知元素宽度。
    这个实现是简化版，依赖 ImGui 的自动换行行为。

    用法:
        with ly.wrap(gap_x=2, gap_y=2) as w:
            for tag in tags:
                w.next()
                draw_tag(tag)
    """
    max_width = imgui.get_content_region_available().x
    ctx = WrapContext(gap_x, gap_y, max_width)

    imgui.begin_group()
    try:
        yield ctx
    finally:
        imgui.end_group()


# =============================================================================
# Inline 布局 - 内联元素
# =============================================================================

def inline(*items, gap: float = 2):
    """内联渲染多个元素

    简化版的 hstack，用于简单的内联场景。

    用法:
        ly.inline(
            lambda: imgui.text("Status:"),
            lambda: imgui.text_colored("OK", 0, 1, 0, 1),
            gap=1
        )
    """
    gap_px = sz(gap)
    first = True
    for item in items:
        if not first:
            imgui.same_line(spacing=gap_px)
        first = False
        item()


# =============================================================================
# Columns 布局 - 固定多列（解决 hstack + 垂直内容的问题）
# =============================================================================

class _ColumnContext:
    """单列上下文"""

    def __init__(self, parent: 'ColumnsContext', col_index: int):
        self._parent = parent
        self._col_index = col_index

    def __enter__(self):
        # 计算此列的 X 位置
        col_x = self._parent._start_x + self._col_index * (self._parent._col_width + self._parent._gap_px)
        # 恢复到行起始 Y 位置
        imgui.set_cursor_pos((col_x, self._parent._start_y))
        imgui.begin_group()
        return self

    def __exit__(self, *args):
        imgui.end_group()
        # 记录此列的高度
        col_height = imgui.get_item_rect_size().y
        self._parent._max_height = max(self._parent._max_height, col_height)


class ColumnsContext:
    """多列布局上下文

    用于管理固定列数的水平布局，每列可以包含垂直内容。
    """

    def __init__(self, num_cols: int, gap: float, col_widths: list[float] | None = None, available_width: float | None = None):
        self._num_cols = num_cols
        self._gap_px = sz(gap)

        # 计算列宽
        # 优先使用传入的 available_width，否则从 ImGui 获取
        avail_width = available_width if available_width is not None else imgui.get_content_region_available().x
        total_gap = self._gap_px * (num_cols - 1)

        if col_widths:
            # 使用指定的列宽 (Tailwind 单位)
            self._col_widths = [sz(w) for w in col_widths]
        else:
            # 等宽列
            single_col_width = (avail_width - total_gap) / num_cols
            self._col_widths = [single_col_width] * num_cols

        self._col_width = self._col_widths[0]  # 兼容等宽情况

        # 记录起始位置
        cursor = imgui.get_cursor_pos()
        self._start_x = cursor.x
        self._start_y = cursor.y
        self._max_height = 0.0

    def col(self, index: int) -> _ColumnContext:
        """获取指定索引的列上下文

        Args:
            index: 列索引 (0-based)

        用法:
            with ly.columns(2) as c:
                with c.col(0):
                    # 第一列内容
                with c.col(1):
                    # 第二列内容
        """
        # 更新列宽为此列的宽度
        if index < len(self._col_widths):
            self._col_width = self._col_widths[index]
        return _ColumnContext(self, index)

    @property
    def col_width(self) -> float:
        """当前列宽度（像素）"""
        return self._col_width

    def get_col_width(self, index: int) -> float:
        """获取指定列的宽度（像素）"""
        if index < len(self._col_widths):
            return self._col_widths[index]
        return self._col_width

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # 移动光标到所有列之后
        imgui.set_cursor_pos((self._start_x, self._start_y + self._max_height))


@contextmanager
def columns(num_cols: int = 2, gap: float = 4, widths: list[float] | None = None, available_width: float | None = None):
    """固定多列布局 - 解决 hstack + 垂直内容的问题

    与 hstack 的区别:
    - hstack: 使用 same_line()，每个 slot 相对于上一个 item 定位
    - columns: 使用固定 X 位置，每列独立渲染垂直内容

    Args:
        num_cols: 列数 (默认 2)
        gap: 列间距 (Tailwind 单位)
        widths: 可选的列宽列表 (Tailwind 单位)，不提供则等宽
        available_width: 可选的可用宽度 (像素)，用于在 panel 等容器内正确计算列宽

    用法:
        # 等宽两列
        with ly.columns(2, gap=4) as c:
            with c.col(0):
                imgui.text("Label 1")
                ly.gap_y(1)
                imgui.input_text("##input1", ...)

            with c.col(1):
                imgui.text("Label 2")
                ly.gap_y(1)
                imgui.input_text("##input2", ...)

        # 在 panel 内使用（传入 content_width）
        with ly.panel("card", ...) as content_width:
            with ly.columns(2, gap=4, available_width=content_width) as c:
                ...
    """
    ctx = ColumnsContext(num_cols, gap, widths, available_width)
    with ctx:
        yield ctx


# =============================================================================
# 旧版 Grid 系统 (向后兼容)
# ⚠️ DEPRECATED: 以下内容将在未来版本移除，请使用 tw/styles 系统
# =============================================================================

# [DEPRECATED] 从 styles 导出尺寸常量和函数
from ui.styles import (
    # 常量
    INPUT_XS, INPUT_S, INPUT_M, INPUT_L, INPUT_XL,
    GRID_COL, GRID_GAP, GRID_DEBUG,
    SPAN_INPUT, SPAN_BADGE, SPAN_ID,
    GAP_XS, GAP_S, GAP_M, GAP_L,
    # 函数
    em, span,
    input_xs, input_s, input_m, input_l, input_xl,
    grid_col, grid_gap,
    gap_xs, gap_s, gap_m, gap_l,
)

# [DEPRECATED] 从 grid 导出布局工具
from ui.grid import (
    GridLayout,
    item_width,
    tooltip,
)

__all__ = [
    # ===== 核心布局 API (推荐使用) =====
    # 间距
    'gap_y', 'gap_x', 'gap_y_px', 'gap_x_px', 'same_line',
    # 居中
    'auto_hcenter', 'auto_vcenter', 'auto_center', 'auto_right',
    # 文本对齐
    'text_center', 'text_right',
    # 图标+文字
    'icon_label',
    # 容器
    'row', 'col', 'card', 'CardState', 'panel', 'clear_panel_cache',
    # 按钮
    'btn',
    # 尺寸转换
    'sz', 'sz_raw', 'scaled',
    # 杂项
    'next_line', 'divider', 'hr',
    'window_size', 'content_region', 'clear_layout_cache',

    # ===== Flex 布局 =====
    'hstack', 'vstack', 'item', 'slot', 'spacer',

    # ===== Grid 布局 (新增) =====
    'grid', 'grid_item', 'grid_row',

    # ===== 表单布局 (新增) =====
    'form_row', 'form_section',

    # ===== 滚动区域 (新增) =====
    'scroll_y', 'scroll_x',

    # ===== 固定尺寸容器 (新增) =====
    'fixed_width', 'fixed_height', 'fixed_size',

    # ===== 比例分割 (新增) =====
    'split_h', 'split_v',

    # ===== 条件渲染 (新增) =====
    'visible_if', 'hidden_if',

    # ===== 对齐 (新增) =====
    'align_bottom',

    # ===== Wrap/Inline (新增) =====
    'wrap', 'WrapContext', 'inline',

    # ===== Columns 多列布局 (新增) =====
    'columns', 'ColumnsContext',

    # ===== 列表项 =====
    'list_item', 'ListItemState', 'clear_list_item_cache',

    # ===== 折叠面板 =====
    'collapsible', 'CollapsibleState',
    'set_collapsible_state', 'get_collapsible_state',

    # ===== 图标按钮 =====
    'icon_btn',

    # ===== 双槽行 =====
    'split_row', 'SplitRowState',
    'push_right', 'right_aligned', 'auto_right_slot',

    # ===== 右键菜单 =====
    'context_menu', 'menu_item', 'menu_separator',

    # ===== [DEPRECATED] 手动居中 - 请使用 auto_* 系列 =====
    'hcenter', 'vcenter', 'center', 'vcenter_start', 'hcenter_start',

    # ===== [DEPRECATED] sp_* 系列 - 请使用 gap_y() =====
    'sp_0', 'sp_1', 'sp_2', 'sp_3', 'sp_4', 'sp_5', 'sp_6', 'sp_8', 'sp_10', 'sp_12', 'sp_16',

    # ===== [DEPRECATED] 旧版 Grid 系统 =====
    'SPAN_INPUT', 'SPAN_BADGE', 'SPAN_ID',
    'GAP_XS', 'GAP_S', 'GAP_M', 'GAP_L',
    'em', 'span',
    'input_xs', 'input_s', 'input_m', 'input_l', 'input_xl',
    'grid_col', 'grid_gap',
    'gap_xs', 'gap_s', 'gap_m', 'gap_l',
    'GridLayout', 'item_width', 'tooltip',
]
