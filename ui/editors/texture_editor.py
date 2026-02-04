# -*- coding: utf-8 -*-
"""贴图编辑器模块

提供贴图编辑器相关方法，包括：
- 武器/装备的穿戴状态贴图
- 多姿势护甲贴图（男性/女性）
- 物品栏贴图
- 战利品贴图
- 混合物品贴图
"""

import os
from typing import Callable, Union

import imgui

from ui.editors.common import draw_indented_separator
from ui.styles import gap_m
from ui.state import state as ui_state

from constants import (
    ARMOR_PREVIEW_WIDTH,
    CHARACTER_MODELS,
    GAME_FPS,
)
from models import Armor, Weapon
from hybrid_item_v2 import HybridItemV2
from specs import (
    WeaponCharTexture, MultiPoseCharTexture, NoCharTexture,
    AnimatedSlot, StaticSlot, LootSlot, loot_speed_to_preview_fps,
)
from ui.layout import tooltip
from ui.styles import text_secondary

# 任何拥有 textures: ItemTexturesV2 属性的物品
AnyItemWithTextures = Union[Weapon, Armor, HybridItemV2]

# 单手武器槽位集合（使用姿势0）
SINGLE_HAND_SLOTS = frozenset({"dagger", "mace", "sword", "axe", "spear", "bow", "shield"})


# ============================================================================
# 模块级函数 - 贴图预览
# ============================================================================


def draw_inventory_textures(
    paths: list[str],
    id_suffix: str,
    importer: Callable[[str], str] | None = None,
) -> list[str]:
    """绘制物品栏贴图编辑器

    Args:
        paths: 当前贴图路径列表
        id_suffix: ID 后缀
        importer: 路径转换函数

    Returns:
        更新后的路径列表
    """
    from ui.widgets import frame_strip, slider_index, texture_preview

    imgui.text("物品栏贴图")
    tooltip("多张贴图可表示不同耐久状态，排在后面的贴图代表更低耐久")

    # 使用 frame_strip 管理路径（非动画模式）
    paths, selected = frame_strip(
        f"{id_suffix}_inv",
        paths,
        animated=False,
        importer=importer,
    )

    # 预览当前选中的贴图
    if paths and 0 <= selected < len(paths) and paths[selected]:
        texture_preview(f"{id_suffix}_inv_preview", paths[selected])

    return paths


def draw_loot_textures(
    loot: LootSlot,
    id_suffix: str,
    importer: Callable[[str], str] | None = None,
) -> None:
    """绘制战利品贴图编辑器

    Args:
        loot: 战利品槽位对象（会被原地修改）
        id_suffix: ID 后缀
        importer: 路径转换函数
    """
    from ui.widgets import frame_strip, texture_preview

    imgui.text("战利品贴图*")
    tooltip("战利品掉落时显示的贴图，支持动画")

    # 计算实际 fps（用于动画预览）
    fps = loot_speed_to_preview_fps(loot.speed, GAME_FPS)

    # 使用 frame_strip 管理路径
    new_paths, frame = frame_strip(
        f"{id_suffix}_loot",
        loot.paths,
        animated=True,
        fps=fps,
        importer=importer,
    )
    loot.paths = new_paths

    # 预览当前帧
    if loot.paths and 0 <= frame < len(loot.paths) and loot.paths[frame]:
        texture_preview(f"{id_suffix}_loot_preview", loot.paths[frame])

    # 动画速度设置
    if loot.is_animated:
        from ui.widgets import loot_speed_input
        loot.speed = loot_speed_input(id_suffix, loot.speed)



# ============================================================================
# 模块级函数 - 角色贴图编辑器
# ============================================================================


