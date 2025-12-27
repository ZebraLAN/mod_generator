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
    BYTE_ATTRIBUTES,
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
    HYBRID_ARMOR_MATERIALS,
    HYBRID_ARMOR_CLASSES,
    HYBRID_SKILL_IDS,
    HYBRID_SKILL_OBJECTS,
    HYBRID_PICKUP_SOUNDS,
    HYBRID_DROP_SOUNDS,
    HYBRID_DURABILITY_POLICIES,
    HYBRID_WEIGHT_LABELS,
    # 消耗品属性常量
    CONSUMABLE_FLOAT_ATTRIBUTES,
    CONSUMABLE_DURATION_ATTRIBUTE,
    CONSUMABLE_INSTANT_GROUP_PREFIX,
    # 混合物品槽位属性
    get_hybrid_attrs_for_slot,
    get_consumable_duration_attrs,
    CONSUMABLE_INSTANT_ATTRS,
)
from generator import CodeGenerator, copy_item_textures
from models import (
    Armor,
    HybridItem,
    ModProject,
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

        # 加载配置并应用
        self.load_config()
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
        """应用颜色主题 - 基于 Design for Non-Designers 四原则优化"""
        style = imgui.get_style()

        # === 间距与布局 (亲密性 Proximity) ===
        style.window_padding = (12, 12)
        style.frame_padding = (8, 4)
        style.item_spacing = (8, 6)
        style.item_inner_spacing = (6, 4)
        style.indent_spacing = 20
        style.scrollbar_size = 14
        style.grab_min_size = 12

        # === 圆角 (重复 Repetition - 统一的视觉语言) ===
        style.window_rounding = 6
        style.frame_rounding = 4
        style.popup_rounding = 4
        style.scrollbar_rounding = 6
        style.grab_rounding = 3
        style.tab_rounding = 4

        # === 边框 ===
        style.window_border_size = 1
        style.frame_border_size = 0
        style.popup_border_size = 1

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
        if imgui.is_item_hovered():
            imgui.set_tooltip("用于展示的名称，可包含中文等字符")

        imgui.text("模组代号")
        changed, self.project.code_name = imgui.input_text(
            "##code_name", self.project.code_name, 256
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip("仅用于内部生成代码，必须是以字母开头的字母/数字组合")

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
        if self.project.file_path and imgui.is_item_hovered():
            imgui.set_tooltip(project_dir)

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

        # 左侧: 列表
        imgui.begin_child(
            f"{panel_id}ListPanel",
            width=list_width,
            height=available_height,
            border=True,
        )
        draw_list_func()
        imgui.end_child()

        imgui.same_line(spacing=spacing)

        # 右侧: 编辑器
        imgui.begin_child(
            f"{panel_id}EditorPanel",
            width=editor_width,
            height=available_height,
            border=True,
        )
        current_index = getattr(self, current_index_attr)
        if 0 <= current_index < len(items):
            draw_editor_func()
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
            new_item.name = self._generate_unique_name(items, default_id_base)
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

            # 显示系统ID和槽位后缀
            if imgui.is_item_hovered():
                imgui.set_tooltip(f"系统ID: {item.name}\nID: {item.id}{suffix}")

    def _generate_unique_name(self, items, base_name):
        """生成唯一的默认名称"""
        existing = {item.name for item in items if item.name}
        if base_name not in existing:
            return base_name

        idx = 1
        while True:
            candidate = f"{base_name}_{idx}"
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
        """绘制混合物品编辑器"""
        hybrid = self.project.hybrid_items[self.current_hybrid_index]

        if imgui.tree_node("基本属性##hybrid", flags=imgui.TREE_NODE_FRAMED | imgui.TREE_NODE_DEFAULT_OPEN):
            self._draw_hybrid_basic_properties(hybrid)
            imgui.tree_pop()

        if imgui.tree_node("功能设置##hybrid", flags=imgui.TREE_NODE_FRAMED):
            self._draw_hybrid_feature_settings(hybrid)
            imgui.tree_pop()

        if hybrid.init_weapon_stats:
            if imgui.tree_node("武器设置##hybrid", flags=imgui.TREE_NODE_FRAMED):
                self._draw_hybrid_weapon_settings(hybrid)
                imgui.tree_pop()

        if hybrid.init_armor_stats:
            if imgui.tree_node("护甲设置##hybrid", flags=imgui.TREE_NODE_FRAMED):
                self._draw_hybrid_armor_settings(hybrid)
                imgui.tree_pop()

        # 属性加成：仅在有被动效果或纯消耗品时显示
        # 武器/护甲的属性在武器设置/护甲设置中配置
        if self._should_show_hybrid_attributes(hybrid):
            if imgui.tree_node("属性加成##hybrid", flags=imgui.TREE_NODE_FRAMED):
                self._draw_hybrid_attributes_editor(hybrid)
                imgui.tree_pop()

        # 消耗品属性编辑器（仅在消耗品主动效果模式下显示）
        if hybrid.active_effect_mode == "consumable":
            self._draw_hybrid_consumable_attributes_editor(hybrid)

        if imgui.tree_node("名称与本地化##hybrid", flags=imgui.TREE_NODE_FRAMED):
            self._draw_localization_editor(hybrid, "hybrid")
            imgui.tree_pop()

        if imgui.tree_node("贴图文件##hybrid", flags=imgui.TREE_NODE_FRAMED):
            self._draw_hybrid_textures_editor(hybrid)
            imgui.tree_pop()

        # 移除自定义代码板块 - 让用户编写代码有悖于设计原则

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

    def _draw_hybrid_basic_properties(self, hybrid: HybridItem):
        """绘制混合物品基本属性"""
        # 系统ID
        imgui.text("混合物品系统ID")
        imgui.same_line()
        self.text_secondary(f"(生成ID: {hybrid.id})")
        imgui.push_item_width(-1)
        changed, hybrid.name = imgui.input_text("##hybrid_sysid", hybrid.name, 256)
        imgui.pop_item_width()
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "用来让游戏识别该物品的内部名称，不向玩家展示。\n请确保ID尽可能独特，以免与其他Mod冲突！"
            )

        imgui.dummy(0, 4)

        # 固定父类为 o_inv_consum（不向用户显示）
        hybrid.parent_object = "o_inv_consum"
        
        # 固定标签为 "special exc"（不向用户显示）
        hybrid.tags = "special exc"

        # 两列布局
        col_width = imgui.get_content_region_available_width() / 2 - 8
        imgui.columns(2, "hybrid_basic_cols", border=False)
        imgui.set_column_width(0, col_width)

        # 左列
        imgui.push_item_width(-1)

        imgui.text("品质")
        old_quality = hybrid.quality
        hybrid.quality = self._draw_enum_combo(
            "##quality_hybrid",
            hybrid.quality,
            list(HYBRID_QUALITY_LABELS.keys()),
            HYBRID_QUALITY_LABELS,
        )
        # 品质变化时自动更新稀有度
        if hybrid.quality != old_quality:
            self._update_hybrid_rarity_from_quality(hybrid)

        imgui.text("基础价格")
        changed, hybrid.base_price = imgui.input_int("##price_hybrid", hybrid.base_price)
        if changed:
            hybrid.base_price = max(0, hybrid.base_price)

        imgui.pop_item_width()

        # 右列
        imgui.next_column()
        imgui.push_item_width(-1)

        imgui.text("等级")
        changed, hybrid.tier = imgui.input_int("##tier_hybrid", hybrid.tier)
        if changed:
            hybrid.tier = max(1, min(7, hybrid.tier))
        if imgui.is_item_hovered():
            imgui.set_tooltip("物品等级 (1-7)，用于商人筛选和悬浮提示显示")

        # Weight 选择（仅非护甲类型需要手动设置，护甲由 armor_class 自动推断）
        if not hybrid.init_armor_stats:
            imgui.text("重量")
            hybrid.weight = self._draw_enum_combo(
                "##weight_hybrid",
                hybrid.weight,
                list(HYBRID_WEIGHT_LABELS.keys()),
                HYBRID_WEIGHT_LABELS,
            )
            if imgui.is_item_hovered():
                imgui.set_tooltip("物品重量分类，影响游泳等行为")

        imgui.pop_item_width()
        imgui.columns(1)

        # 装备设置由物品类型自动推断（在功能设置中处理）

    def _update_hybrid_rarity_from_quality(self, hybrid: HybridItem):
        """根据品质自动更新稀有度"""
        # 普通(1) -> 空, 独特(6) -> "Unique", 文物(7) -> 空
        if hybrid.quality == 6:
            hybrid.rarity = "Unique"
        else:
            hybrid.rarity = ""

    def _draw_hybrid_feature_settings(self, hybrid: HybridItem):
        """绘制混合物品功能设置"""
        # 物品类型选择（单选）
        imgui.text("物品类型")
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "选择物品的类型，决定属性编辑器显示哪些字段：\n"
                "• 无：纯消耗品，不显示属性编辑器\n"
                "• 武器类：显示武器相关属性（伤害、状态几率等）\n"
                "• 护甲饰品类：显示护甲相关属性（防护、抗性等）\n"
                "• 被动类：显示被动属性（放在背包即可生效）"
            )
        
        # 计算当前选中的类型索引
        # 0=无, 1=武器, 2=护甲, 3=被动
        if hybrid.init_weapon_stats:
            current_type = 1
        elif hybrid.init_armor_stats:
            current_type = 2
        elif hybrid.has_passive:
            current_type = 3
        else:
            current_type = 0
        
        type_labels = ["无 (纯消耗品)", "武器类", "护甲饰品类", "被动类"]
        
        # 使用 radio_button 实现单选
        EQUIPMENT_MODES = ["none", "weapon", "armor", "passive"]
        for i, label in enumerate(type_labels):
            if i > 0:
                imgui.same_line(spacing=15)
            if imgui.radio_button(f"{label}##hybrid_type", current_type == i):
                # 更新装备模式
                hybrid.equipment_mode = EQUIPMENT_MODES[i]
                
                # 自动推断装备设置
                if i == 1:  # 武器类
                    hybrid.equipable = True
                    hybrid.slot = "hand"
                    # 手数由武器类型决定，在武器设置中处理
                elif i == 2:  # 护甲饰品类
                    hybrid.equipable = True
                    # 槽位由护甲类型决定
                    if hybrid.armor_type == "shield":
                        hybrid.slot = "hand"
                    else:
                        hybrid.slot = hybrid.armor_type
                else:  # 纯消耗品(i==0) 或 被动类(i==3)
                    # equipable 现在是计算属性，无需手动设置
                    hybrid.slot = "heal"
        
        # is_weapon/mark_as_weapon 现在是计算属性，无需手动设置

        self.draw_indented_separator()

        # ====== 主动效果模式 ======
        imgui.text("主动效果模式")
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "选择物品使用时触发的效果模式：\n"
                "• 无：不触发任何效果\n"
                "• 消耗品使用效果：应用消耗品属性中设置的效果\n"
                "• 技能释放：释放指定技能（支持目标选择）"
            )
        
        # 主动效果模式选择
        mode_labels = ["无", "消耗品使用效果", "技能释放"]
        mode_keys = ["none", "consumable", "skill"]
        
        # 获取当前模式索引
        current_mode_idx = 0
        if hybrid.active_effect_mode in mode_keys:
            current_mode_idx = mode_keys.index(hybrid.active_effect_mode)
        
        # 使用 radio_button 实现单选
        for i, label in enumerate(mode_labels):
            if i > 0:
                imgui.same_line(spacing=15)
            if imgui.radio_button(f"{label}##active_effect_mode", current_mode_idx == i):
                new_mode = mode_keys[i]
                old_mode = hybrid.active_effect_mode
                hybrid.active_effect_mode = new_mode
                
                # 切换模式时清除不相关的数据
                if new_mode == "none":
                    # 切换到"无"时，清空所有主动效果数据
                    hybrid.skill_object = ""
                    hybrid.consumable_attributes.clear()
                elif new_mode == "consumable":
                    # 切换到"消耗品"时，清空技能
                    hybrid.skill_object = ""
                elif new_mode == "skill":
                    # 切换到"技能"时，清空消耗品属性
                    hybrid.consumable_attributes.clear()
        
        # 技能选择（仅在技能释放模式下显示）
        if hybrid.active_effect_mode == "skill":
            imgui.text("技能:")
            imgui.same_line()
            imgui.push_item_width(400)
            
            # 显示当前选中的技能名称
            current_skill = hybrid.skill_object
            if current_skill in SKILL_OBJECT_NAMES:
                current_label = f"{SKILL_OBJECT_NAMES[current_skill]} ({current_skill})"
            elif current_skill:
                current_label = f"自定义: {current_skill}"
            else:
                current_label = "-- 选择技能 --"
            
            if imgui.begin_combo("##skill_object", current_label):
                # 无技能选项
                if imgui.selectable("-- 无 --", current_skill == "")[0]:
                    hybrid.skill_object = ""
                
                imgui.separator()
                
                # 按分支分组显示技能
                for branch in sorted(SKILL_BY_BRANCH.keys()):
                    branch_label = SKILL_BRANCH_TRANSLATIONS.get(branch, branch)
                    skills = SKILL_BY_BRANCH[branch]
                    
                    # 跳过空分支和特殊分支
                    if not skills or branch in ("none", "unknown"):
                        continue
                    
                    if imgui.tree_node(f"{branch_label}##branch_{branch}"):
                        for skill_obj in skills:
                            skill_info = SKILL_OBJECTS.get(skill_obj, {})
                            skill_name = skill_info.get("name_chinese", skill_obj)
                            is_selected = current_skill == skill_obj
                            
                            if imgui.selectable(f"{skill_name}##{skill_obj}", is_selected)[0]:
                                hybrid.skill_object = skill_obj
                            
                            if imgui.is_item_hovered():
                                # 显示技能详情
                                tip = f"对象名: {skill_obj}\n"
                                tip += f"英文名: {skill_info.get('name_english', 'N/A')}\n"
                                tip += f"类型: {skill_info.get('class', 'N/A')}\n"
                                tip += f"目标: {skill_info.get('target', 'N/A')}"
                                imgui.set_tooltip(tip)
                        
                        imgui.tree_pop()
                
                # 特殊分支（敌人技能等）
                special_branches = ["none", "unknown"]
                has_special = any(SKILL_BY_BRANCH.get(b) for b in special_branches)
                if has_special:
                    imgui.separator()
                    if imgui.tree_node("其他/特殊技能##branch_special"):
                        for branch in special_branches:
                            skills = SKILL_BY_BRANCH.get(branch, [])
                            for skill_obj in skills:
                                skill_info = SKILL_OBJECTS.get(skill_obj, {})
                                skill_name = skill_info.get("name_chinese", skill_obj)
                                is_selected = current_skill == skill_obj
                                
                                if imgui.selectable(f"{skill_name}##{skill_obj}", is_selected)[0]:
                                    hybrid.skill_object = skill_obj
                        imgui.tree_pop()
                
                imgui.end_combo()
            
            imgui.pop_item_width()
            
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    "选择物品使用时释放的技能\n"
                    "技能将以独立 CD 方式释放，不影响玩家已学技能的冷却"
                )
        
        # ====== 原技能设置（已注释，保留用于兼容旧项目）======
        # imgui.text("技能设置")
        #
        # if hybrid.has_charges:
        #     changed, hybrid.has_active_skill = imgui.checkbox("拥有主动技能##hybrid", hybrid.has_active_skill)
        #     if imgui.is_item_hovered():
        #         imgui.set_tooltip("物品是否拥有可触发的主动技能")
        #
        #     if hybrid.has_active_skill:
        #         imgui.same_line(spacing=20)
        #         imgui.text("技能ID:")
        #         imgui.same_line()
        #         imgui.push_item_width(220)
        #         current_skill_label = HYBRID_SKILL_IDS.get(hybrid.skill_id, f"自定义 ({hybrid.skill_id})")
        #         if imgui.begin_combo("##skill_id_hybrid", current_skill_label):
        #             for skill_id, skill_label in HYBRID_SKILL_IDS.items():
        #                 if imgui.selectable(skill_label, skill_id == hybrid.skill_id)[0]:
        #                     hybrid.skill_id = skill_id
        #             imgui.end_combo()
        #         imgui.pop_item_width()
        # else:
        #     # 未勾选使用次数时，显示提示（重置已在使用次数区块集中处理）
        #     self.text_secondary('（需要先勾选"拥有使用次数"才能设置主动技能）')

        self.draw_indented_separator()


        # ====== 耐久区块（放在使用次数之前）======
        # has_durability 现在是计算属性（品质非文物且物品类型为武器/护甲时自动有耐久）
        if hybrid.has_durability:
            imgui.text("耐久设置")
            if imgui.is_item_hovered():
                imgui.set_tooltip("武器类/护甲饰品类（非文物）自动拥有耐久度")
            
            # duration_init 已删除，初始耐久固定等于最大耐久
            imgui.text("最大耐久:")
            imgui.same_line()
            imgui.push_item_width(120)
            changed, hybrid.duration_max = imgui.input_int("##dur_max", hybrid.duration_max)
            if changed:
                hybrid.duration_max = max(1, hybrid.duration_max)
            imgui.pop_item_width()
            
            # 耐久耗尽后删除
            imgui.same_line(spacing=20)
            changed, hybrid.destroy_on_durability_zero = imgui.checkbox("耐久耗尽后删除##hybrid", hybrid.destroy_on_durability_zero)
            if imgui.is_item_hovered():
                imgui.set_tooltip("开启：耐久归零时删除物品\n关闭：允许0耐久")

            # 磨损设置（固定在耐久区块，所有模式都在这里设置）
            if hybrid.has_charges:
                imgui.text("每次使用磨损耐久 (%):")
                imgui.same_line()
                imgui.push_item_width(120)
                changed, hybrid.wear_per_use = imgui.input_int("##wear_per_use", hybrid.wear_per_use)
                if changed:
                    # linked 模式下最小为1，normal 模式可为0
                    min_wear = 1 if hybrid.charge_mode == "linked" else 0
                    hybrid.wear_per_use = max(min_wear, min(100, hybrid.wear_per_use))
                imgui.pop_item_width()
                
                # linked 模式下显示计算出的最大次数
                if hybrid.charge_mode == "linked":
                    computed_charge = hybrid.effective_charge
                    imgui.same_line(spacing=10)
                    self.text_secondary(f"→ 最大 {computed_charge} 次")
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(f"最大使用次数 = floor(100 / {hybrid.wear_per_use}) = {computed_charge}\n（次数与耐久挂钩模式）")
                else:
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("每次使用消耗最大耐久的百分比\n无论耐久是否低于消耗都不阻止使用\n物品是否消失取决于\"耐久耗尽后删除\"设置")

            self.draw_indented_separator()

        # ====== 使用次数区块 ======
        # has_charges 现在是计算属性（主动效果模式非"无"时自动有使用次数）
        if hybrid.has_charges:
            imgui.text("使用次数设置")
            if imgui.is_item_hovered():
                imgui.set_tooltip("主动效果模式非\"无\"时自动拥有使用次数")
            
            # 充能消耗模式下拉选择器
            imgui.text("消耗模式:")
            imgui.same_line()
            imgui.push_item_width(180)
            
            # 构建可用模式列表
            mode_options = ["normal", "unlimited"]
            mode_labels = {"normal": "正常消耗", "unlimited": "无消耗"}
            
            # 只有当物品有耐久时才显示"与耐久挂钩"选项
            if hybrid.has_durability:
                mode_options.append("linked")
                mode_labels["linked"] = "与耐久挂钩"
            
            current_mode_label = mode_labels.get(hybrid.charge_mode, "正常消耗")
            if imgui.begin_combo("##charge_mode", current_mode_label):
                for mode_key in mode_options:
                    is_selected = hybrid.charge_mode == mode_key
                    if imgui.selectable(mode_labels[mode_key], is_selected)[0]:
                        hybrid.charge_mode = mode_key
                        # 切换到 linked 模式时，确保 wear_per_use >= 1
                        if mode_key == "linked" and hybrid.wear_per_use < 1:
                            hybrid.wear_per_use = 10  # 默认10%
                imgui.end_combo()
            imgui.pop_item_width()
            
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    "• 正常消耗：每次使用减少1次\n"
                    "• 无消耗：次数永不减少（固定为1次）\n"
                    "• 与耐久挂钩：次数由耐久度和磨损%计算\n"
                    "  (仅武器/护甲类可选)"
                )
            
            # 根据模式显示不同的设置
            if hybrid.charge_mode == "unlimited":
                # 无消耗模式：强制设置
                hybrid.charge = 1
                hybrid.has_charge_recovery = False
                imgui.same_line(spacing=20)
                self.text_secondary("（次数固定为 1，永不减少）")
                
            elif hybrid.charge_mode == "linked":
                # 与耐久挂钩模式：显示计算出的最大次数
                computed_charge = hybrid.effective_charge
                imgui.same_line(spacing=20)
                imgui.text(f"最大次数: {computed_charge}")
                imgui.same_line(spacing=10)
                self.text_secondary("（由耐久设置区的磨损%计算）")
                
            else:  # normal 模式
                # 正常模式：次数输入
                imgui.same_line(spacing=20)
                imgui.text("次数:")
                imgui.same_line()
                imgui.push_item_width(120)
                changed, hybrid.charge = imgui.input_int("##charge_hybrid", hybrid.charge, step=1, step_fast=5)
                if changed:
                    hybrid.charge = max(1, hybrid.charge)
                imgui.pop_item_width()

            imgui.same_line(spacing=20)
            changed, hybrid.draw_charges = imgui.checkbox("显示次数##hybrid", hybrid.draw_charges)
            if imgui.is_item_hovered():
                imgui.set_tooltip("是否在物品图标上显示使用次数")
            
            # 使用次数恢复设置（无消耗模式下不可用）
            if hybrid.charge_mode != "unlimited":
                changed, hybrid.has_charge_recovery = imgui.checkbox("启用次数恢复##hybrid", hybrid.has_charge_recovery)
                if imgui.is_item_hovered():
                    tip = "启用后，使用次数会随时间自动恢复"
                    if hybrid.charge_mode == "linked":
                        tip += "\n（实际恢复的是耐久度）"
                    imgui.set_tooltip(tip)
                
                if hybrid.has_charge_recovery:
                    imgui.same_line(spacing=20)
                    imgui.text("恢复间隔 (回合):")
                    imgui.same_line()
                    imgui.push_item_width(120)
                    changed, hybrid.charge_recovery_interval = imgui.input_int("##recovery_interval", hybrid.charge_recovery_interval, step=1, step_fast=5)
                    if changed:
                        hybrid.charge_recovery_interval = max(1, hybrid.charge_recovery_interval)
                    imgui.pop_item_width()
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("每隔多少回合恢复1次使用次数 (1回合=30秒)")

            self.draw_indented_separator()
        else:
            # 无使用次数时清除相关设置
            hybrid.charge = 1
            hybrid.draw_charges = False
            hybrid.charge_mode = "normal"
            hybrid.has_charge_recovery = False
            hybrid.charge_recovery_interval = 10
            hybrid.wear_per_use = 0
            hybrid.delete_on_charge_zero = False

        # ====== 次数耗尽删除物品 ======
        # 条件：有使用次数、非无消耗模式、没有耐久、非文物
        if hybrid.has_charges and hybrid.charge_mode != "unlimited" and not hybrid.has_durability and hybrid.quality != 7:
            changed, hybrid.delete_on_charge_zero = imgui.checkbox("次数耗尽后删除物品##hybrid", hybrid.delete_on_charge_zero)
            if imgui.is_item_hovered():
                imgui.set_tooltip("开启：使用次数归零时删除物品\n关闭：保留物品（可能需要修理或其他方式恢复次数）")
            self.draw_indented_separator()


        # 音效（使用下拉选项）
        imgui.text("音效设置")

        imgui.text("放下音效:")
        imgui.same_line()
        imgui.push_item_width(200)
        current_drop_label = HYBRID_DROP_SOUNDS.get(hybrid.drop_sound, f"自定义 ({hybrid.drop_sound})")
        if imgui.begin_combo("##drop_sound", current_drop_label):
            for sound_id, sound_label in HYBRID_DROP_SOUNDS.items():
                if imgui.selectable(sound_label, sound_id == hybrid.drop_sound)[0]:
                    hybrid.drop_sound = sound_id
            imgui.end_combo()
        imgui.pop_item_width()
        if imgui.is_item_hovered():
            imgui.set_tooltip("物品放下时播放的音效")

        imgui.same_line(spacing=20)
        imgui.text("拾取音效:")
        imgui.same_line()
        imgui.push_item_width(200)
        current_pickup_label = HYBRID_PICKUP_SOUNDS.get(hybrid.pickup_sound, f"自定义 ({hybrid.pickup_sound})")
        if imgui.begin_combo("##pickup_sound", current_pickup_label):
            for sound_id, sound_label in HYBRID_PICKUP_SOUNDS.items():
                if imgui.selectable(sound_label, sound_id == hybrid.pickup_sound)[0]:
                    hybrid.pickup_sound = sound_id
            imgui.end_combo()
        imgui.pop_item_width()
        if imgui.is_item_hovered():
            imgui.set_tooltip("物品拾取时播放的音效")

    def _draw_hybrid_weapon_settings(self, hybrid: HybridItem):
        """绘制混合物品武器设置"""
        col_width = imgui.get_content_region_available_width() / 2 - 8
        imgui.columns(2, "hybrid_weapon_cols", border=False)
        imgui.set_column_width(0, col_width)

        imgui.push_item_width(-1)

        imgui.text("武器类型")
        hybrid.weapon_type = self._draw_enum_combo(
            "##wep_type",
            hybrid.weapon_type,
            list(HYBRID_WEAPON_TYPES.keys()),
            HYBRID_WEAPON_TYPES,
        )
        
        # 根据武器类型自动设置手数
        # 双手武器：2hsword, 2haxe, 2hmace, 2hStaff, bow, crossbow, spear
        two_handed_types = {"2hsword", "2haxe", "2hmace", "2hStaff", "bow", "crossbow", "spear"}
        hybrid.hands = 2 if hybrid.weapon_type in two_handed_types else 1

        imgui.text("材料")
        hybrid.material = self._draw_enum_combo(
            "##wep_mat",
            hybrid.material,
            list(HYBRID_MATERIALS.keys()),
            HYBRID_MATERIALS,
        )

        imgui.pop_item_width()
        imgui.next_column()
        imgui.push_item_width(-1)

        imgui.text("等级")
        changed, hybrid.tier = imgui.input_int("##wep_tier", hybrid.tier)
        if changed:
            hybrid.tier = max(1, min(7, hybrid.tier))

        imgui.text("平衡")
        changed, hybrid.balance = imgui.input_int("##wep_balance", hybrid.balance)
        if changed:
            hybrid.balance = max(1, hybrid.balance)  # 最小值为1

        imgui.pop_item_width()
        imgui.columns(1)
        # weapon_range 字段已删除，Range 通过属性编辑器设置

        # 伤害汇总（放在区块底部，单独占一行）
        damage_components = self._compute_weapon_damage_components(hybrid)
        total_dmg = sum(v for _, v in damage_components)
        max_val = max([v for _, v in damage_components], default=0)
        ties = [t for t, v in damage_components if v == max_val and v > 0]
        best_type = ties[0] if ties else "Slashing_Damage"  # 默认伤害类型
        dmg_label_map = HYBRID_DAMAGE_TYPES
        dmg_type_label = dmg_label_map.get(best_type, best_type)
        self.text_secondary(f"伤害汇总: DMG={total_dmg}  主类型={dmg_type_label}（自动取最高伤害类型）")

    def _draw_hybrid_armor_settings(self, hybrid: HybridItem):
        """绘制混合物品护甲设置"""
        col_width = imgui.get_content_region_available_width() / 2 - 8
        imgui.columns(2, "hybrid_armor_cols", border=False)
        imgui.set_column_width(0, col_width)

        imgui.push_item_width(-1)

        imgui.text("护甲类型")
        hybrid.armor_type = self._draw_enum_combo(
            "##armor_type",
            hybrid.armor_type,
            list(HYBRID_ARMOR_TYPES.keys()),
            HYBRID_ARMOR_TYPES,
        )
        
        # 根据护甲类型自动设置槽位
        hybrid.slot = "hand" if hybrid.armor_type == "shield" else hybrid.armor_type

        imgui.text("护甲材料")
        # armor_material 已删除，使用 material（武器和护甲共用）
        hybrid.material = self._draw_enum_combo(
            "##armor_mat",
            hybrid.material,
            list(HYBRID_ARMOR_MATERIALS.keys()),
            HYBRID_ARMOR_MATERIALS,
        )

        imgui.pop_item_width()
        imgui.next_column()
        imgui.push_item_width(-1)

        imgui.text("护甲类别")
        # armor_class 已删除，由 weight 计算。这里设置 weight
        hybrid.weight = self._draw_enum_combo(
            "##armor_weight",
            hybrid.weight,
            list(HYBRID_ARMOR_CLASSES.keys()),  # Light/Medium/Heavy
            HYBRID_ARMOR_CLASSES,
        )
        # defense 字段已删除，DEF 通过属性编辑器设置

        imgui.pop_item_width()
        imgui.columns(1)
        
        # 碎片材料编辑器（用于拆解，仅非盾/戒/项链显示）
        if hybrid.slot not in ["hand", "Ring", "Amulet"]:
            if imgui.tree_node("拆解碎片##fragments"):
                imgui.columns(3, "frag_cols", border=False)
                frag_width = 100
                imgui.set_column_width(0, frag_width)
                imgui.set_column_width(1, frag_width)
                imgui.set_column_width(2, frag_width)
                
                frag_labels = {
                    "cloth01": "布料 1", "cloth02": "布料 2", "cloth03": "布料 3", "cloth04": "布料 4",
                    "leather01": "皮革 1", "leather02": "皮革 2", "leather03": "皮革 3", "leather04": "皮革 4",
                    "metal01": "金属 1", "metal02": "金属 2", "metal03": "金属 3", "metal04": "金属 4",
                    "gold": "黄金"
                }
                frag_keys = ["cloth01", "cloth02", "cloth03", "cloth04",
                             "leather01", "leather02", "leather03", "leather04",
                             "metal01", "metal02", "metal03", "metal04", "gold"]
                
                for i, frag in enumerate(frag_keys):
                    val = hybrid.fragments.get(frag, 0)
                    imgui.push_item_width(60)
                    changed, new_val = imgui.input_int(f"##{frag}", val, step=0, step_fast=0)
                    imgui.pop_item_width()
                    if changed:
                        hybrid.fragments[frag] = max(0, new_val)
                    imgui.same_line()
                    imgui.text(frag_labels.get(frag, frag))
                    imgui.next_column()
                
                imgui.columns(1)
                if imgui.is_item_hovered():
                    imgui.set_tooltip("拆解物品时获得的碎片材料")
                imgui.tree_pop()

    def _draw_hybrid_attributes_editor(self, hybrid: HybridItem):
        """绘制混合物品属性编辑器（按武器/护甲/被动区分可选字段）"""
        groups = self._get_hybrid_attribute_groups(hybrid)
        if not groups:
            return

        tips = []
        if hybrid.init_weapon_stats:
            tips.append("武器属性")
        if hybrid.init_armor_stats:
            tips.append("护甲属性")
        if hybrid.has_passive:
            tips.append("被动属性")
        if tips:
            self.text_secondary(" / ".join(tips) + "：仅显示模板允许的字段")
            self.draw_indented_separator()

        for group_name, attributes in groups.items():
            tree_id = f"{group_name}##hybrid_attr"
            if imgui.tree_node(tree_id):
                imgui.columns(2, f"hybrid_attr_cols_{tree_id}", border=False)
                input_col_width = 120 + (self.font_size - 14) * 6
                imgui.set_column_width(0, input_col_width)

                for attr in attributes:
                    desc_name, desc_detail = get_attr_display(attr)
                    if not desc_name:
                        desc_name = attr

                    val = hybrid.attributes.get(attr, 0)

                    imgui.push_item_width(-1)
                    input_id = f"##{attr}_hybrid"
                    changed, new_val = imgui.input_int(input_id, val, step=1, step_fast=10)
                    imgui.pop_item_width()

                    if changed:
                        hybrid.attributes[attr] = new_val

                    imgui.next_column()
                    imgui.text(desc_name)

                    if desc_detail and imgui.is_item_hovered():
                        imgui.set_tooltip(desc_detail)

                    imgui.next_column()

                imgui.columns(1)
                imgui.tree_pop()

        # 清除当前类型不再允许的属性
        self._prune_hybrid_attributes(hybrid, groups)

    def _prune_hybrid_attributes(self, hybrid: HybridItem, groups: dict):
        """移除与当前类型不匹配的属性"""
        allowed = set()
        for attrs in groups.values():
            allowed.update(attrs)
        to_delete = [k for k in hybrid.attributes.keys() if k not in allowed]
        for k in to_delete:
            del hybrid.attributes[k]

    def _draw_hybrid_consumable_attributes_editor(self, hybrid: HybridItem):
        """绘制混合物品消耗品属性编辑器
        
        使用 CONSUMABLE_ATTRIBUTE_GROUPS 中的分组定义，通过分组名称前缀
        (CONSUMABLE_INSTANT_GROUP_PREFIX / CONSUMABLE_DURATION_GROUP_PREFIX)
        自动区分即时效果和持续效果属性。
        
        核心控制属性：CONSUMABLE_DURATION_ATTRIBUTE (Duration)
        - Duration > 0 时，持续效果分组的属性才会生效
        """
        if not hybrid.has_charges:
            return

        if imgui.collapsing_header("消耗品属性")[0]:
            imgui.indent()
            
            # 1. 持续时间 (CONSUMABLE_DURATION_ATTRIBUTE - 控制依赖属性)
            duration_attr = CONSUMABLE_DURATION_ATTRIBUTE
            duration_val = hybrid.consumable_attributes.get(duration_attr, 0)
            
            imgui.push_item_width(120)
            changed, new_dur = imgui.input_int(
                "效果持续时间##consum_duration",
                int(duration_val),
                step=1,
                step_fast=10
            )
            imgui.pop_item_width()
            if changed:
                hybrid.consumable_attributes[duration_attr] = max(0, new_dur)
            
            if imgui.is_item_hovered():
                imgui.set_tooltip('部分属性(如回复/Buff)只有在持续时间 > 0 时生效\n以"持续效果"开头的分组需要此值 > 0')

            # 2. 中毒持续时间（仅当 Poisoning_Chance > 0 时显示）
            poisoning_chance = hybrid.consumable_attributes.get("Poisoning_Chance", 0)
            if poisoning_chance > 0:
                imgui.push_item_width(120)
                changed, hybrid.poison_duration = imgui.input_int(
                    "中毒持续时间##poison_dur",
                    hybrid.poison_duration,
                    step=1,
                    step_fast=10
                )
                imgui.pop_item_width()
                if changed:
                    hybrid.poison_duration = max(0, hybrid.poison_duration)
                
                if imgui.is_item_hovered():
                    imgui.set_tooltip("中毒持续回合数 (仅当设置了中毒几率时生效)")

            imgui.dummy(0, 5)

            # 即时效果分组（独立定义）和持续效果分组（复用装备属性分组）
            instant_groups = CONSUMABLE_INSTANT_ATTRS
            
            # 持续效果分组：复用装备属性分组
            duration_attrs = get_consumable_duration_attrs()
            duration_groups = get_attribute_groups(duration_attrs, DEFAULT_GROUP_ORDER)

            def draw_attr_group(group_name: str, attr_list: list, enabled: bool = True):
                """绘制属性分组，使用两列布局（与其他编辑器一致）"""
                # 显示分组名称（去掉前缀，只保留括号内容）
                display_name = group_name
                if "（" in group_name:
                    display_name = group_name.split("（", 1)[1].rstrip("）")
                
                if imgui.tree_node(f"{display_name}##consum_{group_name}"):
                    if not enabled:
                        imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                    
                    # 使用两列布局：输入框 | 属性名
                    imgui.columns(2, f"consum_cols_{group_name}", border=False)
                    input_col_width = 120 + (self.font_size - 14) * 6
                    imgui.set_column_width(0, input_col_width)
                    
                    for attr in attr_list:
                        attr_name, attr_desc = get_attr_display(attr)
                        if not attr_name:
                            attr_name = attr
                        
                        val = hybrid.consumable_attributes.get(attr, 0)
                        is_float_attr = attr in CONSUMABLE_FLOAT_ATTRIBUTES
                        
                        # 第一列：输入框
                        imgui.push_item_width(-1)
                        input_id = f"##{attr}_consum"
                        
                        if enabled:
                            if is_float_attr:
                                changed, new_val = imgui.input_float(
                                    input_id,
                                    float(val),
                                    step=0.1,
                                    step_fast=1.0,
                                    format="%.2f"
                                )
                            else:
                                changed, new_val = imgui.input_int(
                                    input_id,
                                    int(val),
                                    step=1,
                                    step_fast=10
                                )
                            if changed:
                                hybrid.consumable_attributes[attr] = new_val
                        else:
                            # 禁用时显示只读文本
                            display_val = f"{val:.2f}" if is_float_attr else str(int(val))
                            imgui.text(display_val)
                        
                        imgui.pop_item_width()
                        
                        # 第二列：属性名称
                        imgui.next_column()
                        imgui.text(attr_name)
                        
                        if attr_desc and imgui.is_item_hovered():
                            imgui.set_tooltip(attr_desc)
                        
                        imgui.next_column()
                    
                    imgui.columns(1)
                    
                    if not enabled:
                        imgui.pop_style_var()
                    
                    imgui.tree_pop()

            # 2. 绘制即时效果属性 (始终可用)
            imgui.text_colored("独立/即时效果", *self.theme_colors["accent"])
            self.text_secondary("这些属性不需要设置持续时间即可生效")
            
            for group_name, attrs in instant_groups.items():
                draw_attr_group(group_name, attrs, enabled=True)
            
            imgui.separator()
            
            # 3. 绘制持续效果属性 (需要 Duration > 0)
            duration_valid = hybrid.consumable_attributes.get(duration_attr, 0) > 0
            
            header_text = "持续性效果"
            if not duration_valid:
                header_text += " [需设置持续时间]"
                
            imgui.text_colored(header_text, *self.theme_colors["accent" if duration_valid else "text_secondary"])
            
            if not duration_valid:
                imgui.text_colored("警告: 这些属性需要设置 '效果持续时间' 才能生效。", 1.0, 0.5, 0.0)
            
            if duration_valid or imgui.tree_node("查看被禁用的属性##consum_disabled"):
                for group_name, attrs in duration_groups.items():
                    draw_attr_group(group_name, attrs, enabled=duration_valid)
                if not duration_valid:
                    imgui.tree_pop()
                
            imgui.unindent()

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
        """绘制混合物品贴图编辑器"""
        self.text_secondary("注意: 所有贴图仅支持 PNG 格式")
        self.draw_indented_separator()

        # 预览设置
        imgui.text("预览:")
        imgui.same_line()
        imgui.push_item_width(120)
        changed, self.texture_scale = imgui.input_float(
            "##scale_hybrid",
            self.texture_scale,
            step=0.5,
            step_fast=1.0,
            format="%.1fx",
        )
        imgui.pop_item_width()
        if changed:
            self.texture_scale = max(0.5, min(8.0, self.texture_scale))
            self.save_config()

        self.draw_indented_separator()

        # 穿戴/手持状态贴图
        if hybrid.needs_char_texture():
            imgui.text("穿戴/手持状态贴图")

            # 模特选择
            imgui.same_line()
            imgui.text("  模特:")
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

            imgui.dummy(0, 4)

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
                self.draw_indented_separator()
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

            self.draw_indented_separator()
        else:
            slot_name = HYBRID_SLOT_LABELS.get(hybrid.slot, hybrid.slot)
            self.text_secondary(f"提示: {slot_name} 槽位不需要穿戴状态贴图")
            self.draw_indented_separator()

        # 常规贴图
        imgui.text("常规贴图（物品栏显示）")
        if imgui.is_item_hovered():
            imgui.set_tooltip("物品在物品栏中显示的贴图\n如有多张，可显示不同耐久状态")

        for idx in range(len(hybrid.textures.inventory)):
            current_path = (
                hybrid.textures.inventory[idx]
                if idx < len(hybrid.textures.inventory)
                else ""
            )
            self._draw_single_texture_selector(
                f"常规贴图 {idx + 1}##hybrid",
                current_path,
                ("inventory", idx),
                hybrid,
                "hybrid",
            )

        if imgui.button("添加贴图槽##hybrid"):
            hybrid.textures.inventory.append("")
        if len(hybrid.textures.inventory) > 1:
            imgui.same_line()
            if imgui.button("删除最后一个贴图槽##hybrid"):
                hybrid.textures.inventory.pop()

        self.draw_indented_separator()

        # 战利品贴图
        self._draw_texture_list_selector(
            "战利品贴图*##hybrid", hybrid.textures.loot, "loot", hybrid, "hybrid"
        )

        if hybrid.textures.is_animated("loot"):
            self._draw_loot_animation_settings(hybrid.textures, "hybrid")

    # ==================== 通用属性编辑器 ====================

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
        imgui.same_line(spacing=20)
        item.no_drop = self._draw_inline_checkbox(
            f"不可掉落##{id_suffix}", item.no_drop, "可能无法从宝箱中获取"
        )
        if isinstance(item, Armor):
            imgui.same_line(spacing=20)
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
                    if tooltip_text and imgui.is_item_hovered():
                        imgui.set_tooltip(tooltip_text)

                    imgui.next_column()

                imgui.columns(1)
                imgui.tree_pop()

    def _draw_fragments_editor(self, armor):
        """绘制拆解材料编辑器"""
        imgui.text("设置装备拆解后可获得的材料")
        if imgui.is_item_hovered():
            imgui.set_tooltip("拆解装备时可能获得的材料碎片数量")

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

        self.draw_indented_separator()

        # 主语言
        primary_label = LANGUAGE_LABELS.get(PRIMARY_LANGUAGE, PRIMARY_LANGUAGE)
        imgui.text(f"{primary_label} (主语言)")

        if not item.localization.has_language(PRIMARY_LANGUAGE):
            item.localization.languages[PRIMARY_LANGUAGE] = {
                "name": "",
                "description": "",
            }

        primary_data = item.localization.languages[PRIMARY_LANGUAGE]

        imgui.text("名称")
        imgui.push_item_width(-1)
        changed, val = imgui.input_text(
            f"##{PRIMARY_LANGUAGE}_name{suffix}", primary_data["name"], 256
        )
        if changed:
            primary_data["name"] = val
        if not primary_data["name"] and imgui.is_item_hovered():
            imgui.set_tooltip("主语言名称（建议填写）")
        imgui.pop_item_width()

        imgui.text("描述")
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
        imgui.dummy(0, 10)

        # 其他语言
        langs_to_remove = []
        for lang in LANGUAGE_LABELS:
            if lang == PRIMARY_LANGUAGE:
                continue
            if not item.localization.has_language(lang):
                continue

            data = item.localization.languages[lang]

            self.draw_indented_separator()
            label = LANGUAGE_LABELS.get(lang, lang)
            imgui.text(f"{label}")
            imgui.same_line()
            if imgui.button(f"删除##{lang}{suffix}"):
                langs_to_remove.append(lang)

            imgui.text("名称")
            imgui.push_item_width(-1)
            changed, val = imgui.input_text(f"##{lang}_name{suffix}", data["name"], 256)
            if changed:
                data["name"] = val
            imgui.pop_item_width()

            imgui.text("描述")
            imgui.push_item_width(-1)
            # 描述框高度随字体缩放
            desc_height = 50 + (self.font_size - 14) * 3
            changed, val = imgui.input_text_multiline(
                f"##{lang}_desc{suffix}", data["description"], 1024, height=desc_height
            )
            if changed:
                data["description"] = val
            imgui.pop_item_width()
            imgui.dummy(0, 5)

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
        imgui.same_line(spacing=2)
        imgui.text("X")
        imgui.same_line(spacing=2)
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
        imgui.same_line(spacing=2)
        if imgui.button(f"+##xp_{id_suffix}", width=btn_w) and not disabled:
            new_x = off_x + 1

        imgui.same_line(spacing=8)

        # Y 偏移组
        if imgui.button(f"-##ym_{id_suffix}", width=btn_w) and not disabled:
            new_y = off_y - 1
        imgui.same_line(spacing=2)
        imgui.text("Y")
        imgui.same_line(spacing=2)
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
        imgui.same_line(spacing=2)
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

    def _draw_offset_inputs(self, label, tooltip, offset_x, offset_y, id_suffix):
        """绘制偏移输入"""
        imgui.text(label)
        if imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)

        imgui.push_item_width(150)
        changed_x, new_offset_x = imgui.input_int(f"水平偏移##{id_suffix}", offset_x)
        if imgui.is_item_hovered():
            imgui.set_tooltip("默认 0。正数使人物看起来向右。")

        imgui.same_line()
        imgui.dummy(10, 0)
        imgui.same_line()

        changed_y, new_offset_y = imgui.input_int(f"垂直偏移##{id_suffix}", offset_y)
        if imgui.is_item_hovered():
            imgui.set_tooltip("默认 0。正数使人物看起来向下。")
        imgui.pop_item_width()

        return new_offset_x, new_offset_y

    def _draw_loot_animation_settings(self, textures, id_suffix):
        """绘制战利品动画设置"""
        imgui.text("战利品动画速度设置")
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "设置战利品贴图的动画播放速度。\n此设置会影响生成的模组代码。"
            )

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
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    "每秒播放的帧数。\n这是一个固定值，不会随游戏速度变化。\n默认值: 10"
                )
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
            if imgui.is_item_hovered():
                imgui.set_tooltip(
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
        current_label = labels.get(current_value, current_value)
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
            code = generator.generate()
            with open(mod_dir / f"{mod_name}.cs", "w", encoding="utf-8") as f:
                f.write(code)

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
                    is_multi_pose_armor=False,
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
