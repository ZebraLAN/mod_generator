# -*- coding: utf-8 -*-
"""项目信息编辑器 - 完全自治面板

⚠️ 架构：面板组件完全自治
    - 本组件自己创建 Child Window 并控制样式
    - 接收 (width, height) 参数
    - main_editor.py 路由分发不会为我们创建容器

设计思路 (Tailwind -> ImGui):
    采用卡片分区的设计，每个区域有明确的视觉边界。

间距层级系统 (由大到小):
    - 页面边距 (p-5 = 20px): 内容与窗口边缘的呼吸空间
    - 区块间距 (gap-6 = 24px): 页面标题与卡片、卡片之间
    - 卡片内边距 (p-4 = 16px): 卡片内容与边框
    - 标题间距 (gap-4 = 16px): 卡片标题与内容区
    - 表单行间距 (gap-3 = 12px): 表单字段行之间
    - 紧凑间距 (gap-1.5 = 6px): 标签与输入框

Tailwind 参考:
    <div class="bg-abyss-700 p-5 h-full overflow-y-auto">
        <div class="flex items-center gap-3">...</div>  <!-- Header -->
        <div class="h-6"></div>  <!-- gap-6 -->
        <div class="bg-abyss-800 rounded-lg p-4">...</div>  <!-- Card -->
        <div class="h-5"></div>  <!-- gap-5 -->
        ...
    </div>
"""

from __future__ import annotations

import os

import imgui
from ui import layout as ly
from ui import tw
from ui.icons import (
    FA_FOLDER, FA_TRIANGLE_EXCLAMATION, FA_CIRCLE_CHECK,
    FA_GEM, FA_PEN, FA_INFO, FA_FLOPPY_DISK
)


# =============================================================================
# 样式预设 (原子化、可组合)
# =============================================================================

# 页面容器样式 - 自定义 padding，覆盖 panel_style 的 p_2
# Tailwind: bg-abyss-700 p-5
# 注意: ImGui 中 WindowPadding 只在 border=True 且 child_border_size>0 时生效
#       所以我们用 child_border_size(1) + border_transparent 实现视觉无边框
_page_style = (
    tw.bg_abyss_700 |
    tw.child_rounded_none |
    tw.child_border_size(1) |     # 必须 > 0 才能应用 WindowPadding
    tw.border_transparent |        # 透明边框，视觉上不可见
    tw.p_5  # 20px 页面边距
)

# 输入框样式 - 深色背景 + 微妙边框
# Tailwind: bg-abyss-900 border border-abyss-600 rounded-md p-2
_input_style = (
    tw.frame_p_2 |  # 控件内边距 (FramePadding)
    tw.frame_bg_abyss_900 |
    tw.border_abyss_600 |
    tw.rounded_md |
    tw.frame_border_size(1)
)


# =============================================================================
# 间距层级系统 (Tailwind 单位: 1 = 4px)
# =============================================================================

# 页面级 - 大区块之间 (标题后、卡片之间)
_PAGE_GAP = 6        # 24px - 页面区块间距

# 卡片级 - 卡片内部结构
_CARD_PADDING = 5    # 20px - 卡片内边距 (必须 >= _COL_GAP)
_CARD_ROUNDING = 2   # 8px  - 卡片圆角
_CARD_GAP = 5        # 20px - 卡片之间的间距

# 表单级 - 字段布局
_TITLE_GAP = 4       # 16px - 卡片标题与内容
_FIELD_GAP = 3       # 12px - 表单行间距
_COL_GAP = 4         # 16px - 双列之间的间距 (必须 <= _CARD_PADDING)
_LABEL_GAP = 1.5     # 6px  - 标签与输入框


# =============================================================================
# 主入口 - 自治面板
# =============================================================================

