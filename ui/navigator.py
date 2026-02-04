# -*- coding: utf-8 -*-
"""统一导航组件 - 完全自治面板

提供左侧导航栏的完整实现：
- 项目信息头部（固定区域，点击可编辑项目）
- 武器/装备/混合物品列表
- 物品添加/删除/复制操作

⚠️ 架构：面板组件完全自治
    - 本组件自己创建 Child Window 并控制样式
    - 接收 (width, height) 参数
    - panels.py 布局协调器不会为我们创建容器

设计理念:
    使用 ly.hstack/vstack/list_item/collapsible 等 Flex 原语
    代码更声明式，类似 Tailwind + React 组件

    Tailwind: bg-slate-800 rounded-none p-2

视觉风格:
    - 深色主题 (Abyss 系列)
    - 紫水晶强调色 (Crystal)
    - 清晰的层级分隔
    - 精致的交互反馈
"""

from __future__ import annotations
import copy
from typing import Any, Callable, TYPE_CHECKING

import imgui

from ui.state import state as ui_state, dpi_scale
from ui import layout as ly
from ui import tw
from ui import styles
from ui.icons import (
    FA_PLUS, FA_TRASH, FA_COPY, FA_GEM,
    FA_SWORD, FA_SHIELD, FA_FLASK,
    FA_CHEVRON_DOWN, FA_CHEVRON_RIGHT,
)
from constants import ARMOR_SLOT_LABELS, PRIMARY_LANGUAGE
from models import Armor, Weapon
from hybrid_item_v2 import HybridItemV2

if TYPE_CHECKING:
    pass


# =============================================================================
# 设计常量 - Tailwind 单位 (1 unit = 4px)
# =============================================================================

# 间距
SECTION_GAP = 0              # Section 之间无间距，用分隔线区分
ITEM_GAP = 0                 # 物品之间无间距

# 内边距
HEADER_PADDING_X = 3         # 头部水平内边距 (12px)
HEADER_PADDING_Y = 3         # 头部垂直内边距 (12px)
SECTION_PADDING_X = 3        # Section 水平内边距
SECTION_PADDING_Y = 2        # Section 垂直内边距
ITEM_PADDING_X = 4           # 物品左侧缩进 (16px) - 比 section 多一级
ITEM_PADDING_Y = 1.5         # 物品垂直内边距

# 圆角 - 不使用圆角，保持锐利
CARD_ROUNDING = 0
ROW_ROUNDING = 0

# 按钮
TOOLBAR_BTN_SIZE = 5         # 工具栏按钮尺寸 (20px)

# 左侧指示器
INDICATOR_WIDTH = 0.75       # 选中指示器宽度 (3px)


# =============================================================================
# 视觉辅助函数
# =============================================================================

def _draw_left_indicator(state: ly.ListItemState) -> None:
    """绘制左侧选中指示器 (Crystal 色竖条)

    在 list_item 的 with 块之后调用
    """
    draw_list = imgui.get_window_draw_list()

    # 使用 get_item_rect_min/max 获取刚绘制的 item 位置
    item_min = imgui.get_item_rect_min()
    item_max = imgui.get_item_rect_max()

    # 绘制左侧指示器
    indicator_width = ly.sz(INDICATOR_WIDTH)
    draw_list.add_rect_filled(
        item_min.x, item_min.y,
        item_min.x + indicator_width, item_max.y,
        imgui.get_color_u32_rgba(*tw.CRYSTAL_400),
    )


def _draw_separator() -> None:
    """绘制水平分隔线"""
    draw_list = imgui.get_window_draw_list()
    cursor_screen = imgui.get_cursor_screen_pos()
    avail_width = imgui.get_content_region_available().x

    # 分隔线颜色 - 非常微妙
    color = imgui.get_color_u32_rgba(*tw.ABYSS_600)

    y = cursor_screen.y
    draw_list.add_line(
        cursor_screen.x, y,
        cursor_screen.x + avail_width, y,
        color,
        1.0,  # 线宽
    )

    # 移动光标
    imgui.dummy(0, 1)


