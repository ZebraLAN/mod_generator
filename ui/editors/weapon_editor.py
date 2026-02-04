# -*- coding: utf-8 -*-
"""武器编辑器 Mixin - WeaponEditorMixin

提供武器编辑器相关方法。
"""

from typing import TYPE_CHECKING

import imgui  # type: ignore

from constants import (
    SLOT_LABELS,
    WEAPON_MATERIAL_LABELS,
    WEAPON_ATTR_GROUPS,
)
from models import validate_item
from ui.state import state as ui_state

if TYPE_CHECKING:
    from ui.protocols import GUIProtocol


class WeaponEditorMixin:
    """武器编辑器 Mixin"""

    def draw_weapon_editor(self: "GUIProtocol") -> None:
        """绘制武器编辑器"""
        weapon = ui_state.project.weapons[ui_state.current_weapon_index]
        weapon.markup = 1

        if imgui.tree_node("基本属性", flags=imgui.TREE_NODE_FRAMED):
            self._draw_basic_properties(
                weapon, "weapon", SLOT_LABELS, WEAPON_MATERIAL_LABELS
            )
            imgui.tree_pop()

        if imgui.tree_node("武器属性", flags=imgui.TREE_NODE_FRAMED):
            self._draw_attributes_editor(weapon, WEAPON_ATTR_GROUPS, "weapon")
            imgui.tree_pop()

        if imgui.tree_node("武器名称与本地化", flags=imgui.TREE_NODE_FRAMED):
            self._draw_localization_editor(weapon, "weapon")
            imgui.tree_pop()

        if imgui.tree_node("贴图文件", flags=imgui.TREE_NODE_FRAMED):
            from ui.editors.texture_editor import draw_textures_editor
            draw_textures_editor(weapon, "weapon")
            imgui.tree_pop()

        errors = validate_item(weapon, ui_state.project, include_warnings=True)
        self._draw_validation_errors(errors)
