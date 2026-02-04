# -*- coding: utf-8 -*-
"""混合物品编辑器 - 模块化重构

将 HybridEditorMixin 拆分为独立的面板模块:
- base_panel: 基础信息 (ID, 品质, 分类, 标签)
- behavior_panel: 行为设置 (装备形态, 触发, 充能等) [TODO]
- stats_panel: 属性配置 [TODO]
- presentation_panel: 呈现 (名称, 本地化, 贴图) [TODO]
"""

from ui.editors.hybrid.base_panel import draw_base_panel

__all__ = [
    "draw_base_panel",
]