def draw_weapon_char_textures(
    char: WeaponCharTexture,
    id_suffix: str,
    has_left: bool,
    pose_index: int = 0,
    importer: Callable[[str], str] | None = None,
) -> str:
    """绘制武器/盾牌手持贴图编辑器

    Args:
        char: WeaponCharTexture 对象（会被原地修改）
        id_suffix: ID 后缀
        has_left: 是否需要左手贴图
        pose_index: 姿势索引 (0=单手, 1=双手)
        importer: 路径转换函数

    Returns:
        当前选中的模型 key
    """
    from ui.widgets import model_combo, frame_strip, origin_input, texture_preview

    is_weapon = id_suffix == "weapon"
    title = "手持状态贴图" if is_weapon else "穿戴状态贴图"

    # 标题行 + 模特选择
    imgui.text(title)
    imgui.same_line()
    selected_model = model_combo(id_suffix, ui_state.selected_model)
    ui_state.selected_model = selected_model

    # 获取模型路径
    model_files = CHARACTER_MODELS.get(selected_model, [])
    model_path = (
        os.path.join("resources", model_files[pose_index])
        if pose_index < len(model_files) else None
    )

    imgui.dummy(0, 4)

    # 绘制槽位的辅助函数
    def draw_slot(label: str, slot: AnimatedSlot, slot_suffix: str):
        imgui.text(label)
        slot.paths, frame = frame_strip(
            f"{id_suffix}_{slot_suffix}",
            slot.paths,
            animated=True,
            importer=importer,
        )
        if slot.paths and 0 <= frame < len(slot.paths):
            texture_preview(
                f"{id_suffix}_{slot_suffix}_preview",
                slot.paths[frame],
                origin=slot.origin,
                model_path=model_path,
            )
        slot.origin = origin_input(f"{id_suffix}_{slot_suffix}_origin", slot.origin)

    # 右手/默认贴图
    right_label = "右手/默认*" if has_left else "贴图*"
    draw_slot(right_label, char.main, "main")

    # 左手贴图
    if has_left:
        draw_indented_separator()
        draw_slot("左手*", char.left, "left")

    return selected_model


# 姿势槽位元数据
_POSE_SLOTS = {
    # 男性/默认版
    "standing0": ("站立0", True),   # (标签, 是否必须)
    "standing1": ("站立1", False),
    "rest": ("休息", True),
    # 女性版
    "standing0_female": ("站立0", False),
    "standing1_female": ("站立1", False),
    "rest_female": ("休息", False),
}


def _draw_pose_slot(
    char: MultiPoseCharTexture,
    slot_name: str,
    id_suffix: str,
    model_path: str | None,
    importer: Callable[[str], str] | None = None,
) -> None:
    """绘制单个姿势槽位

    使用 MultiPoseCharTexture 的声明式规则：
    - resolve(): 获取实际显示的贴图和 fallback 来源
    - is_ui_enabled(): 判断是否启用编辑
    - clear_with_cascade(): 清除时级联清除依赖
    """
    from ui.widgets import single_texture_input, origin_input, texture_preview

    label, required = _POSE_SLOTS[slot_name]
    slot: StaticSlot = getattr(char, slot_name)
    is_enabled = char.is_ui_enabled(slot_name)

    # 标签
    imgui.text(label)
    if required:
        imgui.same_line()
        imgui.text_colored("*", 1.0, 0.5, 0.5, 1.0)
    elif not is_enabled:
        imgui.same_line()
        text_secondary("(禁用)")

    # 编辑按钮
    if is_enabled:
        new_path = single_texture_input(
            f"{id_suffix}_{slot_name}",
            slot.path,
            importer=importer,
        )
        if new_path != slot.path:
            if new_path:
                slot.path = new_path
            else:
                # 清除时级联
                char.clear_with_cascade(slot_name)
    else:
        # 禁用状态显示原因
        requires = char.UI_ENABLE_REQUIRES.get(slot_name, ())
        missing = [r for r in requires if not getattr(char, r).has_texture()]
        if missing:
            text_secondary(f"需先设置: {', '.join(missing)}")

    # 预览（使用 resolve 获取实际显示的贴图）
    resolved_slot, fallback_from = char.resolve(slot_name)
    if resolved_slot.has_texture():
        if fallback_from:
            text_secondary(f"(使用 {_POSE_SLOTS.get(fallback_from, (fallback_from,))[0]})")
        # 使用 fallback 时用自己的 origin，否则用 resolved 的 origin
        preview_origin = slot.origin if fallback_from else resolved_slot.origin
        texture_preview(
            f"{id_suffix}_{slot_name}_preview",
            resolved_slot.path,
            origin=preview_origin,
            model_path=model_path,
            size=(ARMOR_PREVIEW_WIDTH, ARMOR_PREVIEW_WIDTH),
        )

    # Origin（仅当有自己的贴图时显示）
    if slot.has_texture():
        slot.origin = origin_input(f"{id_suffix}_{slot_name}_origin", slot.origin)


