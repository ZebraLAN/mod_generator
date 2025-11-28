# -*- coding: utf-8 -*-
"""
Stoneshard 装备模组编辑器 - 主程序

基于 ImGui 的图形界面，用于创建和编辑 Stoneshard 游戏的武器/装备模组。
"""

import copy
import json
import os
import shutil
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
    ARMOR_ATTRIBUTE_GROUPS,
    ARMOR_CLASS_LABELS,
    ARMOR_FRAGMENT_LABELS,
    ARMOR_SLOT_LABELS,
    ATTRIBUTE_DESCRIPTIONS,
    BYTE_ATTRIBUTES,
    CHARACTER_MODEL_LABELS,
    CHARACTER_MODELS,
    GAME_FPS,
    LANGUAGE_LABELS,
    LEFT_HAND_SLOTS,
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
    WEAPON_ATTRIBUTE_GROUPS,
    WEAPON_MATERIAL_LABELS,
    ARMOR_MATERIAL_LABELS,
)
from generator import CodeGenerator, copy_item_textures
from models import (
    Armor,
    ModProject,
    Weapon,
    validate_item,
)


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
        if not os.path.exists("fonts"):
            os.makedirs("fonts", exist_ok=True)

        # 尝试将旧字体移动到 fonts 目录
        old_font = "HanyiSentyYongleEncyclopedia-2020.ttf"
        new_font = os.path.join("fonts", old_font)
        if os.path.exists(old_font) and not os.path.exists(new_font):
            try:
                shutil.move(old_font, new_font)
                print(f"已将 {old_font} 移动到 fonts 目录")
            except Exception as e:
                print(f"移动字体文件失败: {e}")

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
        self.show_import_dialog = False
        self.import_file_path = ""
        self.import_conflicts = []
        self.current_texture_field = ""
        self.texture_preview_cache = {}
        self.selected_model = "Human Male"
        self.preview_states = {}
        self.active_item_tab = 0

        # 弹窗状态
        self.show_error_popup = False
        self.show_save_popup = False
        self.show_success_popup = False

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
        color = getattr(self, "theme_colors", {}).get(
            "text_secondary", (0.6, 0.6, 0.65, 1.0)
        )
        imgui.text_colored(text, *color)

    def text_success(self, text: str):
        """绘制成功文字（绿色）"""
        color = getattr(self, "theme_colors", {}).get("success", (0.3, 0.7, 0.45, 1.0))
        imgui.text_colored(text, *color)

    def text_warning(self, text: str):
        """绘制警告文字（橙色）"""
        color = getattr(self, "theme_colors", {}).get("warning", (0.9, 0.7, 0.25, 1.0))
        imgui.text_colored(text, *color)

    def text_error(self, text: str):
        """绘制错误文字（红色）"""
        color = getattr(self, "theme_colors", {}).get("error", (0.9, 0.35, 0.35, 1.0))
        imgui.text_colored(text, *color)

    def text_accent(self, text: str):
        """绘制强调文字（主题色）"""
        color = getattr(self, "theme_colors", {}).get("accent", (0.4, 0.65, 0.8, 1.0))
        imgui.text_colored(text, *color)

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

        # 工具栏：使用文字按钮
        # 添加按钮
        if imgui.button(f"+##{item_type_label}_add"):
            new_item = item_class()
            new_item.name = self._generate_unique_name(items, default_id_base)
            new_item.localization.set_name(PRIMARY_LANGUAGE, default_name)
            new_item.localization.set_description(PRIMARY_LANGUAGE, default_desc)
            items.append(new_item)
            setattr(self, current_index_attr, len(items) - 1)
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"添加{item_type_label}")

        imgui.same_line()

        # 删除按钮
        can_delete = current_index >= 0
        if not can_delete:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if imgui.button(f"-##{item_type_label}_del") and can_delete:
            del items[current_index]
            setattr(self, current_index_attr, min(current_index, len(items) - 1))
        if not can_delete:
            imgui.pop_style_var()
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"删除选中的{item_type_label}")

        imgui.same_line()

        # 复制按钮
        can_copy = current_index >= 0
        if not can_copy:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if imgui.button(f"=##{item_type_label}_copy") and can_copy:
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
            imgui.set_tooltip(f"复制选中的{item_type_label}")

        imgui.separator()
        current_index = getattr(self, current_index_attr)

        # 列表项 - 使用 Selectable 替代 TreeNode，更适合列表
        for i, item in enumerate(items):
            display_name = item.localization.get_display_name()
            suffix = get_display_suffix(item) if get_display_suffix else ""

            # 主显示名 + 系统ID（较小）
            is_selected = i == current_index

            # 选中项添加前缀标记，增强视觉对比
            # 使用 > 符号替代图标字体，避免不同字体大小导致的对齐问题
            prefix = "> " if is_selected else "  "

            # 使用 selectable，宽度填满容器
            if imgui.selectable(f"{prefix}{display_name}##{i}", is_selected)[0]:
                setattr(self, current_index_attr, i)

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
            self._draw_attributes_editor(weapon, WEAPON_ATTRIBUTE_GROUPS, "weapon")
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
            self._draw_attributes_editor(armor, ARMOR_ATTRIBUTE_GROUPS, "armor")
            imgui.tree_pop()

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
        """绘制属性编辑器"""
        for group_name, attributes in attribute_groups.items():
            tree_id = f"{group_name}##{id_suffix}_attr"
            if imgui.tree_node(tree_id):
                for attr in attributes:
                    desc_info = ATTRIBUTE_DESCRIPTIONS.get(attr, ("", ""))
                    desc_name = desc_info[0]
                    desc_detail = desc_info[1] if len(desc_info) > 1 else ""

                    val = item.attributes.get(attr, 0)

                    input_width = 100 + (self.font_size - 14) * 8
                    imgui.push_item_width(input_width)
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

                    # 负面属性列表（这些属性越低越好）
                    NEGATIVE_ATTRIBUTES = {
                        "FMB",
                        "Cooldown_Reduction",
                        "Abilities_Energy_Cost",
                        "Skills_Energy_Cost",
                        "Spells_Energy_Cost",
                        "Miscast_Chance",
                        "Fatigue_Gain",
                        "Damage_Received",
                    }

                    # 属性值颜色反馈：
                    # 普通属性：正数绿色(增益)，负数红色(减益)
                    # 负面属性：正数红色(减益)，负数绿色(增益)
                    imgui.same_line()
                    is_negative_attr = attr in NEGATIVE_ATTRIBUTES
                    if new_val > 0:
                        if is_negative_attr:
                            self.text_error(f"+{new_val}")
                        else:
                            self.text_success(f"+{new_val}")
                    elif new_val < 0:
                        if is_negative_attr:
                            self.text_success(f"{new_val}")
                        else:
                            self.text_error(f"{new_val}")
                    else:
                        self.text_secondary("0")

                    imgui.same_line()
                    imgui.text(f"{attr}")
                    imgui.same_line()
                    self.text_secondary(f"({desc_name})")

                    if imgui.is_item_hovered():
                        tooltip_text = desc_detail
                        if attr in BYTE_ATTRIBUTES:
                            if tooltip_text:
                                tooltip_text += "\n"
                            tooltip_text += "类型: byte (0-255)"
                        imgui.set_tooltip(tooltip_text)

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

        if item.needs_char_texture():
            imgui.same_line(spacing=16)
            imgui.text("模特:")
            imgui.same_line()
            # 模特选择宽度随字体缩放
            model_combo_width = 100 + (self.font_size - 14) * 4
            imgui.push_item_width(model_combo_width)
            current_model_label = CHARACTER_MODEL_LABELS.get(
                self.selected_model, self.selected_model
            )
            if imgui.begin_combo(f"##model_{id_suffix}", current_model_label):
                for model_key, model_label in CHARACTER_MODEL_LABELS.items():
                    if imgui.selectable(model_label, model_key == self.selected_model)[
                        0
                    ]:
                        self.selected_model = model_key
                imgui.end_combo()
            imgui.pop_item_width()

        self.draw_indented_separator()

        # 穿戴/手持状态贴图
        if item.needs_char_texture():
            char_label = "手持状态贴图*" if id_suffix == "weapon" else "穿戴状态贴图*"
            self._draw_texture_list_selector(
                char_label, item.textures.character, "character", item, id_suffix
            )

            offset_label = (
                "手持贴图偏移 (右手/默认)" if id_suffix == "weapon" else "穿戴贴图偏移"
            )
            item.textures.offset_x, item.textures.offset_y = self._draw_offset_inputs(
                offset_label,
                f"调整{type_name}相对于人物的相对位置",
                item.textures.offset_x,
                item.textures.offset_y,
                id_suffix,
            )

            self.draw_indented_separator()

            # 左手贴图
            if item.needs_left_texture():
                left_label = (
                    "左手手持贴图*" if id_suffix == "weapon" else "左手穿戴贴图*"
                )
                self._draw_texture_list_selector(
                    left_label,
                    item.textures.character_left,
                    "character_left",
                    item,
                    id_suffix,
                )

                item.textures.offset_x_left, item.textures.offset_y_left = (
                    self._draw_offset_inputs(
                        "左手贴图偏移",
                        f"调整左手{type_name}相对于人物的相对位置",
                        item.textures.offset_x_left,
                        item.textures.offset_y_left,
                        f"{id_suffix}_left",
                    )
                )

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

    def _draw_texture_list_selector(
        self, label, texture_list: list, field_name: str, item, id_suffix
    ):
        """绘制贴图列表选择器（支持动画）

        texture_list: 直接引用 item.textures.xxx 列表
        field_name: 字段名，如 "character", "character_left", "loot"
        """
        imgui.text(label)
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
        imgui.text(label)
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
                use_single_hand_pose = slot in [
                    "dagger",
                    "mace",
                    "sword",
                    "axe",
                    "spear",
                    "bow",
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

                    draw_list.add_image(
                        ref_preview["tex_id"],
                        (float(char_draw_x), float(char_draw_y)),
                        (
                            float(char_draw_x + ref_preview["width"] * scale),
                            float(char_draw_y + ref_preview["height"] * scale),
                        ),
                    )

                    wep_rel_x = -off_x
                    wep_rel_y = -off_y

                    wep_draw_x = char_draw_x + wep_rel_x * scale
                    wep_draw_y = char_draw_y + wep_rel_y * scale

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
        """显示验证错误"""
        if not errors:
            return
        self.draw_indented_separator()
        imgui.text("消息:")
        for error in errors:
            if error.endswith("):"):
                continue
            content = error.lstrip()
            if content.startswith("• WARNING:"):
                self.text_warning(error)
            elif content.startswith("•"):
                self.text_error(error)
            else:
                self.text_error(f"  • {error}")

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

            print("复制贴图文件...")
            texture_errors = []
            for item in self.project.weapons + self.project.armors:
                errs = copy_item_textures(
                    item_id=item.id,
                    textures=item.textures,
                    sprites_dir=sprites_dir,
                    copy_char=item.needs_char_texture(),
                    copy_left=item.needs_left_texture(),
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
