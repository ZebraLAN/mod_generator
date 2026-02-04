# -*- coding: utf-8 -*-
"""混合物品编辑器 - 基础面板

"这是什么物品" - 物品的身份信息和分类

================================================================================
样式设计规范 (完整)
================================================================================

布局结构:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 身份组: [ID] [品质] [等级]                              grid-cols-3     │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                         gap-y = 20px    │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ 物理组: [价格] [重量] [材质]                            grid-cols-3     │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                         gap-y = 20px    │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ 分类组: [主分类▼] + [子分类徽章...]                     flex-wrap       │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                         gap-y = 20px    │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ 标签组: + [品质徽章] [地牢徽章] [国家徽章]...           flex-wrap       │
    └─────────────────────────────────────────────────────────────────────────┘

间距常量 (Tailwind 单位: 1 = 4px):
    SECTION_GAP = 5 (20px) - 分组之间的垂直间距
    LABEL_GAP = 1 (4px) - 标签与输入框之间的间距
    COL_GAP = 4 (16px) - 列之间的间距

控件样式:
    标签: text-parchment-400 (灰色小字)
    输入框: frame-bg-abyss-900 border-abyss-600 rounded-sm
    下拉框: frame-bg-abyss-800 border-abyss-600 rounded-sm
    徽章: btn-abyss rounded-sm p-1 (可移除) / btn-crystal (锁定)

Tailwind 映射:
    grid grid-cols-3 gap-4  → ly.columns(3, gap=4)
    flex flex-wrap gap-2    → same_line() + 手动换行
    text-stone-400 text-sm  → tw.text_parchment_400
    bg-slate-900            → tw.frame_bg_abyss_900
================================================================================
"""

from __future__ import annotations
from contextlib import contextmanager

import imgui

from ui import tw
from ui import layout as ly
from hybrid_item_v2 import HybridItemV2
from constants import (
    HYBRID_QUALITY_LABELS,
    HYBRID_WEIGHT_LABELS,
    HYBRID_MATERIALS,
)
from drop_slot_data import (
    ITEM_CATEGORIES,
    ALL_SUBCATEGORY_OPTIONS,
    CATEGORY_TRANSLATIONS,
    QUALITY_TAGS,
    DUNGEON_TAGS,
    COUNTRY_TAGS,
    EXTRA_TAGS,
)
from specs import quality_to_int, quality_from_int


# =============================================================================
# 间距常量 (Tailwind 单位: 1 = 4px)
# =============================================================================

_SECTION_GAP = 5     # 分组之间的间距 (20px)
_LABEL_GAP = 1       # 标签与输入框间距 (4px)
_COL_GAP = 4         # 列间距 (16px)


# =============================================================================
# 本地辅助组件
# =============================================================================

def _tooltip(text: str) -> None:
    """在前一个控件悬停时显示提示"""
    if text and imgui.is_item_hovered():
        imgui.set_tooltip(text)


def _label(text: str) -> None:
    """字段标签

    Tailwind: text-stone-400 text-sm
    """
    tw.text_parchment_400(imgui.text)(text)


def _enum_combo(label: str, current_value, options: list, labels: dict):
    """值模式下拉框

    返回选中的值而非索引。
    Tailwind: bg-slate-800 border-slate-600 rounded-sm
    """
    current_label = str(labels.get(current_value, current_value))
    new_value = current_value

    # 确保当前值在选项中
    if current_value not in options:
        options = list(options) + [current_value]

    with tw.frame_bg_abyss_800 | tw.border_abyss_600 | tw.rounded_sm:
        if imgui.begin_combo(label, current_label):
            for opt in options:
                display = str(labels.get(opt, opt))
                if imgui.selectable(display, opt == current_value)[0]:
                    new_value = opt
            imgui.end_combo()

    return new_value


def _input_text(label: str, value: str, buffer_size: int = 256) -> tuple[bool, str]:
    """文本输入框

    Tailwind: bg-slate-900 border-slate-600 rounded-sm
    """
    with tw.frame_bg_abyss_900 | tw.border_abyss_600 | tw.rounded_sm:
        return imgui.input_text(label, value, buffer_size)


def _input_int(label: str, value: int, step: int = 1, step_fast: int = 10) -> tuple[bool, int]:
    """整数输入框

    Tailwind: bg-slate-900 border-slate-600 rounded-sm
    """
    with tw.frame_bg_abyss_900 | tw.border_abyss_600 | tw.rounded_sm:
        return imgui.input_int(label, value, step, step_fast)


