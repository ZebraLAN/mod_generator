# -*- coding: utf-8 -*-
"""ImGui 样式上下文 - 组合式 API

提供 Tailwind 风格的样式系统：
- StyleContext 类支持 `|` 运算符组合
- 底层构建函数供 token 生成器使用
- 便捷工具 (push_id, disabled_if, group 等)

使用方式:
    from ui import tw

    # 组合样式 (像 Tailwind 一样)
    with tw.bg_slate_800 | tw.text_white | tw.p_4 | tw.rounded_lg:
        imgui.text("Hello, Tailwind!")

    # 多个样式组合
    card_style = tw.bg_gray_800 | tw.rounded_xl | tw.p_6
    with card_style:
        imgui.text("Card content")

    # 条件样式
    with tw.text_green_500 if is_valid else tw.text_red_500:
        imgui.text(status)

设计原则:
    1. 扁平化 - 没有嵌套的 token 命名空间
    2. 预构建 - 所有 tokens 都是预构建的 StyleContext 常量
    3. 组合式 - 用 `|` 组合，不需要函数调用
    4. Agent 友好 - 命名遵循 Tailwind 惯例
"""

from __future__ import annotations
from typing import Any, Callable, TypeVar, TYPE_CHECKING
from contextlib import contextmanager

import imgui  # type: ignore

from ui.state import dpi_scale

if TYPE_CHECKING:
    from ui.fonts import FontSet

# 类型别名
RGBA = tuple[float, float, float, float]
F = TypeVar('F', bound=Callable[..., Any])


# =============================================================================
# Agent 使用指南
# =============================================================================

AGENT_GUIDE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     Tailwind-style ImGui Tokens                              ║
║                     (for AI Agent reference)                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  IMPORT:                                                                     ║
║    from ui import tw                                                         ║
║                                                                              ║
║  USAGE (like Tailwind CSS):                                                  ║
║    with tw.bg_slate_800 | tw.text_white | tw.p_4 | tw.rounded_lg:           ║
║        imgui.text("Hello!")                                                  ║
║                                                                              ║
║  COLORS (22 palettes × 11 shades: 50,100,200,...,900,950):                  ║
║    Text:   tw.text_gray_500, tw.text_blue_600, tw.text_red_500, ...         ║
║    BG:     tw.bg_slate_800, tw.bg_white, tw.bg_black, ...                   ║
║    Border: tw.border_gray_700, tw.border_blue_500, ...                      ║
║                                                                              ║
║    Palettes: slate, gray, zinc, neutral, stone,                             ║
║              red, orange, amber, yellow, lime, green, emerald, teal,        ║
║              cyan, sky, blue, indigo, violet, purple, fuchsia, pink, rose   ║
║                                                                              ║
║  SPACING (padding):                                                          ║
║    tw.p_0, tw.p_1, tw.p_2, tw.p_4, tw.p_6, tw.p_8, ...                      ║
║    (p_1 = 4px, p_2 = 8px, p_4 = 16px, p_8 = 32px)                           ║
║                                                                              ║
║  BORDER RADIUS:                                                              ║
║    tw.rounded_none, tw.rounded_sm, tw.rounded, tw.rounded_md,               ║
║    tw.rounded_lg, tw.rounded_xl, tw.rounded_2xl, tw.rounded_full            ║
║                                                                              ║
║  SEMANTIC (convenience aliases):                                             ║
║    tw.text_muted, tw.text_success, tw.text_danger, tw.text_warning          ║
║    tw.bg_success, tw.bg_danger, tw.bg_warning, tw.bg_info                   ║
║                                                                              ║
║  COMBINING:                                                                  ║
║    style1 | style2 | style3    # Combine multiple styles                    ║
║    tw.when(cond, style)        # Conditional style                          ║
║                                                                              ║
║  UTILITIES:                                                                  ║
║    styles.push_id(id)          # ID scope                                   ║
║    styles.disabled_if(cond)    # Conditional disable                        ║
║    styles.group()              # BeginGroup/EndGroup                         ║
║    styles.font("lg")           # Font size (xs, sm, md, lg, xl)             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# StyleContext 核心类
# =============================================================================