def _draw_section_separator() -> None:
    """绘制 section 之间的分隔线"""
    imgui.dummy(0, ly.sz(0.5))
    draw_list = imgui.get_window_draw_list()
    cursor_screen = imgui.get_cursor_screen_pos()
    avail_width = imgui.get_content_region_available().x

    # 分隔线颜色 - 比普通分隔线更明显
    color = imgui.get_color_u32_rgba(*tw.ABYSS_600)

    y = cursor_screen.y
    # 留一点边距
    margin = ly.sz(2)
    draw_list.add_line(
        cursor_screen.x + margin, y,
        cursor_screen.x + avail_width - margin, y,
        color,
        1.0,
    )

    imgui.dummy(0, ly.sz(0.5))


# =============================================================================
# 槽位标签
# =============================================================================

HYBRID_SLOT_LABELS = {
    "consumable": "消耗品",
    "weapon": "武器",
    "armor": "护甲",
}


# =============================================================================
# 主导航函数
# =============================================================================

def draw_navigator(width: float, height: float) -> None:
    """绘制导航面板

    ⚠️ 容器类型: Child Window (自己创建和管理)

    Tailwind: bg-slate-800 rounded-none p-2

    Args:
        width: 面板宽度 (像素，已应用 DPI)
        height: 面板高度 (像素，已应用 DPI)
    """
    from ui.panels import panel_style

    # 1. 样式 + 容器 (自治)
    with panel_style:
        imgui.begin_child(
            "NavPanel",
            width=width,
            height=height,
            border=False,
            flags=imgui.WINDOW_NO_SCROLLBAR,
        )

    # 2. 内容
    project = ui_state.project

    # ===== 项目头部 =====
    _draw_project_header()

    # ===== 武器列表 =====
    _draw_section(
        section_id="weapons",
        label="武器",
        icon=FA_SWORD,
        items=project.weapons,
        item_class=Weapon,
        item_type="weapon",
        default_name="新武器",
        default_desc="这是新武器的描述",
        default_id_base="new_weapon",
        get_suffix=lambda item: "",
    )

    _draw_section_separator()

    # ===== 装备列表 =====
    _draw_section(
        section_id="armors",
        label="装备",
        icon=FA_SHIELD,
        items=project.armors,
        item_class=Armor,
        item_type="armor",
        default_name="新装备",
        default_desc="这是新装备的描述",
        default_id_base="new_armor",
        get_suffix=lambda item: f" · {ARMOR_SLOT_LABELS.get(item.slot, item.slot)}",
    )

    _draw_section_separator()

    # ===== 混合物品列表 =====
    _draw_section(
        section_id="hybrids",
        label="混合物品",
        icon=FA_FLASK,
        items=project.hybrid_items,
        item_class=HybridItemV2,
        item_type="hybrid",
        default_name="新混合物品",
        default_desc="这是新混合物品的描述",
        default_id_base="new_hybrid",
        get_suffix=lambda item: f" · {HYBRID_SLOT_LABELS.get(item.slot, item.slot)}",
    )

    # 3. 结束容器
    imgui.end_child()


# =============================================================================
# 项目头部
# =============================================================================

def _draw_project_header() -> None:
    """绘制项目信息头部 - 卡片式设计"""
    project = ui_state.project
    is_active = not ui_state.has_selection()

    # 头部整体背景
    with ly.list_item(
        "project_header",
        selected=is_active,
        padding_x=HEADER_PADDING_X,
        padding_y=HEADER_PADDING_Y,
        rounding=0,
        bg_color=tw.ABYSS_850,           # 比父窗口深
        selected_color=tw.ABYSS_650,     # 选中时变亮
        hover_color=tw.ABYSS_700,        # hover 次亮
    ) as state:
        # 使用 hstack 布局: 图标 + 文字
        with ly.hstack(gap=2.5):
            # 项目图标
            with ly.slot():
                with tw.text_crystal_400:
                    imgui.text(FA_GEM)

            # 项目信息
            with ly.slot():
                with ly.vstack(gap=0.5):
                    # 项目名称
                    ly.item()
                    text_style = tw.text_parchment_50 if is_active else tw.text_parchment_100
                    with text_style:
                        imgui.text(project.name or "未命名项目")

                    # 版本和作者
                    ly.item()
                    with tw.text_parchment_500:
                        author_text = f"v{project.version}"
                        if project.author:
                            author_text += f" · {project.author}"
                        imgui.text(author_text)

    # 选中状态下绘制左侧指示器
    if is_active:
        _draw_left_indicator(state)

    if state.clicked:
        ui_state.clear_selection()

    # 底部分隔线
    _draw_separator()