def draw_project_editor(width: float, height: float) -> None:
    """项目编辑器 - 完全自治面板

    ⚠️ 容器类型: Child Window (自己创建和管理)

    Tailwind: bg-abyss-700 p-5 overflow-y-auto

    Args:
        width: 面板宽度 (像素，已应用 DPI)
        height: 面板高度 (像素，已应用 DPI)
    """
    from ui.state import state as ui_state

    project = ui_state.project

    # 1. 样式 + 容器 (使用自定义页面样式)
    # 注意: ImGui 的 Child Window 只有 border=True 时才应用 WindowPadding
    # 我们设置 border=True，但边框宽度为 0 (在 _page_style 中)
    with _page_style:
        imgui.begin_child(
            "ProjectEditor",
            width=width,
            height=height,
            border=True,  # 必须为 True 才能应用 WindowPadding
            flags=imgui.WINDOW_NO_SCROLLBAR,
        )

    # -------------------------------------------------------------------------
    # 页面标题
    # Tailwind: flex items-center gap-3
    # -------------------------------------------------------------------------
    with tw.text_xl:
        ly.icon_label(
            FA_GEM, "项目设置",
            gap=3,
            icon_style=tw.text_crystal_400,
            text_style=tw.text_parchment_50 | tw.text_lg,
        )

    ly.gap_y(_PAGE_GAP)

    # -------------------------------------------------------------------------
    # 基本信息卡片
    # Tailwind: bg-abyss-800 rounded-lg p-4
    # -------------------------------------------------------------------------
    with ly.panel("basic_info_card", tw.ABYSS_800, padding=_CARD_PADDING, rounding=_CARD_ROUNDING) as content_width:
        _card_title("基本信息", FA_PEN)
        ly.gap_y(_TITLE_GAP)

        # Row 1: 模组名称 + 模组代号
        with ly.columns(2, gap=_COL_GAP, available_width=content_width) as c:
            with c.col(0):
                _draw_field(
                    "模组名称", "##name", project.name,
                    "我的超棒模组", c.col_width,
                    lambda v: setattr(project, 'name', v)
                )
            with c.col(1):
                _draw_field(
                    "模组代号", "##code_name", project.code_name,
                    "my_mod", c.col_width,
                    lambda v: setattr(project, 'code_name', v),
                    help_text="用于生成文件名，仅限英文和下划线"
                )

        ly.gap_y(_FIELD_GAP)

        # Row 2: 作者 + 版本
        with ly.columns(2, gap=_COL_GAP, available_width=content_width) as c:
            with c.col(0):
                _draw_field(
                    "作者", "##author", project.author,
                    "Your Name", c.col_width,
                    lambda v: setattr(project, 'author', v)
                )
            with c.col(1):
                _draw_field(
                    "版本", "##version", project.version,
                    "1.0.0", c.col_width,
                    lambda v: setattr(project, 'version', v),
                    help_text="语义化版本号"
                )

        ly.gap_y(_FIELD_GAP)

        # Row 3: 目标游戏版本 (单列)
        with ly.columns(2, gap=_COL_GAP, available_width=content_width) as c:
            with c.col(0):
                _draw_field(
                    "目标游戏版本", "##target_ver", project.target_version,
                    "0.9.3.13", c.col_width,
                    lambda v: setattr(project, 'target_version', v),
                    help_text="兼容的 Stoneshard 版本"
                )

    ly.gap_y(_CARD_GAP)

    # -------------------------------------------------------------------------
    # 描述卡片
    # Tailwind: bg-abyss-800 rounded-lg p-4
    # -------------------------------------------------------------------------
    with ly.panel("description_card", tw.ABYSS_800, padding=_CARD_PADDING, rounding=_CARD_ROUNDING) as content_width:
        _card_title("模组描述", FA_INFO)
        ly.gap_y(_TITLE_GAP)

        imgui.push_item_width(content_width)
        with _input_style:
            _, new_desc = imgui.input_text_multiline(
                "##desc", project.description, 2048, height=ly.sz(20)
            )
            project.description = new_desc
        imgui.pop_item_width()

    ly.gap_y(_CARD_GAP)

    # -------------------------------------------------------------------------
    # 路径信息卡片
    # Tailwind: bg-abyss-850 rounded-md p-5 flex items-center
    # 注意: 使用与其他卡片相同的 padding 保持视觉一致
    # -------------------------------------------------------------------------
    project_dir = os.path.dirname(project.file_path) if project.file_path else ""

    with ly.panel("path_card", tw.ABYSS_850, padding=_CARD_PADDING, rounding=_CARD_ROUNDING):
        # 路径文本 - 只显示路径信息，不显示保存状态（无 dirty tracking）
        icon_style = tw.text_crystal_400 if project_dir else tw.text_parchment_600
        text_style = tw.text_parchment_300 if project_dir else tw.text_parchment_500
        path_text = project_dir if project_dir else "项目尚未保存到磁盘"

        with ly.hstack(gap=2, align='center'):
            with ly.slot():
                with icon_style:
                    imgui.text(FA_FOLDER)
            with ly.slot():
                with text_style:
                    imgui.text(path_text)

    ly.gap_y(_CARD_GAP)

    # -------------------------------------------------------------------------
    # 验证状态
    # -------------------------------------------------------------------------
    errors = project.validate()
    _draw_validation_status(errors)

    # 3. 结束容器
    imgui.end_child()


