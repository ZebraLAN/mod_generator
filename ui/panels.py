# -*- coding: utf-8 -*-
"""三栏布局面板系统 - 布局协调器

提供主界面的三栏布局协调：
- 左侧导航栏 (Navigator)
- 中间主编辑区 (Main Editor)
- 右侧属性面板 (Sidebar)

⚠️ 架构原则：面板组件完全自治
    - 本模块只负责计算尺寸、绘制分隔线、调用子面板
    - 不创建容器，不设置样式
    - 每个面板组件自己创建 Child Window 并控制样式

设计理念:
    类似 VS Code / Figma 的经典三栏布局。
    左侧选择"编辑什么"，中间"大空间编辑"，右侧"快速属性"。

    Tailwind 思路:
        <div class="flex h-full">
            <div class="w-50 bg-slate-800">Navigator (自治)</div>
            <div class="w-px bg-slate-600"></div>  <!-- 分隔线 -->
            <div class="flex-1 bg-slate-800">Main (自治)</div>
            <div class="w-px bg-slate-600"></div>  <!-- 分隔线 -->
            <div class="w-65 bg-slate-800">Sidebar (自治)</div>
        </div>

使用方式:
    from ui.panels import draw_three_column_layout

    def draw_main_interface(self):
        draw_three_column_layout(
            draw_navigator=draw_navigator,  # 签名: (width, height) -> None
            draw_main=draw_main_editor,
            draw_sidebar=draw_sidebar,
        )
"""

from __future__ import annotations
from typing import Callable
from contextlib import contextmanager

import imgui

from ui.state import dpi_scale
from ui import tw
from ui import layout as ly


# =============================================================================
# 布局配置 (使用 Tailwind 单位: 1 = 4px)
# =============================================================================

# 面板宽度配置 (Tailwind 单位)
_NAV_WIDTH_DEFAULT = 50   # 导航栏默认宽度 = 200px
_NAV_WIDTH_MIN = 40       # 导航栏最小宽度 = 160px
_NAV_WIDTH_MAX = 75       # 导航栏最大宽度 = 300px

_SIDEBAR_WIDTH_DEFAULT = 65  # 右侧栏默认宽度 = 260px
_SIDEBAR_WIDTH_MIN = 50      # 右侧栏最小宽度 = 200px
_SIDEBAR_WIDTH_MAX = 90      # 右侧栏最大宽度 = 360px

# VS Code 风格：紧贴式布局，无 gap
_PANEL_GAP = 0  # 面板之间的间距 = 0px (用分隔线代替)

# 面板内边距 (Tailwind 单位)
_PANEL_PADDING = 2  # 面板内部边距 = 8px


# =============================================================================
# 面板状态
# =============================================================================

# 运行时面板宽度状态 (Tailwind 单位)
_panel_widths: dict[str, float] = {
    "nav": _NAV_WIDTH_DEFAULT,
    "sidebar": _SIDEBAR_WIDTH_DEFAULT,
}


def get_nav_width() -> float:
    """获取导航栏宽度 (已应用 DPI，返回像素)"""
    return ly.sz(_panel_widths["nav"])


def get_sidebar_width() -> float:
    """获取右侧栏宽度 (已应用 DPI，返回像素)"""
    return ly.sz(_panel_widths["sidebar"])


def set_nav_width(width_tw: float) -> None:
    """设置导航栏宽度 (Tailwind 单位)"""
    _panel_widths["nav"] = max(_NAV_WIDTH_MIN, min(_NAV_WIDTH_MAX, width_tw))


def set_sidebar_width(width_tw: float) -> None:
    """设置右侧栏宽度 (Tailwind 单位)"""
    _panel_widths["sidebar"] = max(_SIDEBAR_WIDTH_MIN, min(_SIDEBAR_WIDTH_MAX, width_tw))


# =============================================================================
# 面板样式预设 (供子面板使用)
# =============================================================================

# 分隔线颜色
_DIVIDER_COLOR = tw.STONE_700

# 标准面板样式 - 供子面板参考使用
# 子面板可以直接使用这个预设，也可以自定义
panel_style = (
    tw.bg_abyss_700 |
    tw.child_rounded_none |  # 直角 - 紧贴边缘
    tw.child_border_size(0) |  # 无边框 - 用分隔线代替
    tw.p_2  # 内部 padding
)


# =============================================================================
# 三栏布局主函数
# =============================================================================