class StyleContext:
    """可组合的样式上下文

    核心设计:
    - 每个实例持有 (push, pop) 函数对
    - `|` 运算符组合多个上下文 (fold 优化)
    - 作为 context manager 自动处理 push/pop
    - 支持元数据注入 (width, height 等不通过 push/pop 传递的值)

    元数据注入:
        元数据样式 (如 tw.w_40) 不会 push 任何 ImGui 样式，
        而是在函数调用时直接注入 kwargs:

        (tw.w_40 | tw.h_9)(imgui.button)("确定")
        # 等价于: imgui.button("确定", width=160, height=36)

    注意:
        纯元数据样式 (meta_only=True) 禁止使用 context manager，
        因为元数据只能通过函数调用注入。
    """

    __slots__ = ('_actions', '_meta', '_meta_only')

    def __init__(
        self,
        push: Callable[[], None],
        pop: Callable[[], None],
        *,
        meta: dict[str, Any] | None = None,
        meta_only: bool = False,
    ):
        self._actions: list[tuple[Callable[[], None], Callable[[], None]]] = [(push, pop)]
        self._meta: dict[str, Any] = meta or {}
        self._meta_only: bool = meta_only

    @classmethod
    def _from_parts(
        cls,
        actions: list[tuple[Callable[[], None], Callable[[], None]]],
        meta: dict[str, Any],
        meta_only: bool,
    ) -> StyleContext:
        """内部构造器 - 从组件创建"""
        ctx = object.__new__(cls)
        ctx._actions = actions
        ctx._meta = meta
        ctx._meta_only = meta_only
        return ctx

    @classmethod
    def _from_actions(cls, actions: list[tuple[Callable[[], None], Callable[[], None]]]) -> StyleContext:
        """内部构造器 - 直接从 actions 列表创建 (向后兼容)"""
        ctx = object.__new__(cls)
        ctx._actions = actions
        ctx._meta = {}
        ctx._meta_only = False
        return ctx

    @classmethod
    def empty(cls) -> StyleContext:
        """空样式上下文 (无操作)"""
        return cls(lambda: None, lambda: None)

    @classmethod
    def from_meta(cls, **meta: Any) -> StyleContext:
        """创建纯元数据样式 (禁止 context manager)

        用法:
            w_40 = StyleContext.from_meta(width=160)
            h_9 = StyleContext.from_meta(height=36)

            (w_40 | h_9)(imgui.button)("确定")
            # 等价于: imgui.button("确定", width=160, height=36)
        """
        return cls(lambda: None, lambda: None, meta=meta, meta_only=True)

    def __or__(self, other: StyleContext) -> StyleContext:
        """组合两个样式: style1 | style2"""
        if not isinstance(other, StyleContext):
            return NotImplemented
        return StyleContext._from_parts(
            self._actions + other._actions,
            {**self._meta, **other._meta},  # 后者覆盖前者
            self._meta_only and other._meta_only,  # 只有都是 meta_only 时才禁止 CM
        )

    def __enter__(self) -> StyleContext:
        if self._meta_only:
            raise RuntimeError(
                "此样式只能用函数调用式，不支持 context manager:\n"
                "  ✓ tw.w_40(imgui.button)('确定')\n"
                "  ✗ with tw.w_40: ..."
            )
        for push, _ in self._actions:
            push()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        for _, pop in reversed(self._actions):
            pop()

    def __matmul__(self, func: F) -> F:
        """创建样式化组件: styled_fn = style @ fn"""
        return self(func)

    def __call__(self, func: F) -> F:
        """创建样式化组件: styled_fn = style(fn)

        支持两种等价语法:
            tw.p_4(ly.card)("my_card", height=10)
            (tw.p_4 @ ly.card)("my_card", height=10)

        可组合多个样式:
            (tw.p_4 | tw.bg_abyss_800)(ly.card)("my_card")

        元数据注入:
            (tw.w_40 | tw.h_9)(imgui.button)("确定")
            # 元数据 width=160, height=36 会注入到 kwargs

        可保存为 styled 组件:
            styled_card = tw.card_style(ly.card)
            styled_card("card1", height=10)
        """
        meta = self._meta
        actions = self._actions

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 注入元数据 (不覆盖显式传入的值)
            for key, value in meta.items():
                if key not in kwargs:
                    kwargs[key] = value
            # 直接执行 push/pop，不走 __enter__ (避免 meta_only 检查)
            for push, _ in actions:
                push()
            try:
                return func(*args, **kwargs)
            finally:
                for _, pop in reversed(actions):
                    pop()

        wrapper.__name__ = getattr(func, '__name__', 'styled')
        return wrapper  # type: ignore

    def __bool__(self) -> bool:
        return len(self._actions) > 0 or bool(self._meta)


# =============================================================================
# 底层构建函数 (供 codegen 和内部使用)
# =============================================================================


def text(color: RGBA) -> StyleContext:
    """文字颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_TEXT, *color),
        lambda: imgui.pop_style_color()
    )


def text_disabled(color: RGBA) -> StyleContext:
    """禁用文字颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_TEXT_DISABLED, *color),
        lambda: imgui.pop_style_color()
    )


def bg(color: RGBA) -> StyleContext:
    """子窗口背景颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, *color),
        lambda: imgui.pop_style_color()
    )


def window_bg(color: RGBA) -> StyleContext:
    """窗口背景颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, *color),
        lambda: imgui.pop_style_color()
    )


def popup_bg(color: RGBA) -> StyleContext:
    """弹窗背景颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_POPUP_BACKGROUND, *color),
        lambda: imgui.pop_style_color()
    )


def frame_bg(color: RGBA) -> StyleContext:
    """Frame 背景颜色 (输入框等)"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, *color),
        lambda: imgui.pop_style_color()
    )


def frame_bg_hovered(color: RGBA) -> StyleContext:
    """Frame 悬停背景"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_HOVERED, *color),
        lambda: imgui.pop_style_color()
    )


def frame_bg_active(color: RGBA) -> StyleContext:
    """Frame 激活背景"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_ACTIVE, *color),
        lambda: imgui.pop_style_color()
    )