def draw_multi_pose_armor_textures(
    char: MultiPoseCharTexture,
    id_suffix: str,
    importer: Callable[[str], str] | None = None,
) -> tuple[str, int]:
    """绘制多姿势护甲贴图编辑器

    Args:
        char: MultiPoseCharTexture 对象（会被原地修改）
        id_suffix: ID 后缀
        importer: 路径转换函数

    Returns:
        (当前选中的种族 key, 当前性别 tab index)
    """
    from constants import get_model_key, CHARACTER_MODELS
    from ui.widgets import race_combo, tab_index

    imgui.text("穿戴状态贴图")
    text_secondary("需要为站立和休息状态各准备贴图，女性版贴图可选")

    # 模特种族选择
    imgui.same_line()
    selected_race = race_combo(id_suffix, ui_state.selected_race)
    ui_state.selected_race = selected_race

    imgui.dummy(0, 4)

    # 性别 Tab
    has_female = (
        char.standing0_female.has_texture()
        or char.standing1_female.has_texture()
        or char.rest_female.has_texture()
    )
    tab_labels = ["默认/男性", "女性 *" if has_female else "女性"]
    gender_idx = tab_index(f"{id_suffix}_gender", tab_labels, ui_state.gender_tab_index)
    ui_state.gender_tab_index = gender_idx

    imgui.dummy(0, 4)

    # 获取模型路径
    is_female = gender_idx == 1
    model_key = get_model_key(selected_race, is_female)
    model_files = CHARACTER_MODELS.get(model_key, [])
    # 多姿势护甲使用姿势0的模型
    model_path = os.path.join("resources", model_files[0]) if model_files else None

    # 三列布局
    available_width = imgui.get_content_region_available_width()
    col_width = (available_width - gap_m() * 2) / 3

    imgui.columns(3, f"poses_{id_suffix}", False)
    imgui.set_column_width(0, col_width)
    imgui.set_column_width(1, col_width)
    imgui.set_column_width(2, col_width)

    if gender_idx == 0:
        # 男性/默认版
        _draw_pose_slot(char, "standing0", id_suffix, model_path, importer)
        imgui.next_column()
        _draw_pose_slot(char, "standing1", id_suffix, model_path, importer)
        imgui.next_column()
        _draw_pose_slot(char, "rest", id_suffix, model_path, importer)
    else:
        # 女性版
        _draw_pose_slot(char, "standing0_female", id_suffix, model_path, importer)
        imgui.next_column()
        _draw_pose_slot(char, "standing1_female", id_suffix, model_path, importer)
        imgui.next_column()
        _draw_pose_slot(char, "rest_female", id_suffix, model_path, importer)

    imgui.columns(1)

    return selected_race, gender_idx


# ============================================================================
# 主贴图编辑器函数
# ============================================================================


def draw_textures_editor(
    item: AnyItemWithTextures,
    id_suffix: str,
) -> None:
    """绘制贴图编辑器 - 通用实现

    Args:
        item: 物品对象（Weapon/Armor/HybridItemV2）
        id_suffix: ID 后缀（如 "weapon", "armor", "hybrid"）
    """
    # 穿戴/手持状态贴图
    match item.textures.char:
        case MultiPoseCharTexture() as char:
            draw_multi_pose_armor_textures(
                char, id_suffix, importer=ui_state.import_texture
            )

        case WeaponCharTexture() as char:
            # 确定姿势索引：单手武器用 0，双手武器用 1
            pose_index = 0 if item.slot in SINGLE_HAND_SLOTS else 1
            draw_weapon_char_textures(
                char,
                id_suffix,
                has_left=item.needs_left_texture(),
                pose_index=pose_index,
                importer=ui_state.import_texture,
            )

        case NoCharTexture():
            text_secondary(f"{item.slot} 槽位无需穿戴贴图")

    draw_indented_separator()

    # 物品栏贴图
    item.textures.inventory = draw_inventory_textures(
        item.textures.inventory,
        id_suffix,
        importer=ui_state.import_texture,
    )

    draw_indented_separator()

    # 战利品贴图
    draw_loot_textures(item.textures.loot, id_suffix, importer=ui_state.import_texture)