def draw_three_column_layout(
    draw_navigator: Callable[[float, float], None],
    draw_main: Callable[[float, float], None],
    draw_sidebar: Callable[[float, float], None] | None = None,
    show_sidebar: bool = True,
) -> None:
    """绘制三栏布局 - 纯布局协调器

    ⚠️ 架构：面板组件完全自治
        - 本函数只计算尺寸、绘制分隔线、调用子面板
        - 不创建容器，不设置样式
        - 每个子面板函数接收 (width, height) 参数，自己创建 Child Window

    VS Code 风格设计:
        - 直角边缘 (紧贴窗口边缘)
        - 无 gap (用分隔线区分区域)
        - 背景色统一

    Args:
        draw_navigator: 绘制左侧导航栏的函数，签名 (width, height) -> None
        draw_main: 绘制中间主编辑区的函数，签名 (width, height) -> None
        draw_sidebar: 绘制右侧属性面板的函数，签名 (width, height) -> None (可选)
        show_sidebar: 是否显示右侧面板

    布局结构:
        ┌──────────┬────────────────────────────┬──────────┐
        │ Navigator│       Main Editor          │ Sidebar  │
        │  200px   │        flexible            │  260px   │
        │  (自治)  │         (自治)             │  (自治)  │
        └──────────┴────────────────────────────┴──────────┘
    """
    divider_width = 1.0  # 分隔线宽度 (像素)

    # 计算各面板宽度
    available_width = imgui.get_content_region_available_width()
    available_height = imgui.get_content_region_available().y

    nav_width = get_nav_width()
    sidebar_width = get_sidebar_width() if (show_sidebar and draw_sidebar) else 0

    # 计算分隔线数量
    divider_count = 2 if (show_sidebar and draw_sidebar) else 1

    # 中间区域宽度 = 总宽度 - 导航 - 侧边栏 - 分隔线
    main_width = available_width - nav_width - sidebar_width - (divider_width * divider_count)
    main_width = max(main_width, ly.sz(100))  # 最小宽度 400px

    # ===== 左侧导航栏 (自治) =====
    draw_navigator(nav_width, available_height)

    # ===== 分隔线 =====
    imgui.same_line(spacing=0)
    _draw_vertical_divider(available_height)

    # ===== 中间主编辑区 (自治) =====
    imgui.same_line(spacing=0)
    draw_main(main_width, available_height)

    # ===== 右侧属性面板 (自治) =====
    if show_sidebar and draw_sidebar:
        imgui.same_line(spacing=0)
        _draw_vertical_divider(available_height)

        imgui.same_line(spacing=0)
        draw_sidebar(sidebar_width, available_height)


def _draw_vertical_divider(height: float) -> None:
    """绘制垂直分隔线

    Args:
        height: 分隔线高度 (像素)
    """
    draw_list = imgui.get_window_draw_list()
    cursor = imgui.get_cursor_screen_pos()

    # 绘制 1px 宽的垂直线
    draw_list.add_line(
        cursor.x, cursor.y,
        cursor.x, cursor.y + height,
        imgui.get_color_u32_rgba(*_DIVIDER_COLOR),
        1.0
    )

    # 占位 1px 宽度
    imgui.dummy(1, height)


# =============================================================================
# 两栏布局 (用于武器/装备，不显示右侧栏)
# =============================================================================

def draw_two_column_layout(
    draw_navigator: Callable[[float, float], None],
    draw_main: Callable[[float, float], None],
) -> None:
    """绘制两栏布局 (导航 + 主区域)

    Args:
        draw_navigator: 绘制左侧导航栏的函数，签名 (width, height) -> None
        draw_main: 绘制中间主编辑区的函数，签名 (width, height) -> None
    """
    draw_three_column_layout(
        draw_navigator=draw_navigator,
        draw_main=draw_main,
        draw_sidebar=None,
        show_sidebar=False,
    )


# =============================================================================
# 面板内部布局 Helpers
# =============================================================================

@contextmanager
def panel_section(title: str, default_open: bool = True):
    """面板内的可折叠区块

    Tailwind: text-violet-300 (标题颜色)

    Args:
        title: 区块标题
        default_open: 默认是否展开

    用法:
        with panel_section("基本信息"):
            imgui.text("ID: xxx")
    """
    flags = imgui.TREE_NODE_DEFAULT_OPEN if default_open else 0

    # 使用主题色标题
    with tw.text_crystal_300:
        opened = imgui.tree_node(title, flags=flags)

    if opened:
        try:
            imgui.indent(ly.sz(2))  # 8px 缩进
            yield True
            imgui.unindent(ly.sz(2))
        finally:
            imgui.tree_pop()
    else:
        yield False


def panel_label(label: str, value: str = "") -> None:
    """面板内的标签-值对

    Tailwind: 标签 text-stone-400, 值 text-stone-100

    Args:
        label: 标签文字
        value: 值文字 (可选)

    用法:
        panel_label("ID", "sword_001")
        panel_label("状态", "✓ 已验证")
    """
    tw.text_parchment_300(imgui.text)(label)

    if value:
        imgui.same_line()
        tw.text_parchment_100(imgui.text)(value)


def panel_divider() -> None:
    """面板内的分隔线

    Tailwind: border-t border-stone-800, my-1
    """
    ly.gap_y(1)
    with tw.separator_stone_800:
        imgui.separator()
    ly.gap_y(1)


def panel_heading(text: str) -> None:
    """面板内的小标题

    Tailwind: text-violet-400
    """
    tw.text_crystal_400(imgui.text)(text)


def panel_text(text: str) -> None:
    """面板内的普通文字

    Tailwind: text-stone-200
    """
    tw.text_parchment_200(imgui.text)(text)


def panel_text_muted(text: str) -> None:
    """面板内的次要文字

    Tailwind: text-stone-400
    """
    tw.text_parchment_400(imgui.text)(text)


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    # 主布局
    'draw_three_column_layout',
    'draw_two_column_layout',
    # 面板宽度
    'get_nav_width', 'get_sidebar_width',
    'set_nav_width', 'set_sidebar_width',
    # 面板样式
    'panel_style',
    # 面板内部 helpers
    'panel_section', 'panel_label', 'panel_divider',
    'panel_heading', 'panel_text', 'panel_text_muted',
]