# =============================================================================
# 可折叠 Section
# =============================================================================

def _draw_section(
    section_id: str,
    label: str,
    icon: str,
    items: list,
    item_class: type,
    item_type: str,
    default_name: str,
    default_desc: str,
    default_id_base: str,
    get_suffix: Callable[[Any], str],
) -> None:
    """绘制可折叠的物品列表区块"""
    is_expanded = ly.get_collapsible_state(section_id, default=True)
    current_index = _get_current_index_for_type(item_type)
    is_section_active = ui_state.nav_item_type == item_type

    chevron = FA_CHEVRON_DOWN if is_expanded else FA_CHEVRON_RIGHT

    # ===== Section Header - 使用 split_row 原语 =====
    with ly.split_row(
        f"section_{section_id}",
        padding_x=SECTION_PADDING_X,
        padding_y=SECTION_PADDING_Y,
        hover_color=tw.ABYSS_650,
        bg_color=None,  # 透明背景
    ) as row:
        # 左侧内容: chevron + icon + label + count
        with row.left:
            with ly.hstack(gap=2):
                # chevron
                with ly.slot():
                    with tw.text_parchment_500:
                        imgui.text(chevron)

                # icon
                with ly.slot():
                    # 图标使用类型对应颜色
                    icon_style = _get_section_icon_style(item_type)
                    with icon_style:
                        imgui.text(icon)

                # label
                with ly.slot():
                    with tw.text_parchment_100:
                        imgui.text(label)

                # count badge
                with ly.slot():
                    with tw.text_parchment_500:
                        imgui.text(f"({len(items)})")

        # 右侧添加按钮 - 使用 row.right 自动右对齐
        with row.right:
            btn_style = styles.btn_ghost(tw.ABYSS_600, tw.ABYSS_500) | tw.text_crystal_400
            if ly.icon_btn(
                FA_PLUS, f"{section_id}_add",
                size=TOOLBAR_BTN_SIZE,
                tooltip_text=f"添加{label}",
                style=btn_style,
            ):
                _add_item(items, item_class, item_type, default_name, default_desc, default_id_base)

    # 点击切换展开状态
    if row.state.clicked:
        ly.set_collapsible_state(section_id, not is_expanded)

    # ===== Section Content =====
    if is_expanded:
        _draw_item_list(
            section_id=section_id,
            items=items,
            item_type=item_type,
            item_class=item_class,
            current_index=current_index,
            is_section_active=is_section_active,
            get_suffix=get_suffix,
            default_name=default_name,
            default_desc=default_desc,
            default_id_base=default_id_base,
        )


def _get_section_icon_style(item_type: str):
    """获取 section 图标的样式 - 每种类型有不同颜色"""
    if item_type == "weapon":
        return tw.text_crystal_400
    elif item_type == "armor":
        return tw.text_goldrim_400
    elif item_type == "hybrid":
        return tw.text_green_400
    return tw.text_parchment_400