def border(color: RGBA) -> StyleContext:
    """边框颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_BORDER, *color),
        lambda: imgui.pop_style_color()
    )


def button(normal: RGBA, hovered: RGBA | None = None, active: RGBA | None = None) -> StyleContext:
    """按钮颜色"""
    colors: list[tuple[int, RGBA]] = [(imgui.COLOR_BUTTON, normal)]
    if hovered:
        colors.append((imgui.COLOR_BUTTON_HOVERED, hovered))
    if active:
        colors.append((imgui.COLOR_BUTTON_ACTIVE, active))

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


def header(normal: RGBA, hovered: RGBA | None = None, active: RGBA | None = None) -> StyleContext:
    """Header 颜色 (树节点、表头、Selectable)"""
    colors: list[tuple[int, RGBA]] = [(imgui.COLOR_HEADER, normal)]
    if hovered:
        colors.append((imgui.COLOR_HEADER_HOVERED, hovered))
    if active:
        colors.append((imgui.COLOR_HEADER_ACTIVE, active))

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


def btn_ghost(hovered: RGBA, active: RGBA | None = None) -> StyleContext:
    """Ghost 按钮样式 - 透明背景，悬停/激活时显示颜色

    用法:
        with styles.btn_ghost(ABYSS[700], ABYSS[800]):
            if imgui.button(FA_PLUS):
                ...
    """
    TRANSPARENT = (0.0, 0.0, 0.0, 0.0)
    colors: list[tuple[int, RGBA]] = [
        (imgui.COLOR_BUTTON, TRANSPARENT),
        (imgui.COLOR_BUTTON_HOVERED, hovered),
        (imgui.COLOR_BUTTON_ACTIVE, active or hovered),
    ]

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


def selectable_style(
    header_color: RGBA,
    header_hovered: RGBA | None = None,
    header_active: RGBA | None = None,
    text_color: RGBA | None = None,
) -> StyleContext:
    """Selectable 样式组合

    用法:
        with styles.selectable_style(CRYSTAL[600], CRYSTAL[500], text_color=PARCHMENT[50]):
            if imgui.selectable("Item", is_selected)[0]:
                ...
    """
    colors: list[tuple[int, RGBA]] = [(imgui.COLOR_HEADER, header_color)]
    if header_hovered:
        colors.append((imgui.COLOR_HEADER_HOVERED, header_hovered))
    if header_active:
        colors.append((imgui.COLOR_HEADER_ACTIVE, header_active or header_color))
    if text_color:
        colors.append((imgui.COLOR_TEXT, text_color))

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


def scrollbar(bg_color: RGBA | None = None, grab: RGBA | None = None) -> StyleContext:
    """滚动条颜色"""
    colors: list[tuple[int, RGBA]] = []
    if bg_color:
        colors.append((imgui.COLOR_SCROLLBAR_BACKGROUND, bg_color))
    if grab:
        colors.append((imgui.COLOR_SCROLLBAR_GRAB, grab))

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


def separator(color: RGBA) -> StyleContext:
    """分隔线颜色"""
    return StyleContext(
        lambda: imgui.push_style_color(imgui.COLOR_SEPARATOR, *color),
        lambda: imgui.pop_style_color()
    )


# =============================================================================
# 间距和尺寸
# =============================================================================


def item_spacing(x: float | None = None, y: float | None = None) -> StyleContext:
    """项目间距 (运行时应用 DPI 缩放)

    Args:
        x: 水平间距，None 则保持当前值
        y: 垂直间距，None 则保持当前值
    """
    def push():
        style = imgui.get_style()
        d = dpi_scale()
        x_val = x * d if x is not None else style.item_spacing.x
        y_val = y * d if y is not None else style.item_spacing.y
        imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (x_val, y_val))
    return StyleContext(push, lambda: imgui.pop_style_var())


def item_inner_spacing(x: float | None = None, y: float | None = None) -> StyleContext:
    """项目内间距 (运行时应用 DPI 缩放)

    Args:
        x: 水平内间距，None 则保持当前值
        y: 垂直内间距，None 则保持当前值
    """
    def push():
        style = imgui.get_style()
        d = dpi_scale()
        x_val = x * d if x is not None else style.item_inner_spacing.x
        y_val = y * d if y is not None else style.item_inner_spacing.y
        imgui.push_style_var(imgui.STYLE_ITEM_INNER_SPACING, (x_val, y_val))
    return StyleContext(push, lambda: imgui.pop_style_var())


def frame_padding(x: float | None = None, y: float | None = None) -> StyleContext:
    """Frame 内边距 - 控制按钮、输入框等 Frame 控件的内边距 (运行时应用 DPI 缩放)

    Args:
        x: 水平内边距，None 则保持当前值
        y: 垂直内边距，None 则保持当前值

    用法:
        frame_padding(8, 8)  # 同时设置 x 和 y
        frame_padding(8)     # 只设置 x，y 保持当前值
        frame_padding(y=4)   # 只设置 y，x 保持当前值
    """
    def push():
        style = imgui.get_style()
        d = dpi_scale()
        x_val = x * d if x is not None else style.frame_padding.x
        y_val = y * d if y is not None else style.frame_padding.y
        imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (x_val, y_val))
    return StyleContext(push, lambda: imgui.pop_style_var())



def window_padding(x: float | None = None, y: float | None = None) -> StyleContext:
    """窗口内边距 (运行时应用 DPI 缩放)

    Args:
        x: 水平内边距，None 则保持当前值
        y: 垂直内边距，None 则保持当前值

    用法:
        window_padding(8, 8)  # 同时设置 x 和 y
        window_padding(8)     # 只设置 x，y 保持当前值
        window_padding(y=4)   # 只设置 y，x 保持当前值
    """
    def push():
        style = imgui.get_style()
        d = dpi_scale()
        x_val = x * d if x is not None else style.window_padding.x
        y_val = y * d if y is not None else style.window_padding.y
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (x_val, y_val))
    return StyleContext(push, lambda: imgui.pop_style_var())



def menubar_style(py_val: float = 4, px_val: float = 8, gap: float = 4) -> StyleContext:
    """Menu bar 样式 - 需要在 begin_main_menu_bar 之前应用

    设置:
    - WindowPadding: menu bar 左右内边距 (不设置垂直，因为会导致按钮被裁切)
    - FramePadding: 按钮内边距 (这个决定了 menu bar 高度和按钮文字垂直居中)
    - ItemSpacing: 按钮间距

    Args:
        py_val: 垂直内边距 (px) - 应用于按钮内部
        px_val: 水平内边距 (px) - 应用于按钮内部和 menu bar 左右
        gap: 按钮间距 (px)
    """
    def push():
        d = dpi_scale()
        # Menu bar 的 WindowPadding.y 必须为 0，否则按钮会被上下裁切
        # 只设置左右边距
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (px_val * d, 0))
        # Frame padding 决定按钮内边距和 menu bar 高度
        # 这是让按钮文字垂直居中的关键
        imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (px_val * d, py_val * d))
        # Item spacing 影响按钮间距
        imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (gap * d, 0))

    return StyleContext(push, lambda: imgui.pop_style_var(3))


def cell_padding(x: float | None = None, y: float | None = None) -> StyleContext:
    """表格单元格内边距 (运行时应用 DPI 缩放)

    Args:
        x: 水平内边距，None 则保持当前值
        y: 垂直内边距，None 则保持当前值
    """
    def push():
        style = imgui.get_style()
        d = dpi_scale()
        x_val = x * d if x is not None else style.cell_padding.x
        y_val = y * d if y is not None else style.cell_padding.y
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (x_val, y_val))
    return StyleContext(push, lambda: imgui.pop_style_var())


def indent_spacing(amount: float) -> StyleContext:
    """缩进量 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_INDENT_SPACING, amount * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