def _checkbox(label: str, value: bool) -> tuple[bool, bool]:
    """复选框

    Tailwind: bg-slate-800
    """
    with tw.frame_bg_abyss_800:
        return imgui.checkbox(label, value)


def _badge(id_suffix: str, text: str, removable: bool = True) -> bool:
    """徽章组件

    Args:
        id_suffix: 唯一标识符
        text: 显示文本
        removable: 是否可移除

    Returns:
        如果 removable=True, 返回是否被点击 (用于移除)
        否则返回 False
    """
    style = tw.btn_abyss if removable else tw.btn_crystal
    with style | tw.rounded_sm | tw.p_1:
        clicked = imgui.button(f"{text}##{id_suffix}_badge")

    if removable:
        _tooltip("点击移除")
    return clicked and removable


def _locked_badge(id_suffix: str, text: str, reason: str) -> None:
    """锁定徽章 - 不可移除"""
    with tw.btn_crystal | tw.rounded_sm | tw.p_1:
        imgui.button(f"{text}##{id_suffix}_badge")
    _tooltip(f"[{reason}]")


# =============================================================================
# 主入口
# =============================================================================

def draw_base_panel(hybrid: HybridItemV2) -> None:
    """绘制基础面板

    Args:
        hybrid: 混合物品数据对象
    """
    # 固定 parent_object
    hybrid.parent_object = "o_inv_consum"

    # 1. 身份组: ID / 品质 / 等级
    _draw_identity_section(hybrid)

    ly.gap_y(_SECTION_GAP)

    # 2. 物理组: 价格 / 重量 / 材质
    _draw_physical_section(hybrid)

    ly.gap_y(_SECTION_GAP)

    # 3. 分类组: 主分类 / 子分类
    _draw_category_section(hybrid)

    ly.gap_y(_SECTION_GAP)

    # 4. 标签组
    _draw_tags_section(hybrid)


# =============================================================================
# 身份组: ID / 品质 / 等级
# =============================================================================

