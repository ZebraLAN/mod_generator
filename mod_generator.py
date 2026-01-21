# -*- coding: utf-8 -*-
"""
Stoneshard 装备模组编辑器 - 主程序

基于 ImGui 的图形界面，用于创建和编辑 Stoneshard 游戏的武器/装备模组。
"""

import copy
import json
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import glfw
import imgui
from imgui.integrations.glfw import GlfwRenderer
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_NEAREST,
    GL_RGBA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_UNSIGNED_BYTE,
    glBindTexture,
    glClear,
    glClearColor,
    glDeleteTextures,
    glGenTextures,
    glTexImage2D,
    glTexParameteri,
)

try:
    from PIL import Image
except ImportError:
    Image = None

# fonttools 可选，用于读取字体 em 信息（当前未使用，保留备用）
# try:
#     from fontTools.ttLib import TTFont
#     HAS_FONTTOOLS = True
# except ImportError:
#     TTFont = None
#     HAS_FONTTOOLS = False

# 导入拆分后的模块
from constants import (
    # 属性分组系统
    WEAPON_ATTRIBUTES,
    ARMOR_ATTRIBUTES,
    get_attribute_groups,
    DEFAULT_GROUP_ORDER,
    # 其他常量
    ARMOR_CLASS_LABELS,
    ARMOR_FRAGMENT_LABELS,
    ARMOR_PREVIEW_HEIGHT,
    ARMOR_PREVIEW_WIDTH,
    ARMOR_SLOT_LABELS,
    ARMOR_SLOTS_MULTI_POSE,
    STRICT_INT_ATTRIBUTES,
    SPECIAL_STEP_ATTRIBUTES,
    CHARACTER_MODEL_LABELS,
    CHARACTER_MODELS,
    CHARACTER_RACE_LABELS,
    CHARACTER_RACES,
    GAME_FPS,
    LANGUAGE_LABELS,
    LEFT_HAND_SLOTS,
    NEGATIVE_ATTRIBUTES,
    PREVIEW_ANIMATION_FPS,
    PRIMARY_LANGUAGE,
    RARITY_LABELS,
    SLOT_LABELS,
    TAG_LABELS,
    TIER,
    TIER_LABELS,
    VALID_AREA_SIZE,
    VIEWPORT_CHAR_OFFSET_X,
    VIEWPORT_CHAR_OFFSET_Y,
    WEAPON_MATERIAL_LABELS,
    ARMOR_MATERIAL_LABELS,
    get_model_key,
    # 混合物品常量
    HYBRID_SLOT_LABELS,
    HYBRID_QUALITY_LABELS,
    HYBRID_WEAPON_TYPES,
    HYBRID_DAMAGE_TYPES,
    HYBRID_MATERIALS,
    HYBRID_ARMOR_TYPES,
    HYBRID_ARMOR_CLASSES,
    HYBRID_PICKUP_SOUNDS,
    HYBRID_DROP_SOUNDS,
    HYBRID_WEIGHT_LABELS,
    # 消耗品属性常量

    CONSUMABLE_DURATION_ATTRIBUTE,
    CONSUMABLE_INSTANT_GROUP_PREFIX,
    # 混合物品槽位属性
    get_hybrid_attrs_for_slot,
    get_consumable_duration_attrs,
    CONSUMABLE_INSTANT_ATTRS,
    TRIGGER_MODES,
)
from generator import CodeGenerator, copy_item_textures
from models import (
    Armor,
    HybridItem,
    ModProject,
    SpawnRule,
    SpawnMode,  # 保留用于迁移
    EquipmentMode,
    TriggerMode,
    ChargeMode,
    Weapon,
    validate_item,
    validate_hybrid_item,
)
from attribute_data import ATTRIBUTE_TRANSLATIONS, ATTRIBUTE_DESCRIPTIONS
from skill_constants import (
    SKILL_OBJECTS,
    SKILL_BRANCH_TRANSLATIONS,
    SKILL_BY_BRANCH,
    SKILL_OBJECT_NAMES,
)
from drop_slot_data import (
    ITEM_CATEGORIES,
    ALL_SUBCATEGORY_OPTIONS,
    CATEGORY_TRANSLATIONS,
    QUALITY_TAGS,
    DUNGEON_TAGS,
    COUNTRY_TAGS,
    EXTRA_TAGS,
    ALL_TAGS,
    find_matching_slots,
    find_matching_eq_slots,
)
from shop_configs import NPC_METADATA, SHOP_CONFIGS

def get_attr_display(attr: str, lang: str = "Chinese") -> tuple[str, str]:
    """获取属性的本地化显示名称和说明

    Args:
        attr: 属性键名 (如 "Hit_Chance")
        lang: 语言 (默认 "Chinese")，可选: Chinese, English, Russian, German, Spanish, French, Italian, Portuguese, Polish, Turkish, Japanese, Korean

    Returns:
        (显示名称, 详细说明) 元组
    """
    # 获取属性翻译名称
    trans = ATTRIBUTE_TRANSLATIONS.get(attr, {})
    name = trans.get(lang) or trans.get("Chinese") or trans.get("English") or attr

    # 获取属性说明
    desc_dict = ATTRIBUTE_DESCRIPTIONS.get(attr, {})
    desc = desc_dict.get(lang) or desc_dict.get("Chinese") or desc_dict.get("English") or ""

    return (name, desc)


# ==================== ImGui 辅助函数 ====================
# 减少重复的样板代码，提高信息密度

from contextlib import contextmanager


class Layout:
    """布局尺寸 Design System

    所有尺寸以 em 为单位，1em = font_size px。
    配合 apply_theme() 中的 style 缩放，确保不同字号下 UI 比例一致。

    Token 计算基于 ImGui 内部尺寸:
    - Step 按钮宽度 ≈ 1.75em (含 frame_padding)
    - 字符宽度: CJK ≈ 1em, Latin ≈ 0.5em

    使用示例:
        self.layout = Layout(lambda: self.font_size)
        width = self.layout.input_m      # 预定义尺寸
        width = self.layout.em(12)       # 自定义 12em
        width = self.layout.span(2)      # Grid: 2列宽度
    """

    # ===== 输入框宽度 (em) =====
    # 公式: 3.5em (step按钮) + 字符数 × 字符宽度
    INPUT_XS = 5     # 2 CJK字符
    INPUT_S  = 6     # 4 数字字符
    INPUT_M  = 8     # 6 混合字符 (负数+小数)
    INPUT_L  = 12    # 12 拉丁字符 (ID/名称)
    INPUT_XL = 18    # 21 拉丁字符 (长技能名)

    # ===== Grid 系统 (em) =====
    # chunk_width(n) = n * GRID_COL + (n - 1) * GRID_GAP
    GRID_COL = 3.5   # 基础列宽 (3.5em ≈ 3.5中文字)
    GRID_GAP = 0.5   # 列间距 (0.5em ≈ 8px)
    GRID_DEBUG = False  # 开启 grid 调试线

    # ===== Grid 语义别名 (span 数) =====
    SPAN_INPUT = 2   # 输入框默认占用列数
    SPAN_BADGE = 1   # Badge 默认占用列数
    SPAN_ID = 4      # ID 输入框占用列数

    # ===== 列宽 (em) - INPUT 别名 =====
    LABEL_COL = INPUT_S     # 6em - 标签列
    COL_NARROW = INPUT_M    # 8em - 窄列
    COL_NORMAL = INPUT_L    # 12em - 标准列
    COL_WIDE = INPUT_XL     # 18em - 宽列

    # ===== 间距 (em) - 2× 递增节奏 =====
    GAP_XS = 0.25    # inline 紧凑
    GAP_S  = 0.5     # 标签-输入间
    GAP_M  = 1.0     # 行间
    GAP_L  = 1.5     # 区块间

    def __init__(self, get_font_size):
        self._get_font_size = get_font_size

    def em(self, n: float) -> float:
        """将 em 单位转换为像素 (1em = font_size px)"""
        return n * self._get_font_size()

    def span(self, n: int) -> float:
        """Grid 系统：计算 n 列的宽度

        公式: n * col + (n - 1) * gap

        span(1) = 48px   (1列，无间隙)
        span(2) = 104px  (2列，1间隙)
        span(3) = 160px  (3列，2间隙)
        """
        return self.em(n * self.GRID_COL + max(0, n - 1) * self.GRID_GAP)


    # ===== 输入框宽度属性 =====
    @property
    def input_xs(self) -> float: return self.em(self.INPUT_XS)
    @property
    def input_s(self) -> float: return self.em(self.INPUT_S)
    @property
    def input_m(self) -> float: return self.em(self.INPUT_M)
    @property
    def input_l(self) -> float: return self.em(self.INPUT_L)
    @property
    def input_xl(self) -> float: return self.em(self.INPUT_XL)

    # ===== 列宽属性 =====
    @property
    def label_col(self) -> float: return self.em(self.LABEL_COL)
    @property
    def col_narrow(self) -> float: return self.em(self.COL_NARROW)
    @property
    def col_normal(self) -> float: return self.em(self.COL_NORMAL)
    @property
    def col_wide(self) -> float: return self.em(self.COL_WIDE)

    # ===== Grid 属性 =====
    @property
    def grid_col(self) -> float: return self.em(self.GRID_COL)
    @property
    def grid_gap(self) -> float: return self.em(self.GRID_GAP)

    # ===== 间距属性 =====
    @property
    def gap_xs(self) -> float: return self.em(self.GAP_XS)
    @property
    def gap_s(self) -> float: return self.em(self.GAP_S)
    @property
    def gap_m(self) -> float: return self.em(self.GAP_M)
    @property
    def gap_l(self) -> float: return self.em(self.GAP_L)


class WrapLayout:
    """自动换行布局器 - Context Manager API

    使用示例:
        with WrapLayout(self.layout) as wrap:
            wrap.labeled("品质", self.layout.input_s)
            self._draw_enum_combo(...)

            wrap.labeled("等级", self.layout.input_xs)
            ...
    """

    def __init__(self, layout, gap=None):
        self.layout = layout
        self.gap = gap if gap is not None else layout.gap_m
        self._cursor = 0
        self._available = 0
        self._first = True

    def __enter__(self):
        self._available = imgui.get_content_region_available_width()
        self._cursor = 0
        self._first = True
        return self

    def __exit__(self, *args):
        pass

    def _maybe_wrap(self, width: float) -> bool:
        """内部：判断是否需要换行，返回是否换行了"""
        wrapped = False
        if not self._first:
            if self._cursor + self.gap + width > self._available:
                # 放不下，换行
                self._cursor = 0
                wrapped = True
            else:
                # 同行
                imgui.same_line(spacing=self.gap)
                self._cursor += self.gap
        self._cursor += width
        self._first = False
        return wrapped

    def item(self, width: float):
        """单控件占位"""
        self._maybe_wrap(width)

    def labeled(self, label: str, input_width: float):
        """标签+输入框组合 (最常用)

        自动计算标签实际宽度，确保 label+input 作为原子单元不被拆分。
        调用后需紧跟输入控件 (已 set_next_item_width)。
        """
        label_w = imgui.calc_text_size(label)[0]
        total = label_w + self.layout.gap_s + input_width
        self._maybe_wrap(total)
        imgui.align_text_to_frame_padding()  # 垂直居中
        imgui.text(label)
        imgui.same_line(spacing=self.layout.gap_s)
        imgui.set_next_item_width(input_width)

    @contextmanager
    def group(self, width: float):
        """自定义宽度的原子组

        用于非标准组合，用户需自行保证内部元素总宽度 ≈ width。
        """
        self._maybe_wrap(width)
        yield


