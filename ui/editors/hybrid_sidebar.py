# -*- coding: utf-8 -*-
"""混合物品右侧边栏

显示混合物品的快速参考信息：
- 身份信息 (ID, 代码名)
- 类型设置 (槽位, 品质)
- 验证状态
- 快捷操作

设计理念:
    右侧边栏只放"快速参考"内容，不放需要大空间的编辑器。
    复杂编辑（属性网格、多选标签等）都在中间主区域。
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import imgui

from ui.state import state as ui_state, dpi_scale
from ui import tw
from ui import layout as ly
from ui.theme import ABYSS, STONE, CRYSTAL, PARCHMENT, BLOOD, GOLDRIM
from ui.panels import panel_section, panel_label, panel_divider, panel_heading, panel_text_muted
from ui.styles import input_m
from hybrid_item_v2 import HybridItemV2
from models import validate_hybrid_item
from specs import (
    quality_from_int,
    CommonQuality, UniqueQuality, ArtifactQuality,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# 槽位和品质标签
# =============================================================================

HYBRID_SLOT_LABELS = {
    "consumable": "消耗品",
    "weapon": "武器",
    "armor": "护甲",
}

HYBRID_QUALITY_LABELS = {
    0: "普通",
    1: "独特",
    2: "神器",
}


# =============================================================================
# 主绘制函数
# =============================================================================

def draw_hybrid_sidebar() -> None:
    """绘制混合物品右侧边栏

    结构:
        ┌─ 身份 ──────────────┐
        │ ID: xxx             │
        │ 代码名: xxx         │
        ├─ 类型 ──────────────┤
        │ 槽位: [消耗品▼]     │
        │ 品质: [普通▼]       │
        ├─ 状态 ──────────────┤
        │ ✓ ID 有效           │
        │ ⚠️ 名称未设置        │
        ├─ 快捷 ──────────────┤
        │ [复制ID] [复制代码] │
        └──────────────────────┘
    """
    current_index = ui_state.current_hybrid_index
    if current_index < 0 or current_index >= len(ui_state.project.hybrid_items):
        _draw_empty_state()
        return

    hybrid = ui_state.project.hybrid_items[current_index]

    # ===== 身份信息 =====
    _draw_identity_section(hybrid)

    ly.gap_y(2)

    # ===== 类型设置 =====
    _draw_type_section(hybrid)

    ly.gap_y(2)

    # ===== 验证状态 =====
    _draw_validation_section(hybrid)


# =============================================================================
# 各区块实现
# =============================================================================

def _draw_empty_state() -> None:
    """未选中物品时的空状态"""
    region = imgui.get_content_region_available()
    imgui.set_cursor_pos((region.x / 2 - 40, region.y / 2))
    imgui.push_style_color(imgui.COLOR_TEXT, *PARCHMENT[300])
    imgui.text("未选中物品")
    imgui.pop_style_color()


def _draw_identity_section(hybrid: HybridItemV2) -> None:
    """身份信息区块"""
    d = dpi_scale()

    with panel_section("身份", default_open=True) as opened:
        if not opened:
            return

        # ID (只读显示)
        panel_label("ID")
        imgui.push_style_color(imgui.COLOR_TEXT, *PARCHMENT[100])
        imgui.text(hybrid.id or "(未设置)")
        imgui.pop_style_color()

        ly.gap_y(1)

        # 代码名 (只读显示)
        panel_label("代码名")
        imgui.push_style_color(imgui.COLOR_TEXT, *PARCHMENT[200])
        imgui.text(hybrid.name or "(未设置)")
        imgui.pop_style_color()

        ly.gap_y(1)

        # 显示名 (本地化)
        display_name = hybrid.localization.get_display_name()
        panel_label("显示名")
        imgui.push_style_color(imgui.COLOR_TEXT, *PARCHMENT[100])
        imgui.text(display_name or "(未设置)")
        imgui.pop_style_color()


def _draw_type_section(hybrid: HybridItemV2) -> None:
    """类型设置区块"""
    d = dpi_scale()

    with panel_section("类型", default_open=True) as opened:
        if not opened:
            return

        # 槽位 (只读显示 - 编辑在中间区域)
        slot_label = HYBRID_SLOT_LABELS.get(hybrid.slot, hybrid.slot)
        panel_label("槽位")
        imgui.push_style_color(imgui.COLOR_TEXT, *CRYSTAL[400])
        imgui.text(slot_label)
        imgui.pop_style_color()

        ly.gap_y(1)

        # 品质 (只读显示)
        quality_int = _get_quality_int(hybrid)
        quality_label = HYBRID_QUALITY_LABELS.get(quality_int, "未知")
        quality_color = _get_quality_color(quality_int)
        panel_label("品质")
        imgui.push_style_color(imgui.COLOR_TEXT, *quality_color)
        imgui.text(quality_label)
        imgui.pop_style_color()

        ly.gap_y(1)

        # 重量 (只读显示)
        panel_label("重量")
        imgui.push_style_color(imgui.COLOR_TEXT, *PARCHMENT[200])
        # weight 可能是 str 或 float
        weight_val = hybrid.weight
        if isinstance(weight_val, str):
            imgui.text(weight_val if weight_val else "0")
        else:
            imgui.text(f"{weight_val:.1f}")
        imgui.pop_style_color()


def _draw_validation_section(hybrid: HybridItemV2) -> None:
    """验证状态区块"""
    d = dpi_scale()

    with panel_section("状态", default_open=True) as opened:
        if not opened:
            return

        # 获取验证结果
        errors = validate_hybrid_item(hybrid, ui_state.project, include_warnings=True)

        if not errors:
            # 全部通过
            imgui.push_style_color(imgui.COLOR_TEXT, 0.2, 0.8, 0.4, 1.0)  # 绿色
            imgui.text("✓ 验证通过")
            imgui.pop_style_color()
        else:
            # 显示错误和警告
            for error in errors[:5]:  # 最多显示 5 条
                if error.startswith("[警告]"):
                    imgui.push_style_color(imgui.COLOR_TEXT, *GOLDRIM[400])
                    imgui.text_wrapped(f"⚠ {error[4:]}")  # 去掉 [警告] 前缀
                    imgui.pop_style_color()
                else:
                    imgui.push_style_color(imgui.COLOR_TEXT, *BLOOD[400])
                    imgui.text_wrapped(f"✗ {error}")
                    imgui.pop_style_color()

            if len(errors) > 5:
                panel_text_muted(f"... 还有 {len(errors) - 5} 条")


# =============================================================================
# 辅助函数
# =============================================================================

def _get_quality_int(hybrid: HybridItemV2) -> int:
    """获取品质整数值"""
    quality = hybrid.quality
    if isinstance(quality, CommonQuality):
        return 0
    elif isinstance(quality, UniqueQuality):
        return 1
    elif isinstance(quality, ArtifactQuality):
        return 2
    return 0


def _get_quality_color(quality_int: int) -> tuple:
    """获取品质对应的颜色"""
    if quality_int == 0:
        return PARCHMENT[200]  # 普通 - 灰白
    elif quality_int == 1:
        return GOLDRIM[400]    # 独特 - 金色
    elif quality_int == 2:
        return CRYSTAL[300]    # 神器 - 紫色
    return PARCHMENT[200]


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    'draw_hybrid_sidebar',
]