# =============================================================================
# 验证状态
# =============================================================================

def _draw_validation_status(errors: list[str]) -> None:
    """验证状态区域

    Tailwind:
        成功: text-green-400 flex items-center gap-2
        错误: bg-blood-900 rounded p-3
    """
    if not errors:
        # 验证通过
        with ly.hstack(gap=2):
            with ly.slot():
                with tw.text_green_400:
                    imgui.text(FA_CIRCLE_CHECK)
            with ly.slot():
                with tw.text_green_400:
                    imgui.text("项目配置有效")
    else:
        # 显示错误
        with ly.panel("validation_errors", tw.BLOOD_900, padding=3, rounding=2):
            # 标题行
            with ly.hstack(gap=2):
                with ly.slot():
                    with tw.text_blood_400:
                        imgui.text(FA_TRIANGLE_EXCLAMATION)
                with ly.slot():
                    with tw.text_blood_300:
                        imgui.text(f"发现 {len(errors)} 个问题")

            ly.gap_y(2)

            # 错误列表
            with ly.vstack(gap=1):
                for err in errors:
                    with ly.slot():
                        with tw.text_blood_200:
                            imgui.text(f"  • {err}")


# =============================================================================
# 原子组件
# =============================================================================

def _card_title(text: str, icon: str | None = None) -> None:
    """卡片标题 - 图标 + 文字

    Tailwind: flex items-center gap-2 text-parchment-100
    """
    if icon:
        ly.icon_label(
            icon, text,
            gap=2,
            icon_style=tw.text_crystal_400,
            text_style=tw.text_parchment_100,
        )
    else:
        with tw.text_parchment_100:
            imgui.text(text)


def _label(text: str, required: bool = False, help_text: str | None = None) -> None:
    """标签文字

    Tailwind: text-parchment-400 text-sm flex items-center gap-0.5
    """
    with tw.text_parchment_400:
        imgui.text(text)

    if required:
        ly.same_line(0.5)
        with tw.text_blood_400:
            imgui.text("*")

    if help_text:
        ly.same_line(0.5)
        with tw.text_parchment_600:
            imgui.text("(?)")
        if imgui.is_item_hovered():
            imgui.set_tooltip(help_text)


def _draw_field(
    label: str,
    input_id: str,
    value: str,
    placeholder: str,
    width: float,
    setter=None,
    *,
    required: bool = False,
    help_text: str | None = None,
) -> str:
    """带标签的输入字段 - 垂直排列 (label 在上，input 在下)

    Tailwind:
        <div class="flex flex-col gap-1.5">
            <label class="text-parchment-400">...</label>
            <input class="bg-abyss-900 border-abyss-600 rounded-md p-2" />
        </div>
    """
    _label(label, required=required, help_text=help_text)
    ly.gap_y(_LABEL_GAP)

    imgui.push_item_width(width)
    with _input_style:
        changed, new_value = imgui.input_text_with_hint(
            input_id, placeholder, value, 256
        )
    imgui.pop_item_width()

    if changed and setter:
        setter(new_value)

    return new_value
