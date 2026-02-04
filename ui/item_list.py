# -*- coding: utf-8 -*-
"""物品列表和面板 - ItemListMixin

提供物品列表绘制、面板布局功能。
"""

import copy
from typing import TYPE_CHECKING, Any, Callable

import imgui

from ui.styles import gap_s  # type: ignore
from ui.state import state as ui_state
from ui.styles import get_current_theme_colors, text_secondary

from constants import ARMOR_SLOT_LABELS, PRIMARY_LANGUAGE
from models import Armor, Weapon
from hybrid_item_v2 import HybridItemV2

if TYPE_CHECKING:
    from ui.protocols import GUIProtocol

# 混合物品槽位标签
HYBRID_SLOT_LABELS = {
    "consumable": "消耗品",
    "weapon": "武器",
    "armor": "护甲",
}


class ItemListMixin:
    """物品列表 Mixin"""

    def draw_item_panel(
        self: "GUIProtocol",
        panel_id: str,
        items: list,
        current_index_attr: str,
        draw_list_func: Callable[[], None],
        draw_editor_func: Callable[[], None],
        empty_hint: str,
    ) -> None:
        """绘制物品面板（列表 + 编辑器）"""
        available_width = imgui.get_content_region_available_width()
        available_height = imgui.get_content_region_available().y

        # 列表宽度：根据窗口大小自适应，但有合理的最小/最大值
        min_list_width = 180
        max_list_width = 280
        list_width = max(min_list_width, min(max_list_width, available_width * 0.22))
        editor_width = available_width - list_width - 8

        spacing = 4
        padding = gap_s()  # 统一的内边距

        # 左侧: 列表（使用显式 padding 控制）
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (0, 0))
        imgui.begin_child(
            f"{panel_id}ListPanel",
            width=list_width,
            height=available_height,
            border=True,
        )
        imgui.pop_style_var()
        # 顶部 padding（减去 item_spacing.y 避免叠加）
        top_pad = max(0, padding - imgui.get_style().item_spacing.y)
        imgui.dummy(padding, top_pad)
        draw_list_func()
        imgui.end_child()

        imgui.same_line(spacing=spacing)

        # 右侧: 编辑器（使用显式 padding 控制）
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (0, 0))
        imgui.begin_child(
            f"{panel_id}EditorPanel",
            width=editor_width,
            height=available_height,
            border=True,
        )
        imgui.pop_style_var()
        current_index = getattr(ui_state, current_index_attr)
        if 0 <= current_index < len(items):
            # 顶部 padding（减去 item_spacing.y 避免叠加）
            top_pad = max(0, padding - imgui.get_style().item_spacing.y)
            imgui.dummy(padding, top_pad)
            imgui.indent(padding)  # 左侧 padding
            draw_editor_func()
            imgui.unindent()
        else:
            # 居中显示提示
            region = imgui.get_content_region_available()
            hint_size = imgui.calc_text_size(empty_hint)
            imgui.set_cursor_pos(((region.x - hint_size.x) / 2, region.y / 2))
            text_secondary(empty_hint)
        imgui.end_child()

    def draw_weapon_list(self: "GUIProtocol") -> None:
        """绘制武器列表"""
        self._draw_item_list(
            items=ui_state.project.weapons,
            item_class=Weapon,
            current_index_attr="current_weapon_index",
            item_type_label="武器",
            default_name="新武器",
            default_desc="这是新武器的描述",
            default_id_base="请设置武器系统ID",
            get_display_suffix=lambda item: "",
        )

    def draw_armor_list(self: "GUIProtocol") -> None:
        """绘制装备列表"""
        self._draw_item_list(
            items=ui_state.project.armors,
            item_class=Armor,
            current_index_attr="current_armor_index",
            item_type_label="装备",
            default_name="新装备",
            default_desc="这是新装备的描述",
            default_id_base="请设置装备系统ID",
            get_display_suffix=lambda item: f" [{ARMOR_SLOT_LABELS.get(item.slot, item.slot)}]",
        )

    def draw_hybrid_list(self: "GUIProtocol") -> None:
        """绘制混合物品列表"""
        self._draw_item_list(
            items=ui_state.project.hybrid_items,
            item_class=HybridItemV2,
            current_index_attr="current_hybrid_index",
            item_type_label="混合物品",
            default_name="新混合物品",
            default_desc="这是新混合物品的描述",
            default_id_base="请设置混合物品系统ID",
            get_display_suffix=lambda item: f" [{HYBRID_SLOT_LABELS.get(item.slot, item.slot)}]",
        )

    def _draw_item_list(
        self: "GUIProtocol",
        items: list,
        item_class: type,
        current_index_attr: str,
        item_type_label: str,
        default_name: str,
        default_desc: str,
        default_id_base: str,
        get_display_suffix: Callable[[Any], str],
    ) -> None:
        """通用物品列表绘制"""
        current_index = getattr(ui_state, current_index_attr)
        available_width = imgui.get_content_region_available_width()

        # 工具栏：使用语义化中文标签
        # 添加按钮
        if imgui.button(f"添加##{item_type_label}"):
            new_item = item_class()
            new_item.name = self._generate_unique_id(items, default_id_base)
            new_item.localization.set_name(PRIMARY_LANGUAGE, default_name)
            new_item.localization.set_description(PRIMARY_LANGUAGE, default_desc)
            items.append(new_item)
            setattr(ui_state, current_index_attr, len(items) - 1)
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"添加新的{item_type_label}")

        imgui.same_line()

        # 删除按钮
        can_delete = current_index >= 0
        if not can_delete:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if imgui.button(f"删除##{item_type_label}") and can_delete:
            del items[current_index]
            setattr(ui_state, current_index_attr, min(current_index, len(items) - 1))
        if not can_delete:
            imgui.pop_style_var()
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"删除当前选中的{item_type_label}")

        imgui.same_line()

        # 复制按钮
        can_copy = current_index >= 0
        if not can_copy:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if imgui.button(f"复制##{item_type_label}") and can_copy:
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
                new_item.localization.set_name(
                    PRIMARY_LANGUAGE, primary_name + " (副本)"
                )

            items.append(new_item)
            setattr(ui_state, current_index_attr, len(items) - 1)
        if not can_copy:
            imgui.pop_style_var()
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"复制当前选中的{item_type_label}")

        imgui.separator()
        current_index = getattr(ui_state, current_index_attr)

        # 列表项 - 使用 Selectable 替代 TreeNode，更适合列表
        for i, item in enumerate(items):
            display_name = item.localization.get_display_name()
            suffix = get_display_suffix(item) if get_display_suffix else ""

            # 主显示名 + 系统ID（较小）
            is_selected = i == current_index

            # 选中项使用主题色高亮背景，增强视觉对比
            if is_selected:
                imgui.push_style_color(imgui.COLOR_HEADER, *get_current_theme_colors()["accent"])

            # 使用 selectable，宽度填满容器
            if imgui.selectable(
                f"{display_name}##{i}", is_selected, imgui.SELECTABLE_SPAN_ALL_COLUMNS
            )[0]:
                setattr(ui_state, current_index_attr, i)

            if is_selected:
                imgui.pop_style_color()

            # 显示ID和槽位后缀
            if imgui.is_item_hovered():
                imgui.set_tooltip(f"ID: {item.id}{suffix}")

    def _generate_unique_id(self, items, base_id):
        """生成唯一的默认ID"""
        existing = {getattr(item, 'id', getattr(item, 'name', '')) for item in items}
        if base_id not in existing:
            return base_id

        idx = 1
        while True:
            candidate = f"{base_id}_{idx}"
            if candidate not in existing:
                return candidate
            idx += 1