class GridLayout:
    """Grid 布局助手 - 用于 label-on-top 的表单布局

    使用示例:
        grid = GridLayout(self.layout, self.text_secondary)

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

    def __init__(self, layout: Layout, text_secondary_fn=None):
        """
        Args:
            layout: Layout 实例
            text_secondary_fn: 可选的 text_secondary 函数，用于绘制标签
        """
        self.layout = layout
        self.text_secondary = text_secondary_fn or (lambda t: imgui.text(t))

    @property
    def span(self):
        """返回 layout.span 函数"""
        return self.layout.span

    @property
    def gap(self) -> float:
        """返回 grid_gap 像素值"""
        return self.layout.grid_gap

    def next_cell(self):
        """移动到下一个 grid cell (同一行)"""
        imgui.same_line(spacing=self.layout.grid_gap)

    def label_header(self, text: str, cols: int = 3):
        """绘制 label header，占用 cols 列宽度"""
        target_w = self.layout.span(cols)
        self.text_secondary(text)
        text_w = imgui.calc_text_size(text).x
        if text_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - text_w, 0)

    def field_width(self, cols: int = 3):
        """设置下一个控件的宽度为 span(cols)"""
        imgui.set_next_item_width(self.layout.span(cols))

    def text_cell(self, text: str, cols: int = 3):
        """绘制只读文本，占用 cols 列宽度"""
        target_w = self.layout.span(cols)
        imgui.align_text_to_frame_padding()
        imgui.text(text)
        text_w = imgui.calc_text_size(text).x
        if text_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - text_w, 0)

    def button_cell(self, label: str, cols: int = 3) -> bool:
        """绘制按钮，占用 cols 列宽度，返回是否点击"""
        target_w = self.layout.span(cols)
        clicked = imgui.button(label)
        btn_w = imgui.get_item_rect_size()[0]
        if btn_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - btn_w, 0)
        return clicked

    def checkbox_cell(self, label: str, value: bool, cols: int = 3) -> tuple:
        """绘制 checkbox，占用 cols 列宽度，返回 (changed, new_value)"""
        target_w = self.layout.span(cols)
        changed, new_value = imgui.checkbox(label, value)
        cb_w = imgui.get_item_rect_size()[0]
        if cb_w < target_w:
            imgui.same_line(spacing=0)
            imgui.dummy(target_w - cb_w, 0)
        return changed, new_value

    # ===== 流式布局支持 (Flow Layout) =====
    # 用于处理可变宽度的 badges、buttons 等

    def begin_flow(self, max_width: float = None):
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
        self._flow_gap = self.layout.gap_s

    def end_flow(self):
        """结束流式布局区域"""
        self._flow_cursor = 0
        self._flow_first = True

    def flow_item(self, width: float = None) -> bool:
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
            self._flow_gap = self.layout.gap_s

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


@contextmanager
def item_width(width: float):
    """上下文管理器：自动 push/pop item width"""
    imgui.push_item_width(width)
    try:
        yield
    finally:
        imgui.pop_item_width()


@contextmanager
def framed_group(title: str = "", padding: float = 6.0):
    """带1px边框的分组容器，经典工具软件风格

    Args:
        title: 可选标题，显示在边框左上角
        padding: 内边距

    Usage:
        with framed_group("形态"):
            # 内容...
    """
    draw_list = imgui.get_window_draw_list()

    # 记录起始位置
    start_pos = imgui.get_cursor_screen_pos()
    start_cursor = imgui.get_cursor_pos()

    # 标题高度计算
    title_height = 0
    if title:
        title_height = imgui.get_text_line_height()

    # 为边框和标题留出空间
    imgui.dummy(0, padding + title_height * 0.5 if title else padding)
    imgui.indent(padding)

    # 开始一个 group 来追踪内容尺寸
    imgui.begin_group()

    try:
        yield
    finally:
        imgui.end_group()

        # 获取 group 尺寸
        content_min = imgui.get_item_rect_min()
        content_max = imgui.get_item_rect_max()

        # 取消缩进
        imgui.unindent(padding)
        imgui.dummy(0, padding)

        # 计算边框位置
        frame_min_x = start_pos.x
        frame_min_y = start_pos.y + (title_height * 0.5 if title else 0)
        frame_max_x = content_max.x + padding
        frame_max_y = imgui.get_cursor_screen_pos().y

        # 获取边框颜色
        border_color = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 0.6)
        bg_color = imgui.get_color_u32_rgba(0.0, 0.0, 0.0, 0.0)  # 透明背景

        # 绘制边框（1px 实线）
        draw_list.add_rect(
            frame_min_x, frame_min_y,
            frame_max_x, frame_max_y,
            border_color, rounding=0.0, thickness=1.0
        )

        # 绘制标题
        if title:
            title_x = frame_min_x + padding
            title_y = start_pos.y
            title_size = imgui.calc_text_size(title)

            # 绘制标题背景（覆盖边框线）
            window_bg = imgui.get_style().colors[imgui.COLOR_WINDOW_BACKGROUND]
            bg_color = imgui.get_color_u32_rgba(window_bg.x, window_bg.y, window_bg.z, window_bg.w)
            draw_list.add_rect_filled(
                title_x - 4, title_y,
                title_x + title_size.x + 4, title_y + title_size.y,
                bg_color
            )

            # 绘制标题文字
            text_color = imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1.0)
            draw_list.add_text(title_x, title_y, text_color, title)



def tooltip(text: str):
    """在前一个控件悬停时显示提示，简化 is_item_hovered + set_tooltip 模式"""
    if text and imgui.is_item_hovered():
        imgui.set_tooltip(text)


class ModGeneratorGUI:
    """主 GUI 类"""

    def __init__(self):
        self.window = None
        self.error_message = ""

        if not glfw.init():
            print("无法初始化 GLFW")
            sys.exit(1)

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)

        self.window = glfw.create_window(
            1200, 800, "Stoneshard 装备模组编辑器", None, None
        )
        if not self.window:
            glfw.terminate()
            print("无法创建 GLFW 窗口")
            sys.exit(1)

        glfw.make_context_current(self.window)
        imgui.create_context()
        self.io = imgui.get_io()
        self.renderer = GlfwRenderer(self.window)

        # 确保字体目录存在
        os.makedirs("fonts", exist_ok=True)

        # 配置项
        self.font_size = 16
        self.primary_font_path = ""
        self.fallback_font_path = ""
        self.is_dark_theme = True
        self.texture_scale = 4.0
        self.should_reload_fonts = False

        # 加载配置
        self.load_config()

        # 布局尺寸系统（必须在 apply_theme 之前初始化）
        self.layout = Layout(lambda: self.font_size)

        # 应用主题和字体
        self.apply_theme()
        self.reload_fonts()

        # 项目和状态
        self.project = ModProject()
        self.current_weapon_index = -1
        self.current_armor_index = -1
        self.current_hybrid_index = -1
        self.show_import_dialog = False
        self.import_file_path = ""
        self.import_conflicts = []
        self.current_texture_field = ""
        self.texture_preview_cache = {}
        self.selected_model = "Human Male"
        self.selected_race = "Human"  # 多姿势编辑器中的人种选择
        self.preview_states = {}
        self.active_item_tab = 0
        self.gender_tab_index = 0  # 0=男性, 1=女性

        # 弹窗状态
        self.show_error_popup = False
        self.show_save_popup = False
        self.show_success_popup = False

        # 缓存属性分组（避免每帧重复计算）
        self._weapon_attr_groups = get_attribute_groups(WEAPON_ATTRIBUTES, DEFAULT_GROUP_ORDER)
        self._armor_attr_groups = get_attribute_groups(ARMOR_ATTRIBUTES, DEFAULT_GROUP_ORDER)

    # ==================== ImGui Custom Widgets ====================

    def _draw_text_action_button(self, label: str, active_color, hover_color) -> bool:
        """绘制纯文本样式的动作按钮 (无边框/背景，hover变色)"""
        # 处理 ID (text##id)
        display_text = label.split("##")[0]

        start_x = imgui.get_cursor_pos_x()
        start_y = imgui.get_cursor_pos_y()

        text_w = imgui.calc_text_size(display_text).x
        text_h = imgui.get_text_line_height()

        imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, 0))
        imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)

        # 按钮也是 invisible 的，但需要唯一 ID (label 本身应包含 ##ID)
        clicked = imgui.invisible_button(f"btn_{label}", text_w, text_h)
        is_hovered = imgui.is_item_hovered()

        imgui.pop_style_color(3)
        imgui.pop_style_var()

        if is_hovered:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)

        current_x = imgui.get_cursor_pos_x()
        current_y = imgui.get_cursor_pos_y()

        imgui.set_cursor_pos((start_x, start_y))
        # Remove alignment to match standard text headers

        col = hover_color if is_hovered else active_color
        imgui.text_colored(display_text, *col)

        imgui.set_cursor_pos((current_x, current_y))
        return clicked

    # ==================== 配置管理 ====================

    def load_config(self):
        """加载用户配置"""
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.font_size = config.get("font_size", 16)
                    self.primary_font_path = config.get("primary_font_path", "")
                    self.fallback_font_path = config.get("fallback_font_path", "")
                    self.is_dark_theme = config.get("is_dark_theme", True)
                    self.texture_scale = config.get("texture_scale", 4.0)
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save_config(self):
        """保存用户配置"""
        config = {
            "font_size": self.font_size,
            "primary_font_path": self.primary_font_path,
            "fallback_font_path": self.fallback_font_path,
            "is_dark_theme": self.is_dark_theme,
            "texture_scale": self.texture_scale,
        }
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def apply_theme(self):
        """应用颜色主题 - 基于 Layout 常量系统

        使用 self.layout 的 gap_* 属性确保 style 与 Layout token 一致
        """
        style = imgui.get_style()

        # === 间距与布局 - 直接使用 Layout 常量 ===
        gap_xs = self.layout.gap_xs  # 0.25em
        gap_s = self.layout.gap_s    # 0.5em
        gap_m = self.layout.gap_m    # 1.0em

        style.window_padding = (gap_s, gap_s)
        style.frame_padding = (gap_s, gap_xs)
        style.item_spacing = (gap_s, gap_xs)
        style.item_inner_spacing = (gap_xs, gap_xs)
        style.indent_spacing = gap_m
        style.scrollbar_size = gap_m        # 1em
        style.grab_min_size = gap_s

        # === 圆角 - 使用 GAP token ===
        style.window_rounding = gap_s   # 0.5em
        style.child_rounding = gap_xs   # 子窗口
        style.frame_rounding = gap_xs   # 0.25em
        style.popup_rounding = gap_xs
        style.scrollbar_rounding = gap_s
        style.grab_rounding = gap_xs
        style.tab_rounding = gap_xs

        # === 边框 ===
        style.window_border_size = 1
        style.child_border_size = 0
        style.frame_border_size = 0
        style.popup_border_size = 1
        style.tab_border_size = 0

        # === 表格与其他 ===
        style.cell_padding = (gap_xs, gap_xs)       # 表格单元格
        style.touch_extra_padding = (gap_xs, gap_xs)  # 触控扩展
        style.columns_min_spacing = gap_xs

        if self.is_dark_theme:
            self._apply_dark_theme(style)
        else:
            self._apply_light_theme(style)

    def _apply_dark_theme(self, style):
        """暗色主题 - 高对比、护眼、专业"""
        # 基础色板 (对比 Contrast)
        bg_dark = (0.08, 0.08, 0.10, 1.0)  # 最深背景
        bg_mid = (0.12, 0.12, 0.14, 1.0)  # 中间背景
        bg_light = (0.18, 0.18, 0.21, 1.0)  # 浅背景/悬停

        accent = (0.40, 0.65, 0.80, 1.0)  # 主强调色 - 冷蓝
        accent_hover = (0.50, 0.75, 0.90, 1.0)
        accent_active = (0.35, 0.55, 0.70, 1.0)

        text_primary = (0.95, 0.95, 0.95, 1.0)  # 主文字
        text_secondary = (0.60, 0.60, 0.65, 1.0)  # 次要文字
        text_disabled = (0.40, 0.40, 0.45, 1.0)

        border = (0.25, 0.25, 0.28, 1.0)

        success = (0.30, 0.70, 0.45, 1.0)  # 成功/确认
        warning = (0.90, 0.70, 0.25, 1.0)  # 警告
        error = (0.90, 0.35, 0.35, 1.0)  # 错误

        c = style.colors
        c[imgui.COLOR_TEXT] = text_primary
        c[imgui.COLOR_TEXT_DISABLED] = text_disabled
        c[imgui.COLOR_WINDOW_BACKGROUND] = bg_dark
        c[imgui.COLOR_CHILD_BACKGROUND] = (0, 0, 0, 0)
        c[imgui.COLOR_POPUP_BACKGROUND] = (0.10, 0.10, 0.12, 0.98)
        c[imgui.COLOR_BORDER] = border
        c[imgui.COLOR_BORDER_SHADOW] = (0, 0, 0, 0)
        c[imgui.COLOR_FRAME_BACKGROUND] = bg_mid
        c[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = bg_light
        c[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = (0.22, 0.22, 0.25, 1.0)
        c[imgui.COLOR_TITLE_BACKGROUND] = bg_dark
        c[imgui.COLOR_TITLE_BACKGROUND_ACTIVE] = bg_mid
        c[imgui.COLOR_TITLE_BACKGROUND_COLLAPSED] = bg_dark
        c[imgui.COLOR_MENUBAR_BACKGROUND] = bg_dark
        c[imgui.COLOR_SCROLLBAR_BACKGROUND] = bg_dark
        c[imgui.COLOR_SCROLLBAR_GRAB] = (0.30, 0.30, 0.33, 1.0)
        c[imgui.COLOR_SCROLLBAR_GRAB_HOVERED] = (0.40, 0.40, 0.43, 1.0)
        c[imgui.COLOR_SCROLLBAR_GRAB_ACTIVE] = accent
        c[imgui.COLOR_CHECK_MARK] = accent
        c[imgui.COLOR_SLIDER_GRAB] = accent
        c[imgui.COLOR_SLIDER_GRAB_ACTIVE] = accent_hover
        c[imgui.COLOR_BUTTON] = (0.20, 0.20, 0.23, 1.0)
        c[imgui.COLOR_BUTTON_HOVERED] = accent
        c[imgui.COLOR_BUTTON_ACTIVE] = accent_active
        c[imgui.COLOR_HEADER] = (0.20, 0.20, 0.23, 1.0)
        c[imgui.COLOR_HEADER_HOVERED] = accent
        c[imgui.COLOR_HEADER_ACTIVE] = accent_active
        c[imgui.COLOR_SEPARATOR] = border
        c[imgui.COLOR_SEPARATOR_HOVERED] = accent
        c[imgui.COLOR_SEPARATOR_ACTIVE] = accent
        c[imgui.COLOR_RESIZE_GRIP] = (0.25, 0.25, 0.28, 0.5)
        c[imgui.COLOR_RESIZE_GRIP_HOVERED] = accent
        c[imgui.COLOR_RESIZE_GRIP_ACTIVE] = accent_active
        c[imgui.COLOR_TAB] = bg_mid
        c[imgui.COLOR_TAB_HOVERED] = accent
        c[imgui.COLOR_TAB_ACTIVE] = accent_active
        c[imgui.COLOR_TAB_UNFOCUSED] = bg_mid
        c[imgui.COLOR_TAB_UNFOCUSED_ACTIVE] = bg_light
        c[imgui.COLOR_PLOT_LINES] = accent
        c[imgui.COLOR_PLOT_LINES_HOVERED] = accent_hover
        c[imgui.COLOR_PLOT_HISTOGRAM] = accent
        c[imgui.COLOR_PLOT_HISTOGRAM_HOVERED] = accent_hover
        c[imgui.COLOR_TEXT_SELECTED_BACKGROUND] = (*accent[:3], 0.35)
        c[imgui.COLOR_DRAG_DROP_TARGET] = accent
        c[imgui.COLOR_NAV_HIGHLIGHT] = accent
        c[imgui.COLOR_NAV_WINDOWING_HIGHLIGHT] = (1, 1, 1, 0.7)
        c[imgui.COLOR_NAV_WINDOWING_DIM_BACKGROUND] = (0.8, 0.8, 0.8, 0.2)
        c[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0, 0, 0, 0.6)

        # 保存主题色供其他地方使用
        self.theme_colors = {
            "text_secondary": text_secondary,
            "success": success,
            "warning": warning,
            "error": error,
            "accent": accent,
            # Badge 颜色系统
            "badge_subcat": (0.25, 0.35, 0.45, 1.0),       # 子分类: 蓝灰
            "badge_tag": (0.25, 0.40, 0.40, 1.0),          # 普通标签: 青色
            "badge_quality": (0.45, 0.38, 0.25, 1.0),      # 品质标签: 金色
            "badge_special": (0.40, 0.25, 0.45, 1.0),      # 特殊标签: 紫色
            "badge_hover_remove": (0.70, 0.30, 0.30, 1.0), # 可移除hover: 红色
            "badge_hover_locked": (0.35, 0.35, 0.38, 1.0), # 不可移除hover: 微亮灰
        }

    def _apply_light_theme(self, style):
        """亮色主题 - 清爽、高可读性"""
        bg_white = (0.98, 0.98, 0.98, 1.0)
        bg_light = (0.94, 0.94, 0.95, 1.0)
        bg_mid = (0.88, 0.88, 0.90, 1.0)

        accent = (0.20, 0.50, 0.70, 1.0)
        accent_hover = (0.25, 0.55, 0.75, 1.0)
        accent_active = (0.15, 0.45, 0.65, 1.0)

        text_primary = (0.10, 0.10, 0.12, 1.0)
        text_secondary = (0.45, 0.45, 0.50, 1.0)
        text_disabled = (0.60, 0.60, 0.65, 1.0)

        border = (0.75, 0.75, 0.78, 1.0)

        c = style.colors
        c[imgui.COLOR_TEXT] = text_primary
        c[imgui.COLOR_TEXT_DISABLED] = text_disabled
        c[imgui.COLOR_WINDOW_BACKGROUND] = bg_white
        c[imgui.COLOR_CHILD_BACKGROUND] = (0, 0, 0, 0)
        c[imgui.COLOR_POPUP_BACKGROUND] = (1, 1, 1, 0.98)
        c[imgui.COLOR_BORDER] = border
        c[imgui.COLOR_FRAME_BACKGROUND] = bg_light
        c[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = bg_mid
        c[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = (0.82, 0.82, 0.85, 1.0)
        c[imgui.COLOR_TITLE_BACKGROUND] = bg_light
        c[imgui.COLOR_TITLE_BACKGROUND_ACTIVE] = bg_mid
        c[imgui.COLOR_MENUBAR_BACKGROUND] = bg_light
        c[imgui.COLOR_SCROLLBAR_BACKGROUND] = bg_light
        c[imgui.COLOR_SCROLLBAR_GRAB] = (0.70, 0.70, 0.73, 1.0)
        c[imgui.COLOR_SCROLLBAR_GRAB_HOVERED] = (0.60, 0.60, 0.63, 1.0)
        c[imgui.COLOR_SCROLLBAR_GRAB_ACTIVE] = accent
        c[imgui.COLOR_CHECK_MARK] = accent
        c[imgui.COLOR_SLIDER_GRAB] = accent
        c[imgui.COLOR_SLIDER_GRAB_ACTIVE] = accent_hover
        c[imgui.COLOR_BUTTON] = bg_mid
        c[imgui.COLOR_BUTTON_HOVERED] = accent
        c[imgui.COLOR_BUTTON_ACTIVE] = accent_active
        c[imgui.COLOR_HEADER] = bg_mid
        c[imgui.COLOR_HEADER_HOVERED] = accent
        c[imgui.COLOR_HEADER_ACTIVE] = accent_active
        c[imgui.COLOR_SEPARATOR] = border
        c[imgui.COLOR_TAB] = bg_light
        c[imgui.COLOR_TAB_HOVERED] = accent
        c[imgui.COLOR_TAB_ACTIVE] = accent_active
        c[imgui.COLOR_TEXT_SELECTED_BACKGROUND] = (*accent[:3], 0.35)
        c[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0, 0, 0, 0.4)

        self.theme_colors = {
            "text_secondary": text_secondary,
            "success": (0.20, 0.60, 0.35, 1.0),
            "warning": (0.85, 0.60, 0.10, 1.0),
            "error": (0.85, 0.25, 0.25, 1.0),
            "accent": accent,
            # Badge 颜色系统 (亮色主题适配)
            "badge_subcat": (0.55, 0.65, 0.75, 1.0),       # 子分类: 浅蓝灰
            "badge_tag": (0.50, 0.70, 0.70, 1.0),          # 普通标签: 浅青色
            "badge_quality": (0.75, 0.65, 0.45, 1.0),      # 品质标签: 浅金色
            "badge_special": (0.70, 0.55, 0.75, 1.0),      # 特殊标签: 浅紫色
            "badge_hover_remove": (0.85, 0.45, 0.45, 1.0), # 可移除hover: 浅红色
            "badge_hover_locked": (0.65, 0.65, 0.68, 1.0), # 不可移除hover: 微亮灰
        }

    # ==================== 主题颜色辅助方法 ====================

    def text_secondary(self, text: str):
        """绘制次要文字（灰色）"""
        imgui.text_colored(text, *self.theme_colors["text_secondary"])

    def text_success(self, text: str):
        """绘制成功文字（绿色）"""
        imgui.text_colored(text, *self.theme_colors["success"])

    def text_warning(self, text: str):
        """绘制警告文字（橙色）"""
        imgui.text_colored(text, *self.theme_colors["warning"])

    def text_error(self, text: str):
        """绘制错误文字（红色）"""
        imgui.text_colored(text, *self.theme_colors["error"])

    def text_accent(self, text: str):
        """绘制强调文字（主题色）"""
        imgui.text_colored(text, *self.theme_colors["accent"])

    # ==================== 字体管理 ====================

    def _find_font(self, user_path: str, bundled_dir: str, *fallbacks: str) -> str:
        """查找第一个存在的字体路径"""
        candidates = []
        if user_path:
            candidates.append(os.path.join(bundled_dir, user_path))
            candidates.append(user_path)
        candidates.extend(fallbacks)
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return ""

    def reload_fonts(self):
        """重新加载字体"""
        self.io.fonts.clear()

        # 英文字体 (主字体)
        en_path = self._find_font(
            self.primary_font_path, "fonts/english", "C:/Windows/Fonts/arial.ttf"
        )
        if en_path:
            try:
                self.io.fonts.add_font_from_file_ttf(en_path, self.font_size)
            except Exception as e:
                print(f"英文字体加载失败: {e}")
                self.io.fonts.add_font_default()
        else:
            self.io.fonts.add_font_default()

        # 中文字体 (合并模式)
        cn_path = self._find_font(
            self.fallback_font_path,
            "fonts/chinese",
            "fonts/chinese/HanyiSentyYongleEncyclopedia-2020.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        )
        if cn_path:
            try:
                font_config = imgui.core.FontConfig(merge_mode=True)
                try:
                    ranges = self.io.fonts.get_glyph_ranges_chinese_full()
                except AttributeError:
                    ranges = self.io.fonts.get_glyph_ranges_chinese()
                self.io.fonts.add_font_from_file_ttf(
                    cn_path,
                    self.font_size,
                    font_config=font_config,
                    glyph_ranges=ranges,
                )
            except Exception as e:
                print(f"中文字体加载失败: {e}")

        try:
            self.renderer.refresh_font_texture()
        except Exception as e:
            print(f"刷新字体纹理失败: {e}")

    def get_bundled_fonts(self, subdir):
        """获取 fonts 子目录下的字体文件列表"""
        path = os.path.join("fonts", subdir)
        if not os.path.exists(path):
            return []
        return [
            f for f in os.listdir(path) if f.lower().endswith((".ttf", ".ttc", ".otf"))
        ]

    # ==================== 主循环 ====================

    def run(self):
        """主循环"""
        running = True
        while running:
            if glfw.window_should_close(self.window):
                running = False
            glfw.poll_events()
            self.renderer.process_inputs()

            if self.should_reload_fonts:
                self.reload_fonts()
                self.apply_theme()  # 同步更新 style 缩放
                self.should_reload_fonts = False

            imgui.new_frame()

            self.draw_main_menu()
            self.draw_main_interface()

            if self.show_import_dialog:
                self.draw_import_dialog()

            self.draw_common_popups()

            imgui.render()
            glClearColor(0, 0, 0, 1)
            glClear(GL_COLOR_BUFFER_BIT)
            self.renderer.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)

        self.clear_texture_previews()
        self.renderer.shutdown()
        glfw.terminate()

    # ==================== 弹窗 ====================

    def draw_common_popups(self):
        """绘制通用弹窗"""
        if self.show_error_popup:
            imgui.open_popup("错误")
            self.show_error_popup = False

        if self.show_save_popup:
            imgui.open_popup("保存项目")
            self.show_save_popup = False

        if self.show_success_popup:
            imgui.open_popup("生成成功")
            self.show_success_popup = False

        # 生成成功弹窗
        imgui.set_next_window_size(450, 180, imgui.ONCE)
        if imgui.begin_popup_modal("生成成功", flags=imgui.WINDOW_NO_RESIZE)[0]:
            base_dir = (
                os.path.dirname(self.project.file_path)
                if self.project.file_path
                else "."
            )
            mod_dir = os.path.abspath(
                os.path.join(base_dir, self.project.code_name.strip() or "ModProject")
            )

            imgui.dummy(0, 8)
            self.text_success("[OK] 模组生成成功！")
            imgui.dummy(0, 8)

            self.text_secondary("输出目录:")
            imgui.text_wrapped(mod_dir)

            imgui.dummy(0, 16)

            # 按钮右对齐
            button_width = 100
            imgui.set_cursor_pos_x(imgui.get_window_width() - button_width * 2 - 24)
            if imgui.button("打开目录", width=button_width):
                try:
                    os.startfile(mod_dir)
                except Exception:
                    pass

            imgui.same_line()
            if imgui.button("确定", width=button_width):
                imgui.close_current_popup()
            imgui.end_popup()

        # 错误弹窗
        imgui.set_next_window_size(450, 0, imgui.ONCE)  # 高度自适应
        if imgui.begin_popup_modal("错误", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            imgui.dummy(0, 4)
            self.text_error("[X] 发生错误")
            imgui.dummy(0, 8)
            imgui.text_wrapped(getattr(self, "error_message", "发生未知错误"))
            imgui.dummy(0, 12)

            button_width = 80
            imgui.set_cursor_pos_x(imgui.get_window_width() - button_width - 12)
            if imgui.button("确定", width=button_width):
                imgui.close_current_popup()
            imgui.end_popup()

        # 保存项目弹窗
        imgui.set_next_window_size(350, 0, imgui.ONCE)
        if imgui.begin_popup_modal("保存项目", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[
            0
        ]:
            imgui.dummy(0, 4)
            self.text_warning("[!] 需要保存项目")
            imgui.dummy(0, 8)
            imgui.text("生成模组前需要先保存项目。")
            imgui.text("是否现在保存？")
            imgui.dummy(0, 12)

            button_width = 80
            imgui.set_cursor_pos_x(imgui.get_window_width() - button_width * 2 - 20)
            if imgui.button("保存", width=button_width):
                imgui.close_current_popup()
                self.save_project_dialog()
                if self.project.file_path:
                    self._execute_generation()

            imgui.same_line()
            if imgui.button("取消", width=button_width):
                imgui.close_current_popup()

            imgui.end_popup()

    def _show_error(self, message: str):
        """显示错误弹窗"""
        print(f"错误: {message.split(chr(10))[0]}")
        self.error_message = message
        self.show_error_popup = True

    # ==================== 主菜单 ====================

    def draw_main_menu(self):
        """绘制主菜单"""
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("文件", True):
                if imgui.menu_item("新建项目")[0]:
                    self.new_project_dialog()
                if imgui.menu_item("打开项目")[0]:
                    self.open_project_dialog()
                if imgui.menu_item("保存项目")[0]:
                    if self.project.file_path:
                        self.project.save()
                if imgui.menu_item("导入项目", enabled=False)[0]:
                    self.show_import_dialog = True
                if imgui.is_item_hovered(flags=imgui.HOVERED_ALLOW_WHEN_DISABLED):
                    imgui.set_tooltip("该功能尚未测试")

                imgui.separator()
                if imgui.menu_item("生成模组")[0]:
                    self.generate_mod()
                imgui.separator()
                if imgui.menu_item("退出")[0]:
                    glfw.set_window_should_close(self.window, True)
                imgui.end_menu()

            if imgui.begin_menu("设置", True):
                # 字号设置
                if imgui.begin_menu("字体大小"):
                    for size in [14, 16, 18, 20, 24, 28, 32]:
                        if imgui.menu_item(
                            f"{size} px", selected=(self.font_size == size)
                        )[0]:
                            self.font_size = size
                            self.save_config()
                            self.should_reload_fonts = True
                    imgui.end_menu()

                # 主题设置
                if imgui.menu_item("暗色主题", selected=self.is_dark_theme)[0]:
                    self.is_dark_theme = True
                    self.apply_theme()
                    self.save_config()

                if imgui.menu_item("亮色主题", selected=not self.is_dark_theme)[0]:
                    self.is_dark_theme = False
                    self.apply_theme()
                    self.save_config()

                imgui.separator()

                # 字体选择
                if imgui.begin_menu("选择字体"):
                    self._draw_font_menu(
                        "英文字体 (English)",
                        "english",
                        "primary_font_path",
                        [
                            ("Arial", "C:/Windows/Fonts/arial.ttf"),
                            ("Times New Roman", "C:/Windows/Fonts/times.ttf"),
                            ("Segoe UI", "C:/Windows/Fonts/segoeui.ttf"),
                            ("Verdana", "C:/Windows/Fonts/verdana.ttf"),
                            ("Tahoma", "C:/Windows/Fonts/tahoma.ttf"),
                            ("Consolas", "C:/Windows/Fonts/consolas.ttf"),
                        ],
                        "系统英文字体:",
                    )
                    self._draw_font_menu(
                        "中文字体 (Chinese)",
                        "chinese",
                        "fallback_font_path",
                        [
                            ("微软雅黑 (Microsoft YaHei)", "C:/Windows/Fonts/msyh.ttc"),
                            ("黑体 (SimHei)", "C:/Windows/Fonts/simhei.ttf"),
                            ("宋体 (SimSun)", "C:/Windows/Fonts/simsun.ttc"),
                            ("楷体 (KaiTi)", "C:/Windows/Fonts/simkai.ttf"),
                        ],
                        "系统中文字体:",
                    )
                    imgui.end_menu()

                imgui.end_menu()

            imgui.end_main_menu_bar()

    def _draw_font_menu(
        self, menu_label, font_type, attr_name, system_fonts, system_label
    ):
        """绘制字体选择子菜单"""
        if imgui.begin_menu(menu_label):
            current_path = getattr(self, attr_name)
            bundled_fonts = self.get_bundled_fonts(font_type)
            if bundled_fonts:
                self.text_secondary("内置字体:")
                for font_file in bundled_fonts:
                    if imgui.menu_item(font_file, selected=(current_path == font_file))[
                        0
                    ]:
                        setattr(self, attr_name, font_file)
                        self.save_config()
                        self.should_reload_fonts = True
                imgui.separator()

            self.text_secondary(system_label)
            for label, path in system_fonts:
                if os.path.exists(path):
                    if imgui.menu_item(label, selected=(current_path == path))[0]:
                        setattr(self, attr_name, path)
                        self.save_config()
                        self.should_reload_fonts = True

            if current_path:
                imgui.separator()
                if imgui.menu_item("清除选择 (使用默认)", selected=False)[0]:
                    setattr(self, attr_name, "")
                    self.save_config()
                    self.should_reload_fonts = True
            imgui.end_menu()

    # ==================== 主界面 ====================

    def draw_main_interface(self):
        """绘制主界面"""
        display_w, display_h = self.io.display_size
        menu_bar_height = imgui.get_frame_height()

        imgui.set_next_window_position(0, menu_bar_height)
        imgui.set_next_window_size(display_w, display_h - menu_bar_height)

        imgui.begin(
            "Main Interface",
            flags=imgui.WINDOW_NO_RESIZE
            | imgui.WINDOW_NO_MOVE
            | imgui.WINDOW_NO_COLLAPSE
            | imgui.WINDOW_NO_TITLE_BAR,
        )

        if not self.project.file_path:
            # 显示欢迎界面 - 居中布局
            self._draw_welcome_screen()
        else:
            # 项目信息
            if imgui.tree_node("项目信息", flags=imgui.TREE_NODE_FRAMED):
                self.draw_project_info()
                imgui.tree_pop()

            # 物品标签页
            if imgui.begin_tab_bar("ItemTabBar"):
                # Tab ID 必须固定，否则动态内容（数量）变化会导致 tab 跳转
                weapon_tab_label = f"武器 ({len(self.project.weapons)})###WeaponTab"
                if imgui.begin_tab_item(weapon_tab_label)[0]:
                    self.active_item_tab = 0
                    self.draw_item_panel(
                        "Weapon",
                        self.project.weapons,
                        "current_weapon_index",
                        self.draw_weapon_list,
                        self.draw_weapon_editor,
                        "请从左侧列表选择一个武器进行编辑",
                    )
                    imgui.end_tab_item()

                armor_tab_label = f"装备 ({len(self.project.armors)})###ArmorTab"
                if imgui.begin_tab_item(armor_tab_label)[0]:
                    self.active_item_tab = 1
                    self.draw_item_panel(
                        "Armor",
                        self.project.armors,
                        "current_armor_index",
                        self.draw_armor_list,
                        self.draw_armor_editor,
                        "请从左侧列表选择一个装备进行编辑",
                    )
                    imgui.end_tab_item()

                hybrid_tab_label = f"混合物品 ({len(self.project.hybrid_items)})###HybridTab"
                if imgui.begin_tab_item(hybrid_tab_label)[0]:
                    self.active_item_tab = 2
                    self.draw_item_panel(
                        "Hybrid",
                        self.project.hybrid_items,
                        "current_hybrid_index",
                        self.draw_hybrid_list,
                        self.draw_hybrid_editor,
                        "请从左侧列表选择一个混合物品进行编辑",
                    )
                    imgui.end_tab_item()

                imgui.end_tab_bar()

        imgui.end()

    def _draw_welcome_screen(self):
        """绘制欢迎界面 - 带品牌感的居中布局"""
        window_width = imgui.get_window_width()
        window_height = imgui.get_window_height()

        # 计算居中位置
        content_height = 180  # 内容高度
        start_y = (window_height - content_height) / 2

        # 装饰性顶部线条（使用 ASCII 兼容字符，长度与标题匹配）
        decorator = "- - - - - - - - - - - - - - - - - -"
        dec_size = imgui.calc_text_size(decorator)
        imgui.set_cursor_pos(((window_width - dec_size.x) / 2, start_y))
        self.text_secondary(decorator)

        # 标题
        title = "Stoneshard 装备模组编辑器"
        title_size = imgui.calc_text_size(title)
        imgui.set_cursor_pos(((window_width - title_size.x) / 2, start_y + 25))
        self.text_accent(title)

        # 装饰性底部线条
        imgui.set_cursor_pos(((window_width - dec_size.x) / 2, start_y + 50))
        self.text_secondary(decorator)

        # 副标题
        subtitle = "创建武器和装备模组的可视化工具"
        subtitle_size = imgui.calc_text_size(subtitle)
        imgui.set_cursor_pos(((window_width - subtitle_size.x) / 2, start_y + 75))
        self.text_secondary(subtitle)

        # 按钮区域
        button_width = 140
        button_spacing = 20
        total_buttons_width = button_width * 2 + button_spacing
        buttons_start_x = (window_width - total_buttons_width) / 2

        imgui.set_cursor_pos((buttons_start_x, start_y + 110))
        if imgui.button("新建项目", width=button_width, height=32):
            self.new_project_dialog()

        imgui.set_cursor_pos(
            (buttons_start_x + button_width + button_spacing, start_y + 110)
        )
        if imgui.button("打开项目", width=button_width, height=32):
            self.open_project_dialog()

        # 底部提示
        hint = "提示: 项目将保存为文件夹结构，包含 project.json 和 assets 目录"
        hint_size = imgui.calc_text_size(hint)
        imgui.set_cursor_pos(((window_width - hint_size.x) / 2, start_y + 160))
        self.text_secondary(hint)

    def draw_project_info(self):
        """绘制项目信息"""
        # 使用两列布局：左边是基本信息，右边是描述
        imgui.columns(2, "project_info_cols", border=False)
        imgui.set_column_width(0, imgui.get_window_width() * 0.5)

        # 记录左列起始位置
        left_start_y = imgui.get_cursor_pos().y

        # 左列：基本信息
        imgui.push_item_width(-1)
        imgui.text("模组名称")
        changed, self.project.name = imgui.input_text("##name", self.project.name, 256)
        tooltip("用于展示的名称，可包含中文等字符")

        imgui.text("模组代号")
        changed, self.project.code_name = imgui.input_text(
            "##code_name", self.project.code_name, 256
        )
        tooltip("仅用于内部生成代码，必须是以字母开头的字母/数字组合")

        imgui.text("作者")
        changed, self.project.author = imgui.input_text(
            "##author", self.project.author, 256
        )

        # 版本信息：与其它字段一致，标签一行，输入框一行
        imgui.text("版本")
        changed, self.project.version = imgui.input_text(
            "##version", self.project.version, 32
        )

        imgui.text("目标游戏版本")
        changed, self.project.target_version = imgui.input_text(
            "##target_ver", self.project.target_version, 32
        )
        imgui.pop_item_width()

        # 记录左列结束位置
        left_end_y = imgui.get_cursor_pos().y
        left_height = left_end_y - left_start_y

        # 右列：描述（多行），高度与左列对齐
        imgui.next_column()
        imgui.push_item_width(-1)

        imgui.text("描述")
        # 计算描述框高度：与左列内容高度对齐
        # 减去"描述"标签高度，再减去少量边距补偿
        label_height = imgui.get_text_line_height_with_spacing()
        desc_height = left_height - label_height - 6
        desc_height = max(60, desc_height)  # 最小高度 60
        changed, self.project.description = imgui.input_text_multiline(
            "##desc", self.project.description, 1024, height=desc_height
        )
        imgui.pop_item_width()

        imgui.columns(1)

        # 项目路径（可能很长，单独一行）
        imgui.dummy(0, 4)
        project_dir = (
            os.path.dirname(self.project.file_path)
            if self.project.file_path
            else "未保存"
        )
        self.text_secondary(f"路径: {project_dir}")
        if self.project.file_path:
            tooltip(project_dir)

        # 验证错误
        errors = self.project.validate()
        if errors:
            self.draw_indented_separator()
            self.text_error("错误:")
            for err in errors:
                self.text_error(f"  • {err}")

    # ==================== 物品面板 ====================

    def draw_item_panel(
        self,
        panel_id,
        items,
        current_index_attr,
        draw_list_func,
        draw_editor_func,
        empty_hint,
    ):
        """绘制物品面板（列表 + 编辑器）"""
        available_width = imgui.get_content_region_available_width()
        available_height = imgui.get_content_region_available().y

        # 列表宽度：根据窗口大小自适应，但有合理的最小/最大值
        min_list_width = 180
        max_list_width = 280
        list_width = max(min_list_width, min(max_list_width, available_width * 0.22))
        editor_width = available_width - list_width - 8

        spacing = 4
        padding = self.layout.gap_s  # 统一的内边距

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
        current_index = getattr(self, current_index_attr)
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
            self.text_secondary(empty_hint)
        imgui.end_child()

    # ==================== 物品列表 ====================

    def draw_weapon_list(self):
        """绘制武器列表"""
        self._draw_item_list(
            items=self.project.weapons,
            item_class=Weapon,
            current_index_attr="current_weapon_index",
            item_type_label="武器",
            default_name="新武器",
            default_desc="这是新武器的描述",
            default_id_base="请设置武器系统ID",
            get_display_suffix=lambda item: "",
        )

    def draw_armor_list(self):
        """绘制装备列表"""
        self._draw_item_list(
            items=self.project.armors,
            item_class=Armor,
            current_index_attr="current_armor_index",
            item_type_label="装备",
            default_name="新装备",
            default_desc="这是新装备的描述",
            default_id_base="请设置装备系统ID",
            get_display_suffix=lambda item: f" [{ARMOR_SLOT_LABELS.get(item.slot, item.slot)}]",
        )

    def _draw_item_list(
        self,
        items,
        item_class,
        current_index_attr,
        item_type_label,
        default_name,
        default_desc,
        default_id_base,
        get_display_suffix,
    ):
        """通用物品列表绘制"""
        current_index = getattr(self, current_index_attr)
        available_width = imgui.get_content_region_available_width()

        # 工具栏：使用语义化中文标签
        # 添加按钮
        if imgui.button(f"添加##{item_type_label}"):
            new_item = item_class()
            new_item.name = self._generate_unique_id(items, default_id_base)
            new_item.localization.set_name(PRIMARY_LANGUAGE, default_name)
            new_item.localization.set_description(PRIMARY_LANGUAGE, default_desc)
            items.append(new_item)
            setattr(self, current_index_attr, len(items) - 1)
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"添加新的{item_type_label}")

        imgui.same_line()

        # 删除按钮
        can_delete = current_index >= 0
        if not can_delete:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if imgui.button(f"删除##{item_type_label}") and can_delete:
            del items[current_index]
            setattr(self, current_index_attr, min(current_index, len(items) - 1))
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
            setattr(self, current_index_attr, len(items) - 1)
        if not can_copy:
            imgui.pop_style_var()
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"复制当前选中的{item_type_label}")

        imgui.separator()
        current_index = getattr(self, current_index_attr)

        # 列表项 - 使用 Selectable 替代 TreeNode，更适合列表
        for i, item in enumerate(items):
            display_name = item.localization.get_display_name()
            suffix = get_display_suffix(item) if get_display_suffix else ""

            # 主显示名 + 系统ID（较小）
            is_selected = i == current_index

            # 选中项使用主题色高亮背景，增强视觉对比
            if is_selected:
                imgui.push_style_color(imgui.COLOR_HEADER, *self.theme_colors["accent"])

            # 使用 selectable，宽度填满容器
            if imgui.selectable(
                f"{display_name}##{i}", is_selected, imgui.SELECTABLE_SPAN_ALL_COLUMNS
            )[0]:
                setattr(self, current_index_attr, i)

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

    # ==================== 武器编辑器 ====================

    def draw_weapon_editor(self):
        """绘制武器编辑器"""
        weapon = self.project.weapons[self.current_weapon_index]
        weapon.markup = 1

        if imgui.tree_node("基本属性", flags=imgui.TREE_NODE_FRAMED):
            self._draw_basic_properties(
                weapon, "weapon", SLOT_LABELS, WEAPON_MATERIAL_LABELS
            )
            imgui.tree_pop()

        if imgui.tree_node("武器属性", flags=imgui.TREE_NODE_FRAMED):
            self._draw_attributes_editor(weapon, self._weapon_attr_groups, "weapon")
            imgui.tree_pop()

        if imgui.tree_node("武器名称与本地化", flags=imgui.TREE_NODE_FRAMED):
            self._draw_localization_editor(weapon, "weapon")
            imgui.tree_pop()

        if imgui.tree_node("贴图文件", flags=imgui.TREE_NODE_FRAMED):
            self._draw_textures_editor(weapon, "weapon", SLOT_LABELS)
            imgui.tree_pop()

        errors = validate_item(weapon, self.project, include_warnings=True)
        self._draw_validation_errors(errors)

    # ==================== 护甲编辑器 ====================

    def draw_armor_editor(self):
        """绘制护甲编辑器"""
        armor = self.project.armors[self.current_armor_index]

        if imgui.tree_node("基本属性##armor", flags=imgui.TREE_NODE_FRAMED):
            self._draw_basic_properties(
                armor, "armor", ARMOR_SLOT_LABELS, ARMOR_MATERIAL_LABELS
            )
            imgui.tree_pop()

        if imgui.tree_node("装备属性", flags=imgui.TREE_NODE_FRAMED):
            self._draw_attributes_editor(armor, self._armor_attr_groups, "armor")
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
            self._draw_textures_editor(armor, "armor", ARMOR_SLOT_LABELS)
            imgui.tree_pop()

        errors = validate_item(armor, self.project, include_warnings=True)
        self._draw_validation_errors(errors)

    # ==================== 混合物品列表和编辑器 ====================

    def draw_hybrid_list(self):
        """绘制混合物品列表"""
        self._draw_item_list(
            items=self.project.hybrid_items,
            item_class=HybridItem,
            current_index_attr="current_hybrid_index",
            item_type_label="混合物品",
            default_name="新混合物品",
            default_desc="这是新混合物品的描述",
            default_id_base="请设置混合物品系统ID",
            get_display_suffix=lambda item: f" [{HYBRID_SLOT_LABELS.get(item.slot, item.slot)}]",
        )

    def draw_hybrid_editor(self):
        """绘制混合物品编辑器 - 4区块结构: 基础/行为/属性/呈现"""
        hybrid = self.project.hybrid_items[self.current_hybrid_index]

        # 1. 基础 - "这是什么物品"
        if imgui.collapsing_header("基础##hybrid", imgui.TREE_NODE_DEFAULT_OPEN)[0]:
            self._draw_hybrid_base(hybrid)

        # 2. 行为 - "物品做什么"
        if imgui.collapsing_header("行为##hybrid", imgui.TREE_NODE_DEFAULT_OPEN)[0]:
            self._draw_hybrid_behavior(hybrid)

        # 3. 属性 - "数值配置"
        if self._should_show_hybrid_attributes(hybrid) or hybrid.trigger_mode == TriggerMode.EFFECT:
            if imgui.collapsing_header("属性##hybrid")[0]:
                self._draw_hybrid_stats(hybrid)

        # 4. 呈现 - "外观"
        if imgui.collapsing_header("呈现##hybrid")[0]:
            self._draw_hybrid_presentation(hybrid)

        # 验证错误
        errors = validate_hybrid_item(hybrid, self.project, include_warnings=True)
        self._draw_validation_errors(errors)

    def _should_show_hybrid_attributes(self, hybrid: HybridItem) -> bool:
        """判断是否显示属性加成编辑器

        需求调整：即使是武器/护甲也允许编辑额外属性（例如 HYBRID_ITEM_TEMPLATE 中提到的武器可选属性）。
        因此只要是武器/护甲/有被动效果，就展示属性编辑器。
        """
        if hybrid.init_weapon_stats or hybrid.init_armor_stats or hybrid.has_passive:
            return True
        return False

    # ==================== 新 4 区块结构 ====================

    def _draw_hybrid_base(self, hybrid: HybridItem):
        """绘制基础区块 - GridLayout label-on-top 布局（两行）"""
        hybrid.parent_object = "o_inv_consum"

        # 使用 GridLayout 类
        grid = GridLayout(self.layout, self.text_secondary)
        L = self.layout  # 语义别名引用

        # === 第一行：ID / 品质 / 等级（核心标识和稀有度）===
        # Label 行
        grid.label_header("ID", L.SPAN_ID)
        grid.next_cell()
        grid.label_header("品质", L.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("等级", L.SPAN_INPUT)

        # Control 行
        grid.field_width(L.SPAN_ID)
        changed, new_id = imgui.input_text("##hybrid_id", hybrid.id, 256)
        if changed:
            hybrid.id = new_id.lower()
        tooltip("物品唯一标识符")

        grid.next_cell()
        grid.field_width(L.SPAN_INPUT)
        old_quality = hybrid.quality
        hybrid.quality = self._draw_enum_combo(
            "##quality_hybrid", hybrid.quality,
            list(HYBRID_QUALITY_LABELS.keys()), HYBRID_QUALITY_LABELS
        )
        if hybrid.quality != old_quality:
            self._update_hybrid_rarity_from_quality(hybrid)

        grid.next_cell()
        grid.field_width(L.SPAN_INPUT)
        if hybrid.quality == 7:
            grid.text_cell("T0", L.SPAN_INPUT)
            tooltip("文物固定等级 0")
        else:
            tier_options = [0, 1, 2, 3, 4, 5]
            tier_labels = {0: "全", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
            hybrid.tier = self._draw_enum_combo("##tier_hybrid", hybrid.tier, tier_options, tier_labels)
            tooltip("用于掉落/商店筛选")

        # === 第二行：价格 / 重量 / 材质（物理/经济属性）===
        # Label 行
        grid.label_header("价格", L.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("重量", L.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("材质", L.SPAN_INPUT)

        # Control 行
        grid.field_width(L.SPAN_INPUT)
        changed, hybrid.base_price = imgui.input_int("##price_hybrid", hybrid.base_price, 1, 10)
        if changed:
            hybrid.base_price = max(0, hybrid.base_price)

        grid.next_cell()
        grid.field_width(L.SPAN_INPUT)
        hybrid.weight = self._draw_enum_combo(
            "##weight_hybrid", hybrid.weight,
            list(HYBRID_WEIGHT_LABELS.keys()), HYBRID_WEIGHT_LABELS
        )
        tooltip("影响游泳；护甲时决定类别")

        grid.next_cell()
        grid.field_width(L.SPAN_INPUT)
        hybrid.material = self._draw_enum_combo(
            "##material_hybrid", hybrid.material,
            list(HYBRID_MATERIALS.keys()), HYBRID_MATERIALS
        )

        # === 分类组（和物理组之间有 gap_s 间隔）===
        imgui.dummy(0, L.gap_m)

        # 主分类下拉 + 子分类流式布局（同一行）
        # 分类下拉：文物固定为 treasure
        is_treasure = hybrid.quality == 7
        if is_treasure:
            hybrid.cat = "treasure"
        elif hybrid.cat == "treasure":
            hybrid.cat = ""

        available_cats = [c for c in ITEM_CATEGORIES if c != "treasure"] if not is_treasure else ["treasure"]
        cat_options = (["treasure"] if is_treasure else [""]) + ([] if is_treasure else available_cats)
        cat_labels = {"": "—"}
        cat_labels.update({c: CATEGORY_TRANSLATIONS.get(c, c) for c in ITEM_CATEGORIES})

        # Label 行：分类
        grid.label_header("分类", L.SPAN_INPUT)

        # Control 行：分类下拉
        if is_treasure:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.6)
        grid.field_width(L.SPAN_INPUT)
        new_cat = self._draw_enum_combo("##cat_hybrid", hybrid.cat, cat_options, cat_labels)
        if not is_treasure:
            hybrid.cat = new_cat
        if is_treasure:
            imgui.pop_style_var()

        # === 子分类行（独立一行，从左边开始）===
        grid.label_header("子分类", L.SPAN_INPUT)

        subcat_options = ALL_SUBCATEGORY_OPTIONS if hybrid.quality == 7 else [s for s in ALL_SUBCATEGORY_OPTIONS if s != "treasure"]
        if "treasure" in hybrid.subcats and hybrid.quality != 7:
            hybrid.subcats.remove("treasure")

        # 流式布局从新行开始，使用完整 8 span 宽度
        grid.begin_flow(L.span(8))

        # 添加子分类按钮 (span=1)
        if imgui.button("+##add_subcat", L.span(L.SPAN_BADGE), 0):
            imgui.open_popup("subcats_popup")
        tooltip("添加子分类")
        grid.flow_item_after()

        # 显示已选子分类 badges (固定 span=1 宽度)
        badge_width = L.span(L.SPAN_BADGE)
        to_remove_subcat = None
        for subcat in sorted(hybrid.subcats):
            full_label = CATEGORY_TRANSLATIONS.get(subcat, subcat)
            # 检测是否需要截断
            text_size = imgui.calc_text_size(full_label)
            style = imgui.get_style()
            available_width = badge_width - 2 * style.frame_padding.x
            is_truncated = text_size.x > available_width

            grid.flow_item(badge_width)
            imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, style.frame_padding.y))
            imgui.push_style_color(imgui.COLOR_BUTTON, *self.theme_colors["badge_subcat"])
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *self.theme_colors["badge_hover_remove"])
            if imgui.button(f"{full_label}##{subcat}_badge", badge_width, 0):
                to_remove_subcat = subcat
            imgui.pop_style_color(2)
            imgui.pop_style_var()
            # 组合 tooltip: 截断时显示完整文本 + 操作提示
            tooltip_parts = []
            if is_truncated:
                tooltip_parts.append(full_label)
            tooltip_parts.append("[点击移除]")
            tooltip("\n".join(tooltip_parts))
            grid.flow_item_after()
        if to_remove_subcat:
            hybrid.subcats.remove(to_remove_subcat)

        if imgui.begin_popup("subcats_popup"):
            for subcat in subcat_options:
                is_selected = subcat in hybrid.subcats
                is_disabled = (subcat == hybrid.cat)
                if is_disabled:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                changed, new_value = imgui.checkbox(
                    f"{CATEGORY_TRANSLATIONS.get(subcat, subcat)}##subcat_{subcat}",
                    is_selected
                )
                if changed and not is_disabled:
                    if new_value:
                        hybrid.subcats.append(subcat)
                    else:
                        hybrid.subcats.remove(subcat)
                if is_disabled:
                    imgui.pop_style_var()
            imgui.end_popup()

        grid.end_flow()

        # === 第四行：标签（流式布局）===
        grid.label_header("标签", L.SPAN_INPUT)

        # 品质标签实时更新
        hybrid.quality_tag = "unique" if hybrid.quality == 6 else ""

        # 收集所有有效标签
        all_set_tags = []
        if hybrid.quality_tag:
            all_set_tags.append(("quality", hybrid.quality_tag))
        if hybrid.dungeon_tag:
            all_set_tags.append(("dungeon", hybrid.dungeon_tag))
        if hybrid.country_tag:
            all_set_tags.append(("country", hybrid.country_tag))
        for tag in hybrid.extra_tags:
            all_set_tags.append(("extra", tag))
        if hybrid.exclude_from_random:
            all_set_tags.append(("special", "special"))

        grid.begin_flow(L.span(8))  # 限制在8列宽度内换行

        # 添加标签按钮
        if imgui.button("+##add_tag", L.span(L.SPAN_BADGE), 0):
            imgui.open_popup("tags_popup")
        tooltip("添加标签")
        grid.flow_item_after()

        # 显示标签 badges (固定 span=1 宽度)
        badge_width = L.span(L.SPAN_BADGE)
        to_remove_tag = None
        for tag_type, tag_val in all_set_tags:
            # 确定标签文本、颜色和可移除性
            if tag_type == "quality":
                full_label = QUALITY_TAGS.get(tag_val, tag_val)
                badge_color = self.theme_colors["badge_quality"]
                can_remove = False
                locked_reason = "由品质自动设置"
            elif tag_type == "dungeon":
                full_label = DUNGEON_TAGS.get(tag_val, tag_val)
                badge_color = self.theme_colors["badge_tag"]
                can_remove = True
                locked_reason = ""
            elif tag_type == "country":
                full_label = COUNTRY_TAGS.get(tag_val, tag_val)
                badge_color = self.theme_colors["badge_tag"]
                can_remove = True
                locked_reason = ""
            elif tag_type == "special":
                full_label = EXTRA_TAGS.get(tag_val, tag_val)
                badge_color = self.theme_colors["badge_special"]
                can_remove = False
                locked_reason = "由「排除随机生成」控制"
            else:
                full_label = EXTRA_TAGS.get(tag_val, tag_val)
                badge_color = self.theme_colors["badge_tag"]
                can_remove = True
                locked_reason = ""

            # 检测是否需要截断
            text_size = imgui.calc_text_size(full_label)
            style = imgui.get_style()
            available_width = badge_width - 2 * style.frame_padding.x
            is_truncated = text_size.x > available_width

            # 选择 hover 颜色
            hover_color = self.theme_colors["badge_hover_remove"] if can_remove else self.theme_colors["badge_hover_locked"]

            grid.flow_item(badge_width)
            imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, style.frame_padding.y))
            imgui.push_style_color(imgui.COLOR_BUTTON, *badge_color)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *hover_color)

            if imgui.button(f"{full_label}##{tag_type}_{tag_val}_badge", badge_width, 0):
                if can_remove:
                    to_remove_tag = (tag_type, tag_val)
            imgui.pop_style_color(2)
            imgui.pop_style_var()

            # 组合 tooltip: 截断文本 + 操作提示
            tooltip_parts = []
            if is_truncated:
                tooltip_parts.append(full_label)
            if can_remove:
                tooltip_parts.append("[点击移除]")
            elif locked_reason:
                tooltip_parts.append(f"[{locked_reason}]")
            if tooltip_parts:
                tooltip("\n".join(tooltip_parts))
            grid.flow_item_after()

        # 处理移除
        if to_remove_tag:
            tag_type, tag_val = to_remove_tag
            if tag_type == "dungeon":
                hybrid.dungeon_tag = ""
            elif tag_type == "country":
                hybrid.country_tag = ""
            elif tag_type == "extra":
                hybrid.extra_tags.remove(tag_val)

        if imgui.begin_popup("tags_popup"):
            self.text_secondary("地牢")
            for tag_val, tag_label in DUNGEON_TAGS.items():
                if imgui.radio_button(f"{tag_label}##dungeon", hybrid.dungeon_tag == tag_val):
                    hybrid.dungeon_tag = tag_val

            imgui.separator()
            self.text_secondary("国家/地区")
            for tag_val, tag_label in COUNTRY_TAGS.items():
                if imgui.radio_button(f"{tag_label}##country", hybrid.country_tag == tag_val):
                    hybrid.country_tag = tag_val

            imgui.separator()
            self.text_secondary("其他")
            for tag_val, tag_label in EXTRA_TAGS.items():
                if tag_val == "special":
                    continue
                is_selected = tag_val in hybrid.extra_tags
                changed, new_value = imgui.checkbox(f"{tag_label}##extra_{tag_val}", is_selected)
                if changed:
                    if new_value:
                        hybrid.extra_tags.append(tag_val)
                    else:
                        hybrid.extra_tags.remove(tag_val)
            imgui.end_popup()

        grid.end_flow()

        # 注：生成规则已移至 _draw_hybrid_behavior 末尾


    def _draw_hybrid_spawn_settings(self, hybrid: HybridItem):
        """绘制生成规则设置（使用 Grid 系统 - label 在上方）"""
        # 使用 GridLayout 类
        grid = GridLayout(self.layout, self.text_secondary)
        L = self.layout  # 语义别名引用

        # 生成规则设置
        spawn_rule_labels = {
            SpawnRule.EQUIPMENT: "按装备池",
            SpawnRule.ITEM: "按道具池",
            SpawnRule.NONE: "不生成",
        }
        can_use_equipment = hybrid.equipment_mode != EquipmentMode.NONE

        # Label 行
        grid.label_header("排除随机生成", L.SPAN_INPUT)
        grid.next_cell()
        if not hybrid.exclude_from_random:
            grid.label_header("容器生成", L.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("商店生成", L.SPAN_INPUT)
            grid.next_cell()

        grid.label_header("生成预测", L.SPAN_INPUT)

        # Control 行
        _, hybrid.exclude_from_random = grid.checkbox_cell("##exc_random", hybrid.exclude_from_random, L.SPAN_INPUT)
        tooltip("排除随机生成：物品不会在宝箱/商店随机出现\n仍会添加 special 标签用于脚本添加")

        grid.next_cell()
        if not hybrid.exclude_from_random:
            # 容器
            grid.field_width(L.SPAN_INPUT)
            container_options = [SpawnRule.EQUIPMENT, SpawnRule.ITEM, SpawnRule.NONE] if can_use_equipment else [SpawnRule.ITEM, SpawnRule.NONE]
            if hybrid.container_spawn not in container_options:
                hybrid.container_spawn = SpawnRule.NONE
            if imgui.begin_combo("##container_spawn", spawn_rule_labels[hybrid.container_spawn]):
                for rule in container_options:
                    if imgui.selectable(spawn_rule_labels[rule], hybrid.container_spawn == rule)[0]:
                        hybrid.container_spawn = rule
                imgui.end_combo()
            tooltip(
                "容器生成规则（宝箱/桶/尸体等）\n\n"
                "• 按装备池：根据武器类型/护甲类型 + 标签 + 层级匹配\n"
                "• 按道具池：根据分类/子分类 + 标签 + 层级匹配\n"
                "• 不生成：不在容器中随机出现"
            )

            grid.next_cell()
            # 商店
            grid.field_width(L.SPAN_INPUT)
            shop_options = [SpawnRule.EQUIPMENT, SpawnRule.ITEM, SpawnRule.NONE] if can_use_equipment else [SpawnRule.ITEM, SpawnRule.NONE]
            if hybrid.shop_spawn not in shop_options:
                hybrid.shop_spawn = SpawnRule.NONE
            if imgui.begin_combo("##shop_spawn", spawn_rule_labels[hybrid.shop_spawn]):
                for rule in shop_options:
                    if imgui.selectable(spawn_rule_labels[rule], hybrid.shop_spawn == rule)[0]:
                        hybrid.shop_spawn = rule
                imgui.end_combo()
            tooltip(
                "商店生成规则（商人进货时）\n\n"
                "• 按装备池：根据武器/护甲/珠宝类别 + 层级 + 材质 + 标签匹配\n"
                "• 按道具池：根据分类/子分类 + 层级 + 标签匹配\n"
                "• 不生成：不在商店随机出现"
            )

            grid.next_cell()


        # 生成预测按钮
        if grid.button_cell("▶##gen_preview", L.SPAN_INPUT):
            imgui.open_popup("generation_preview_popup")
        tooltip("查看生成预测")
        self._draw_generation_preview_popup(hybrid)

    def _draw_generation_preview_popup(self, hybrid: HybridItem):
        """绘制生成预测弹窗 - 三场景版"""
        imgui.set_next_window_size(500, 350, imgui.ALWAYS)
        if imgui.begin_popup("generation_preview_popup"):
            imgui.text("生成预测")
            imgui.separator()

            if hybrid.exclude_from_random:
                self.text_secondary("物品已排除随机生成 (+special)")
                imgui.text("不会出现在宝箱掉落、商店库存或击杀掉落中")
            else:
                # 容器掉落
                imgui.text("容器掉落:")
                if hybrid.container_spawn == SpawnRule.NONE:
                    self.text_secondary("  关闭")
                elif hybrid.container_spawn == SpawnRule.EQUIPMENT:
                    self._draw_container_preview_simplified(hybrid, is_equipment=True)
                else:  # ITEM
                    self._draw_container_preview_simplified(hybrid, is_equipment=False)

                imgui.dummy(0, self.layout.gap_m)

                # 商店进货
                imgui.text("商店进货:")
                if hybrid.shop_spawn == SpawnRule.NONE:
                    self.text_secondary("  关闭")
                else:
                    self._draw_shop_preview_simplified(hybrid)

                imgui.dummy(0, self.layout.gap_m)



            imgui.end_popup()

    def _draw_container_preview_simplified(self, hybrid: HybridItem, is_equipment: bool):
        """简化版容器预测 - 只显示容器名称"""
        if is_equipment:
            # 装备路径
            eq_categories = []
            if hybrid.equipment_mode == EquipmentMode.WEAPON and hybrid.weapon_type:
                eq_categories.append(hybrid.weapon_type)
                eq_categories.append("weapon")
            elif hybrid.equipment_mode == EquipmentMode.ARMOR and hybrid.armor_type:
                eq_categories.append(hybrid.armor_type)
                if hybrid.armor_type in ("Ring", "Amulet"):
                    eq_categories.append("jewelry")
                else:
                    eq_categories.append("armor")

            if not eq_categories:
                self.text_secondary("  (无匹配)")
                return

            all_matches = []
            for eq_cat in eq_categories:
                matches = find_matching_eq_slots(eq_cat, hybrid.tags_tuple, hybrid.tier)
                all_matches.extend(matches)

            if not all_matches:
                self.text_secondary("  (无匹配)")
                return

            # 去重并只显示名称
            names = list(dict.fromkeys(m["entry_name_cn"] for m in all_matches))
            display = ", ".join(names)
            imgui.text_wrapped(f"  {display}")
        else:
            # 非装备路径
            if not (hybrid.cat or hybrid.subcats):
                self.text_secondary("  (请设置分类)")
                return

            matches = find_matching_slots(
                hybrid.cat, tuple(hybrid.subcats),
                hybrid.tags_tuple, hybrid.tier
            )

            if not matches:
                self.text_secondary("  (无匹配)")
                return

            names = list(dict.fromkeys(m["entry_name_cn"] for m in matches))
            display = ", ".join(names)
            imgui.text_wrapped(f"  {display}")

    def _draw_shop_preview_simplified(self, hybrid: HybridItem):
        """简化版商店预测 - 只显示城镇·商店名"""
        if hybrid.shop_spawn == SpawnRule.ITEM:
            # 非装备路径
            if not (hybrid.cat or hybrid.subcats):
                self.text_secondary("  (请设置分类)")
                return
            item_cats = set([hybrid.cat] + list(hybrid.subcats))
            item_tags = set(hybrid.effective_tags.split()) if hybrid.effective_tags else set()
            matching = []

            for objects_tuple, config in SHOP_CONFIGS.items():
                selling_cats = config.get("selling_loot_category", {})
                tier_range = config.get("tier_range", [1, 1])
                trade_tags = set(config.get("trade_tags", []))
                matched_cats = item_cats & set(selling_cats.keys())
                if not matched_cats:
                    continue
                # Tier 过滤（与装备规则一致）
                if hybrid.tier > 0 and not (tier_range[0] <= hybrid.tier <= tier_range[1]):
                    continue
                if trade_tags and item_tags and not item_tags.issubset(trade_tags):
                    continue
                for obj in objects_tuple:
                    meta = NPC_METADATA.get(obj, {})
                    name = meta.get("name_zh") or meta.get("name_en")
                    if name:
                        town = meta.get("town_zh") or meta.get("town") or ""
                        matching.append(f"{town}·{name}" if town else name)
        else:
            # 装备路径
            item_tier = hybrid.tier
            item_material = hybrid.material
            item_tags = set(hybrid.effective_tags.split()) if hybrid.effective_tags else set()
            item_weapon_type = hybrid.weapon_type if hybrid.equipment_mode == EquipmentMode.WEAPON else None
            item_armor_slot = hybrid.slot if hybrid.equipment_mode == EquipmentMode.ARMOR else None
            is_jewelry = item_armor_slot in ("ring", "amulet", "Ring", "Amulet") if item_armor_slot else False
            matching = []

            for objects_tuple, config in SHOP_CONFIGS.items():
                selling_cats = set(config.get("selling_loot_category", {}).keys())
                tier_range = config.get("tier_range", [1, 1])
                material_spec = config.get("material_spec", ["all"])
                trade_tags = set(config.get("trade_tags", []))

                category_matched = False
                if "weapon" in selling_cats and item_weapon_type:
                    category_matched = True
                elif "armor" in selling_cats and item_armor_slot and not is_jewelry:
                    category_matched = True
                elif "jewelry" in selling_cats and is_jewelry:
                    category_matched = True

                if not category_matched:
                    continue
                if item_tier > 0 and not (tier_range[0] <= item_tier <= tier_range[1]):
                    continue
                if "all" not in material_spec and item_material not in material_spec:
                    continue
                if trade_tags and (not item_tags or not item_tags.issubset(trade_tags)):
                    continue

                for obj in objects_tuple:
                    meta = NPC_METADATA.get(obj, {})
                    name = meta.get("name_zh") or meta.get("name_en")
                    if name:
                        town = meta.get("town_zh") or meta.get("town") or ""
                        matching.append(f"{town}·{name}" if town else name)

        if not matching:
            self.text_secondary("  (无匹配)")
            return

        display = ", ".join(matching)
        imgui.text_wrapped(f"  {display}")

    def _draw_kill_preview_simplified(self, hybrid: HybridItem):
        """简化版击杀掉落预测 - 显示可能掉落此物品的敌人"""
        # 导入击杀掉落数据
        try:
            from enemy_drop_constants import DROP_TABLE, ENEMY_META
        except ImportError:
            self.text_secondary("  (击杀数据未加载)")
            return

        # 确定物品的 slot（武器类型或护甲槽位）
        if hybrid.equipment_mode == EquipmentMode.WEAPON:
            item_slot = hybrid.weapon_type
        elif hybrid.equipment_mode == EquipmentMode.ARMOR:
            item_slot = hybrid.armor_type
        else:
            self.text_secondary("  (需要装备形态)")
            return

        item_tier = hybrid.tier
        matching_enemies = []

        # 精确匹配 DROP_TABLE: {(tier, slot): [敌人列表]}
        key = (item_tier, item_slot)
        if key in DROP_TABLE:
            for enemy_obj in DROP_TABLE[key]:
                meta = ENEMY_META.get(enemy_obj, {})
                name = meta.get("name_zh") or meta.get("name_en") or enemy_obj
                enemy_tier = meta.get("tier", 0)
                matching_enemies.append(f"{name}(T{enemy_tier})")

        if not matching_enemies:
            self.text_secondary("  (无匹配)")
            return

        # 去重
        unique_enemies = list(dict.fromkeys(matching_enemies))
        display = ", ".join(unique_enemies)
        imgui.text_wrapped(f"  {display}")

    def _draw_fragments_popup(self, hybrid: HybridItem):
        """绘制拆解碎片材料弹窗"""
        if imgui.begin_popup("fragments_popup"):
            imgui.text("拆解碎片")
            imgui.separator()
            self.text_secondary("拆解物品时可获得的材料碎片")

            frag_data = [
                ("cloth01", "布1"), ("cloth02", "布2"), ("cloth03", "布3"), ("cloth04", "布4"),
                ("leather01", "皮1"), ("leather02", "皮2"), ("leather03", "皮3"), ("leather04", "皮4"),
                ("metal01", "铁1"), ("metal02", "铁2"), ("metal03", "铁3"), ("metal04", "铁4"),
                ("gold", "金"),
            ]

            imgui.dummy(0, self.layout.gap_s)

            # 4列布局
            if imgui.begin_table("frag_popup_table", 4, imgui.TABLE_SIZING_STRETCH_SAME):
                imgui.table_setup_column("L1", imgui.TABLE_COLUMN_WIDTH_FIXED, 30)
                imgui.table_setup_column("I1", imgui.TABLE_COLUMN_WIDTH_FIXED, 50)
                imgui.table_setup_column("L2", imgui.TABLE_COLUMN_WIDTH_FIXED, 30)
                imgui.table_setup_column("I2", imgui.TABLE_COLUMN_WIDTH_FIXED, 50)

                for i, (frag_key, frag_label) in enumerate(frag_data):
                    if i % 2 == 0:
                        imgui.table_next_row()

                    imgui.table_next_column()
                    imgui.text(frag_label)

                    imgui.table_next_column()
                    val = hybrid.fragments.get(frag_key, 0)
                    with item_width(-1):
                        changed, new_val = imgui.input_int(f"##{frag_key}_popup", val, step=0, step_fast=0)
                    if changed:
                        hybrid.fragments[frag_key] = max(0, new_val)

                imgui.end_table()

            imgui.end_popup()

    def _draw_hybrid_behavior(self, hybrid: HybridItem):
        """绘制行为区块 - Grid 系统布局

        Grid 规则:
        - 每个 chunk 宽度 = span(n) = n * col + (n-1) * gap
        - chunk 之间用 grid_gap 分隔
        - 保证垂直对齐
        """
        # UI 标签映射
        EQUIPMENT_MODE_LABELS = {
            EquipmentMode.NONE: "无",
            EquipmentMode.WEAPON: "武器",
            EquipmentMode.ARMOR: "护甲",
            EquipmentMode.CHARM: "护符",
        }
        TRIGGER_MODE_LABELS = {
            TriggerMode.NONE: "无",
            TriggerMode.EFFECT: "效果",
            TriggerMode.SKILL: "技能",
        }
        CHARGE_MODE_LABELS = {
            ChargeMode.LIMITED: "有限",
            ChargeMode.UNLIMITED: "无限",
        }

        # GridLayout 类替代内联 helper 函数
        grid = GridLayout(self.layout, self.text_secondary)
        L = self.layout  # 语义别名引用
        col = L.grid_col
        gap = L.grid_gap
        debug_grid = L.GRID_DEBUG

        # Debug: draw grid lines
        if debug_grid:
            draw_list = imgui.get_window_draw_list()
            cursor_pos = imgui.get_cursor_screen_pos()
            content_x = cursor_pos[0]
            window_y = cursor_pos[1]
            window_h = 150  # 绘制高度
            available_w = imgui.get_content_region_available_width()

            # 交替绘制 col (红色) 和 gap (绿色) 区域
            x = content_x
            is_col = True  # 交替标记
            while x < content_x + available_w:
                if is_col:
                    # Column - 红色半透明
                    w = col
                    color = imgui.get_color_u32_rgba(1, 0.3, 0.3, 0.15)
                else:
                    # Gap - 绿色半透明
                    w = gap
                    color = imgui.get_color_u32_rgba(0.3, 1, 0.3, 0.25)

                # 绘制填充矩形
                if x + w <= content_x + available_w:
                    draw_list.add_rect_filled(x, window_y, x + w, window_y + window_h, color)
                    # 边框线
                    border_color = imgui.get_color_u32_rgba(1, 1, 1, 0.3)
                    draw_list.add_rect(x, window_y, x + w, window_y + window_h, border_color, 0, 0, 1.0)

                x += w
                is_col = not is_col

        # ━━━ 形态行 ━━━
        # Label 行 (所有 labels 画在一行)
        grid.label_header("装备形态", L.SPAN_INPUT)
        if hybrid.init_weapon_stats:
            grid.next_cell()
            grid.label_header("武器类型", L.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("平衡", L.SPAN_INPUT)
        elif hybrid.init_armor_stats:
            grid.next_cell()
            grid.label_header("护甲类型", L.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("护甲分类", L.SPAN_INPUT)
            if hybrid.slot not in ["hand", "Ring", "Amulet"]:
                grid.next_cell()
                grid.label_header("碎片数", L.SPAN_INPUT)
        # Label 行结束，不调用 next_cell()

        # Control 行 (新的一行开始)
        grid.field_width(L.SPAN_INPUT)
        old_mode = hybrid.equipment_mode
        hybrid.equipment_mode = self._draw_mode_combo(
            "##eq_mode", hybrid.equipment_mode,
            EquipmentMode, EQUIPMENT_MODE_LABELS
        )
        if hybrid.equipment_mode != old_mode:
            if hybrid.equipment_mode == EquipmentMode.WEAPON:
                hybrid.slot = "hand"
            elif hybrid.equipment_mode == EquipmentMode.ARMOR:
                hybrid.slot = "hand" if hybrid.armor_type == "shield" else hybrid.armor_type
            else:
                hybrid.slot = "heal"

        if hybrid.init_weapon_stats:
            grid.next_cell()
            grid.field_width(L.SPAN_INPUT)
            hybrid.weapon_type = self._draw_enum_combo(
                "##wep_type", hybrid.weapon_type,
                list(HYBRID_WEAPON_TYPES.keys()), HYBRID_WEAPON_TYPES
            )
            grid.next_cell()
            grid.field_width(L.SPAN_INPUT)
            balance_options = {"0": "0", "1": "1", "2": "2", "3": "3", "4": "4"}
            hybrid.balance = int(self._draw_enum_combo(
                "##wep_balance", str(hybrid.balance),
                list(balance_options.keys()), balance_options
            ))
        elif hybrid.init_armor_stats:
            grid.next_cell()
            grid.field_width(L.SPAN_INPUT)
            old_armor_type = hybrid.armor_type
            hybrid.armor_type = self._draw_enum_combo(
                "##armor_type", hybrid.armor_type,
                list(HYBRID_ARMOR_TYPES.keys()), HYBRID_ARMOR_TYPES
            )
            if hybrid.armor_type != old_armor_type:
                hybrid.slot = "hand" if hybrid.armor_type == "shield" else hybrid.armor_type
            grid.next_cell()
            grid.text_cell(hybrid.armor_class, L.SPAN_INPUT)
            if hybrid.slot not in ["hand", "Ring", "Amulet"]:
                grid.next_cell()
                frag_count = sum(hybrid.fragments.values())
                if grid.button_cell(f"({frag_count})##frags", L.SPAN_INPUT):
                    imgui.open_popup("fragments_popup")
                self._draw_fragments_popup(hybrid)
        # Control 行结束，不调用 next_cell()

        # 逻辑组间隔
        imgui.dummy(0, L.gap_m)

        # ━━━ 触发组 ━━━
        # Label 行
        grid.label_header("触发模式", L.SPAN_INPUT)
        if hybrid.trigger_mode == TriggerMode.SKILL:
            grid.next_cell()
            grid.label_header("技能", L.SPAN_INPUT)
        # Label 行结束

        # Control 行
        grid.field_width(L.SPAN_INPUT)
        old_trigger = hybrid.trigger_mode
        hybrid.trigger_mode = self._draw_mode_combo(
            "##trigger_mode", hybrid.trigger_mode,
            TriggerMode, TRIGGER_MODE_LABELS
        )
        if hybrid.trigger_mode != old_trigger:
            if hybrid.trigger_mode != TriggerMode.SKILL:
                hybrid.skill_object = ""
            if hybrid.trigger_mode != TriggerMode.EFFECT:
                hybrid.consumable_attributes.clear()

        if hybrid.trigger_mode == TriggerMode.SKILL:
            grid.next_cell()
            grid.field_width(L.SPAN_INPUT)
            current_skill = hybrid.skill_object
            current_label = SKILL_OBJECT_NAMES.get(current_skill, current_skill) if current_skill else "-- 选择 --"
            if imgui.begin_combo("##skill_object", current_label):
                if imgui.selectable("-- 无 --", current_skill == "")[0]:
                    hybrid.skill_object = ""
                imgui.separator()
                for branch in sorted(SKILL_BY_BRANCH.keys()):
                    branch_label = SKILL_BRANCH_TRANSLATIONS.get(branch, branch)
                    skills = SKILL_BY_BRANCH[branch]
                    if not skills or branch in ("none", "unknown"):
                        continue
                    if imgui.tree_node(f"{branch_label}##branch_{branch}"):
                        for skill_obj in skills:
                            skill_info = SKILL_OBJECTS.get(skill_obj, {})
                            skill_name = skill_info.get("name_chinese", skill_obj)
                            if imgui.selectable(f"{skill_name}##{skill_obj}", current_skill == skill_obj)[0]:
                                hybrid.skill_object = skill_obj
                        imgui.tree_pop()
                imgui.end_combo()
        # Control 行结束

        # ━━━ 耐久组（条件显示）━━━
        if hybrid.has_durability:
            # 逻辑组间隔（仅在有内容时显示）
            imgui.dummy(0, L.gap_m)
            # Label 行
            grid.label_header("耐久上限", L.SPAN_INPUT)
            grid.next_cell()
            if hybrid.has_charges:
                grid.label_header("磨损%", L.SPAN_INPUT)
                grid.next_cell()
            grid.label_header("耐久归零销毁", L.SPAN_INPUT)

            # Control 行
            grid.field_width(L.SPAN_INPUT)
            changed, hybrid.duration_max = imgui.input_int("##dur_max", hybrid.duration_max)
            if changed:
                hybrid.duration_max = max(1, hybrid.duration_max)
            grid.next_cell()

            if hybrid.has_charges:
                grid.field_width(L.SPAN_INPUT)
                changed, hybrid.wear_per_use = imgui.input_int("##wear", hybrid.wear_per_use)
                tooltip("每次使用消耗的耐久百分比")
                if changed:
                    hybrid.wear_per_use = max(0, min(100, hybrid.wear_per_use))
                grid.next_cell()

            _, hybrid.destroy_on_durability_zero = grid.checkbox_cell("##dur_del", hybrid.destroy_on_durability_zero, L.SPAN_INPUT)

        # ━━━ 次数组（条件显示，拆分为两行）━━━
        if hybrid.has_charges:
            # 逻辑组间隔（在耐久组后或触发组后显示）
            imgui.dummy(0, L.gap_m)
            charge_options = [ChargeMode.LIMITED, ChargeMode.UNLIMITED]

            # === 第一行：核心设置（次数模式 + 次数值 + 显示）===
            # Label 行
            grid.label_header("次数模式", L.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("次数值", L.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("显次数点", L.SPAN_INPUT)

            # Control 行
            grid.field_width(L.SPAN_INPUT)
            old_mode = hybrid.charge_mode
            hybrid.charge_mode = self._draw_mode_combo(
                "##charge_mode", hybrid.charge_mode,
                ChargeMode, CHARGE_MODE_LABELS, options=charge_options
            )
            grid.next_cell()
            if hybrid.charge_mode == ChargeMode.UNLIMITED:
                hybrid.charge = 1
                hybrid.has_charge_recovery = False
                grid.text_cell("∞", L.SPAN_INPUT)
            else:
                grid.field_width(L.SPAN_INPUT)
                changed, hybrid.charge = imgui.input_int("##charge", hybrid.charge)
                if changed:
                    hybrid.charge = max(1, hybrid.charge)

            grid.next_cell()
            _, hybrid.draw_charges = grid.checkbox_cell("##show_charge", hybrid.draw_charges, L.SPAN_INPUT)
            tooltip("在物品贴图左下角绘制小点表示剩余次数")

            # === 第二行：恢复/终止设置（仅在有限次数时显示）===
            if hybrid.charge_mode != ChargeMode.UNLIMITED:
                is_artifact_limited = hybrid.quality == 7 and hybrid.charge_mode == ChargeMode.LIMITED

                # Label 行
                grid.label_header("自动恢复", L.SPAN_INPUT)
                if hybrid.has_charge_recovery:
                    grid.next_cell()
                    grid.label_header("恢复间隔", L.SPAN_INPUT)
                if not hybrid.has_durability and hybrid.quality != 7:
                    grid.next_cell()
                    grid.label_header("耗尽销毁", L.SPAN_INPUT)

                # Control 行
                if is_artifact_limited:
                    hybrid.has_charge_recovery = True
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                    grid.checkbox_cell("##recovery_locked", True, L.SPAN_INPUT)
                    imgui.pop_style_var()
                    tooltip("文物自动恢复")
                else:
                    _, hybrid.has_charge_recovery = grid.checkbox_cell("##recovery", hybrid.has_charge_recovery, L.SPAN_INPUT)

                if hybrid.has_charge_recovery:
                    grid.next_cell()
                    grid.field_width(L.SPAN_INPUT)
                    changed, hybrid.charge_recovery_interval = imgui.input_int("##interval", hybrid.charge_recovery_interval)
                    if changed:
                        hybrid.charge_recovery_interval = max(1, hybrid.charge_recovery_interval)

                if not hybrid.has_durability and hybrid.quality != 7:
                    grid.next_cell()
                    _, hybrid.delete_on_charge_zero = grid.checkbox_cell("##charge_del", hybrid.delete_on_charge_zero, L.SPAN_INPUT)

        if not hybrid.has_durability and not hybrid.has_charges:
            hybrid.charge = 1
            hybrid.draw_charges = False
            hybrid.charge_mode = ChargeMode.LIMITED
            hybrid.has_charge_recovery = False
            hybrid.charge_recovery_interval = 10
            hybrid.wear_per_use = 0
            hybrid.delete_on_charge_zero = False

        # 逻辑组间隔
        imgui.dummy(0, L.gap_m)

        # ━━━ 生成组 ━━━
        self._draw_hybrid_spawn_settings(hybrid)

    def _draw_hybrid_stats(self, hybrid: HybridItem):
        """绘制属性区块 - Active-Only 模式"""
        L = self.layout

        # 装备属性
        if self._should_show_hybrid_attributes(hybrid):
            self._draw_hybrid_attributes_editor(hybrid)

        # 消耗品属性
        if hybrid.trigger_mode == TriggerMode.EFFECT:
            # 如果同时显示装备属性，添加间距
            if self._should_show_hybrid_attributes(hybrid):
                imgui.dummy(0, L.gap_m)

            self._draw_hybrid_consumable_attributes_editor(hybrid)

    def _draw_hybrid_presentation(self, hybrid: HybridItem):
        """绘制呈现区块 - 贴图、音效、本地化"""
        # 贴图
        self._draw_hybrid_textures_editor(hybrid)

        imgui.dummy(0, self.layout.gap_m)
        imgui.separator()
        imgui.dummy(0, self.layout.gap_s)

        # 音效 - 使用 GridLayout（label-on-top 布局，与基础/行为区块一致）
        grid = GridLayout(self.layout, self.text_secondary)
        L = self.layout

        # Label 行
        grid.label_header("放下音效", L.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("拾取音效", L.SPAN_INPUT)

        # Control 行
        grid.field_width(L.SPAN_INPUT)
        current_drop_label = HYBRID_DROP_SOUNDS.get(hybrid.drop_sound, f"{hybrid.drop_sound}")
        if imgui.begin_combo("##drop_sound", current_drop_label):
            for sound_id, sound_label in HYBRID_DROP_SOUNDS.items():
                if imgui.selectable(sound_label, sound_id == hybrid.drop_sound)[0]:
                    hybrid.drop_sound = sound_id
            imgui.end_combo()
        tooltip("物品放入物品栏或地面时的音效")

        grid.next_cell()
        grid.field_width(L.SPAN_INPUT)
        current_pickup_label = HYBRID_PICKUP_SOUNDS.get(hybrid.pickup_sound, f"{hybrid.pickup_sound}")
        if imgui.begin_combo("##pickup_sound", current_pickup_label):
            for sound_id, sound_label in HYBRID_PICKUP_SOUNDS.items():
                if imgui.selectable(sound_label, sound_id == hybrid.pickup_sound)[0]:
                    hybrid.pickup_sound = sound_id
            imgui.end_combo()
        tooltip("物品被拾取时的音效")

        imgui.dummy(0, self.layout.gap_m)
        imgui.separator()
        imgui.dummy(0, self.layout.gap_s)

        # 本地化
        self._draw_localization_editor(hybrid, "hybrid")

    def _update_hybrid_rarity_from_quality(self, hybrid: HybridItem):
        """根据品质自动更新稀有度"""
        # 普通(1) -> 空, 独特(6) -> "Unique", 文物(7) -> 空
        if hybrid.quality == 6:
            hybrid.rarity = "Unique"
        else:
            hybrid.rarity = ""

    def _render_attribute_grid(self, display_list: list, target_dict: dict, hybrid: HybridItem = None) -> list:
        """Shared logic for rendering a grid of attributes (Label-on-Top)

        Args:
            display_list: List of dicts with:
                - key: str
                - name: str (display name)
                - is_basic: bool (if True, no delete button, shows placeholder)
                - custom_bind: str (optional, e.g. "poison_duration" for redirect)
                - is_float: bool (optional)
                - desc: str (optional tooltip)
            target_dict: The dict to modify values in (e.g. hybrid.attributes)
            hybrid: The hybrid item object (required if using custom_bind)

        Returns:
            list of keys to remove
        """
        L = self.layout
        grid = GridLayout(L, self.text_secondary)
        WIDTH_SPAN = 2
        to_remove = []

        chunk_size = 4
        for i in range(0, len(display_list), chunk_size):
            chunk = display_list[i : i + chunk_size]

            # --- Row 1: Labels & Delete Buttons ---
            for idx, item in enumerate(chunk):
                if idx > 0: grid.next_cell()

                key = item["key"]
                name = item.get("name", key)
                is_basic = item.get("is_basic", False)

                # Render Label Cell Manually for alignment
                target_w = L.span(WIDTH_SPAN)
                start_x = imgui.get_cursor_pos_x()

                self.text_secondary(name)

                # Delete Button / Placeholder
                if not is_basic:
                    btn_label = f" x##d_{key}"
                    btn_display = " x"
                    btn_w = imgui.calc_text_size(btn_display).x
                    target_x = start_x + target_w - btn_w

                    # Ensure we don't overlap if text is too long
                    current_x = imgui.get_cursor_pos_x()
                    if target_x > current_x:
                        imgui.same_line(target_x)
                    else:
                        imgui.same_line()

                    if self._draw_text_action_button(
                        btn_label,
                        self.theme_colors["text_secondary"],
                        self.theme_colors["badge_hover_remove"]
                    ):
                        to_remove.append(key)

                    tooltip("移除此属性")
                else:
                    # Basic attributes: Draw inert placeholder to maintain row height consistency
                    btn_display = " x"
                    btn_w = imgui.calc_text_size(btn_display).x
                    target_x = start_x + target_w - btn_w

                    current_x = imgui.get_cursor_pos_x()
                    if target_x > current_x:
                        imgui.same_line(target_x)
                    else:
                        imgui.same_line()

                    imgui.dummy(btn_w, 0)
                    tooltip("基础属性不可移除")

                # Calculate remaining width to pad (safety)
                end_x = imgui.get_item_rect_max().x
                current_w = end_x - start_x
                if current_w < target_w:
                    imgui.same_line(spacing=0)
                    imgui.dummy(target_w - current_w, 0)

            # --- Row 2: Controls ---
            grid.field_width(WIDTH_SPAN)
            for idx, item in enumerate(chunk):
                if idx > 0: grid.next_cell()

                key = item["key"]
                is_basic = item.get("is_basic", False)
                custom_bind = item.get("custom_bind", None)
                is_float = item.get("is_float", False)
                desc = item.get("desc", None)

                grid.field_width(WIDTH_SPAN)
                full_w = L.span(WIDTH_SPAN)
                imgui.set_next_item_width(full_w)

                if custom_bind == "poison_duration" and hybrid:
                    val = hybrid.poison_duration
                    ch, nv = imgui.input_int(f"##v_poison_dur", val)
                    if ch: hybrid.poison_duration = max(0, nv)
                else:
                    val = target_dict.get(key, 0)
                    if key in STRICT_INT_ATTRIBUTES:
                        # 严格整数 (Strict Integer)
                        ch, nv = imgui.input_int(f"##v_{key}", int(val))
                    else:
                        # 默认为浮点数 (Default Float)
                        # 获取自定义 step，如果没有配置则默认步进为 0.1 (兼顾小数编辑)
                        step = SPECIAL_STEP_ATTRIBUTES.get(key, 0.1)

                        # 使用 %.2f 精度
                        ch, nv = imgui.input_float(f"##v_{key}", float(val), step, step * 10 if step else 0, "%.2f")

                    if ch:
                        target_dict[key] = nv
                        if is_basic:
                             target_dict[key] = max(0, target_dict[key])

                if desc:
                    tooltip(desc)

        return to_remove

    def _draw_hybrid_weapon_settings(self, hybrid: HybridItem):
        """绘制混合物品武器设置 - 使用 Table API"""
        if imgui.begin_table("hybrid_weapon_table", 4, imgui.TABLE_SIZING_STRETCH_SAME):
            imgui.table_setup_column("L1", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_setup_column("I1", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_setup_column("L2", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_setup_column("I2", imgui.TABLE_COLUMN_WIDTH_STRETCH)

            imgui.table_next_row()

            imgui.table_next_column()
            imgui.text("武器类型")

            imgui.table_next_column()
            with item_width(-1):
                hybrid.weapon_type = self._draw_enum_combo(
                    "##wep_type", hybrid.weapon_type,
                    list(HYBRID_WEAPON_TYPES.keys()), HYBRID_WEAPON_TYPES
                )
            # hands 是计算属性，由 weapon_type 自动推断

            imgui.table_next_column()
            imgui.text("平衡")

            imgui.table_next_column()
            with item_width(-1):
                changed, hybrid.balance = imgui.input_int("##wep_balance", hybrid.balance)
            if changed:
                hybrid.balance = max(1, hybrid.balance)

            imgui.end_table()

        # 伤害汇总（放在区块底部）
        damage_components = self._compute_weapon_damage_components(hybrid)
        total_dmg = sum(v for _, v in damage_components)
        max_val = max([v for _, v in damage_components], default=0)
        ties = [t for t, v in damage_components if v == max_val and v > 0]
        best_type = ties[0] if ties else "Slashing_Damage"
        dmg_type_label = HYBRID_DAMAGE_TYPES.get(best_type, best_type)
        self.text_secondary(f"伤害汇总: DMG={total_dmg}  主类型={dmg_type_label}（自动取最高伤害类型）")

    def _draw_hybrid_armor_settings(self, hybrid: HybridItem):
        """绘制混合物品护甲设置 - 使用 Table API"""
        # 护甲类型和护甲类别
        if imgui.begin_table("hybrid_armor_table", 4, imgui.TABLE_SIZING_STRETCH_SAME):
            imgui.table_setup_column("L1", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_setup_column("I1", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_setup_column("L2", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_setup_column("I2", imgui.TABLE_COLUMN_WIDTH_STRETCH)

            imgui.table_next_row()

            imgui.table_next_column()
            imgui.text("护甲类型")

            imgui.table_next_column()
            with item_width(-1):
                hybrid.armor_type = self._draw_enum_combo(
                    "##armor_type", hybrid.armor_type,
                    list(HYBRID_ARMOR_TYPES.keys()), HYBRID_ARMOR_TYPES
                )

            # 根据护甲类型自动设置槽位
            hybrid.slot = "hand" if hybrid.armor_type == "shield" else hybrid.armor_type

            imgui.table_next_column()
            imgui.text("护甲类别")

            imgui.table_next_column()
            self.text_secondary(f"{hybrid.armor_class}")
            tooltip("由基本属性中的'重量'自动计算:\nLight/VeryLight → Light\nMedium → Medium\nHeavy → Heavy")

            imgui.end_table()

        # 碎片材料编辑器（用于拆解，仅非盾/戒/项链显示）
        if hybrid.slot not in ["hand", "Ring", "Amulet"]:
            if imgui.tree_node("拆解碎片##fragments"):
                frag_data = [
                    ("cloth01", "布1"), ("cloth02", "布2"), ("cloth03", "布3"), ("cloth04", "布4"),
                    ("leather01", "皮1"), ("leather02", "皮2"), ("leather03", "皮3"), ("leather04", "皮4"),
                    ("metal01", "铁1"), ("metal02", "铁2"), ("metal03", "铁3"), ("metal04", "铁4"),
                    ("gold", "金"),
                ]

                # 4列布局: 标签|输入|标签|输入
                if imgui.begin_table("frag_table", 4, imgui.TABLE_SIZING_STRETCH_SAME):
                    imgui.table_setup_column("L1", imgui.TABLE_COLUMN_WIDTH_FIXED, 30)
                    imgui.table_setup_column("I1", imgui.TABLE_COLUMN_WIDTH_FIXED, 50)
                    imgui.table_setup_column("L2", imgui.TABLE_COLUMN_WIDTH_FIXED, 30)
                    imgui.table_setup_column("I2", imgui.TABLE_COLUMN_WIDTH_FIXED, 50)

                    for i, (frag_key, frag_label) in enumerate(frag_data):
                        if i % 2 == 0:
                            imgui.table_next_row()

                        imgui.table_next_column()
                        imgui.text(frag_label)

                        imgui.table_next_column()
                        val = hybrid.fragments.get(frag_key, 0)
                        with item_width(-1):
                            changed, new_val = imgui.input_int(f"##{frag_key}", val, step=0, step_fast=0)
                        if changed:
                            hybrid.fragments[frag_key] = max(0, new_val)

                    imgui.end_table()

                tooltip("拆解物品时获得的碎片材料")
                imgui.tree_pop()

    def _draw_hybrid_attributes_editor(self, hybrid: HybridItem):
        """绘制装备属性编辑器 - Active-Only Label-on-Top"""
        groups = self._get_hybrid_attribute_groups(hybrid)
        if not groups:
            return

        L = self.layout
        grid = GridLayout(L, self.text_secondary)

        # 1. 收集所有可用属性用于搜索
        all_available_attrs = []
        for group, attrs in groups.items():
            for attr in attrs:
                all_available_attrs.append((attr, group))

        # 2. 绘制已激活属性 (Label-on-Top Grid Active List)
        # 按 groups 顺序排序 active_attrs 以保持稳定视觉顺序
        active_attrs = []
        for group, attrs in groups.items():
            for attr in attrs:
                if hybrid.attributes.get(attr, 0) != 0:
                    active_attrs.append(attr)

        to_remove = []
        if active_attrs:
            # Construct display list for shared renderer
            display_list = []
            for attr in active_attrs:
                attr_name, attr_desc = get_attr_display(attr)
                display_list.append({
                    "key": attr,
                    "name": attr_name or attr,
                    "desc": attr_desc,
                    "is_basic": False
                })

            # Use shared renderer
            to_remove_keys = self._render_attribute_grid(display_list, hybrid.attributes)
            to_remove.extend(to_remove_keys)

        # 执行移除
        for attr in to_remove:
            hybrid.attributes[attr] = 0 # 设为0即视为未激活，会被清理逻辑处理

        # 3. 添加按钮
        self._draw_add_attribute_button("添加装备属性", "equip_attr", hybrid.attributes, all_available_attrs)

        # 清理
        self._prune_hybrid_attributes(hybrid, groups)

    def _draw_add_attribute_button(self, label, popup_id, target_dict, available_attrs):
        """绘制带搜索的添加属性按钮"""
        L = self.layout
        if imgui.button(f"+ {label}", width=L.span(8)):
            imgui.open_popup(popup_id)

        imgui.set_next_window_size(300, 400)
        if imgui.begin_popup(popup_id):
            # 搜索框
            imgui.dummy(0, 2)
            imgui.set_next_item_width(-1)
            # 使用静态变量存储搜索词
            if not hasattr(self, "_attr_search_buffers"):
                self._attr_search_buffers = {}
            if popup_id not in self._attr_search_buffers:
                self._attr_search_buffers[popup_id] = ""

            changed, search_text = imgui.input_text(f"##search_{popup_id}", self._attr_search_buffers[popup_id], 64)
            if changed:
                self._attr_search_buffers[popup_id] = search_text

            search_lower = search_text.lower()
            imgui.separator()

            # 过滤列表
            current_group = None
            group_visible = False

            filtered = []
            for attr, group in available_attrs:
                if target_dict.get(attr, 0) != 0: continue
                name, desc = get_attr_display(attr)
                match_text = f"{attr} {name}".lower()
                if not search_lower or search_lower in match_text:
                    filtered.append((group, attr, name, desc))

            if not filtered:
                self.text_secondary("无匹配属性")

            last_group = None
            last_group_open = False
            flat_mode = bool(search_lower)

            for group, attr, name, desc in filtered:
                if group != last_group:
                    if not flat_mode:
                        if last_group and last_group_open:
                            imgui.tree_pop()
                        # 使用完整 group 名称作为 ID，避免相同 display_name 导致 ID 冲突
                        last_group_open = imgui.tree_node(f"{group}##grp_{group}_{popup_id}")
                        group_visible = last_group_open
                    else:
                        imgui.dummy(0, 2)
                        self.text_secondary(f"--- {group} ---")
                        group_visible = True
                        last_group_open = False
                    last_group = group

                if group_visible:
                    if imgui.selectable(f"{name or attr}##sel_{attr}")[0]:
                        target_dict[attr] = 1 # 激活
                        imgui.close_current_popup()
                        self._attr_search_buffers[popup_id] = ""
                    if desc:
                        tooltip(desc)

            if not flat_mode and last_group and last_group_open:
                imgui.tree_pop()

            imgui.end_popup()










    def _prune_hybrid_attributes(self, hybrid: HybridItem, groups: dict):
        """移除与当前类型不匹配的属性"""
        allowed = set()
        for attrs in groups.values():
            allowed.update(attrs)
        to_delete = [k for k in hybrid.attributes.keys() if k not in allowed]
        for k in to_delete:
            del hybrid.attributes[k]

    def _draw_hybrid_consumable_attributes_editor(self, hybrid: HybridItem):
        """绘制消耗品属性编辑器 - Active-Only Label-on-Top (Fully Merged)"""
        if not hybrid.has_charges:
            return

        L = self.layout
        grid = GridLayout(L, self.text_secondary)
        WIDTH_SPAN = 2

        # 顶部标题 (唯一的层级)
        # imgui.text_colored("消耗品属性", *self.theme_colors["text_secondary"])
        # imgui.dummy(0, L.gap_s)

        # === 1. 构建统一的显示列表 ===
        display_list = []

        # 1.1 基础属性 (Mandatory)
        display_list.append({
            "key": CONSUMABLE_DURATION_ATTRIBUTE,
            "name": "效果持续 (轮)",
            "is_basic": True
        })
        display_list.append({
            "key": "Poisoning_Chance",
            "name": "中毒几率 (%)",
            "is_basic": True
        })

        # 1.2 条件基础属性 (Pseudo-attributes)
        if hybrid.consumable_attributes.get("Poisoning_Chance", 0) > 0:
            display_list.append({
                "key": "Poison_Duration",
                "name": "中毒持续 (轮)",
                "is_basic": True,
                "custom_bind": "poison_duration"
            })

        # 1.3 即时效果 (Instant Effects)
        for grp, attrs in CONSUMABLE_INSTANT_ATTRS.items():
            for attr in attrs:
                if attr == "Poisoning_Chance": continue
                if hybrid.consumable_attributes.get(attr, 0) != 0:
                    d_name, d_desc = get_attr_display(attr)
                    display_list.append({
                        "key": attr,
                        "name": d_name or attr,
                        "desc": d_desc,
                        "is_basic": False
                    })

        # 1.4 持续效果 (Persistent Effects)
        dur_keys = get_consumable_duration_attrs()
        dur_groups = get_attribute_groups(dur_keys, DEFAULT_GROUP_ORDER)
        for grp, attrs in dur_groups.items():
            for attr in attrs:
                if attr == CONSUMABLE_DURATION_ATTRIBUTE: continue
                if hybrid.consumable_attributes.get(attr, 0) != 0:
                    d_name, d_desc = get_attr_display(attr)
                    display_list.append({
                        "key": attr,
                        "name": d_name or attr,
                        "desc": d_desc,
                        "is_basic": False
                    })

        # === 2. 统一渲染 Grid ===
        if display_list:
            to_remove = self._render_attribute_grid(
                display_list,
                hybrid.consumable_attributes,
                hybrid
            )

            # Process removals
            for attr in to_remove:
                hybrid.consumable_attributes[attr] = 0

            # Skip manual loop
            display_list = []





















            # Row Spacing
            # imgui.dummy(0, L.gap_s)



        # === 3. Add Buttons (Searchable) ===
        all_instants = []
        for grp, attrs in CONSUMABLE_INSTANT_ATTRS.items():
            for a in attrs:
                if a not in {"Poisoning_Chance"}: all_instants.append((a, grp))

        all_durations = []
        for grp, attrs in dur_groups.items():
            for a in attrs:
                if a != CONSUMABLE_DURATION_ATTRIBUTE: all_durations.append((a, grp))

        merged_source = []
        for a, g in all_instants:
            # 去除冗余的 "即时效果" 前缀
            suffix = g.split("（")[-1].rstrip("）") if "（" in g else g
            merged_source.append((a, f"即时效果 - {suffix}"))

        for a, g in all_durations: merged_source.append((a, f"持续效果 - {g}"))

        self._draw_add_attribute_button("添加效果...", "add_consum_effect", hybrid.consumable_attributes, merged_source)







    def _get_hybrid_attribute_groups(self, hybrid: HybridItem) -> dict:
        """根据槽位获取可编辑属性分组"""
        # 获取该槽位的属性列表（被动携带物品需要额外抗性属性）
        attrs = get_hybrid_attrs_for_slot(hybrid.slot, hybrid.has_passive)
        result = get_attribute_groups(attrs, DEFAULT_GROUP_ORDER)

        # 清理不再允许的属性
        if result:
            allowed = {a for attr_list in result.values() for a in attr_list}
            for k in [k for k in hybrid.attributes if k not in allowed]:
                del hybrid.attributes[k]

        return result

    def _compute_weapon_damage_components(self, hybrid: HybridItem) -> list[tuple[str, int]]:
        """收集所有伤害（不区分主/额外，全部来自属性伤害键）"""
        damage_keys = [
            "Slashing_Damage",
            "Piercing_Damage",
            "Blunt_Damage",
            "Rending_Damage",
            "Fire_Damage",
            "Shock_Damage",
            "Poison_Damage",
            "Caustic_Damage",
            "Frost_Damage",
            "Arcane_Damage",
            "Unholy_Damage",
            "Sacred_Damage",
            "Psionic_Damage",
        ]
        comps: list[tuple[str, int]] = []
        for k, v in hybrid.attributes.items():
            if k in damage_keys and v != 0:
                comps.append((k, v))
        return comps


    def _draw_hybrid_textures_editor(self, hybrid: HybridItem):
        """绘制混合物品贴图编辑器 - 精简版

        设计原则: Tufte - 删除静态提示文字，改为 tooltip
        """
        # 预览缩放 + 格式提示 (内联)
        self.text_secondary("预览缩放:")
        imgui.same_line()
        imgui.set_next_item_width(self.layout.input_m)
        changed, self.texture_scale = imgui.input_float("##scale_hybrid", self.texture_scale, 0.5, 1.0, "%.1fx")
        tooltip("仅支持 PNG 格式")
        if changed:
            self.texture_scale = max(0.5, min(8.0, self.texture_scale))
            self.save_config()

        imgui.dummy(0, self.layout.gap_s)

        # 穿戴/手持状态贴图
        if hybrid.needs_char_texture():
            # 多姿势护甲（头/身/手/腿/背）使用完整护甲贴图编辑器
            if hybrid.needs_multi_pose_textures():
                self._draw_multi_pose_armor_textures(hybrid, "hybrid")
            else:
                # 武器/盾牌模式
                self.text_secondary("穿戴/手持状态贴图")

                # 模特选择
                imgui.same_line()
                self.text_secondary("  模特:")
                imgui.same_line()
                model_combo_width = 100 + (self.font_size - 14) * 4
                imgui.push_item_width(model_combo_width)
                current_model_label = CHARACTER_MODEL_LABELS.get(
                    self.selected_model, self.selected_model
                )
                if imgui.begin_combo("##model_hybrid", current_model_label):
                    for model_key, model_label in CHARACTER_MODEL_LABELS.items():
                        if imgui.selectable(model_label, model_key == self.selected_model)[0]:
                            self.selected_model = model_key
                    imgui.end_combo()
                imgui.pop_item_width()

                imgui.dummy(0, self.layout.gap_s)

                # 角色贴图
                self._draw_texture_list_selector(
                    "角色贴图*", hybrid.textures.character, "character", hybrid, "hybrid"
                )

                hybrid.textures.offset_x, hybrid.textures.offset_y = self._draw_offset_inputs(
                    "偏移",
                    "调整物品相对于人物的相对位置",
                    hybrid.textures.offset_x,
                    hybrid.textures.offset_y,
                    "hybrid",
                )

                # 左手贴图（如果需要）
                if hybrid.needs_left_texture():
                    imgui.dummy(0, self.layout.gap_s)
                    self._draw_texture_list_selector(
                        "左手贴图*",
                        hybrid.textures.character_left,
                        "character_left",
                        hybrid,
                        "hybrid",
                    )

                    hybrid.textures.offset_x_left, hybrid.textures.offset_y_left = (
                        self._draw_offset_inputs(
                            "偏移 (左手)",
                            "调整左手物品相对于人物的相对位置",
                            hybrid.textures.offset_x_left,
                            hybrid.textures.offset_y_left,
                            "hybrid_left",
                        )
                    )

            imgui.dummy(0, self.layout.gap_s)
            imgui.separator()
            imgui.dummy(0, self.layout.gap_s)
        else:
            slot_name = HYBRID_SLOT_LABELS.get(hybrid.slot, hybrid.slot)
            self.text_secondary(f"{slot_name} 槽位无需穿戴贴图")
            imgui.dummy(0, self.layout.gap_s)


        # 常规贴图
        self.text_secondary("物品栏贴图")
        imgui.same_line()
        if imgui.button("+##inv_add"):
            hybrid.textures.inventory.append("")
        tooltip("添加贴图槽（多张可显示不同耐久状态）")
        if len(hybrid.textures.inventory) > 1:
            imgui.same_line()
            if imgui.button("-##inv_remove"):
                hybrid.textures.inventory.pop()
            tooltip("删除最后一个贴图槽")

        for idx in range(len(hybrid.textures.inventory)):
            current_path = (
                hybrid.textures.inventory[idx]
                if idx < len(hybrid.textures.inventory)
                else ""
            )
            self._draw_single_texture_selector(
                f"贴图 {idx + 1}##hybrid",
                current_path,
                ("inventory", idx),
                hybrid,
                "hybrid",
            )

        imgui.dummy(0, self.layout.gap_s)
        imgui.separator()
        imgui.dummy(0, self.layout.gap_s)

        # 战利品贴图
        self._draw_texture_list_selector(
            "战利品贴图*##hybrid", hybrid.textures.loot, "loot", hybrid, "hybrid"
        )

        if hybrid.textures.is_animated("loot"):
            self._draw_loot_animation_settings(hybrid.textures, "hybrid")

    def _draw_hybrid_drop_slot_settings(self, hybrid: HybridItem):
        """绘制掉落分类设置"""
        # ====== 排除随机生成开关 ======
        changed, hybrid.exclude_from_random = imgui.checkbox(
            "排除随机生成##hybrid", hybrid.exclude_from_random
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "开启后，物品不会出现在宝箱掉落和商店库存中\n"
                "物品将添加 'special' 标签\n"
                "关闭后，可设置分类和标签使物品参与随机生成"
            )

        self.draw_indented_separator()

        if hybrid.exclude_from_random:
            self.text_secondary("提示: 已排除随机生成，下方设置用于自定义生成逻辑或指令添加")

        # ====== 分类设置 ======
        imgui.text("分类设置")

        # 两列布局
        col_width = imgui.get_content_region_available_width() / 2 - 8
        imgui.columns(2, "drop_slot_cols", border=False)
        imgui.set_column_width(0, col_width)

        # 左列: Cat
        imgui.push_item_width(-1)
        imgui.text("主分类 (Cat)")

        # 文物主分类固定为 treasure
        if hybrid.quality == 7:  # 文物
            hybrid.cat = "treasure"
            self.text_secondary("文物分类固定为 treasure")
        else:
            # 非文物不能选择 treasure
            available_cats = [c for c in ITEM_CATEGORIES if c != "treasure"]
            # 如果当前选择了 treasure，重置为空
            if hybrid.cat == "treasure":
                hybrid.cat = ""
            cat_options = [""] + available_cats
            cat_labels = {"": "-- 无 --"}
            cat_labels.update({c: f"{CATEGORY_TRANSLATIONS.get(c, c)} ({c})" for c in available_cats})
            hybrid.cat = self._draw_enum_combo("##cat_hybrid", hybrid.cat, cat_options, cat_labels)
        if imgui.is_item_hovered():
            imgui.set_tooltip("物品的主分类，用于掉落表匹配")
        imgui.pop_item_width()

        # 等级已移至基本属性区域

        imgui.columns(1)

        # ====== Subcats 多选 ======
        imgui.dummy(0, 4)
        imgui.text("子分类 (Subcats)")
        if imgui.is_item_hovered():
            imgui.set_tooltip("可多选。物品可以匹配主分类或任一子分类")

        # 使用四列网格布局
        # 非文物不能选择 treasure
        if hybrid.quality == 7:
            subcat_options = ALL_SUBCATEGORY_OPTIONS
        else:
            subcat_options = [s for s in ALL_SUBCATEGORY_OPTIONS if s != "treasure"]
            # 如果当前选择了 treasure，移除它
            if "treasure" in hybrid.subcats:
                hybrid.subcats.remove("treasure")

        num_cols = 4
        col_width = imgui.get_content_region_available_width() / num_cols - 4
        imgui.columns(num_cols, "subcat_cols", border=False)
        for i in range(num_cols):
            imgui.set_column_width(i, col_width)

        for i, subcat in enumerate(subcat_options):
            is_selected = subcat in hybrid.subcats
            is_disabled = (subcat == hybrid.cat)

            if is_disabled:
                imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)

            changed, new_value = imgui.checkbox(
                f"{CATEGORY_TRANSLATIONS.get(subcat, subcat)}##subcat_{subcat}",
                is_selected
            )
            if changed and not is_disabled:
                if new_value:
                    hybrid.subcats.append(subcat)
                else:
                    hybrid.subcats.remove(subcat)

            if is_disabled:
                imgui.pop_style_var()
                if imgui.is_item_hovered():
                    imgui.set_tooltip("已选为主分类，无需重复选择")

            imgui.next_column()

        imgui.columns(1)

        self.draw_indented_separator()

        # ====== Tags 设置 ======
        imgui.text("标签设置")

        imgui.columns(3, "tags_cols", border=False)

        # 品质标签自动设置（不显示控件）
        # quality 6 = 独特 -> 品质标签为 unique
        # 其他 -> 品质标签为空
        hybrid.quality_tag = "unique" if hybrid.quality == 6 else ""

        # 地牢标签 (单选)
        imgui.text("地牢")
        for tag_val, tag_label in DUNGEON_TAGS.items():
            if imgui.radio_button(f"{tag_label}##dungeon", hybrid.dungeon_tag == tag_val):
                hybrid.dungeon_tag = tag_val

        imgui.next_column()

        # 国家标签 (单选，互斥)
        imgui.text("国家/地区")
        for tag_val, tag_label in COUNTRY_TAGS.items():
            if imgui.radio_button(f"{tag_label}##country", hybrid.country_tag == tag_val):
                hybrid.country_tag = tag_val

        imgui.next_column()

        # 其他标签 (多选)
        imgui.text("其他")
        for tag_val, tag_label in EXTRA_TAGS.items():
            is_selected = tag_val in hybrid.extra_tags
            changed, new_value = imgui.checkbox(f"{tag_label}##extra_{tag_val}", is_selected)
            if changed:
                if new_value:
                    hybrid.extra_tags.append(tag_val)
                else:
                    hybrid.extra_tags.remove(tag_val)

        imgui.columns(1)

        # 显示有效 tags
        imgui.dummy(0, 4)
        self.text_secondary(f"有效标签: {hybrid.effective_tags or '(无)'}")

        self.draw_indented_separator()

        # ====== 生成路径配置 ======
        imgui.text("生成路径配置")
        if imgui.is_item_hovered():
            imgui.set_tooltip("统一控制容器/商店/击杀的生成路径\n"
                              "装备品: 从装备筛选路径生成（与原生装备一起随机）\n"
                              "非装备品: 保持当前行为")

        spawn_mode_options = [SpawnMode.NON_EQUIPMENT, SpawnMode.EQUIPMENT]
        spawn_mode_labels = {
            SpawnMode.EQUIPMENT: "装备品路径",
            SpawnMode.NON_EQUIPMENT: "非装备品路径",
        }

        imgui.set_next_item_width(200)
        if imgui.begin_combo("##spawn_mode", spawn_mode_labels[hybrid.spawn_mode]):
            for mode in spawn_mode_options:
                selected = hybrid.spawn_mode == mode
                if imgui.selectable(spawn_mode_labels[mode], selected)[0]:
                    hybrid.spawn_mode = mode
            imgui.end_combo()

        if hybrid.spawn_mode == SpawnMode.EQUIPMENT:
            imgui.same_line()
            self.text_secondary("(自动添加 special 标签)")

        self.draw_indented_separator()

        # ====== 掉落匹配预览 ======
        self._draw_drop_pool_preview(hybrid)

        # ====== 商店预览 ======
        self.draw_indented_separator()
        imgui.text("商店进货预览")
        if imgui.is_item_hovered():
            imgui.set_tooltip("显示物品可能出现的商店\n"
                              "商店根据分类/标签/等级筛选库存")

        if hybrid.spawn_mode == SpawnMode.NON_EQUIPMENT:
            # 非装备路径商店：匹配 selling_loot_category
            self._draw_shop_preview_non_equipment(hybrid)
        elif hybrid.spawn_mode == SpawnMode.EQUIPMENT:
            # 装备路径商店：匹配 tier_range, material_spec, trade_tags
            self._draw_shop_preview_equipment(hybrid)

    def _draw_shop_preview_non_equipment(self, hybrid: HybridItem):
        """绘制非装备路径商店预览"""
        if not (hybrid.cat or hybrid.subcats):
            self.text_secondary("(请设置分类以查看匹配商店)")
            return

        # 匹配商店：检查 selling_loot_category 是否包含物品的分类
        item_cats = set([hybrid.cat] + list(hybrid.subcats))
        item_tags = set(hybrid.effective_tags.split()) if hybrid.effective_tags else set()
        matching_shops = []

        for objects_tuple, config in SHOP_CONFIGS.items():
            selling_cats = config.get("selling_loot_category", {})
            trade_tags = set(config.get("trade_tags", []))

            matched_cats = item_cats & set(selling_cats.keys())
            if not matched_cats:
                continue

            # 计算匹配分类的数量
            total_count = sum(selling_cats.get(c, 0) for c in matched_cats if isinstance(selling_cats.get(c), int))

            # 标签检查：物品标签须为商店 trade_tags 的子集
            if trade_tags and item_tags and not item_tags.issubset(trade_tags):
                continue

            for obj in objects_tuple:
                meta = NPC_METADATA.get(obj, {})
                # 暂时隐藏没有名字的商店
                if not meta.get("name_en") and not meta.get("name_zh"):
                    continue
                matching_shops.append({
                    "npc_object": obj,
                    "name": meta.get("name_zh") or meta.get("name_en") or obj,
                    "town": meta.get("town_zh") or meta.get("town") or "",
                    "matched_info": ", ".join(CATEGORY_TRANSLATIONS.get(c, c) for c in matched_cats),
                    "count": str(total_count) if total_count else "-",
                    "tags": " ".join(trade_tags) if trade_tags else "-",
                })

        self._render_shop_table(matching_shops, "noneq", ["商店名称", "城镇", "匹配分类", "数量", "标签"])

    def _draw_shop_preview_equipment(self, hybrid: HybridItem):
        """绘制装备路径商店预览"""
        item_tier = hybrid.tier
        item_material = hybrid.material
        item_tags = set(hybrid.effective_tags.split()) if hybrid.effective_tags else set()

        # 获取物品的装备分类
        item_weapon_type = hybrid.weapon_type if hybrid.equipment_mode == EquipmentMode.WEAPON else None
        item_armor_slot = hybrid.slot if hybrid.equipment_mode == EquipmentMode.ARMOR else None
        is_jewelry = item_armor_slot in ("ring", "amulet") if item_armor_slot else False

        matching_shops = []

        for objects_tuple, config in SHOP_CONFIGS.items():
            selling_cats = config.get("selling_loot_category", {})
            tier_range = config.get("tier_range", [1, 1])
            material_spec = config.get("material_spec", ["all"])
            trade_tags = set(config.get("trade_tags", []))

            # 1. 检查 selling_loot_category 是否匹配物品类型
            category_matched = False
            matched_type = ""
            selling_keys = set(selling_cats.keys())

            if "weapon" in selling_keys and item_weapon_type:
                category_matched = True
                matched_type = "武器"
            elif "armor" in selling_keys and item_armor_slot and not is_jewelry:
                category_matched = True
                matched_type = "护甲"
            elif "jewelry" in selling_keys and is_jewelry:
                category_matched = True
                matched_type = "饰品"

            if item_weapon_type:
                type_lower = item_weapon_type.lower()
                if type_lower in selling_keys or item_weapon_type in selling_keys:
                    category_matched = True
                    matched_type = CATEGORY_TRANSLATIONS.get(item_weapon_type, item_weapon_type)

            if item_armor_slot:
                slot_cap = item_armor_slot.capitalize()
                if slot_cap in selling_keys or item_armor_slot in selling_keys:
                    category_matched = True
                    matched_type = CATEGORY_TRANSLATIONS.get(slot_cap, slot_cap)

            if not category_matched:
                continue

            # 2. 检查等级范围
            if item_tier > 0 and not (tier_range[0] <= item_tier <= tier_range[1]):
                continue

            # 3. 检查材料筛选
            if "all" not in material_spec and item_material not in material_spec:
                continue

            # 4. 检查标签匹配
            if trade_tags:
                if not item_tags:
                    continue
                if not item_tags.issubset(trade_tags):
                    continue

            for obj in objects_tuple:
                meta = NPC_METADATA.get(obj, {})
                if not meta.get("name_en") and not meta.get("name_zh"):
                    continue
                matching_shops.append({
                    "npc_object": obj,
                    "name": meta.get("name_zh") or meta.get("name_en") or obj,
                    "town": meta.get("town_zh") or meta.get("town") or "",
                    "matched_info": matched_type,
                    "count": f"T{tier_range[0]}-{tier_range[1]}",
                    "tags": " ".join(trade_tags) if trade_tags else "-",
                })

        self._render_shop_table(matching_shops, "eq", ["商店名称", "城镇", "匹配类型", "等级", "标签"])

    def _render_shop_table(self, shops: list, table_id: str, headers: list):
        """渲染商店预览表格（通用帮助函数）"""
        if not shops:
            self.text_secondary("(无匹配的商店)")
            return

        self.text_secondary(f"物品可能出现在 {len(shops)} 个商店:")
        imgui.begin_child(f"##shop_preview_{table_id}", height=150, border=True)
        imgui.columns(len(headers), f"shop_table_{table_id}")
        imgui.set_column_width(0, 130)
        imgui.set_column_width(1, 70)
        imgui.set_column_width(2, 80)
        imgui.set_column_width(3, 50)

        for header in headers:
            imgui.text(header)
            imgui.next_column()
        imgui.separator()

        for shop in shops[:30]:
            imgui.text(shop["name"])
            if imgui.is_item_hovered():
                imgui.set_tooltip(shop["npc_object"])
            imgui.next_column()
            imgui.text(shop["town"])
            imgui.next_column()
            imgui.text(shop["matched_info"])
            imgui.next_column()
            imgui.text(shop["count"])
            imgui.next_column()
            imgui.text(shop["tags"])
            imgui.next_column()

        if len(shops) > 30:
            imgui.text(f"...还有 {len(shops) - 30} 个商店")

        imgui.columns(1)
        imgui.end_child()

    def _draw_drop_pool_preview(self, hybrid: HybridItem):
        """绘制掉落池预览（非装备路径和装备路径）"""
        imgui.text("容器掉落预览")
        if imgui.is_item_hovered():
            imgui.set_tooltip("显示物品可能在哪些容器（宝箱等）中生成")

        # 根据生成路径显示不同预览
        if hybrid.spawn_mode == SpawnMode.NON_EQUIPMENT:
            self._draw_non_equipment_drop_preview(hybrid)
        elif hybrid.spawn_mode == SpawnMode.EQUIPMENT:
            self._draw_equipment_drop_preview(hybrid)

    def _draw_non_equipment_drop_preview(self, hybrid: HybridItem):
        """绘制非装备路径容器掉落预览"""
        if not (hybrid.cat or hybrid.subcats):
            return  # 没有设置分类时不显示

        matches = find_matching_slots(
            hybrid.cat,
            tuple(hybrid.subcats),
            hybrid.tags_tuple,
            hybrid.tier
        )

        if not matches:
            self.text_secondary("(无匹配的掉落池)")
            return

        self.text_secondary(f"物品可加入 {len(matches)} 个掉落池:")

        imgui.begin_child("##drop_slots_preview", height=180, border=True)

        imgui.columns(7, "slots_table")
        imgui.set_column_width(0, 120)
        imgui.set_column_width(1, 30)
        imgui.set_column_width(2, 200)
        imgui.set_column_width(3, 45)
        imgui.set_column_width(4, 40)
        imgui.set_column_width(5, 45)

        for header in ["来源", "#", "分类", "概率", "数量", "等级", "标签"]:
            imgui.text(header)
            imgui.next_column()
        imgui.separator()

        for slot in matches[:50]:
            imgui.text(slot["entry_name_cn"])
            if imgui.is_item_hovered():
                imgui.set_tooltip(slot["entry_id"])
            imgui.next_column()

            imgui.text(str(slot["slot_num"]))
            imgui.next_column()

            cat_cn = ", ".join(CATEGORY_TRANSLATIONS.get(c.strip(), c.strip()) for c in slot["category"].split(","))
            imgui.text(cat_cn[:25])
            imgui.next_column()

            imgui.text(f"{slot['chance']}%")
            imgui.next_column()

            imgui.text(str(slot["slot_count"]))
            imgui.next_column()

            imgui.text(slot["tier_range"])
            imgui.next_column()

            if slot["slot_tags"]:
                tags_cn = " ".join(ALL_TAGS.get(t, t) for t in slot["slot_tags"].split())
                imgui.text(tags_cn[:15])
                tooltip(slot["slot_tags"])
            else:
                imgui.text("-")
            imgui.next_column()

        imgui.columns(1)
        imgui.end_child()

    def _draw_equipment_drop_preview(self, hybrid: HybridItem):
        """绘制装备路径容器掉落预览"""
        # 确定装备类别
        eq_categories = []
        if hybrid.equipment_mode == EquipmentMode.WEAPON:
            # 武器: 添加具体武器类型(如 sword, axe)和通用 weapon
            if hybrid.weapon_type:
                eq_categories.append(hybrid.weapon_type)
            eq_categories.append("weapon")
        elif hybrid.equipment_mode == EquipmentMode.ARMOR:
            # 护甲: 添加具体护甲类型，再添加 jewelry 或 armor
            if hybrid.armor_type:
                eq_categories.append(hybrid.armor_type)
            if hybrid.armor_type in ("Ring", "Amulet"):
                eq_categories.append("jewelry")
            else:
                eq_categories.append("armor")

        if not eq_categories:
            return

        all_matches = []
        for eq_cat in eq_categories:
            matches = find_matching_eq_slots(eq_cat, hybrid.tags_tuple, hybrid.tier)
            all_matches.extend(matches)

        if not all_matches:
            self.text_secondary("(无匹配的装备掉落池)")
            return

        self.text_secondary(f"装备可从 {len(all_matches)} 个容器生成:")

        imgui.begin_child("##eq_drop_preview", height=180, border=True)

        imgui.columns(6, "eq_slots_table")
        imgui.set_column_width(0, 130)
        imgui.set_column_width(1, 30)
        imgui.set_column_width(2, 80)
        imgui.set_column_width(3, 45)
        imgui.set_column_width(4, 50)

        for header in ["来源", "#", "类型", "概率", "等级", "标签"]:
            imgui.text(header)
            imgui.next_column()
        imgui.separator()

        for slot in all_matches[:50]:
            imgui.text(slot["entry_name_cn"])
            if imgui.is_item_hovered():
                imgui.set_tooltip(slot["entry_id"])
            imgui.next_column()

            imgui.text(str(slot["eq_num"]))
            imgui.next_column()

            eq_cat_cn = ", ".join(CATEGORY_TRANSLATIONS.get(c.strip(), c) for c in slot["eq_category"].split(","))
            imgui.text(eq_cat_cn)
            imgui.next_column()

            imgui.text(f"{slot['chance']}%")
            imgui.next_column()

            imgui.text(slot["tier_range"])
            imgui.next_column()

            if slot["eq_tags"]:
                tags_cn = " ".join(ALL_TAGS.get(t, t) for t in slot["eq_tags"].split())
                imgui.text(tags_cn[:15])
                if imgui.is_item_hovered():
                    imgui.set_tooltip(f"tags: {slot['eq_tags']}\nrarity: {slot.get('eq_rarity', '')}")
            else:
                imgui.text("-")
            imgui.next_column()

        imgui.columns(1)
        imgui.end_child()

    def _draw_basic_properties(self, item, id_suffix, slot_labels, material_labels):
        """绘制物品基本属性"""
        type_name = "武器" if id_suffix == "weapon" else "装备"

        # 系统ID - 占满宽度
        imgui.text(f"{type_name}系统ID")
        imgui.same_line()
        self.text_secondary(f"(生成ID: {item.id})")
        imgui.push_item_width(-1)
        changed, item.name = imgui.input_text(f"##{id_suffix}_sysid", item.name, 256)
        imgui.pop_item_width()
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "用来让游戏识别该物品的内部名称，不向玩家展示。\n请确保ID尽可能独特，以免与其他Mod冲突！"
            )

        imgui.dummy(0, 4)

        # 使用两列布局
        col_width = imgui.get_content_region_available_width() / 2 - 8

        imgui.columns(2, f"basic_props_{id_suffix}", border=False)
        imgui.set_column_width(0, col_width)

        # 左列
        imgui.push_item_width(-1)
        imgui.text("槽位")
        new_slot = self._draw_enum_combo(
            f"##slot_{id_suffix}", item.slot, list(slot_labels.keys()), slot_labels
        )
        if new_slot != item.slot:
            item.slot = new_slot
            if not item.needs_char_texture():
                item.textures.clear_char()
            if not item.needs_left_texture():
                item.textures.clear_left()

        imgui.text("等级")
        item.tier = self._draw_enum_combo(
            f"##tier_{id_suffix}", item.tier, TIER, TIER_LABELS
        )

        imgui.text("材料")
        item.mat = self._draw_enum_combo(
            f"##mat_{id_suffix}",
            item.mat,
            list(material_labels.keys()),
            material_labels,
        )

        if isinstance(item, Armor):
            imgui.text("护甲类别")
            item.armor_class = self._draw_enum_combo(
                f"##class_{id_suffix}",
                item.armor_class,
                list(ARMOR_CLASS_LABELS.keys()),
                ARMOR_CLASS_LABELS,
            )
        imgui.pop_item_width()

        # 右列
        imgui.next_column()
        imgui.push_item_width(-1)

        imgui.text("标签")
        # 使用 item.name 作为唯一标识，避免武器/装备间的 combo 状态冲突
        new_tags = self._draw_enum_combo(
            f"##tags_{id_suffix}_{item.name}",
            item.tags,
            list(TAG_LABELS.keys()),
            TAG_LABELS,
        )
        if new_tags != item.tags:
            item.tags = new_tags
            item.rarity = (
                "Unique"
                if new_tags in ["unique", "special", "special exc"]
                else "Common"
            )

        imgui.text("稀有度")
        rarity_label = RARITY_LABELS.get(item.rarity, item.rarity)
        imgui.input_text(
            f"##rarity_{id_suffix}", rarity_label, 256, flags=imgui.INPUT_TEXT_READ_ONLY
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip("由标签自动决定")

        imgui.text("价格")
        changed, item.price = imgui.input_int(f"##price_{id_suffix}", item.price)

        imgui.text("最大耐久")
        changed, item.max_duration = imgui.input_int(
            f"##dur_{id_suffix}", item.max_duration
        )
        imgui.pop_item_width()

        imgui.columns(1)

        # 武器距离（仅武器，弓弩专用）
        if isinstance(item, Weapon):
            if item.slot in ["bow", "crossbow"]:
                imgui.push_item_width(120)
                imgui.text("攻击距离")
                changed, item.rng = imgui.input_int(f"##rng_{id_suffix}", item.rng)
                if changed:
                    item.rng = max(0, min(255, item.rng))
                imgui.pop_item_width()
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        "决定武器的基础攻击距离（游戏内部字段）\n类型: byte (0-255)"
                    )
            else:
                item.rng = 1

        self.draw_indented_separator()

        # 布尔属性 - 横向排列
        imgui.text("特殊属性")
        item.fireproof = self._draw_inline_checkbox(
            f"防火##{id_suffix}", item.fireproof, "未被拾取时是否会被火焰摧毁"
        )
        imgui.same_line(spacing=self.layout.gap_l)
        item.no_drop = self._draw_inline_checkbox(
            f"不可掉落##{id_suffix}", item.no_drop, "可能无法从宝箱中获取"
        )
        if isinstance(item, Armor):
            imgui.same_line(spacing=self.layout.gap_l)
            item.is_open = self._draw_inline_checkbox(
                f"开放式##{id_suffix}",
                item.is_open,
                "装备是否为开放式设计（如头盔的面甲）",
            )

    def _draw_inline_checkbox(self, label, value, tooltip=""):
        """绘制内联复选框"""
        changed, new_value = imgui.checkbox(label, value)
        if tooltip and imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)
        return new_value if changed else value

    def _draw_attributes_editor(self, item, attribute_groups, id_suffix):
        """绘制属性编辑器 - 使用两列布局优化对齐"""
        for group_name, attributes in attribute_groups.items():
            tree_id = f"{group_name}##{id_suffix}_attr"
            if imgui.tree_node(tree_id):
                # 使用两列布局：输入框 | 属性名，确保对齐
                imgui.columns(2, f"attr_cols_{tree_id}", border=False)
                input_col_width = 120 + (self.font_size - 14) * 6
                imgui.set_column_width(0, input_col_width)

                for attr in attributes:
                    desc_name, desc_detail = get_attr_display(attr)
                    if not desc_name:
                        desc_name = attr

                    val = item.attributes.get(attr, 0)

                    # 第一列：输入框
                    imgui.push_item_width(-1)
                    input_id = f"##{attr}_{id_suffix}"
                    changed, new_val = imgui.input_int(
                        input_id, val, step=1, step_fast=10
                    )
                    imgui.pop_item_width()

                    if attr in BYTE_ATTRIBUTES:
                        if new_val < 0:
                            new_val = 0
                            changed = True
                        elif new_val > 255:
                            new_val = 255
                            changed = True

                    if changed:
                        item.attributes[attr] = new_val

                    # 第二列：属性名称
                    imgui.next_column()
                    imgui.text(desc_name)

                    # tooltip 显示详细说明
                    tooltip_text = ""
                    if desc_detail:
                        tooltip_text = desc_detail
                    if attr in BYTE_ATTRIBUTES:
                        if tooltip_text:
                            tooltip_text += "\n"
                        tooltip_text += "类型: byte (0-255)"
                    tooltip(tooltip_text)

                    imgui.next_column()

                imgui.columns(1)
                imgui.tree_pop()

    def _draw_fragments_editor(self, armor):
        """绘制拆解材料编辑器"""
        imgui.text("设置装备拆解后可获得的材料")
        tooltip("拆解装备时可能获得的材料碎片数量")

        for frag_type in ARMOR_FRAGMENT_LABELS:
            frag_label = ARMOR_FRAGMENT_LABELS.get(frag_type, frag_type)
            val = armor.fragments.get(frag_type, 0)

            imgui.push_item_width(100)
            changed, new_val = imgui.input_int(
                f"##{frag_type}", val, step=1, step_fast=5
            )
            imgui.pop_item_width()

            if new_val < 0:
                new_val = 0
                changed = True
            elif new_val > 255:
                new_val = 255
                changed = True

            if changed:
                if new_val == 0:
                    armor.fragments.pop(frag_type, None)
                else:
                    armor.fragments[frag_type] = new_val

            imgui.same_line()
            imgui.text(frag_label)

    def _draw_localization_editor(self, item, id_suffix):
        """绘制本地化编辑器"""
        suffix = f"_{id_suffix}"

        # 语言添加器
        if imgui.button(f"添加语言##{id_suffix}"):
            imgui.open_popup(f"add_language_popup{suffix}")

        if imgui.begin_popup(f"add_language_popup{suffix}"):
            for lang in LANGUAGE_LABELS:
                if not item.localization.has_language(lang):
                    label = LANGUAGE_LABELS.get(lang, lang)
                    if imgui.selectable(label)[0]:
                        item.localization.languages[lang] = {
                            "name": "",
                            "description": "",
                        }
            imgui.end_popup()

        imgui.dummy(0, self.layout.gap_s)

        # 主语言
        primary_label = LANGUAGE_LABELS.get(PRIMARY_LANGUAGE, PRIMARY_LANGUAGE)
        self.text_secondary(f"{primary_label} (主语言)")

        if not item.localization.has_language(PRIMARY_LANGUAGE):
            item.localization.languages[PRIMARY_LANGUAGE] = {
                "name": "",
                "description": "",
            }

        primary_data = item.localization.languages[PRIMARY_LANGUAGE]

        self.text_secondary("名称")
        imgui.push_item_width(-1)
        changed, val = imgui.input_text(
            f"##{PRIMARY_LANGUAGE}_name{suffix}", primary_data["name"], 256
        )
        if changed:
            primary_data["name"] = val
        if not primary_data["name"] and imgui.is_item_hovered():
            imgui.set_tooltip("主语言名称（建议填写）")
        imgui.pop_item_width()

        self.text_secondary("描述")
        imgui.push_item_width(-1)
        # 描述框高度随字体缩放
        desc_height = 50 + (self.font_size - 14) * 3
        changed, val = imgui.input_text_multiline(
            f"##{PRIMARY_LANGUAGE}_desc{suffix}",
            primary_data["description"],
            1024,
            height=desc_height,
        )
        if changed:
            primary_data["description"] = val
        imgui.pop_item_width()
        imgui.dummy(0, self.layout.gap_m)

        # 其他语言
        langs_to_remove = []
        for lang in LANGUAGE_LABELS:
            if lang == PRIMARY_LANGUAGE:
                continue
            if not item.localization.has_language(lang):
                continue

            data = item.localization.languages[lang]

            imgui.separator()
            imgui.dummy(0, self.layout.gap_s)
            label = LANGUAGE_LABELS.get(lang, lang)
            self.text_secondary(f"{label}")
            imgui.same_line()
            if imgui.button(f"删除##{lang}{suffix}"):
                langs_to_remove.append(lang)

            self.text_secondary("名称")
            imgui.push_item_width(-1)
            changed, val = imgui.input_text(f"##{lang}_name{suffix}", data["name"], 256)
            if changed:
                data["name"] = val
            imgui.pop_item_width()

            self.text_secondary("描述")
            imgui.push_item_width(-1)
            # 描述框高度随字体缩放
            desc_height = 50 + (self.font_size - 14) * 3
            changed, val = imgui.input_text_multiline(
                f"##{lang}_desc{suffix}", data["description"], 1024, height=desc_height
            )
            if changed:
                data["description"] = val
            imgui.pop_item_width()
            imgui.dummy(0, self.layout.gap_s)

        for lang in langs_to_remove:
            del item.localization.languages[lang]

    # ==================== 贴图编辑器 ====================

    def _draw_textures_editor(self, item, id_suffix, slot_labels):
        """绘制贴图编辑器"""
        type_name = "武器" if id_suffix == "weapon" else "装备"

        self.text_secondary("注意: 所有贴图仅支持 PNG 格式")
        self.draw_indented_separator()

        # 预览设置 - 紧凑横向布局
        imgui.text("预览:")
        imgui.same_line()
        imgui.push_item_width(120)
        changed, self.texture_scale = imgui.input_float(
            f"##scale_{id_suffix}",
            self.texture_scale,
            step=0.5,
            step_fast=1.0,
            format="%.1fx",
        )
        imgui.pop_item_width()
        if changed:
            self.texture_scale = max(0.5, min(8.0, self.texture_scale))
            self.save_config()
        if imgui.is_item_hovered():
            imgui.set_tooltip("设置预览图的显示倍率 (默认 4.0)")

        self.draw_indented_separator()

        # 穿戴/手持状态贴图
        if item.needs_char_texture():
            # 判断是否为多姿势护甲（头/身/手/腿/背）
            is_multi_pose_armor = (
                isinstance(item, Armor) and item.needs_multi_pose_textures()
            )

            if is_multi_pose_armor:
                # 多姿势护甲 UI（内部自带人种选择）
                self._draw_multi_pose_armor_textures(item, id_suffix)
            else:
                # 武器/盾牌的手持贴图编辑器
                self._draw_weapon_char_textures(item, id_suffix, type_name)

            self.draw_indented_separator()
        else:
            slot_name = slot_labels.get(item.slot, item.slot)
            self.text_secondary(f"提示: {slot_name} 槽位不需要穿戴状态贴图")
            self.draw_indented_separator()

        # 常规贴图
        imgui.text("常规贴图（顺序越靠后耐久越低）")
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                f"排在后面的贴图代表更低耐久状态下的{type_name}\n注意：游戏内一格为 27 像素"
            )



        for idx in range(len(item.textures.inventory)):
            current_path = (
                item.textures.inventory[idx]
                if idx < len(item.textures.inventory)
                else ""
            )
            self._draw_single_texture_selector(
                f"常规贴图 {idx + 1}##{id_suffix}",
                current_path,
                ("inventory", idx),
                item,
                id_suffix,
            )

        if imgui.button(f"添加贴图槽##{id_suffix}"):
            item.textures.inventory.append("")
        if len(item.textures.inventory) > 1:
            imgui.same_line()
            if imgui.button(f"删除最后一个贴图槽##{id_suffix}"):
                item.textures.inventory.pop()

        self.draw_indented_separator()
        self._draw_texture_list_selector(
            f"战利品贴图*##{id_suffix}", item.textures.loot, "loot", item, id_suffix
        )

        # 战利品动画速度
        if item.textures.is_animated("loot"):
            self._draw_loot_animation_settings(item.textures, id_suffix)

    def _draw_weapon_char_textures(self, item, id_suffix: str, type_name: str):
        """绘制武器/盾牌的手持贴图编辑器

        将右手和左手贴图编辑整合到一起，模特选择放在标题行同时影响两者预览。
        """
        is_weapon = id_suffix == "weapon"
        has_left = item.needs_left_texture()

        # 标题行：标题 + 模特选择
        title = "手持状态贴图" if is_weapon else "穿戴状态贴图"
        imgui.text(title)
        imgui.same_line()
        imgui.text("  模特:")
        imgui.same_line()
        model_combo_width = 100 + (self.font_size - 14) * 4
        imgui.push_item_width(model_combo_width)
        current_model_label = CHARACTER_MODEL_LABELS.get(
            self.selected_model, self.selected_model
        )
        if imgui.begin_combo(f"##model_{id_suffix}", current_model_label):
            for model_key, model_label in CHARACTER_MODEL_LABELS.items():
                if imgui.selectable(model_label, model_key == self.selected_model)[0]:
                    self.selected_model = model_key
            imgui.end_combo()
        imgui.pop_item_width()

        imgui.dummy(0, 4)

        # === 右手/默认贴图 ===
        right_label = "右手/默认*" if has_left else "贴图*"
        self._draw_texture_list_selector(
            right_label, item.textures.character, "character", item, id_suffix
        )

        offset_label = "偏移 (右手)" if has_left else "偏移"
        item.textures.offset_x, item.textures.offset_y = self._draw_offset_inputs(
            offset_label,
            f"调整{type_name}相对于人物的相对位置",
            item.textures.offset_x,
            item.textures.offset_y,
            id_suffix,
        )

        # === 左手贴图 ===
        if has_left:
            self.draw_indented_separator()

            self._draw_texture_list_selector(
                "左手*",
                item.textures.character_left,
                "character_left",
                item,
                id_suffix,
            )

            item.textures.offset_x_left, item.textures.offset_y_left = (
                self._draw_offset_inputs(
                    "偏移 (左手)",
                    f"调整左手{type_name}相对于人物的相对位置",
                    item.textures.offset_x_left,
                    item.textures.offset_y_left,
                    f"{id_suffix}_left",
                )
            )

    def _draw_multi_pose_armor_textures(self, item: Armor, id_suffix: str):
        """绘制多姿势装备贴图编辑器（头/身/手/腿/背）- 支持男性/女性贴图

        游戏姿势系统：
        - 站立姿势0: 单手武器/盾牌/长杆时 → character[0] → s_char_{id}_0.png
        - 站立姿势1: 其他双手武器时 → character_standing1 → s_char_{id}_1.png (可选)
        - 休息姿势: 休息状态 → character_rest → s_char3_{id}.png (必须)

        女性版贴图：
        - 游戏会检查是否存在女性版贴图，若不存在则使用默认/男性版
        - 各姿势独立设置，可只为部分姿势提供女性版
        - 文件名加 _female 后缀（在帧序号前）
        """
        imgui.text("穿戴状态贴图")
        self.text_secondary("需要为站立和休息状态各准备贴图，女性版贴图可选")

        # 人种选择 + 性别标签页
        imgui.same_line()
        imgui.text("  模特:")
        imgui.same_line()
        imgui.push_item_width(80)
        current_race_label = CHARACTER_RACE_LABELS.get(
            self.selected_race, self.selected_race
        )
        if imgui.begin_combo(f"##race_{id_suffix}", current_race_label):
            for race in CHARACTER_RACES:
                label = CHARACTER_RACE_LABELS.get(race, race)
                if imgui.selectable(label, race == self.selected_race)[0]:
                    self.selected_race = race
            imgui.end_combo()
        imgui.pop_item_width()

        imgui.dummy(0, 4)

        # 性别 Tab 切换按钮（手动实现，避免 ImGui Tab 状态问题）
        if self.gender_tab_index == 0:
            imgui.push_style_color(imgui.COLOR_BUTTON, *self.theme_colors["accent"])
            imgui.button("默认/男性")
            imgui.pop_style_color()
        else:
            if imgui.button("默认/男性"):
                self.gender_tab_index = 0

        imgui.same_line()

        female_label = "女性 *" if item.textures.has_female() else "女性"
        if self.gender_tab_index == 1:
            imgui.push_style_color(imgui.COLOR_BUTTON, *self.theme_colors["accent"])
            imgui.button(female_label)
            imgui.pop_style_color()
        else:
            if imgui.button(female_label):
                self.gender_tab_index = 1

        imgui.dummy(0, 4)

        # 根据选择绘制对应内容
        if self.gender_tab_index == 0:
            self._draw_multi_pose_armor_textures_male(item, id_suffix)
        else:
            self._draw_multi_pose_armor_textures_female(item, id_suffix)

    def _draw_multi_pose_armor_textures_male(self, item: Armor, id_suffix: str):
        """绘制男性/默认版多姿势贴图编辑器"""
        available_width = imgui.get_content_region_available_width()
        use_horizontal = available_width > 550
        pose_width = (
            (available_width - 24) / 3 if use_horizontal else available_width - 8
        )
        scale = self.texture_scale
        preview_h = ARMOR_PREVIEW_HEIGHT * scale
        child_height = 24 + 28 + preview_h + 44 + 20

        # 获取男性模特
        model_key = get_model_key(self.selected_race, False)

        # === 站立姿势0 (必须) ===
        imgui.begin_child(
            f"pose_s0_m_{id_suffix}",
            width=pose_width,
            height=child_height,
            border=True,
        )
        standing0_path = item.textures.character[0] if item.textures.character else ""

        imgui.text("站立0")
        imgui.same_line()
        self.text_error("*")
        imgui.same_line()
        if imgui.small_button(f"选择##s0_m_{id_suffix}"):
            path = self.file_dialog([("PNG文件", "*.png")])
            if path:
                imported = self._import_texture(path)
                if item.textures.character:
                    item.textures.character[0] = imported
                else:
                    item.textures.character.append(imported)
        if imgui.is_item_hovered():
            imgui.set_tooltip("选择贴图 (必填 - 单手武器/盾牌/长杆时的站立姿势)")
        if standing0_path:
            imgui.same_line()
            if imgui.small_button(f"清除##s0c_m_{id_suffix}"):
                item.textures.character.clear()
                item.textures.offset_x = 0
                item.textures.offset_y = 0
            if imgui.is_item_hovered():
                imgui.set_tooltip("清除贴图")

        item.textures.offset_x, item.textures.offset_y = (
            self._draw_full_width_offset_inputs(
                item.textures.offset_x,
                item.textures.offset_y,
                f"{id_suffix}_off0_m",
                disabled=not standing0_path,
            )
        )

        self._draw_armor_pose_preview_centered(
            item, standing0_path, 0, id_suffix, pose_width, model_key=model_key
        )
        imgui.end_child()

        if use_horizontal:
            imgui.same_line()

        # === 站立姿势1 (可选) ===
        imgui.begin_child(
            f"pose_s1_m_{id_suffix}",
            width=pose_width,
            height=child_height,
            border=True,
        )
        standing1_path = item.textures.character_standing1

        imgui.text("站立1")
        imgui.same_line()
        self.text_secondary("可选")
        imgui.same_line()
        if imgui.small_button(f"选择##s1_m_{id_suffix}"):
            path = self.file_dialog([("PNG文件", "*.png")])
            if path:
                item.textures.character_standing1 = self._import_texture(path)
        if imgui.is_item_hovered():
            imgui.set_tooltip("选择贴图 (可选 - 其他双手武器时的站立姿势)")
        if standing1_path:
            imgui.same_line()
            if imgui.small_button(f"清除##s1c_m_{id_suffix}"):
                item.textures.character_standing1 = ""
                item.textures.offset_x_standing1 = 0
                item.textures.offset_y_standing1 = 0
                # 同时清除女性版站立姿势1
                item.textures.clear_female_standing1()
            if imgui.is_item_hovered():
                imgui.set_tooltip("清除贴图（同时清除女性版站立姿势1）")

        item.textures.offset_x_standing1, item.textures.offset_y_standing1 = (
            self._draw_full_width_offset_inputs(
                item.textures.offset_x_standing1,
                item.textures.offset_y_standing1,
                f"{id_suffix}_off1_m",
                disabled=not standing1_path,
            )
        )

        preview_path = standing1_path if standing1_path else standing0_path
        fallback_hint = (
            "(复用站立姿势0)" if not standing1_path and standing0_path else ""
        )
        self._draw_armor_pose_preview_centered(
            item,
            preview_path,
            1,
            id_suffix,
            pose_width,
            fallback_hint=fallback_hint,
            model_key=model_key,
        )
        imgui.end_child()

        if use_horizontal:
            imgui.same_line()

        # === 休息姿势 (必须) ===
        imgui.begin_child(
            f"pose_sr_m_{id_suffix}",
            width=pose_width,
            height=child_height,
            border=True,
        )
        rest_path = item.textures.character_rest

        imgui.text("休息")
        imgui.same_line()
        self.text_error("*")
        imgui.same_line()
        if imgui.small_button(f"选择##sr_m_{id_suffix}"):
            path = self.file_dialog([("PNG文件", "*.png")])
            if path:
                item.textures.character_rest = self._import_texture(path)
        if imgui.is_item_hovered():
            imgui.set_tooltip("选择贴图 (必填 - 休息状态时的姿势)")
        if rest_path:
            imgui.same_line()
            if imgui.small_button(f"清除##src_m_{id_suffix}"):
                item.textures.character_rest = ""
                item.textures.offset_x_rest = 0
                item.textures.offset_y_rest = 0
            if imgui.is_item_hovered():
                imgui.set_tooltip("清除贴图")

        item.textures.offset_x_rest, item.textures.offset_y_rest = (
            self._draw_full_width_offset_inputs(
                item.textures.offset_x_rest,
                item.textures.offset_y_rest,
                f"{id_suffix}_off2_m",
                disabled=not rest_path,
            )
        )

        self._draw_armor_pose_preview_centered(
            item, rest_path, 2, id_suffix, pose_width, model_key=model_key
        )
        imgui.end_child()

    def _draw_multi_pose_armor_textures_female(self, item: Armor, id_suffix: str):
        """绘制女性版多姿势贴图编辑器"""
        self.text_secondary("女性版贴图可选，未设置时游戏将使用默认/男性版贴图")
        imgui.dummy(0, 4)

        available_width = imgui.get_content_region_available_width()
        use_horizontal = available_width > 550
        pose_width = (
            (available_width - 24) / 3 if use_horizontal else available_width - 8
        )
        scale = self.texture_scale
        preview_h = ARMOR_PREVIEW_HEIGHT * scale
        child_height = 24 + 28 + preview_h + 44 + 20

        # 获取女性模特
        model_key = get_model_key(self.selected_race, True)

        # 获取男性版贴图路径（用于 fallback 预览）
        male_standing0 = item.textures.character[0] if item.textures.character else ""
        male_standing1 = item.textures.character_standing1
        male_rest = item.textures.character_rest

        # === 女性站立姿势0 (可选) ===
        imgui.begin_child(
            f"pose_s0_f_{id_suffix}",
            width=pose_width,
            height=child_height,
            border=True,
        )
        female_standing0 = item.textures.character_female

        imgui.text("站立0")
        imgui.same_line()
        self.text_secondary("可选")
        imgui.same_line()
        if imgui.small_button(f"选择##s0_f_{id_suffix}"):
            path = self.file_dialog([("PNG文件", "*.png")])
            if path:
                item.textures.character_female = self._import_texture(path)
        if imgui.is_item_hovered():
            imgui.set_tooltip("选择女性版贴图 (可选)")
        if female_standing0:
            imgui.same_line()
            if imgui.small_button(f"清除##s0c_f_{id_suffix}"):
                item.textures.clear_female_standing0()
                # 同时清除女性版站立姿势1（因为姿势1依赖姿势0）
                item.textures.clear_female_standing1()
            if imgui.is_item_hovered():
                imgui.set_tooltip("清除贴图（同时清除女性版站立姿势1）")

        item.textures.offset_x_female, item.textures.offset_y_female = (
            self._draw_full_width_offset_inputs(
                item.textures.offset_x_female,
                item.textures.offset_y_female,
                f"{id_suffix}_off0_f",
                disabled=not female_standing0,
            )
        )

        # 预览：优先女性版，否则显示男性版
        preview_path = female_standing0 if female_standing0 else male_standing0
        fallback_hint = (
            "(使用默认/男性版)" if not female_standing0 and male_standing0 else ""
        )
        self._draw_armor_pose_preview_centered(
            item,
            preview_path,
            0,
            id_suffix + "_f",
            pose_width,
            fallback_hint=fallback_hint,
            model_key=model_key,
            use_female_offset=bool(female_standing0),
        )
        imgui.end_child()

        if use_horizontal:
            imgui.same_line()

        # === 女性站立姿势1 (仅当男性版姿势1已设置且女性版姿势0已设置时可用) ===
        imgui.begin_child(
            f"pose_s1_f_{id_suffix}",
            width=pose_width,
            height=child_height,
            border=True,
        )
        female_standing1 = item.textures.character_standing1_female
        # 需要同时满足：男性版姿势1已设置 且 女性版姿势0已设置
        can_set_female_standing1 = bool(male_standing1) and bool(female_standing0)

        imgui.text("站立1")
        imgui.same_line()
        if can_set_female_standing1:
            self.text_secondary("可选")
        else:
            self.text_secondary("禁用")
        imgui.same_line()

        if not can_set_female_standing1:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if imgui.small_button(f"选择##s1_f_{id_suffix}") and can_set_female_standing1:
            path = self.file_dialog([("PNG文件", "*.png")])
            if path:
                item.textures.character_standing1_female = self._import_texture(path)
        if not can_set_female_standing1:
            imgui.pop_style_var()
        if imgui.is_item_hovered():
            if can_set_female_standing1:
                imgui.set_tooltip("选择女性版贴图 (可选)")
            elif not male_standing1:
                imgui.set_tooltip("需要先设置默认/男性版站立姿势1贴图")
            else:
                imgui.set_tooltip("需要先设置女性版站立姿势0贴图")

        if female_standing1:
            imgui.same_line()
            if imgui.small_button(f"清除##s1c_f_{id_suffix}"):
                item.textures.clear_female_standing1()
            if imgui.is_item_hovered():
                imgui.set_tooltip("清除贴图")

        (
            item.textures.offset_x_standing1_female,
            item.textures.offset_y_standing1_female,
        ) = self._draw_full_width_offset_inputs(
            item.textures.offset_x_standing1_female,
            item.textures.offset_y_standing1_female,
            f"{id_suffix}_off1_f",
            disabled=not female_standing1,
        )

        # 预览逻辑及提示（基于游戏实际 fallback 顺序）：
        # - 女性姿势1设置了 → 显示女性姿势1
        # - 女性姿势1未设置，女性姿势0设置了 → 显示女性姿势0（游戏优先复用女性0）
        # - 女性姿势0也未设置，男性姿势1设置了 → 显示男性姿势1
        # - 都未设置 → 显示男性姿势0
        if female_standing1:
            preview_path = female_standing1
            fallback_hint = ""
            use_female_offset = True
        elif female_standing0:
            preview_path = female_standing0
            fallback_hint = "(复用女性版站立0)"
            use_female_offset = True
        elif male_standing1:
            preview_path = male_standing1
            fallback_hint = "(使用默认/男性版站立1)"
            use_female_offset = False
        else:
            preview_path = male_standing0
            fallback_hint = "(使用默认/男性版站立0)" if male_standing0 else ""
            use_female_offset = False

        self._draw_armor_pose_preview_centered(
            item,
            preview_path,
            1,
            id_suffix + "_f",
            pose_width,
            fallback_hint=fallback_hint,
            model_key=model_key,
            use_female_offset=use_female_offset,
        )
        imgui.end_child()

        if use_horizontal:
            imgui.same_line()

        # === 女性休息姿势 (可选) ===
        imgui.begin_child(
            f"pose_sr_f_{id_suffix}",
            width=pose_width,
            height=child_height,
            border=True,
        )
        female_rest = item.textures.character_rest_female

        imgui.text("休息")
        imgui.same_line()
        self.text_secondary("可选")
        imgui.same_line()
        if imgui.small_button(f"选择##sr_f_{id_suffix}"):
            path = self.file_dialog([("PNG文件", "*.png")])
            if path:
                item.textures.character_rest_female = self._import_texture(path)
        if imgui.is_item_hovered():
            imgui.set_tooltip("选择女性版贴图 (可选)")
        if female_rest:
            imgui.same_line()
            if imgui.small_button(f"清除##src_f_{id_suffix}"):
                item.textures.clear_female_rest()
            if imgui.is_item_hovered():
                imgui.set_tooltip("清除贴图")

        item.textures.offset_x_rest_female, item.textures.offset_y_rest_female = (
            self._draw_full_width_offset_inputs(
                item.textures.offset_x_rest_female,
                item.textures.offset_y_rest_female,
                f"{id_suffix}_off2_f",
                disabled=not female_rest,
            )
        )

        # 预览：优先女性版，否则显示男性版
        preview_path = female_rest if female_rest else male_rest
        fallback_hint = "(使用默认/男性版)" if not female_rest and male_rest else ""
        self._draw_armor_pose_preview_centered(
            item,
            preview_path,
            2,
            id_suffix + "_f",
            pose_width,
            fallback_hint=fallback_hint,
            model_key=model_key,
            use_female_offset=bool(female_rest),
        )
        imgui.end_child()

    def _draw_full_width_offset_inputs(
        self, off_x: int, off_y: int, id_suffix: str, disabled: bool = False
    ) -> tuple:
        """绘制填满一行的偏移输入控件"""
        available_width = imgui.get_content_region_available_width()

        # 布局: [-][X输入框][+]  [-][Y输入框][+]
        # 两组控件平分宽度
        group_width = (available_width - 8) / 2  # 8px 间距
        btn_w = 20
        input_w = group_width - btn_w * 2 - 16  # 减去按钮和标签宽度

        new_x, new_y = off_x, off_y

        # 禁用时降低透明度
        if disabled:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)

        imgui.push_button_repeat(True)

        # X 偏移组
        if imgui.button(f"-##xm_{id_suffix}", width=btn_w) and not disabled:
            new_x = off_x - 1
        imgui.same_line(spacing=self.layout.gap_xs)
        imgui.text("X")
        imgui.same_line(spacing=self.layout.gap_xs)
        imgui.push_item_width(input_w)
        if disabled:
            imgui.input_int(
                f"##offx_{id_suffix}",
                off_x,
                step=0,
                step_fast=0,
                flags=imgui.INPUT_TEXT_READ_ONLY,
            )
        else:
            changed_x, val_x = imgui.input_int(
                f"##offx_{id_suffix}", off_x, step=0, step_fast=0
            )
            if changed_x:
                new_x = val_x
        imgui.pop_item_width()
        imgui.same_line(spacing=self.layout.gap_xs)
        if imgui.button(f"+##xp_{id_suffix}", width=btn_w) and not disabled:
            new_x = off_x + 1

        imgui.same_line(spacing=self.layout.gap_s)

        # Y 偏移组
        if imgui.button(f"-##ym_{id_suffix}", width=btn_w) and not disabled:
            new_y = off_y - 1
        imgui.same_line(spacing=self.layout.gap_xs)
        imgui.text("Y")
        imgui.same_line(spacing=self.layout.gap_xs)
        imgui.push_item_width(input_w)
        if disabled:
            imgui.input_int(
                f"##offy_{id_suffix}",
                off_y,
                step=0,
                step_fast=0,
                flags=imgui.INPUT_TEXT_READ_ONLY,
            )
        else:
            changed_y, val_y = imgui.input_int(
                f"##offy_{id_suffix}", off_y, step=0, step_fast=0
            )
            if changed_y:
                new_y = val_y
        imgui.pop_item_width()
        imgui.same_line(spacing=self.layout.gap_xs)
        if imgui.button(f"+##yp_{id_suffix}", width=btn_w) and not disabled:
            new_y = off_y + 1

        imgui.pop_button_repeat()

        if disabled:
            imgui.pop_style_var()

        return (new_x, new_y)

    def _draw_armor_pose_preview_centered(
        self,
        item: Armor,
        texture_path: str,
        pose_index: int,
        id_suffix: str,
        container_width: float,
        fallback_hint: str = "",
        model_key: str = None,
        use_female_offset: bool = False,
    ):
        """绘制护甲姿势预览（在容器内居中）

        Args:
            item: 护甲物品
            texture_path: 贴图路径
            pose_index: 姿势索引 (0, 1, 2)
            id_suffix: ID后缀
            container_width: 容器宽度
            fallback_hint: 回退提示文字，空字符串表示无回退
            model_key: 角色模型键名（如 "Human Male"），None则使用默认
            use_female_offset: 是否使用女性版偏移
        """
        scale = self.texture_scale
        preview_w = ARMOR_PREVIEW_WIDTH * scale

        # 使用传入的容器宽度和样式计算内容区域宽度
        style = imgui.get_style()
        # 子窗口有边框时，边框占用 1px，内容区域 = 容器宽度 - 2*padding - 2*border
        content_width = container_width - style.window_padding.x * 2 - 2
        center_offset = max(0, (content_width - preview_w) / 2)

        # 直接设置光标 X 位置
        imgui.set_cursor_pos_x(style.window_padding.x + center_offset)

        # 调用原有预览绘制逻辑
        self._draw_armor_pose_preview(
            item,
            texture_path,
            pose_index,
            id_suffix,
            fallback_hint=fallback_hint,
            model_key=model_key,
            use_female_offset=use_female_offset,
        )

    # 偏移控件尺寸常量
    OFFSET_BTN_W = 24  # 微调按钮宽度
    OFFSET_INPUT_W = 42  # 输入框宽度
    OFFSET_SPACING = 2  # 元素间距
    OFFSET_GAP = 6  # X/Y 组之间间距

    @classmethod
    def _calc_offset_controls_width(cls) -> float:
        """计算偏移控件组的总宽度"""
        # 布局: [-] X [input] [+]  [-] Y [input] [+]
        # 每组: btn + spacing + label(~8) + spacing + input + spacing + btn
        single_group = (
            cls.OFFSET_BTN_W * 2 + cls.OFFSET_INPUT_W + cls.OFFSET_SPACING * 3 + 8
        )
        return single_group * 2 + cls.OFFSET_GAP

    def _draw_compact_offset_inputs(
        self, off_x: int, off_y: int, id_suffix: str
    ) -> tuple:
        """绘制紧凑的偏移输入控件（带微调按钮，支持按住连续调整）"""
        # 布局: [-] X [input] [+]  [-] Y [input] [+]
        btn_w = self.OFFSET_BTN_W
        input_w = self.OFFSET_INPUT_W
        sp = self.OFFSET_SPACING

        new_x, new_y = off_x, off_y

        # X 偏移
        imgui.push_button_repeat(True)  # 启用按住重复触发
        if imgui.button(f"-##xm_{id_suffix}", width=btn_w):
            new_x = off_x - 1
        imgui.same_line(spacing=sp)
        imgui.text("X")
        imgui.same_line(spacing=sp)
        imgui.push_item_width(input_w)
        changed_x, val_x = imgui.input_int(
            f"##offx_{id_suffix}", off_x, step=0, step_fast=0
        )
        if changed_x:
            new_x = val_x
        imgui.pop_item_width()
        imgui.same_line(spacing=sp)
        if imgui.button(f"+##xp_{id_suffix}", width=btn_w):
            new_x = off_x + 1

        # Y 偏移
        imgui.same_line(spacing=self.OFFSET_GAP)
        if imgui.button(f"-##ym_{id_suffix}", width=btn_w):
            new_y = off_y - 1
        imgui.same_line(spacing=sp)
        imgui.text("Y")
        imgui.same_line(spacing=sp)
        imgui.push_item_width(input_w)
        changed_y, val_y = imgui.input_int(
            f"##offy_{id_suffix}", off_y, step=0, step_fast=0
        )
        if changed_y:
            new_y = val_y
        imgui.pop_item_width()
        imgui.same_line(spacing=sp)
        if imgui.button(f"+##yp_{id_suffix}", width=btn_w):
            new_y = off_y + 1
        imgui.pop_button_repeat()  # 恢复默认行为

        return (new_x, new_y)

    def _draw_armor_pose_preview(
        self,
        item: Armor,
        texture_path: str,
        pose_index: int,
        id_suffix: str,
        fallback_hint: str = "",
        model_key: str = None,
        use_female_offset: bool = False,
    ):
        """绘制护甲姿势预览

        Args:
            item: 护甲物品
            texture_path: 贴图路径
            pose_index: 姿势索引 (0, 1, 2)
            id_suffix: ID后缀
            fallback_hint: 回退提示文字，空字符串表示无回退
            model_key: 角色模型键名（如 "Human Male"），None则使用 self.selected_model
            use_female_offset: 是否使用女性版偏移
        """
        scale = self.texture_scale
        preview_w = ARMOR_PREVIEW_WIDTH * scale
        preview_h = ARMOR_PREVIEW_HEIGHT * scale

        draw_list = imgui.get_window_draw_list()
        start_pos = imgui.get_cursor_screen_pos()

        # 获取裁剪矩形
        clip_rect = draw_list.get_clip_rect_min(), draw_list.get_clip_rect_max()
        clip_min_x, clip_min_y = clip_rect[0]
        clip_max_x, clip_max_y = clip_rect[1]

        # 计算预览区域与窗口裁剪区域的交集
        preview_clip_min_x = max(start_pos[0], clip_min_x)
        preview_clip_min_y = max(start_pos[1], clip_min_y)
        preview_clip_max_x = min(start_pos[0] + preview_w, clip_max_x)
        preview_clip_max_y = min(start_pos[1] + preview_h, clip_max_y)

        # 只有当裁剪区域有效时才绘制
        if (
            preview_clip_min_x < preview_clip_max_x
            and preview_clip_min_y < preview_clip_max_y
        ):
            draw_list.push_clip_rect(
                preview_clip_min_x,
                preview_clip_min_y,
                preview_clip_max_x,
                preview_clip_max_y,
            )

            # 绘制棋盘格背景
            self.draw_checkerboard(
                draw_list,
                start_pos,
                (start_pos[0] + preview_w, start_pos[1] + preview_h),
                cell_size=int(8 * scale),
            )

            # 绘制模特参考图
            actual_model_key = model_key if model_key else self.selected_model
            model_files = CHARACTER_MODELS.get(
                actual_model_key,
                ["s_human_male_0.png", "s_human_male_1.png", "s_human_male_2.png"],
            )
            if pose_index < len(model_files):
                ref_path = os.path.join("resources", model_files[pose_index])
                if not os.path.exists(ref_path):
                    ref_path = model_files[pose_index]

                ref_preview = self.get_texture_preview(ref_path)
                if ref_preview:
                    draw_list.add_image(
                        ref_preview["tex_id"],
                        (float(start_pos[0]), float(start_pos[1])),
                        (
                            float(start_pos[0] + ref_preview["width"] * scale),
                            float(start_pos[1] + ref_preview["height"] * scale),
                        ),
                    )

            # 绘制护甲贴图（应用各姿势独立的偏移）
            if texture_path:
                preview = self.get_texture_preview(texture_path)
                if preview:
                    # 根据姿势索引和是否使用女性偏移选择对应的偏移值
                    if use_female_offset:
                        # 女性版偏移
                        if pose_index == 0:
                            off_x = item.textures.offset_x_female
                            off_y = item.textures.offset_y_female
                        elif pose_index == 1:
                            off_x = item.textures.offset_x_standing1_female
                            off_y = item.textures.offset_y_standing1_female
                        else:  # pose_index == 2
                            off_x = item.textures.offset_x_rest_female
                            off_y = item.textures.offset_y_rest_female
                    else:
                        # 男性版/默认偏移
                        if pose_index == 0 or bool(fallback_hint):
                            off_x = item.textures.offset_x
                            off_y = item.textures.offset_y
                        elif pose_index == 1:
                            off_x = item.textures.offset_x_standing1
                            off_y = item.textures.offset_y_standing1
                        else:  # pose_index == 2
                            off_x = item.textures.offset_x_rest
                            off_y = item.textures.offset_y_rest

                    # 计算绘制位置（偏移向负方向移动贴图）
                    armor_x = start_pos[0] - off_x * scale
                    armor_y = start_pos[1] - off_y * scale

                    draw_list.add_image(
                        preview["tex_id"],
                        (float(armor_x), float(armor_y)),
                        (
                            float(armor_x + preview["width"] * scale),
                            float(armor_y + preview["height"] * scale),
                        ),
                    )

            draw_list.pop_clip_rect()

        # 占位
        imgui.dummy(preview_w, preview_h)

        # 状态提示 - 居中显示
        hint_text = ""
        is_warning = False
        if fallback_hint:
            hint_text = fallback_hint
            is_warning = True
        elif not texture_path:
            hint_text = "(未设置)"

        if hint_text:
            hint_size = imgui.calc_text_size(hint_text)
            # 计算居中偏移
            available_w = imgui.get_content_region_available_width()
            center_offset = max(0, (available_w - hint_size.x) / 2)
            if center_offset > 0:
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + center_offset)
            if is_warning:
                self.text_warning(hint_text)
            else:
                self.text_secondary(hint_text)

    def _draw_texture_list_selector(
        self, label, texture_list: list, field_name: str, item, id_suffix
    ):
        """绘制贴图列表选择器（支持动画）

        texture_list: 直接引用 item.textures.xxx 列表
        field_name: 字段名，如 "character", "character_left", "loot"
        """
        # 提取显示文本（去掉 ## 及其后的 ID 部分）
        display_label = label.split("##")[0] if "##" in label else label
        imgui.text(display_label)
        imgui.same_line()

        label_suffix = f"_{id_suffix}_{field_name}"
        state_key = f"{id_suffix}_{field_name}"
        is_animated = len(texture_list) > 1

        if is_animated:
            # 动画模式
            imgui.text(f"动画模式 (共 {len(texture_list)} 帧)")
            if imgui.is_item_hovered():
                # 战利品贴图速度可变，其他使用预览默认速度
                if field_name == "loot" and item:
                    if item.textures.loot_use_relative_speed:
                        actual_fps = GAME_FPS * item.textures.loot_fps
                    else:
                        actual_fps = item.textures.loot_fps
                    fps_hint = f"预览播放速度: {actual_fps:.1f} fps (可在下方调整)"
                else:
                    fps_hint = f"预览播放速度: {PREVIEW_ANIMATION_FPS} fps"
                imgui.set_tooltip(f"当前动画包含 {len(texture_list)} 帧\n{fps_hint}")

            if imgui.button(f"添加帧##{label_suffix}"):
                paths = self.file_dialog([("PNG文件", "*.png")], multiple=True)
                if paths:
                    for path in paths if isinstance(paths, list) else [paths]:
                        texture_list.append(self._import_texture(path))

            imgui.same_line()
            if imgui.button(f"清空##{label_suffix}"):
                texture_list.clear()

            # 播放控制
            state = self.preview_states.get(
                state_key, {"paused": False, "current_frame": 0}
            )
            imgui.same_line()
            if imgui.checkbox(f"暂停##{label_suffix}", state["paused"])[0]:
                state["paused"] = not state["paused"]

            if state["paused"] and texture_list:
                max_frame = len(texture_list) - 1
                state["current_frame"] = min(state["current_frame"], max_frame)

                imgui.same_line()
                if imgui.arrow_button(f"##prev_{label_suffix}", imgui.DIRECTION_LEFT):
                    state["current_frame"] = (state["current_frame"] - 1) % (
                        max_frame + 1
                    )

                imgui.same_line()
                imgui.push_item_width(100)
                _, new_frame = imgui.slider_int(
                    f"##frame_{label_suffix}",
                    state["current_frame"] + 1,
                    1,
                    max_frame + 1,
                    format="%d",
                )
                state["current_frame"] = new_frame - 1
                imgui.pop_item_width()

                imgui.same_line()
                if imgui.arrow_button(f"##next_{label_suffix}", imgui.DIRECTION_RIGHT):
                    state["current_frame"] = (state["current_frame"] + 1) % (
                        max_frame + 1
                    )

                imgui.same_line()
                imgui.text(f"帧: {state['current_frame'] + 1}/{max_frame + 1}")

            self.preview_states[state_key] = state

            # 帧列表管理
            if imgui.tree_node(f"帧列表##{label_suffix}"):
                self._draw_frame_list_manager(texture_list, label_suffix)
                imgui.tree_pop()

        else:
            # 静态模式（0或1帧）
            if imgui.button(f"选择文件##{label_suffix}"):
                paths = self.file_dialog([("PNG文件", "*.png")], multiple=True)
                if paths:
                    paths = paths if isinstance(paths, list) else [paths]
                    texture_list.clear()
                    for path in paths:
                        texture_list.append(self._import_texture(path))

            imgui.same_line()
            current_path = texture_list[0] if texture_list else ""
            imgui.text(os.path.basename(current_path) if current_path else "未选择")
            if current_path and imgui.is_item_hovered():
                imgui.set_tooltip(current_path)

            if texture_list:
                imgui.same_line()
                if imgui.button(f"添加更多帧##{label_suffix}"):
                    paths = self.file_dialog([("PNG文件", "*.png")], multiple=True)
                    if paths:
                        for path in paths if isinstance(paths, list) else [paths]:
                            texture_list.append(self._import_texture(path))

        # 预览
        self._draw_animated_texture_preview(
            texture_list, field_name, item, state_key, id_suffix
        )

    def _draw_single_texture_selector(
        self, label, current_path, field_identifier, item, id_suffix
    ):
        """绘制单个贴图选择器（用于 inventory 等不支持动画的字段）"""
        # 提取显示文本（去掉 ## 及其后的 ID 部分）
        display_label = label.split("##")[0] if "##" in label else label
        imgui.text(display_label)
        imgui.same_line()

        label_suffix = (
            f"_{id_suffix}_{field_identifier[0]}_{field_identifier[1]}"
            if isinstance(field_identifier, tuple)
            else f"_{id_suffix}_{field_identifier}"
        )

        if imgui.button(f"选择文件##{label_suffix}"):
            path = self.file_dialog([("PNG文件", "*.png")], multiple=False)
            if path:
                final_path = self._import_texture(path)
                self._apply_texture_selection(final_path, field_identifier, item)

        imgui.same_line()
        display_path = os.path.basename(current_path) if current_path else "未选择"
        imgui.text(display_path)
        if current_path and imgui.is_item_hovered():
            imgui.set_tooltip(current_path)

        # 预览
        preview = self.get_texture_preview(current_path)
        if preview:
            imgui.same_line()
            self.text_secondary(f"({preview['width']}x{preview['height']})")
            imgui.new_line()
            self._draw_texture_preview(preview, field_identifier, item, None)

    def _draw_frame_list_manager(self, frames: list, label_suffix: str):
        """绘制帧列表管理界面"""
        to_remove = []
        for i, frame_path in enumerate(frames):
            imgui.push_id(f"frame_{label_suffix}_{i}")
            imgui.text(f"帧 {i+1}: {os.path.basename(frame_path)}")

            imgui.same_line()
            if imgui.arrow_button("##up", imgui.DIRECTION_UP) and i > 0:
                frames[i], frames[i - 1] = frames[i - 1], frames[i]

            imgui.same_line()
            if (
                imgui.arrow_button("##down", imgui.DIRECTION_DOWN)
                and i < len(frames) - 1
            ):
                frames[i], frames[i + 1] = frames[i + 1], frames[i]

            imgui.same_line()
            if imgui.small_button("X"):
                to_remove.append(i)

            imgui.pop_id()

        for i in reversed(to_remove):
            frames.pop(i)

    def _draw_animated_texture_preview(
        self, texture_list: list, field_name: str, item, state_key: str, id_suffix: str
    ):
        """绘制动画贴图预览"""
        if not texture_list:
            return

        # 计算当前帧
        fps = PREVIEW_ANIMATION_FPS
        if field_name == "loot" and item:
            fps = (
                GAME_FPS * item.textures.loot_fps
                if item.textures.loot_use_relative_speed
                else item.textures.loot_fps
            )

        state = self.preview_states.get(
            state_key, {"paused": False, "current_frame": 0}
        )
        if state.get("paused") and len(texture_list) > 1:
            frame_idx = min(state["current_frame"], len(texture_list) - 1)
        else:
            frame_idx = int(time.time() * fps) % len(texture_list)

        preview_path = texture_list[frame_idx]

        # 计算动画最大尺寸
        override_size = None
        if len(texture_list) > 1:
            max_w, max_h = 0, 0
            for f_path in texture_list:
                p = self.get_texture_preview(f_path)
                if p:
                    max_w = max(max_w, p["width"])
                    max_h = max(max_h, p["height"])
            if max_w > 0 and max_h > 0:
                override_size = (max_w, max_h)

        preview = self.get_texture_preview(preview_path)
        if preview:
            imgui.same_line()
            dims = override_size or (preview["width"], preview["height"])
            self.text_secondary(f"({dims[0]}x{dims[1]})")
            imgui.new_line()
            self._draw_texture_preview(preview, field_name, item, override_size)

    def _draw_offset_inputs(self, label, tooltip_text, offset_x, offset_y, id_suffix):
        """绘制偏移输入"""
        imgui.text(label)
        tooltip(tooltip_text)

        imgui.push_item_width(150)
        changed_x, new_offset_x = imgui.input_int(f"水平偏移##{id_suffix}", offset_x)
        tooltip("默认 0。正数使人物看起来向右。")

        imgui.same_line()
        imgui.dummy(10, 0)
        imgui.same_line()

        changed_y, new_offset_y = imgui.input_int(f"垂直偏移##{id_suffix}", offset_y)
        tooltip("默认 0。正数使人物看起来向下。")
        imgui.pop_item_width()

        return new_offset_x, new_offset_y

    def _draw_loot_animation_settings(self, textures, id_suffix):
        """绘制战利品动画设置"""
        imgui.text("战利品动画速度设置")
        tooltip("设置战利品贴图的动画播放速度。\n此设置会影响生成的模组代码。")

        mode_labels = ["固定帧率 (FPS)", "相对帧率"]
        current_mode = 1 if textures.loot_use_relative_speed else 0
        if imgui.begin_combo(
            f"速度模式##{id_suffix}_loot_speed_mode", mode_labels[current_mode]
        ):
            if imgui.selectable("固定帧率 (FPS)", not textures.loot_use_relative_speed)[
                0
            ]:
                if textures.loot_use_relative_speed:
                    textures.loot_use_relative_speed = False
                    textures.loot_fps = 10.0
            if imgui.selectable("相对帧率", textures.loot_use_relative_speed)[0]:
                if not textures.loot_use_relative_speed:
                    textures.loot_use_relative_speed = True
                    textures.loot_fps = 0.25
            imgui.end_combo()

        if not textures.loot_use_relative_speed:
            imgui.push_item_width(150)
            changed, textures.loot_fps = imgui.input_float(
                f"播放帧率 (FPS)##{id_suffix}_loot_fps",
                textures.loot_fps,
                step=1.0,
                step_fast=5.0,
                format="%.1f",
            )
            if changed and textures.loot_fps < 0.1:
                textures.loot_fps = 0.1
            imgui.pop_item_width()
            tooltip("每秒播放的帧数。\n这是一个固定值，不会随游戏速度变化。\n默认值: 10")
        else:
            imgui.push_item_width(180)
            changed, textures.loot_fps = imgui.input_float(
                f"相对帧率##{id_suffix}_loot_relative_fps",
                textures.loot_fps,
                step=0.01,
                step_fast=0.1,
                format="%.3f",
            )
            if changed:
                if textures.loot_fps < 0.001:
                    textures.loot_fps = 0.001
                textures.loot_fps = round(textures.loot_fps, 3)
            imgui.pop_item_width()
            tooltip(
                f"每个游戏帧内动画前进的帧数。\n\n"
                f"例如:\n  • 值为 0.1 时: 实际播放速度 = {GAME_FPS} × 0.1 = 4 fps\n"
                f"  • 值为 0.25 时: 实际播放速度 = {GAME_FPS} × 0.25 = 10 fps\n"
                f"  • 值为 0.5 时: 实际播放速度 = {GAME_FPS} × 0.5 = 20 fps\n"
                f"  • 值为 1.0 时: 实际播放速度 = {GAME_FPS} × 1.0 = 40 fps\n\n"
                f"提示: 手持贴图默认相对帧率为 0.25 (即 {GAME_FPS // 4} fps)。\n最小值: 0.001"
            )

            actual_fps = GAME_FPS * textures.loot_fps
            self.text_secondary(
                f"实际播放速度: {actual_fps:.3f} fps (游戏 {GAME_FPS} fps 时)"
            )

    def _import_texture(self, source_path):
        """导入贴图"""
        if self.project.file_path:
            rel_path = self.project.import_texture(source_path)
            return os.path.join(os.path.dirname(self.project.file_path), rel_path)
        return source_path

    def _apply_texture_selection(self, file_path, field_identifier, item):
        """应用贴图选择"""
        if not file_path or not os.path.exists(file_path):
            return False

        if item is None:
            return False

        field = field_identifier
        if isinstance(field, tuple):
            field_type, idx = field
            if (
                field_type == "inventory"
                and idx is not None
                and 0 <= idx < len(item.textures.inventory)
            ):
                item.textures.inventory[idx] = file_path
                return True
        else:
            if field == "character":
                item.textures.character = file_path
                return True
            if field == "character_left":
                item.textures.character_left = file_path
                return True
            if field == "loot":
                item.textures.loot = file_path
                return True
        return False

    # ==================== 贴图预览 ====================

    def _draw_texture_preview(self, preview, field_identifier, item, override_size):
        """绘制贴图预览"""
        scale = self.texture_scale
        tex_w = preview["width"]
        tex_h = preview["height"]

        box_w = tex_w
        box_h = tex_h
        if override_size:
            box_w, box_h = override_size

        is_handheld = False
        if isinstance(field_identifier, str) and field_identifier in [
            "character",
            "character_left",
        ]:
            is_handheld = True

        draw_list = imgui.get_window_draw_list()
        start_pos = imgui.get_cursor_screen_pos()

        # 获取当前 draw list 的裁剪矩形，这会正确反映窗口层级的裁剪
        clip_rect = draw_list.get_clip_rect_min(), draw_list.get_clip_rect_max()
        clip_min_x, clip_min_y = clip_rect[0]
        clip_max_x, clip_max_y = clip_rect[1]

        if is_handheld:
            target_item = item

            pose_index = 0
            if hasattr(target_item, "slot"):
                # Hybrid 武器用 weapon_type 判断姿势，普通武器用 slot
                if hasattr(target_item, "init_weapon_stats") and target_item.init_weapon_stats:
                    slot = target_item.weapon_type
                else:
                    slot = target_item.slot
                # 单手武器、长杆武器、弓、盾牌使用姿势0
                use_single_hand_pose = slot in [
                    "dagger",
                    "mace",
                    "sword",
                    "axe",
                    "spear",
                    "bow",
                    "shield",  # 盾牌也使用姿势0
                ]
                pose_index = 0 if use_single_hand_pose else 1


            model_files = CHARACTER_MODELS.get(
                self.selected_model, ["s_elf_male_0.png", "s_elf_male_1.png"]
            )
            if pose_index >= len(model_files):
                pose_index = 0

            ref_img_name = model_files[pose_index]
            ref_path = os.path.join("resources", ref_img_name)
            if not os.path.exists(ref_path):
                ref_path = ref_img_name

            ref_preview = self.get_texture_preview(ref_path)

            if ref_preview:
                off_x = target_item.textures.offset_x
                off_y = target_item.textures.offset_y
                is_shield_mainhand = (
                    field_identifier == "character"
                    and getattr(target_item, "slot", None) == "shield"
                )

                if field_identifier == "character_left":
                    off_x = target_item.textures.offset_x_left
                    off_y = target_item.textures.offset_y_left

                viewport_w = VALID_AREA_SIZE * scale
                viewport_h = VALID_AREA_SIZE * scale

                # 计算预览区域与窗口裁剪区域的交集
                preview_clip_min_x = max(start_pos[0], clip_min_x)
                preview_clip_min_y = max(start_pos[1], clip_min_y)
                preview_clip_max_x = min(start_pos[0] + viewport_w, clip_max_x)
                preview_clip_max_y = min(start_pos[1] + viewport_h, clip_max_y)

                # 只有当裁剪区域有效时才绘制
                if (
                    preview_clip_min_x < preview_clip_max_x
                    and preview_clip_min_y < preview_clip_max_y
                ):
                    draw_list.push_clip_rect(
                        preview_clip_min_x,
                        preview_clip_min_y,
                        preview_clip_max_x,
                        preview_clip_max_y,
                    )

                    self.draw_checkerboard(
                        draw_list,
                        start_pos,
                        (start_pos[0] + viewport_w, start_pos[1] + viewport_h),
                        cell_size=int(8 * scale),
                    )

                    char_draw_x = start_pos[0] + VIEWPORT_CHAR_OFFSET_X * scale
                    char_draw_y = start_pos[1] + VIEWPORT_CHAR_OFFSET_Y * scale

                    wep_rel_x = -off_x
                    wep_rel_y = -off_y

                    wep_draw_x = char_draw_x + wep_rel_x * scale
                    wep_draw_y = char_draw_y + wep_rel_y * scale

                    # 盾牌主手特例：先绘制盾牌，再绘制角色，实现盾牌在角色图下方
                    if is_shield_mainhand:
                        draw_list.add_image(
                            preview["tex_id"],
                            (float(wep_draw_x), float(wep_draw_y)),
                            (
                                float(wep_draw_x + tex_w * scale),
                                float(wep_draw_y + tex_h * scale),
                            ),
                        )
                        draw_list.add_image(
                            ref_preview["tex_id"],
                            (float(char_draw_x), float(char_draw_y)),
                            (
                                float(char_draw_x + ref_preview["width"] * scale),
                                float(char_draw_y + ref_preview["height"] * scale),
                            ),
                        )
                    else:
                        draw_list.add_image(
                            ref_preview["tex_id"],
                            (float(char_draw_x), float(char_draw_y)),
                            (
                                float(char_draw_x + ref_preview["width"] * scale),
                                float(char_draw_y + ref_preview["height"] * scale),
                            ),
                        )
                        draw_list.add_image(
                            preview["tex_id"],
                            (float(wep_draw_x), float(wep_draw_y)),
                            (
                                float(wep_draw_x + tex_w * scale),
                                float(wep_draw_y + tex_h * scale),
                            ),
                        )

                    draw_list.add_rect(
                        wep_draw_x,
                        wep_draw_y,
                        wep_draw_x + tex_w * scale,
                        wep_draw_y + tex_h * scale,
                        imgui.get_color_u32_rgba(0.0, 1.0, 1.0, 0.8),
                        thickness=2.0,
                    )

                    draw_list.pop_clip_rect()

                imgui.dummy(viewport_w, viewport_h)

                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        "视图已锁定为 64x64 游戏有效区域。\n超出此区域的贴图部分将不会显示。\n青色框指示武器贴图的完整范围。"
                    )

                return

        # 默认绘制逻辑
        width = tex_w * scale
        height = tex_h * scale
        bg_width = box_w * scale
        bg_height = box_h * scale

        # 计算预览区域与窗口裁剪区域的交集
        preview_clip_min_x = max(start_pos[0], clip_min_x)
        preview_clip_min_y = max(start_pos[1], clip_min_y)
        preview_clip_max_x = min(start_pos[0] + bg_width, clip_max_x)
        preview_clip_max_y = min(start_pos[1] + bg_height, clip_max_y)

        # 只有当裁剪区域有效时才绘制
        if (
            preview_clip_min_x < preview_clip_max_x
            and preview_clip_min_y < preview_clip_max_y
        ):
            draw_list.push_clip_rect(
                preview_clip_min_x,
                preview_clip_min_y,
                preview_clip_max_x,
                preview_clip_max_y,
            )

            self.draw_checkerboard(
                draw_list,
                start_pos,
                (start_pos[0] + bg_width, start_pos[1] + bg_height),
                cell_size=int(8 * scale),
            )

            draw_list.add_image(
                preview["tex_id"],
                (float(start_pos[0]), float(start_pos[1])),
                (float(start_pos[0] + width), float(start_pos[1] + height)),
            )

            draw_list.pop_clip_rect()

        imgui.dummy(bg_width, bg_height)

    def draw_checkerboard(self, draw_list, p_min, p_max, cell_size=24):
        """绘制棋盘格背景"""
        x0, y0 = p_min
        x1, y1 = p_max

        col_bg = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1.0)
        draw_list.add_rect_filled(x0, y0, x1, y1, col_bg)

        col_fg = imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1.0)

        y = y0
        row = 0
        while y < y1:
            x = x0 + (cell_size if row % 2 != 0 else 0)
            row_next_y = min(y + cell_size, y1)

            while x < x1:
                next_x = min(x + cell_size, x1)
                draw_list.add_rect_filled(x, y, next_x, row_next_y, col_fg)
                x += cell_size * 2

            y = row_next_y
            row += 1

    def get_texture_preview(self, path):
        """获取贴图预览"""
        if not path or not os.path.exists(path) or Image is None:
            return None
        mtime = os.path.getmtime(path)
        cached = self.texture_preview_cache.get(path)
        if cached and cached["mtime"] == mtime:
            return cached

        if cached:
            glDeleteTextures(int(cached["tex_id"]))

        try:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                width, height = img.size
                image_data = img.tobytes()
        except Exception as exc:
            print(f"无法加载贴图预览 {path}: {exc}")
            return None

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            image_data,
        )

        preview = {"tex_id": tex_id, "width": width, "height": height, "mtime": mtime}
        self.texture_preview_cache[path] = preview
        return preview

    def clear_texture_previews(self):
        """清理所有贴图预览"""
        for preview in self.texture_preview_cache.values():
            glDeleteTextures(int(preview["tex_id"]))
        self.texture_preview_cache.clear()

    # ==================== 辅助UI方法 ====================

    def _draw_enum_combo(self, label, current_value, options, labels, tooltip=""):
        """通用枚举下拉框"""
        current_label = str(labels.get(current_value, current_value))
        new_value = current_value

        if current_value not in options:
            options = list(options) + [current_value]

        if imgui.begin_combo(label, current_label):
            for opt in options:
                display = labels.get(opt, opt)
                if imgui.selectable(display, opt == current_value)[0]:
                    new_value = opt
            imgui.end_combo()

        if tooltip and imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)

        return new_value

    def _draw_mode_combo(self, label, current_enum, enum_class, labels: dict,
                         options=None, tooltip=""):
        """Enum 类型的下拉框

        Args:
            label: imgui 标签
            current_enum: 当前 Enum 值
            enum_class: Enum 类型
            labels: {Enum成员: 显示文本} 映射
            options: 可选的选项列表（Enum成员），默认为所有成员
            tooltip: 提示文本
        Returns:
            选中的 Enum 值
        """
        if options is None:
            options = list(enum_class)

        current_label = labels.get(current_enum, str(current_enum.value))
        new_value = current_enum

        if imgui.begin_combo(label, current_label):
            for opt in options:
                display = labels.get(opt, str(opt.value))
                if imgui.selectable(display, opt == current_enum)[0]:
                    new_value = opt
            imgui.end_combo()

        if tooltip and imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)

        return new_value

    def _draw_validation_errors(self, errors):
        """显示验证错误 - 增强视觉对比"""
        if not errors:
            return
        self.draw_indented_separator()
        imgui.text("消息:")

        for error in errors:
            if error.endswith("):"):
                # 物品标题行，跳过
                continue
            content = error.lstrip()

            # 区分警告和错误，使用图标增强辨识度
            if content.startswith("• WARNING:"):
                # 警告：黄色 + 警告图标
                imgui.text("  ")
                imgui.same_line()
                self.text_warning("!")
                imgui.same_line()
                self.text_warning(content[10:].strip())  # 去掉 "• WARNING:" 前缀
            elif content.startswith("•"):
                # 错误：红色 + 错误图标
                imgui.text("  ")
                imgui.same_line()
                self.text_error("X")
                imgui.same_line()
                self.text_error(content[1:].strip())  # 去掉 "•" 前缀
            else:
                # 其他错误
                imgui.text("  ")
                imgui.same_line()
                self.text_error("X")
                imgui.same_line()
                self.text_error(error)

    def draw_indented_separator(self):
        """绘制缩进分隔线"""
        style = imgui.get_style()
        spacing = style.item_spacing.y
        imgui.dummy(0, spacing * 0.3)
        cursor_x, cursor_y = imgui.get_cursor_screen_pos()
        max_x = cursor_x + imgui.get_content_region_available_width()
        color = style.colors[imgui.COLOR_SEPARATOR]
        draw_list = imgui.get_window_draw_list()
        draw_list.add_line(
            cursor_x, cursor_y, max_x, cursor_y, imgui.get_color_u32_rgba(*color)
        )
        imgui.dummy(0, spacing * 0.3)

    # ==================== 文件对话框 ====================

    def file_dialog(self, file_types=None, multiple=False):
        """文件对话框"""
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            ftypes = file_types if file_types else [("All files", "*.*")]

            if multiple:
                file_paths = filedialog.askopenfilenames(filetypes=ftypes)
                return list(file_paths) if file_paths else []
            else:
                file_path = filedialog.askopenfilename(filetypes=ftypes)
                return file_path
        except Exception as e:
            print(f"文件对话框错误: {e}")
            return [] if multiple else ""
        finally:
            if root:
                root.destroy()

    def select_directory_dialog(self):
        """选择目录对话框"""
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            return filedialog.askdirectory()
        except Exception as e:
            print(f"目录选择错误: {e}")
            return ""
        finally:
            if root:
                root.destroy()

    # ==================== 项目操作 ====================

    def new_project_dialog(self):
        """新建项目"""
        directory = self.select_directory_dialog()
        if directory:
            project_file = os.path.join(directory, "project.json")
            assets_dir = os.path.join(directory, "assets")

            self.project = ModProject()
            self.project.file_path = project_file
            self.current_weapon_index = -1
            self.current_armor_index = -1
            self.error_message = ""

            try:
                os.makedirs(assets_dir, exist_ok=True)
                self.project.save()
            except Exception as e:
                self._show_error(f"创建项目失败: {e}")

    def open_project_dialog(self):
        """打开项目"""
        directory = self.select_directory_dialog()
        if directory:
            file_path = os.path.join(directory, "project.json")
            if os.path.exists(file_path):
                if self.project.load(file_path):
                    self.current_weapon_index = -1
                else:
                    self._show_error("无法加载项目文件，文件可能已损坏")
            else:
                self._show_error(f"在 {directory} 中未找到 project.json")

    def save_project_dialog(self):
        """保存项目"""
        if self.project.file_path:
            self.project.save()

    def draw_import_dialog(self):
        """绘制导入对话框"""
        imgui.open_popup("导入项目")
        if imgui.begin_popup_modal("导入项目")[0]:
            imgui.text("选择要导入的项目文件:")
            changed, self.import_file_path = imgui.input_text(
                "文件路径", self.import_file_path, 512
            )

            if imgui.button("浏览"):
                self.import_file_path = self.file_dialog()

            imgui.same_line()

            if imgui.button("确定"):
                if os.path.exists(self.import_file_path):
                    success, message, conflicts = self.project.import_project(
                        self.import_file_path
                    )
                    if success:
                        if conflicts:
                            self.import_conflicts = conflicts
                            imgui.open_popup("导入冲突")
                        else:
                            self.show_import_dialog = False
                    else:
                        imgui.open_popup("导入错误")
                else:
                    imgui.open_popup("文件不存在")

            imgui.same_line()

            if imgui.button("取消"):
                self.show_import_dialog = False

            if imgui.begin_popup_modal("导入冲突")[0]:
                imgui.text("以下武器名称冲突，已自动重命名:")
                for conflict in self.import_conflicts:
                    imgui.text(f"  • {conflict}")
                if imgui.button("确定"):
                    imgui.close_current_popup()
                    self.import_conflicts = []
                    self.show_import_dialog = False
                imgui.end_popup()

            if imgui.begin_popup_modal("导入错误")[0]:
                imgui.text("导入失败!")
                if imgui.button("确定"):
                    imgui.close_current_popup()
                imgui.end_popup()

            imgui.end_popup()

    # ==================== 模组生成 ====================

    def generate_mod(self):
        """生成模组"""
        print("开始生成模组...")

        project_errors = self.project.validate()
        if project_errors:
            self._show_error(
                "项目验证失败:\n" + "\n".join(f"  • {e}" for e in project_errors)
            )
            return

        item_errors = []
        for item in self.project.weapons + self.project.armors:
            item_errors.extend(validate_item(item, self.project))

        # 验证混合物品
        for hybrid in self.project.hybrid_items:
            item_errors.extend(validate_hybrid_item(hybrid, self.project))

        if item_errors:
            self._show_error("物品验证失败:\n" + "\n".join(item_errors))
            return

        if not self.project.file_path:
            self.show_save_popup = True
            return

        self._execute_generation()

    def _execute_generation(self):
        """执行生成"""
        try:
            mod_name = self.project.code_name.strip() or "ModProject"
            base_dir = os.path.dirname(self.project.file_path)
            mod_dir = Path(base_dir) / mod_name
            sprites_dir = mod_dir / "Sprites"

            print(f"创建目录: {mod_dir}")
            mod_dir.mkdir(exist_ok=True)
            sprites_dir.mkdir(exist_ok=True)

            print("生成 C# 代码...")
            generator = CodeGenerator(self.project)
            files = generator.generate()
            for filename, content in files.items():
                with open(mod_dir / filename, "w", encoding="utf-8") as f:
                    f.write(content)

            print("生成空的 .csproj 文件...")
            with open(mod_dir / f"{mod_name}.csproj", "w", encoding="utf-8"):
                pass

            # 如果有混合物品，生成 Codes 文件夹和 GML 脚本
            if self.project.hybrid_items:
                codes_dir = mod_dir / "Codes"
                codes_dir.mkdir(exist_ok=True)
                print("生成 hover 辅助脚本...")

                # 生成 scr_hoversEnsureExtendedOrderLists.gml
                with open(codes_dir / "scr_hoversEnsureExtendedOrderLists.gml", "w", encoding="utf-8") as f:
                    f.write(generator._generate_ensure_extended_order_lists_gml())

                # 生成 scr_hoversDrawHybridConsumAttributes.gml
                with open(codes_dir / "scr_hoversDrawHybridConsumAttributes.gml", "w", encoding="utf-8") as f:
                    f.write(generator._generate_draw_hybrid_consum_attrs_gml())

            print("复制贴图文件...")
            texture_errors = []
            for item in self.project.weapons + self.project.armors:
                # 判断是否为多姿势护甲
                is_multi_pose = (
                    isinstance(item, Armor) and item.needs_multi_pose_textures()
                )
                errs = copy_item_textures(
                    item_id=item.id,
                    textures=item.textures,
                    sprites_dir=sprites_dir,
                    copy_char=item.needs_char_texture(),
                    copy_left=item.needs_left_texture(),
                    is_multi_pose_armor=is_multi_pose,
                )
                texture_errors.extend(errs)

            # 复制混合物品贴图
            for hybrid in self.project.hybrid_items:
                errs = copy_item_textures(
                    item_id=hybrid.id,
                    textures=hybrid.textures,
                    sprites_dir=sprites_dir,
                    copy_char=hybrid.needs_char_texture(),
                    copy_left=hybrid.needs_left_texture(),
                    is_multi_pose_armor=hybrid.needs_multi_pose_textures(),
                )
                texture_errors.extend(errs)

            if texture_errors:
                # 有警告/错误但仍然生成了，显示给用户
                for err in texture_errors:
                    print(err)

            print("生成成功！")
            self.show_success_popup = True
        except Exception as e:
            self._show_error(f"生成模组失败:\n{e}")


if __name__ == "__main__":
    app = ModGeneratorGUI()
    app.run()
