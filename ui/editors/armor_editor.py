# -*- coding: utf-8 -*-
"""装备编辑器 Mixin - ArmorEditorMixin

提供装备编辑器相关方法。
"""

from typing import TYPE_CHECKING

import imgui  # type: ignore

from constants import (
    ARMOR_MATERIAL_LABELS,
    ARMOR_SLOT_LABELS,
    ARMOR_ATTR_GROUPS,
)
from models import validate_item
from ui.state import state as ui_state

if TYPE_CHECKING:
    from ui.protocols import GUIProtocol


class ArmorEditorMixin:
    """装备编辑器 Mixin"""

    def draw_armor_editor(self: "GUIProtocol") -> None:
        """绘制护甲编辑器"""
        armor = ui_state.project.armors[ui_state.current_armor_index]

        if imgui.tree_node("基本属性##armor", flags=imgui.TREE_NODE_FRAMED):
            self._draw_basic_properties(
                armor, "armor", ARMOR_SLOT_LABELS, ARMOR_MATERIAL_LABELS
            )
            imgui.tree_pop()

        if imgui.tree_node("装备属性", flags=imgui.TREE_NODE_FRAMED):
            self._draw_attributes_editor(armor, ARMOR_ATTR_GROUPS, "armor")
            imgui.tree_pop()

        # 项链、戒指、盾牌不允许拆解材料
        no_fragment_slots = ["Ring", "Amulet", "shield"]
        if armor.slot in no_fragment_slots:
            # 强制清空拆解材料
            armor.fragments.clear()
        else:
            if imgui.tree_node("拆解材料", flags=imgui.TREE_NODE_FRAMED):
                self._draw_fragments_editor(armor)
                imgui.tree_pop()

        if imgui.tree_node("装备名称与本地化", flags=imgui.TREE_NODE_FRAMED):
            self._draw_localization_editor(armor, "armor")
            imgui.tree_pop()

        if imgui.tree_node("贴图文件##armor", flags=imgui.TREE_NODE_FRAMED):
            from ui.editors.texture_editor import draw_textures_editor
            draw_textures_editor(armor, "armor")
            imgui.tree_pop()

        errors = validate_item(armor, ui_state.project, include_warnings=True)
        self._draw_validation_errors(errors)