# =============================================================================
# 尺寸控制 (宽高)
# =============================================================================

# 存储当前 push 的宽度 (用于 width context)
_width_stack: list[float] = []
_height_stack: list[float] = []


def width(px: float) -> StyleContext:
    """控件宽度 (运行时应用 DPI 缩放)

    用法:
        with tw.w_40:  # 160px
            imgui.button("OK")

    注意: 这会设置 push_item_width，影响后续控件宽度
    """
    def push():
        w = px * dpi_scale()
        _width_stack.append(w)
        imgui.push_item_width(w)

    def pop():
        _width_stack.pop()
        imgui.pop_item_width()

    return StyleContext(push, pop)


def height(px: float) -> StyleContext:
    """控件高度提示 (运行时应用 DPI 缩放)

    用法:
        with tw.h_10:  # 40px
            # height 会被存储，供 sized_button 等使用
            pass

    注意: ImGui 没有通用的 push_item_height，这只是存储值供 helper 使用
    """
    def push():
        h = px * dpi_scale()
        _height_stack.append(h)

    def pop():
        _height_stack.pop()

    return StyleContext(push, pop)


def get_current_width() -> float | None:
    """获取当前 push 的宽度"""
    return _width_stack[-1] if _width_stack else None


def get_current_height() -> float | None:
    """获取当前 push 的高度"""
    return _height_stack[-1] if _height_stack else None


def size_meta(
    *,
    width: float | None = None,
    height: float | None = None,
) -> StyleContext:
    """创建尺寸元数据样式 (纯元数据，禁止 context manager)

    元数据会在函数调用时注入到 kwargs，用于 imgui.button 等接受
    width/height 参数的函数。

    Args:
        width: 宽度 (Tailwind 单位, 1 = 4px)
        height: 高度 (Tailwind 单位, 1 = 4px)

    用法:
        # 通过 tw.py 的预设使用
        (tw.w_40 | tw.h_9)(imgui.button)("确定")

        # 直接创建
        size_meta(width=40, height=9)(imgui.button)("确定")
        # 等价于: imgui.button("确定", width=160, height=36)

    注意:
        此样式禁止 context manager，因为尺寸只能通过函数调用注入。
        with tw.w_40:  # ❌ RuntimeError
            imgui.button("确定")
    """
    d = dpi_scale()
    meta: dict[str, float] = {}
    if width is not None:
        meta['width'] = width * 4 * d
    if height is not None:
        meta['height'] = height * 4 * d
    return StyleContext.from_meta(**meta)


# =============================================================================
# 圆角
# =============================================================================


def rounding(radius: float) -> StyleContext:
    """全局圆角 (运行时应用 DPI 缩放)"""
    def push() -> None:
        r = radius * dpi_scale()
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, r)
        imgui.push_style_var(imgui.STYLE_CHILD_ROUNDING, r)
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, r)
        imgui.push_style_var(imgui.STYLE_POPUP_ROUNDING, r)
        imgui.push_style_var(imgui.STYLE_SCROLLBAR_ROUNDING, r)
        imgui.push_style_var(imgui.STYLE_GRAB_ROUNDING, r)
        imgui.push_style_var(imgui.STYLE_TAB_ROUNDING, r)

    return StyleContext(push, lambda: imgui.pop_style_var(7))


