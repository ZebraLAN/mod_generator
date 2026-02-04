# -*- coding: utf-8 -*-
"""Grid 布局工具 - GridLayout 类和 ImGui 辅助函数

⚠️ DEPRECATED: 本模块为旧版布局系统，将在未来版本移除。
新代码请使用:
  - ui.layout (ly.gap_y, ly.same_line, ly.auto_hcenter 等)
  - ui.tw (Tailwind 风格 tokens)

现有使用此模块的代码（如 hybrid_editor.py）将在后续重构中迁移。

提供 ImGui 布局的辅助工具类。
"""

import warnings
from contextlib import contextmanager

import imgui  # type: ignore

from ui import styles

# 模块级 deprecation 警告（仅在首次导入时触发）
warnings.warn(
    "ui.grid 模块已废弃，请使用 ui.layout 和 ui.tw。"
    "此模块将在未来版本中移除。",
    DeprecationWarning,
    stacklevel=2
)


class GridLayout:
    """Grid 布局助手 - 用于 label-on-top 的表单布局

    使用示例:
        grid = GridLayout(text_secondary)

        # Label 行
        grid.label_header("品质")
        grid.next_cell()
        grid.label_header("等级")

        # Control 行 (新的一行, 不调用 next_cell)
        grid.field_width()
        imgui.combo(...)
        grid.next_cell()
        grid.field_width()
        imgui.combo(...)
    """

    def __init__(self, text_secondary_fn=None):
        """
        Args:
            text_secondary_fn: 可选的 text_secondary 函数，用于绘制标签
        """
        self.text_secondary = text_secondary_fn or (lambda t: imgui.text(t))

    def next_cell(self):
        """移动到下一个 grid cell (同一行)"""
        imgui.same_line(spacing=styles.grid_gap())

    def label_header(self, text: str, cols: int = 3):
        """绘制 label header，占用 cols 列宽度"""
        target_w = styles.span(cols)
        self.text_secondary(text)
        text_w = imgui.calc_text_size(text).x
        if text_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - text_w, 0)

    def field_width(self, cols: int = 3):
        """设置下一个控件的宽度为 span(cols)"""
        imgui.set_next_item_width(styles.span(cols))

    def text_cell(self, text: str, cols: int = 3):
        """绘制只读文本，占用 cols 列宽度"""
        target_w = styles.span(cols)
        imgui.align_text_to_frame_padding()
        imgui.text(text)
        text_w = imgui.calc_text_size(text).x
        if text_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - text_w, 0)

    def button_cell(self, label: str, cols: int = 3) -> bool:
        """绘制按钮，占用 cols 列宽度，返回是否点击"""
        target_w = styles.span(cols)
        clicked = imgui.button(label)
        btn_w = imgui.get_item_rect_size()[0]
        if btn_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - btn_w, 0)
        return clicked

    def checkbox_cell(self, label: str, value: bool, cols: int = 3) -> tuple:
        """绘制 checkbox，占用 cols 列宽度，返回 (changed, new_value)"""
        target_w = styles.span(cols)
        changed, new_value = imgui.checkbox(label, value)
        cb_w = imgui.get_item_rect_size()[0]
        if cb_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - cb_w, 0)
        return changed, new_value

    # ===== 流式布局支持 (Flow Layout) =====
    # 用于处理可变宽度的 badges、buttons 等

    def begin_flow(self, max_width: float | None = None):
        """开始流式布局区域

        Args:
            max_width: 可选的最大宽度限制。用于限制内容区域宽度（考虑padding）。

        在流式布局中，使用 flow_item() 自动处理换行。
        调用后需配合 end_flow() 使用。
        """
        self._flow_cursor = 0
        available = imgui.get_content_region_available_width()
        self._flow_available = min(available, max_width) if max_width else available
        self._flow_first = True
        self._flow_gap = styles.gap_s()

    def end_flow(self):
        """结束流式布局区域"""
        self._flow_cursor = 0
        self._flow_first = True

    def flow_item(self, width: float | None = None) -> bool:
        """在流式布局中放置一个元素

        Args:
            width: 元素预估宽度（可选，用于预判是否换行）
                   如果不提供，会在元素绘制后检查

        Returns:
            是否发生了换行（True = 换到新行了）

        使用方式:
            grid.begin_flow()
            for badge in badges:
                grid.flow_item()  # 自动处理 same_line 或换行
                imgui.small_button(badge)
            grid.end_flow()
        """
        wrapped = False

        if not hasattr(self, '_flow_cursor'):
            self._flow_cursor = 0
            self._flow_available = imgui.get_content_region_available_width()
            self._flow_first = True
            self._flow_gap = styles.gap_s()

        if not self._flow_first:
            # 预判：如果提供了宽度，检查是否放得下
            if width is not None:
                if self._flow_cursor + self._flow_gap + width > self._flow_available:
                    # 放不下，换行
                    self._flow_cursor = 0
                    wrapped = True
                else:
                    # 同行
                    imgui.same_line(spacing=self._flow_gap)
                    self._flow_cursor += self._flow_gap
            else:
                # 没有预判宽度，先 same_line，之后检查
                imgui.same_line(spacing=self._flow_gap)
                self._flow_cursor += self._flow_gap

        self._flow_first = False
        return wrapped

    def flow_item_after(self):
        """在元素绘制后调用，更新流式布局游标

        如果 flow_item() 没有传入 width，需要在元素绘制后调用此方法。
        """
        if hasattr(self, '_flow_cursor'):
            item_w = imgui.get_item_rect_size()[0]
            self._flow_cursor += item_w
            self._flow_first = False  # 确保后续元素会调用 same_line


# ==================== 便利函数 ====================


@contextmanager
def item_width(width: float):
    """上下文管理器：自动 push/pop item width"""
    imgui.push_item_width(width)
    try:
        yield
    finally:
        imgui.pop_item_width()


def tooltip(text: str):
    """在前一个控件悬停时显示提示，简化 is_item_hovered + set_tooltip 模式"""
    if text and imgui.is_item_hovered():
        imgui.set_tooltip(text)