def _draw_identity_section(hybrid: HybridItemV2) -> None:
    """身份信息: ID、品质、等级

    Tailwind: grid grid-cols-3 gap-4
    """
    with ly.columns(3, gap=_COL_GAP) as cols:
        # === ID ===
        with cols.col(0):
            _label("ID")
            ly.gap_y(_LABEL_GAP)
            imgui.push_item_width(cols.col_width)
            changed, new_id = _input_text("##hybrid_id", hybrid.id)
            imgui.pop_item_width()
            if changed:
                hybrid.id = new_id.lower()
            _tooltip("物品唯一标识符")

        # === 品质 ===
        with cols.col(1):
            _label("品质")
            ly.gap_y(_LABEL_GAP)
            old_quality_int = quality_to_int(hybrid.quality)
            imgui.push_item_width(cols.col_width)
            new_quality_int = _enum_combo(
                "##quality_hybrid",
                old_quality_int,
                list(HYBRID_QUALITY_LABELS.keys()),
                HYBRID_QUALITY_LABELS,
            )
            imgui.pop_item_width()
            # 品质变化时更新相关字段
            if new_quality_int != old_quality_int:
                hybrid.quality = quality_from_int(new_quality_int)
                _on_quality_changed(hybrid)

        # === 等级 ===
        with cols.col(2):
            _label("等级")
            ly.gap_y(_LABEL_GAP)
            quality_int = quality_to_int(hybrid.quality)
            if quality_int == 7:
                # 文物固定 T0
                tw.text_parchment_400(imgui.text)("T0 (文物固定)")
                _tooltip("文物品质固定为等级 0")
            else:
                tier_options = [0, 1, 2, 3, 4, 5]
                tier_labels = {0: "全", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
                imgui.push_item_width(cols.col_width)
                hybrid.tier = _enum_combo(
                    "##tier_hybrid",
                    hybrid.tier,
                    tier_options,
                    tier_labels,
                )
                imgui.pop_item_width()
                _tooltip("用于掉落/商店筛选")


# =============================================================================
# 物理组: 价格 / 重量 / 材质
# =============================================================================

def _draw_physical_section(hybrid: HybridItemV2) -> None:
    """物理/经济属性: 价格、重量、材质

    Tailwind: grid grid-cols-3 gap-4
    """
    with ly.columns(3, gap=_COL_GAP) as cols:
        # === 价格 ===
        with cols.col(0):
            _label("价格")
            ly.gap_y(_LABEL_GAP)
            imgui.push_item_width(cols.col_width)
            changed, new_price = _input_int("##price_hybrid", hybrid.base_price)
            imgui.pop_item_width()
            if changed:
                hybrid.base_price = max(0, new_price)

        # === 重量 ===
        with cols.col(1):
            _label("重量")
            ly.gap_y(_LABEL_GAP)
            imgui.push_item_width(cols.col_width)
            hybrid.weight = _enum_combo(  # type: ignore[assignment]
                "##weight_hybrid",
                hybrid.weight,
                list(HYBRID_WEIGHT_LABELS.keys()),
                HYBRID_WEIGHT_LABELS,
            )
            imgui.pop_item_width()
            _tooltip("影响游泳；护甲时决定类别")

        # === 材质 ===
        with cols.col(2):
            _label("材质")
            ly.gap_y(_LABEL_GAP)
            imgui.push_item_width(cols.col_width)
            hybrid.material = _enum_combo(  # type: ignore[assignment]
                "##material_hybrid",
                hybrid.material,
                list(HYBRID_MATERIALS.keys()),
                HYBRID_MATERIALS,
            )
            imgui.pop_item_width()


# =============================================================================
# 分类组: 主分类 / 子分类
# =============================================================================

def _draw_category_section(hybrid: HybridItemV2) -> None:
    """分类设置: 主分类 + 子分类徽章

    Tailwind: flex flex-col gap-1
    """
    quality_int = quality_to_int(hybrid.quality)
    is_treasure = quality_int == 7

    # 文物强制 treasure 分类
    if is_treasure:
        hybrid.cat = "treasure"
    elif hybrid.cat == "treasure":
        hybrid.cat = ""

    # 构建选项
    available_cats = (
        ["treasure"] if is_treasure
        else [c for c in ITEM_CATEGORIES if c != "treasure"]
    )
    cat_options = (["treasure"] if is_treasure else [""]) + (
        [] if is_treasure else available_cats
    )
    cat_labels = {"": "—"}
    cat_labels.update({c: CATEGORY_TRANSLATIONS.get(c, c) for c in ITEM_CATEGORIES})

    _label("分类")
    ly.gap_y(_LABEL_GAP)

    # 主分类 + 子分类徽章 (同一行)
    # 主分类下拉
    if is_treasure:
        imgui.push_style_var(imgui.STYLE_ALPHA, 0.6)

    imgui.push_item_width(ly.sz(25))  # 100px
    new_cat = _enum_combo(
        "##cat_hybrid", hybrid.cat, cat_options, cat_labels
    )
    imgui.pop_item_width()

    if not is_treasure:
        hybrid.cat = new_cat

    if is_treasure:
        imgui.pop_style_var()

    _tooltip("主分类 (Cat)\n用于掉落表匹配")

    # 同行：添加子分类按钮
    imgui.same_line()
    if (tw.btn_secondary | tw.btn_xs)(imgui.button)("+##add_subcat"):
        imgui.open_popup("subcats_popup")
    _tooltip("添加子分类 (Subcats)\n可多选")

    # 同行：已选子分类徽章
    for subcat in sorted(hybrid.subcats):
        imgui.same_line()
        if _badge(subcat, CATEGORY_TRANSLATIONS.get(subcat, subcat)):
            hybrid.subcats.remove(subcat)
            break  # 避免在迭代时修改列表

    # 子分类 popup
    _draw_subcats_popup(hybrid, is_treasure)


def _draw_subcats_popup(hybrid: HybridItemV2, is_treasure: bool) -> None:
    """子分类选择弹窗"""
    subcat_options = (
        ALL_SUBCATEGORY_OPTIONS if is_treasure
        else [s for s in ALL_SUBCATEGORY_OPTIONS if s != "treasure"]
    )

    # 清理无效子分类
    if "treasure" in hybrid.subcats and not is_treasure:
        hybrid.subcats.remove("treasure")

    if imgui.begin_popup("subcats_popup"):
        for subcat in subcat_options:
            is_selected = subcat in hybrid.subcats
            is_disabled = subcat == hybrid.cat

            if is_disabled:
                imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)

            changed, new_value = _checkbox(
                f"{CATEGORY_TRANSLATIONS.get(subcat, subcat)}##subcat_{subcat}",
                is_selected,
            )

            if changed and not is_disabled:
                if new_value:
                    hybrid.subcats.append(subcat)
                else:
                    hybrid.subcats.remove(subcat)

            if is_disabled:
                imgui.pop_style_var()
        imgui.end_popup()