def frame_rounding(radius: float) -> StyleContext:
    """Frame 圆角 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, radius * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def window_rounding(radius: float) -> StyleContext:
    """窗口圆角 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, radius * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def child_rounding(radius: float) -> StyleContext:
    """子窗口圆角 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_CHILD_ROUNDING, radius * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def popup_rounding(radius: float) -> StyleContext:
    """弹窗圆角 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_POPUP_ROUNDING, radius * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def tab_rounding(radius: float) -> StyleContext:
    """Tab 圆角 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_TAB_ROUNDING, radius * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def tab_colors(
    normal: RGBA,
    hovered: RGBA,
    active: RGBA,
    unfocused: RGBA | None = None,
    unfocused_active: RGBA | None = None,
) -> StyleContext:
    """Tab 颜色样式

    Args:
        normal: 普通状态颜色
        hovered: 悬停状态颜色
        active: 激活/选中状态颜色
        unfocused: 失焦状态颜色 (可选)
        unfocused_active: 失焦但激活状态颜色 (可选)
    """
    colors: list[tuple[int, RGBA]] = [
        (imgui.COLOR_TAB, normal),
        (imgui.COLOR_TAB_HOVERED, hovered),
        (imgui.COLOR_TAB_ACTIVE, active),
    ]
    if unfocused:
        colors.append((imgui.COLOR_TAB_UNFOCUSED, unfocused))
    if unfocused_active:
        colors.append((imgui.COLOR_TAB_UNFOCUSED_ACTIVE, unfocused_active))

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


def checkbox_colors(
    frame_bg: RGBA,
    frame_bg_hovered: RGBA,
    checkmark: RGBA,
) -> StyleContext:
    """Checkbox 颜色样式"""
    colors: list[tuple[int, RGBA]] = [
        (imgui.COLOR_FRAME_BACKGROUND, frame_bg),
        (imgui.COLOR_FRAME_BACKGROUND_HOVERED, frame_bg_hovered),
        (imgui.COLOR_CHECK_MARK, checkmark),
    ]

    def push() -> None:
        for key, c in colors:
            imgui.push_style_color(key, *c)

    return StyleContext(push, lambda: imgui.pop_style_color(len(colors)))


# =============================================================================
# 边框与透明度
# =============================================================================


def border_size(size: float) -> StyleContext:
    """边框粗细 (运行时应用 DPI 缩放)"""
    def push() -> None:
        s = size * dpi_scale()
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, s)
        imgui.push_style_var(imgui.STYLE_CHILD_BORDERSIZE, s)
        imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, s)
        imgui.push_style_var(imgui.STYLE_POPUP_BORDERSIZE, s)

    return StyleContext(push, lambda: imgui.pop_style_var(4))


def frame_border_size(size: float) -> StyleContext:
    """Frame 边框粗细 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, size * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def child_border_size(size: float) -> StyleContext:
    """Child window 边框粗细 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_CHILD_BORDERSIZE, size * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def popup_border(size: float) -> StyleContext:
    """Popup 边框粗细 (运行时应用 DPI 缩放)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_POPUP_BORDERSIZE, size * dpi_scale()),
        lambda: imgui.pop_style_var()
    )


def alpha(value: float) -> StyleContext:
    """全局透明度 (0-1)"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_ALPHA, value),
        lambda: imgui.pop_style_var()
    )


# =============================================================================
# 对齐
# =============================================================================


def button_text_align(x: float = 0.5, y: float = 0.5) -> StyleContext:
    """按钮文字对齐"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_BUTTON_TEXT_ALIGN, (x, y)),
        lambda: imgui.pop_style_var()
    )


def selectable_text_align(x: float = 0.0, y: float = 0.5) -> StyleContext:
    """Selectable 文字对齐"""
    return StyleContext(
        lambda: imgui.push_style_var(imgui.STYLE_SELECTABLE_TEXT_ALIGN, (x, y)),
        lambda: imgui.pop_style_var()
    )


# =============================================================================
# 字体
# =============================================================================

_font_set: FontSet | None = None


def set_font_set(fonts: FontSet) -> None:
    """设置字体集 (由 fonts.py 调用)"""
    global _font_set
    _font_set = fonts


# 用于跟踪 font() push 是否成功
_font_push_stack: list[bool] = []


def font(size: str) -> StyleContext:
    """字体大小: "xs", "sm", "md", "lg", "xl"

    注意: 动态获取字体，支持运行时字体重载
    """
    def push():
        if _font_set is not None:
            font_obj = _font_set.get(size)
            if font_obj is not None:
                imgui.push_font(font_obj)
                _font_push_stack.append(True)
                return
        _font_push_stack.append(False)

    def pop():
        if _font_push_stack and _font_push_stack.pop():
            imgui.pop_font()

    return StyleContext(push, pop)


# =============================================================================
# 便捷工具
# =============================================================================


def when(condition: bool, ctx: StyleContext) -> StyleContext:
    """条件样式

    用法:
        with tw.text_green_500 if is_ok else tw.text_red_500:
            ...

        # 或使用 when:
        with when(is_ok, tw.text_green_500):
            ...
    """
    return ctx if condition else StyleContext.empty()


def combine(*contexts: StyleContext) -> StyleContext:
    """组合多个样式

    等价于 ctx1 | ctx2 | ctx3
    """
    if not contexts:
        return StyleContext.empty()
    result = contexts[0]
    for ctx in contexts[1:]:
        result = result | ctx
    return result