def _draw_item_list(
    section_id: str,
    items: list,
    item_type: str,
    item_class: type,
    current_index: int,
    is_section_active: bool,
    get_suffix: Callable[[Any], str],
    default_name: str,
    default_desc: str,
    default_id_base: str,
) -> None:
    """绘制物品列表"""
    if not items:
        # 空状态提示
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + ly.sz(ITEM_PADDING_X))
        ly.gap_y(0.5)
        with tw.text_parchment_600:
            imgui.text("暂无物品，点击 + 添加")
        ly.gap_y(0.5)
        return

    for i, item in enumerate(items):
        is_selected = (i == current_index) and is_section_active
        row_id = f"item_{section_id}_{i}"

        with ly.list_item(
            row_id,
            selected=is_selected,
            padding_x=ITEM_PADDING_X,
            padding_y=ITEM_PADDING_Y,
            rounding=0,
            bg_color=None,               # 透明 (父窗口背景是 ABYSS_700)
            selected_color=tw.ABYSS_600, # 选中最亮
            hover_color=tw.ABYSS_650,    # hover 次亮
        ) as state:
            # 物品名称 + 可选的类型标签
            display_name = item.localization.get_display_name()
            suffix = get_suffix(item) if get_suffix else ""

            with ly.hstack(gap=1):
                # 名称
                with ly.slot():
                    text_style = tw.text_parchment_50 if is_selected else tw.text_parchment_300
                    with text_style:
                        imgui.text(display_name)

                # 类型标签 (如果有)
                if suffix:
                    with ly.slot():
                        with tw.text_parchment_600:
                            imgui.text(suffix)

        # 选中状态绘制左侧指示器
        if is_selected:
            _draw_left_indicator(state)

        if state.clicked:
            ui_state.select_item(item_type, i)

        # Context menu (右键菜单) - 使用样式化原语
        with ly.context_menu(f"ctx_{row_id}") as opened:
            if opened:
                if ly.menu_item("复制", icon=FA_COPY):
                    _copy_item(items, i, item_type)
                ly.menu_separator()
                if ly.menu_item("删除", icon=FA_TRASH, danger=True):
                    _delete_item(items, i, item_type, current_index)

        # Tooltip 显示 ID
        if state.hovered:
            imgui.set_tooltip(f"ID: {item.id}")


# =============================================================================
# 辅助函数
# =============================================================================

def _get_current_index_for_type(item_type: str) -> int:
    """获取指定类型的当前索引"""
    if item_type == "weapon":
        return ui_state.current_weapon_index
    elif item_type == "armor":
        return ui_state.current_armor_index
    elif item_type == "hybrid":
        return ui_state.current_hybrid_index
    return -1


def _add_item(
    items: list,
    item_class: type,
    item_type: str,
    default_name: str,
    default_desc: str,
    default_id_base: str,
) -> None:
    """添加新物品"""
    new_item = item_class()
    new_item.name = _generate_unique_id(items, default_id_base)
    new_item.localization.set_name(PRIMARY_LANGUAGE, default_name)
    new_item.localization.set_description(PRIMARY_LANGUAGE, default_desc)
    items.append(new_item)
    ui_state.select_item(item_type, len(items) - 1)


def _copy_item(items: list, current_index: int, item_type: str) -> None:
    """复制物品"""
    source_item = items[current_index]
    new_item = copy.deepcopy(source_item)

    existing_names = {item.name for item in items}
    base_name = f"{source_item.name}_copy"
    new_name = base_name
    idx = 1
    while new_name in existing_names:
        new_name = f"{base_name}_{idx}"
        idx += 1
    new_item.name = new_name

    primary_name = new_item.localization.get_name(PRIMARY_LANGUAGE)
    if primary_name:
        new_item.localization.set_name(PRIMARY_LANGUAGE, primary_name + " (副本)")

    items.append(new_item)
    ui_state.select_item(item_type, len(items) - 1)


def _delete_item(items: list, index: int, item_type: str, current_index: int) -> None:
    """删除物品"""
    del items[index]
    # 调整选中索引
    if current_index == index:
        # 删除的是当前选中的
        new_idx = min(index, len(items) - 1)
        if new_idx >= 0:
            ui_state.select_item(item_type, new_idx)
        else:
            ui_state.clear_selection()
    elif current_index > index:
        # 删除的在当前选中之前
        ui_state.select_item(item_type, current_index - 1)


def _generate_unique_id(items: list, base_id: str) -> str:
    """生成唯一 ID"""
    existing = {getattr(item, 'id', getattr(item, 'name', '')) for item in items}
    if base_id not in existing:
        return base_id

    idx = 1
    while True:
        candidate = f"{base_id}_{idx}"
        if candidate not in existing:
            return candidate
        idx += 1


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    'draw_navigator',
]