# =============================================================================
# 标签组
# =============================================================================

def _draw_tags_section(hybrid: HybridItemV2) -> None:
    """标签设置: 品质标签 + 地牢/国家/其他标签

    Tailwind: flex flex-wrap gap-2
    """
    # 品质标签自动更新
    quality_int = quality_to_int(hybrid.quality)
    hybrid.quality_tag = "unique" if quality_int == 6 else ""

    _label("标签")
    ly.gap_y(_LABEL_GAP)

    # 特殊情况: 排除随机生成时只显示 special
    if hybrid.exclude_from_random:
        _locked_badge("special_only", EXTRA_TAGS.get("special", "特殊"), "已排除随机生成")
        return

    # 正常模式 - 添加标签按钮
    if (tw.btn_secondary | tw.btn_xs)(imgui.button)("+##add_tag"):
        imgui.open_popup("tags_popup")
    _tooltip("添加标签")

    # 品质标签 (锁定)
    if hybrid.quality_tag:
        imgui.same_line()
        _locked_badge(
            hybrid.quality_tag,
            QUALITY_TAGS.get(hybrid.quality_tag, hybrid.quality_tag),
            "由品质自动设置",
        )

    # 地牢标签
    if hybrid.dungeon_tag:
        imgui.same_line()
        if _badge(f"dungeon_{hybrid.dungeon_tag}", DUNGEON_TAGS.get(hybrid.dungeon_tag, hybrid.dungeon_tag)):
            hybrid.dungeon_tag = ""

    # 国家标签
    if hybrid.country_tag:
        imgui.same_line()
        if _badge(f"country_{hybrid.country_tag}", COUNTRY_TAGS.get(hybrid.country_tag, hybrid.country_tag)):
            hybrid.country_tag = ""

    # 其他标签
    for tag in list(hybrid.extra_tags):
        imgui.same_line()
        if _badge(f"extra_{tag}", EXTRA_TAGS.get(tag, tag)):
            hybrid.extra_tags.remove(tag)
            break  # 避免在迭代时修改列表

    # 标签选择 popup
    _draw_tags_popup(hybrid)


def _draw_tags_popup(hybrid: HybridItemV2) -> None:
    """标签选择弹窗"""
    if imgui.begin_popup("tags_popup"):
        _label("地牢")
        for tag_val, tag_label in DUNGEON_TAGS.items():
            if imgui.radio_button(f"{tag_label}##dungeon", hybrid.dungeon_tag == tag_val):
                hybrid.dungeon_tag = tag_val

        imgui.separator()

        _label("国家/地区")
        for tag_val, tag_label in COUNTRY_TAGS.items():
            if imgui.radio_button(f"{tag_label}##country", hybrid.country_tag == tag_val):
                hybrid.country_tag = tag_val

        imgui.separator()

        _label("其他")
        for tag_val, tag_label in EXTRA_TAGS.items():
            if tag_val == "special":
                continue
            is_selected = tag_val in hybrid.extra_tags
            changed, new_value = _checkbox(f"{tag_label}##extra_{tag_val}", is_selected)
            if changed:
                if new_value:
                    hybrid.extra_tags.append(tag_val)
                else:
                    hybrid.extra_tags.remove(tag_val)

        imgui.end_popup()


# =============================================================================
# 业务逻辑
# =============================================================================

def _on_quality_changed(hybrid: HybridItemV2) -> None:
    """品质变化时的副作用

    - 文物 (quality=7) 自动设置 tier=0, cat="treasure"
    - quality=6 (独特) 自动设置 quality_tag="unique"
    """
    quality_int = quality_to_int(hybrid.quality)
    if quality_int == 7:
        hybrid.tier = 0
        hybrid.cat = "treasure"
    elif quality_int == 6:
        hybrid.quality_tag = "unique"
    else:
        hybrid.quality_tag = ""


# =============================================================================
# 导出
# =============================================================================

__all__ = ["draw_base_panel"]