@contextmanager
def push_id(id_str: str):
    """ID 作用域"""
    imgui.push_id(id_str)
    try:
        yield
    finally:
        imgui.pop_id()


def noop() -> StyleContext:
    """空操作样式 - 不做任何事

    用法:
        style = tw.btn_primary if is_primary else styles.noop()
        with style:
            imgui.button("按钮")
    """
    return StyleContext.empty()


# 禁用状态透明度
_DISABLED_ALPHA = 0.4


def disabled() -> StyleContext:
    """禁用区域 - 使用 alpha 模拟禁用状态

    用法:
        with styles.disabled():
            imgui.button("不可点击")

        # 可组合
        with tw.text_parchment_300 | styles.disabled():
            imgui.button("不可点击")
    """
    return alpha(_DISABLED_ALPHA)


def disabled_if(condition: bool) -> StyleContext:
    """条件禁用 - 使用 alpha 模拟禁用状态

    用法:
        with styles.disabled_if(not can_operate):
            if imgui.button("删除"):
                ...

        # 可组合
        with tw.text_parchment_300 | styles.disabled_if(is_locked):
            imgui.button("编辑")
    """
    return alpha(_DISABLED_ALPHA) if condition else StyleContext.empty()


@contextmanager
def group():
    """分组 (BeginGroup/EndGroup)"""
    imgui.begin_group()
    try:
        yield
    finally:
        imgui.end_group()


@contextmanager
def clip_rect(x1: float, y1: float, x2: float, y2: float, intersect: bool = True):
    """裁剪区域"""
    draw_list = imgui.get_window_draw_list()
    draw_list.push_clip_rect(x1, y1, x2, y2, intersect)
    try:
        yield
    finally:
        draw_list.pop_clip_rect()


@contextmanager
def text_wrap_pos(wrap_pos: float = 0.0):
    """文本换行位置 (0 = 窗口右边缘)"""
    imgui.push_text_wrap_pos(wrap_pos)
    try:
        yield
    finally:
        imgui.pop_text_wrap_pos()


@contextmanager
def item_width(width: float):
    """控件宽度"""
    imgui.push_item_width(width)
    try:
        yield
    finally:
        imgui.pop_item_width()


def scaled(px: float) -> float:
    """返回 DPI 缩放后的像素值

    用于需要精确像素值的场景：
        button_width = styles.scaled(144)
        imgui.button("OK", width=button_width)
    """
    return px * dpi_scale()


# =============================================================================
# 语义化文字绘制函数
# ⚠️ DEPRECATED: 请使用 tw.text_* tokens 代替
#   text_secondary -> with tw.text_muted: imgui.text(...)
#   text_success   -> with tw.text_success: imgui.text(...)
#   text_error     -> with tw.text_danger: imgui.text(...)
# =============================================================================

# 语义颜色定义 (使用 Tailwind 色板)
_SEMANTIC_COLORS: dict[str, RGBA] = {
    "secondary": (0.3922, 0.4549, 0.5451, 1.0),  # slate-500
    "muted": (0.3922, 0.4549, 0.5451, 1.0),      # slate-500
    "success": (0.1333, 0.7725, 0.3686, 1.0),    # green-500
    "warning": (0.9804, 0.5490, 0.0235, 1.0),    # amber-500
    "error": (0.9373, 0.2667, 0.2667, 1.0),      # red-500
    "danger": (0.9373, 0.2667, 0.2667, 1.0),     # red-500
    "accent": (0.2314, 0.5098, 0.9647, 1.0),     # blue-500
    "info": (0.2314, 0.5098, 0.9647, 1.0),       # blue-500
}


def text_secondary(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_muted: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["secondary"])


def text_muted(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_muted: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["muted"])


def text_success(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_success: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["success"])


def text_warning(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_warning: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["warning"])


def text_error(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_danger: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["error"])


def text_danger(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_danger: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["danger"])


def text_accent(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_primary: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["accent"])


def text_info(text: str) -> None:
    """[DEPRECATED] 请使用 with tw.text_info: imgui.text(...)"""
    imgui.text_colored(text, *_SEMANTIC_COLORS["info"])


def get_semantic_color(name: str) -> RGBA:
    """[DEPRECATED] 请使用 tw.py 中的颜色常量"""
    return _SEMANTIC_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))


def get_current_theme_colors() -> dict[str, RGBA]:
    """[DEPRECATED] 请使用 tw.py 中的颜色 tokens"""
    return {
        "text_secondary": _SEMANTIC_COLORS["secondary"],
        "success": _SEMANTIC_COLORS["success"],
        "warning": _SEMANTIC_COLORS["warning"],
        "error": _SEMANTIC_COLORS["error"],
        "accent": _SEMANTIC_COLORS["accent"],
        # Badge 颜色 (简化版)
        "badge_subcat": (0.2314, 0.5098, 0.9647, 0.2),   # blue-500 @ 20%
        "badge_tag": (0.1333, 0.7725, 0.3686, 0.2),      # green-500 @ 20%
        "badge_quality": (0.9804, 0.5490, 0.0235, 0.2),  # amber-500 @ 20%
        "badge_special": (0.9804, 0.2941, 0.0824, 0.2),  # orange-600 @ 20%
        "badge_hover_remove": (0.9373, 0.2667, 0.2667, 0.2),  # red-500 @ 20%
        "badge_hover_locked": (0.3922, 0.4549, 0.5451, 0.2),  # slate-500 @ 20%
    }


