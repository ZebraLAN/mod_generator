# -*- coding: utf-8 -*-
"""混合物品编辑器 V2 - Tab 路由

仅负责 Tab Bar 分发，不包含具体编辑逻辑。
每个 Tab 的内容由对应的 panel 模块实现。

设计原则:
    - 不使用 gui god object (尽可能)
    - 每个 panel 函数接收 hybrid 数据对象
    - 遵循 tw/ly UI 规范

================================================================================
样式设计规范 (Tailwind 思路)
================================================================================

整体布局:
    ```jsx
    {/* 外层容器由 main_editor 提供，这里是 Tab 区域 */}
    <div className="flex flex-col h-full">
      {/* Tab Bar - 贴着顶部，有左右边距 */}
      <div className="px-3 pt-2 bg-abyss-700">
        <TabBar className="gap-1">
          <Tab className="px-4 py-2 rounded-t-md
                         bg-abyss-800 hover:bg-abyss-600
                         data-[active]:bg-abyss-900 data-[active]:border-b-0
                         text-parchment-200 data-[active]:text-parchment-50">
            基础
          </Tab>
        </TabBar>
      </div>

      {/* 内容区 - 有 padding，可滚动 */}
      <div className="flex-1 bg-abyss-900 p-4 overflow-auto">
        {/* Panel 内容 */}
      </div>

      {/* 验证错误区 (如有) */}
      <div className="px-4 pb-4">
        <ErrorBox />
      </div>
    </div>
    ```

Tab 设计决策:
    - 贴边: 否，保留 12px 左边距与导航对齐
    - 圆角: 顶部圆角 (rounded-t-md = 6px)
    - 边框: 无，用背景色区分
    - 实现: 使用 ImGui TabBar (成熟的交互逻辑)

间距常量:
    - TAB_BAR_PX = 3 (12px) - TabBar 水平内边距
    - TAB_BAR_PT = 2 (8px) - TabBar 顶部内边距
    - CONTENT_P = 4 (16px) - 内容区内边距
    - SECTION_GAP = 5 (20px) - 表单分组间距
================================================================================
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import imgui

from ui import tw, styles
from ui import layout as ly
from hybrid_item_v2 import HybridItemV2
from specs import EffectTrigger
from models import validate_hybrid_item
from ui.state import state as ui_state

if TYPE_CHECKING:
    from ui.protocols import GUIProtocol


# =============================================================================
# 间距常量 (Tailwind 单位: 1 = 4px)
# =============================================================================

_TAB_BAR_PX = 3     # TabBar 水平内边距 (12px)
_TAB_BAR_PT = 2     # TabBar 顶部内边距 (8px)
_CONTENT_P = 4      # 内容区内边距 (16px)
_TAB_GAP = 2        # Tab 与内容区间距 (8px)
_ERROR_GAP = 3      # 错误区与内容区间距 (12px)


def draw_hybrid_editor_tabs(hybrid: HybridItemV2, gui: "GUIProtocol") -> None:
    """混合物品编辑器 Tab Bar

    布局结构:
        ┌─────────────────────────────────────────────────────┐
        │ ← px=12 → [基础] [行为] [属性] [呈现]              │ TabBar 区
        ├─────────────────────────────────────────────────────┤
        │ ┌─────────────────────────────────────────────────┐ │
        │ │ ← p=16 →                                        │ │
        │ │  ID        品质        等级                     │ │ 内容区
        │ │  [input]   [combo]     [combo]                  │ │ (可滚动)
        │ │  ...                                            │ │
        │ └─────────────────────────────────────────────────┘ │
        ├─────────────────────────────────────────────────────┤
        │ ⚠️ 验证错误...                                      │ 错误区
        └─────────────────────────────────────────────────────┘

    Args:
        hybrid: 混合物品数据对象
        gui: GUI 实例 (仅用于尚未迁移的 tabs, 后续移除)
    """
    # 导入 panel 模块
    from ui.editors.hybrid.base_panel import draw_base_panel

    # 是否显示属性 Tab
    show_attrs = _should_show_attributes(hybrid) or isinstance(hybrid.trigger, EffectTrigger)

    # =========================================================================
    # 样式定义
    # =========================================================================
    # Tab 按钮样式 - 顶部圆角，选中时紫水晶高亮
    _tab_style = (
        styles.tab_colors(
            normal=tw.ABYSS_800,
            hovered=tw.ABYSS_600,
            active=tw.ABYSS_900,  # 选中时与内容区背景融合
            unfocused=tw.ABYSS_800,
            unfocused_active=tw.ABYSS_900,
        ) |
        styles.tab_rounding(ly.sz(1.5)) |            # 6px 顶部圆角
        styles.frame_padding(ly.sz(4), ly.sz(2)) |   # Tab 内边距 16px×8px
        tw.text_parchment_200                         # Tab 文字颜色
    )

    # =========================================================================
    # 渲染 TabBar
    # =========================================================================
    # 顶部间距
    ly.gap_y(_TAB_BAR_PT)

    # TabBar 区域 - 有水平边距
    imgui.indent(ly.sz(_TAB_BAR_PX))

    if styles.frame_padding(ly.sz(4), ly.sz(2))(imgui.begin_tab_bar)("##hybrid_tabs"):
        try:
            # Tab: 基础
            if _tab_style(imgui.begin_tab_item)("基础")[0]:
                imgui.unindent(ly.sz(_TAB_BAR_PX))  # 恢复缩进
                _draw_tab_content(lambda: draw_base_panel(hybrid))
                imgui.indent(ly.sz(_TAB_BAR_PX))  # 重新缩进以正确结束
                imgui.end_tab_item()

            # Tab: 行为
            if _tab_style(imgui.begin_tab_item)("行为")[0]:
                imgui.unindent(ly.sz(_TAB_BAR_PX))
                _draw_tab_content(lambda: gui._draw_hybrid_behavior(hybrid))
                imgui.indent(ly.sz(_TAB_BAR_PX))
                imgui.end_tab_item()

            # Tab: 属性 (条件显示)
            if show_attrs:
                if _tab_style(imgui.begin_tab_item)("属性")[0]:
                    imgui.unindent(ly.sz(_TAB_BAR_PX))
                    _draw_tab_content(lambda: gui._draw_hybrid_stats(hybrid))
                    imgui.indent(ly.sz(_TAB_BAR_PX))
                    imgui.end_tab_item()

            # Tab: 呈现
            if _tab_style(imgui.begin_tab_item)("呈现")[0]:
                imgui.unindent(ly.sz(_TAB_BAR_PX))
                _draw_tab_content(lambda: gui._draw_hybrid_presentation(hybrid))
                imgui.indent(ly.sz(_TAB_BAR_PX))
                imgui.end_tab_item()

        finally:
            imgui.end_tab_bar()

    imgui.unindent(ly.sz(_TAB_BAR_PX))

    # =========================================================================
    # 验证错误区域
    # =========================================================================
    errors = validate_hybrid_item(hybrid, ui_state.project, include_warnings=True)
    if errors:
        ly.gap_y(_ERROR_GAP)
        _draw_validation_errors(errors, gui)


def _draw_tab_content(draw_fn) -> None:
    """Tab 内容区容器

    提供:
        - 与 TabBar 的间距
        - 内容区内边距
        - 可滚动区域 (TODO: 如需要)
    """
    ly.gap_y(_TAB_GAP)

    # 内容区内边距
    imgui.indent(ly.sz(_CONTENT_P))
    draw_fn()
    imgui.unindent(ly.sz(_CONTENT_P))


def _draw_validation_errors(errors: list[str], gui: "GUIProtocol") -> None:
    """绘制验证错误区域"""
    with tw.bg_abyss_900 | tw.border_blood_700 | tw.child_border_size(1) | tw.rounded_md | tw.p_3:
        gui._draw_validation_errors(errors)


def _should_show_attributes(hybrid: HybridItemV2) -> bool:
    """判断是否显示属性加成编辑器

    武器/护甲/护符都显示属性编辑器。
    """
    from specs import is_weapon_mode, is_armor_mode, is_charm_mode

    if is_weapon_mode(hybrid.equipment) or is_armor_mode(hybrid.equipment) or is_charm_mode(hybrid.equipment):
        return True
    return False


__all__ = ["draw_hybrid_editor_tabs"]