# =============================================================================
# 尺寸系统 (旧版 Grid 系统)
# ⚠️ DEPRECATED: 请使用 ly.sz() / Tailwind 单位系统代替
#   em(4)    -> ly.sz(4) 或直接使用 Tailwind 单位
#   span(3)  -> ly.sz(40) 即 160px
#   input_m  -> tw.w_32 或 ly.sz(32)
# =============================================================================

# 默认基础字号 (sm = 14px)
_DEFAULT_FONT_SIZE = 14.0


def em(n: float) -> float:
    """[DEPRECATED] 请使用 ly.sz() 代替"""
    return n * _DEFAULT_FONT_SIZE * dpi_scale()


def span(n: int) -> float:
    """[DEPRECATED] 请使用 ly.sz() 代替"""
    GRID_COL = 3.5
    GRID_GAP = 0.5
    return em(n * GRID_COL + max(0, n - 1) * GRID_GAP)


# ===== [DEPRECATED] 输入框宽度常量 (em 单位) =====
INPUT_XS = 5     # 2 CJK字符
INPUT_S  = 6     # 4 数字字符
INPUT_M  = 8     # 6 混合字符 (负数+小数)
INPUT_L  = 12    # 12 拉丁字符 (ID/名称)
INPUT_XL = 18    # 21 拉丁字符 (长技能名)

# ===== [DEPRECATED] Grid 常量 (em 单位) =====
GRID_COL = 3.5   # 基础列宽
GRID_GAP = 0.5   # 列间距
GRID_DEBUG = False

# ===== [DEPRECATED] Span 语义别名 =====
SPAN_INPUT = 2
SPAN_BADGE = 1
SPAN_ID = 4

# ===== [DEPRECATED] 间距常量 (em 单位) =====
GAP_XS = 0.25
GAP_S  = 0.5
GAP_M  = 1.0
GAP_L  = 1.5


# ===== [DEPRECATED] 输入框宽度函数 (返回像素) =====
def input_xs() -> float: return em(INPUT_XS)
def input_s() -> float: return em(INPUT_S)
def input_m() -> float: return em(INPUT_M)
def input_l() -> float: return em(INPUT_L)
def input_xl() -> float: return em(INPUT_XL)


# ===== [DEPRECATED] 间距函数 (返回像素) =====
def gap_xs() -> float: return em(GAP_XS)
def gap_s() -> float: return em(GAP_S)
def gap_m() -> float: return em(GAP_M)
def gap_l() -> float: return em(GAP_L)


# ===== [DEPRECATED] Grid 函数 (返回像素) =====
def grid_col() -> float: return em(GRID_COL)
def grid_gap() -> float: return em(GRID_GAP)


# =============================================================================
# Preflight - 样式重置 (类似 Tailwind preflight / CSS reset)
# =============================================================================


def apply_preflight() -> None:
    """ImGui 样式重置 (类似 Tailwind preflight / CSS reset)

    将所有 ImGui 样式归零，提供干净的起点。
    之后用 tw tokens 组合具体样式：

        apply_preflight()  # 重置

        with tw.bg_slate_900 | tw.text_slate_200 | tw.p_4 | tw.rounded_md:
            imgui.text("Hello!")

    重置内容：
    - 间距: 0
    - 圆角: 0
    - 边框: 0
    - 颜色: 中性灰 (可读但无风格)
    """
    style = imgui.get_style()
    dpi = dpi_scale()

    # === 间距 - 全部归零 ===
    style.window_padding = (0, 0)
    style.frame_padding = (0, 0)
    style.cell_padding = (0, 0)
    style.item_spacing = (0, 0)
    style.item_inner_spacing = (0, 0)
    style.touch_extra_padding = (0, 0)
    style.indent_spacing = 0
    style.scrollbar_size = 14 * dpi  # 滚动条需要最小尺寸才能用
    style.grab_min_size = 10 * dpi   # 抓取手柄需要最小尺寸
    style.window_min_size = (1, 1)   # 最小窗口尺寸

    # === 圆角 - 全部归零 ===
    style.window_rounding = 0
    style.child_rounding = 0
    style.frame_rounding = 0
    style.popup_rounding = 0
    style.scrollbar_rounding = 0
    style.grab_rounding = 0
    style.tab_rounding = 0

    # === 边框 - 全部归零 ===
    style.window_border_size = 0
    style.child_border_size = 0
    style.frame_border_size = 0
    style.popup_border_size = 0
    style.tab_border_size = 0

    # === 透明度/Alpha ===
    style.alpha = 1.0

    # === 对齐 ===
    style.window_title_align = (0.0, 0.5)
    style.button_text_align = (0.5, 0.5)
    style.selectable_text_align = (0.0, 0.0)

    # === 颜色 - 纯中性黑白灰 (真正的 preflight/reset) ===
    # 只有纯黑、纯灰、纯白，不带任何色调
    black = (0.0, 0.0, 0.0, 1.0)
    gray_900 = (0.1, 0.1, 0.1, 1.0)
    gray_800 = (0.2, 0.2, 0.2, 1.0)
    gray_700 = (0.3, 0.3, 0.3, 1.0)
    gray_500 = (0.5, 0.5, 0.5, 1.0)
    gray_300 = (0.7, 0.7, 0.7, 1.0)
    white = (1.0, 1.0, 1.0, 1.0)
    transparent = (0.0, 0.0, 0.0, 0.0)

    c = style.colors
    c[imgui.COLOR_TEXT] = white
    c[imgui.COLOR_TEXT_DISABLED] = gray_500
    c[imgui.COLOR_WINDOW_BACKGROUND] = black
    c[imgui.COLOR_CHILD_BACKGROUND] = transparent
    c[imgui.COLOR_POPUP_BACKGROUND] = gray_900
    c[imgui.COLOR_BORDER] = gray_700
    c[imgui.COLOR_BORDER_SHADOW] = transparent
    c[imgui.COLOR_FRAME_BACKGROUND] = gray_800
    c[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = gray_700
    c[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = gray_500
    c[imgui.COLOR_TITLE_BACKGROUND] = black
    c[imgui.COLOR_TITLE_BACKGROUND_ACTIVE] = gray_800
    c[imgui.COLOR_TITLE_BACKGROUND_COLLAPSED] = black
    c[imgui.COLOR_MENUBAR_BACKGROUND] = black
    c[imgui.COLOR_SCROLLBAR_BACKGROUND] = black
    c[imgui.COLOR_SCROLLBAR_GRAB] = gray_700
    c[imgui.COLOR_SCROLLBAR_GRAB_HOVERED] = gray_500
    c[imgui.COLOR_SCROLLBAR_GRAB_ACTIVE] = gray_300
    c[imgui.COLOR_CHECK_MARK] = white
    c[imgui.COLOR_SLIDER_GRAB] = gray_500
    c[imgui.COLOR_SLIDER_GRAB_ACTIVE] = gray_300
    c[imgui.COLOR_BUTTON] = gray_800
    c[imgui.COLOR_BUTTON_HOVERED] = gray_700
    c[imgui.COLOR_BUTTON_ACTIVE] = gray_500
    c[imgui.COLOR_HEADER] = gray_800
    c[imgui.COLOR_HEADER_HOVERED] = gray_700
    c[imgui.COLOR_HEADER_ACTIVE] = gray_500
    c[imgui.COLOR_SEPARATOR] = gray_700
    c[imgui.COLOR_SEPARATOR_HOVERED] = gray_500
    c[imgui.COLOR_SEPARATOR_ACTIVE] = gray_300
    c[imgui.COLOR_RESIZE_GRIP] = gray_700
    c[imgui.COLOR_RESIZE_GRIP_HOVERED] = gray_500
    c[imgui.COLOR_RESIZE_GRIP_ACTIVE] = gray_300
    c[imgui.COLOR_TAB] = gray_800
    c[imgui.COLOR_TAB_HOVERED] = gray_700
    c[imgui.COLOR_TAB_ACTIVE] = gray_500
    c[imgui.COLOR_TAB_UNFOCUSED] = black
    c[imgui.COLOR_TAB_UNFOCUSED_ACTIVE] = gray_800
    c[imgui.COLOR_PLOT_LINES] = white
    c[imgui.COLOR_PLOT_LINES_HOVERED] = gray_300
    c[imgui.COLOR_PLOT_HISTOGRAM] = white
    c[imgui.COLOR_PLOT_HISTOGRAM_HOVERED] = gray_300
    c[imgui.COLOR_TABLE_HEADER_BACKGROUND] = gray_800
    c[imgui.COLOR_TABLE_BORDER_STRONG] = gray_700
    c[imgui.COLOR_TABLE_BORDER_LIGHT] = gray_800
    c[imgui.COLOR_TABLE_ROW_BACKGROUND] = transparent
    c[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT] = (0.1, 0.1, 0.1, 0.3)
    c[imgui.COLOR_TEXT_SELECTED_BACKGROUND] = (0.5, 0.5, 0.5, 0.35)
    c[imgui.COLOR_DRAG_DROP_TARGET] = white
    c[imgui.COLOR_NAV_HIGHLIGHT] = white
    c[imgui.COLOR_NAV_WINDOWING_HIGHLIGHT] = (1.0, 1.0, 1.0, 0.7)
    c[imgui.COLOR_NAV_WINDOWING_DIM_BACKGROUND] = (0.0, 0.0, 0.0, 0.2)
    c[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0.0, 0.0, 0.0, 0.35)


# 向后兼容别名
def apply_global_style() -> None:
    """[已废弃] 使用 apply_preflight() 代替"""
    apply_preflight()


# =============================================================================
# ThemeMixin (向后兼容)
# ⚠️ DEPRECATED: 请使用 tw.py tokens 代替
# =============================================================================

class ThemeMixin:
    """[DEPRECATED] 主题管理 Mixin - 请使用 tw.py tokens 代替"""

    @property
    def theme_colors(self) -> dict[str, RGBA]:
        """获取当前主题颜色（向后兼容）"""
        return get_current_theme_colors()

    # 便捷方法
    def text_secondary(self, text: str) -> None:
        text_secondary(text)

    def text_success(self, text: str) -> None:
        text_success(text)

    def text_warning(self, text: str) -> None:
        text_warning(text)

    def text_error(self, text: str) -> None:
        text_error(text)

    def text_accent(self, text: str) -> None:
        text_accent(text)
