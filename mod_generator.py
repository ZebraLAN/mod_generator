# -*- coding: utf-8 -*-
"""
Stoneshard 装备模组编辑器 - 主程序

基于 ImGui 的图形界面，用于创建和编辑 Stoneshard 游戏的武器/装备模组。

模块化架构:
- ui/layout.py: 布局系统 (Layout, GridLayout)
- ui/theme.py: 主题系统 (ThemeMixin)
- ui/texture_manager.py: 贴图加载与缓存 (load_texture, unload_all_textures)
- ui/dialogs.py: 对话框模块函数 (file_dialog, new_project_dialog, ...)
- ui/popups.py: 弹窗服务 (popups.error/success/save_prompt)
- ui/menu.py: 主菜单 (MenuMixin)
- ui/item_list.py: 物品列表 (ItemListMixin)
- ui/editors/common.py: 通用编辑器方法 (CommonEditorMixin)
- ui/editors/weapon_editor.py: 武器编辑器 (WeaponEditorMixin)
- ui/editors/armor_editor.py: 装备编辑器 (ArmorEditorMixin)
"""

import os
import sys
from pathlib import Path

import glfw
import imgui  # type: ignore
from imgui.integrations.glfw import GlfwRenderer  # type: ignore
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    glClear,
    glClearColor,
)

from ui.dialogs import open_project_dialog

try:
    from PIL import Image
except ImportError:
    Image = None

# 导入 UI 模块
from ui import config
from ui.state import state as ui_state
from ui.styles import ThemeMixin, apply_preflight
from ui.texture_manager import unload_all_textures
from ui import popups
from ui.menu import MenuMixin, draw_main_menu, get_toolbar_height
from ui.item_list import ItemListMixin
from ui.fonts import load_fonts
from ui.editors.common import CommonEditorMixin
from ui.editors.weapon_editor import WeaponEditorMixin
from ui.editors.armor_editor import ArmorEditorMixin
from ui.editors.hybrid_editor import HybridEditorMixin

# 导入常量和模型
from generator import CodeGenerator, copy_item_textures_v2
from models import (
    Armor,
    ModProject,
    validate_item,
    validate_hybrid_item,
)


# ==================== 工具函数 ====================


def validate_project_for_generation(project: ModProject) -> list[str]:
    """验证项目是否可以生成（独立工具函数）

    Args:
        project: 要验证的模组项目

    Returns:
        错误消息列表，如果为空则验证通过
    """
    errors = []

    # 验证项目本身
    project_errors = project.validate()
    if project_errors:
        errors.extend(project_errors)

    # 验证武器和装备
    for item in project.weapons + project.armors:
        errors.extend(validate_item(item, project))

    # 验证混合物品
    for hybrid in project.hybrid_items:
        errors.extend(validate_hybrid_item(hybrid, project))

    return errors


def generate_mod_files_to_disk(project: ModProject) -> list[str]:
    """生成模组文件到磁盘（独立工具函数）

    将项目中的所有内容（C# 代码、GML 脚本、贴图等）生成到磁盘的模组目录中。

    Args:
        project: 要生成的模组项目

    Returns:
        贴图复制过程中的警告/错误列表

    Raises:
        Exception: 生成过程中的任何错误
    """
    mod_name = project.code_name.strip() or "ModProject"
    base_dir = os.path.dirname(project.file_path)
    mod_dir = Path(base_dir) / mod_name
    sprites_dir = mod_dir / "Sprites"

    print(f"创建目录: {mod_dir}")
    mod_dir.mkdir(exist_ok=True)
    sprites_dir.mkdir(exist_ok=True)

    print("生成 C# 代码...")
    generator = CodeGenerator(project)
    files = generator.generate()
    for filename, content in files.items():
        with open(mod_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)

    print("生成空的 .csproj 文件...")
    with open(mod_dir / f"{mod_name}.csproj", "w", encoding="utf-8"):
        pass

    # 如果有混合物品，生成 Codes 文件夹和 GML 脚本
    if project.hybrid_items:
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
    for item in project.weapons + project.armors:
        # 判断是否为多姿势护甲
        is_multi_pose = (
            isinstance(item, Armor) and item.needs_multi_pose_textures()
        )
        errs = copy_item_textures_v2(
            item_id=item.id,
            textures=item.textures,
            sprites_dir=sprites_dir,
            copy_char=item.needs_char_texture(),
            copy_left=item.needs_left_texture(),
            is_multi_pose_armor=is_multi_pose,
        )
        texture_errors.extend(errs)

    # 复制混合物品贴图
    for hybrid in project.hybrid_items:
        errs = copy_item_textures_v2(
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
    return texture_errors


def generate_mod_and_show_result(project: ModProject) -> None:
    """生成模组并显示结果弹窗

    执行模组生成并通过弹窗显示成功消息或错误信息。

    Args:
        project: 要生成的模组项目
    """
    try:
        generate_mod_files_to_disk(project)
        base_dir = os.path.dirname(project.file_path) if project.file_path else "."
        mod_dir = os.path.abspath(os.path.join(base_dir, project.code_name.strip() or "ModProject"))
        popups.success(mod_dir)
    except Exception as e:
        popups.error(f"生成模组失败:\n{e}")


def generate_mod_with_validation(project: ModProject) -> None:
    """验证并生成模组

    执行项目验证、保存检查，然后生成模组。

    Args:
        project: 要生成的模组项目
    """
    print("开始生成模组...")

    # 验证项目
    validation_errors = validate_project_for_generation(project)
    if validation_errors:
        popups.error("验证失败:\n" + "\n".join(f"  • {e}" for e in validation_errors))
        return

    # 检查是否已保存
    if not project.file_path:
        def save_and_generate():
            if project.file_path:
                project.save()
                generate_mod_and_show_result(project)
        popups.save_prompt(on_confirm=save_and_generate)
        return

    # 执行生成
    generate_mod_and_show_result(project)


# ==================== 主 GUI 类 ====================
# 所有 UI 功能已模块化到 ui/ 目录下的各个模块


class ModGeneratorGUI(
    ThemeMixin,
    MenuMixin,
    ItemListMixin,
    CommonEditorMixin,
    WeaponEditorMixin,
    ArmorEditorMixin,
    HybridEditorMixin,
):
    """主 GUI 类 - 使用 Mixin 模式组合功能

    Mixin 继承顺序决定方法解析顺序 (MRO):
    1. ThemeMixin - 主题和颜色
    2. MenuMixin - 主菜单
    3. ItemListMixin - 物品列表和面板
    4. CommonEditorMixin - 通用编辑器方法
    5. WeaponEditorMixin - 武器编辑器
    6. ArmorEditorMixin - 装备编辑器
    7. HybridEditorMixin - 混合物品编辑器
    8. TextureEditorMixin - 贴图编辑器
    """

    def __init__(self):
        self.window = None

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
        self.renderer = GlfwRenderer(self.window)

        # 初始化 DPI 缩放 (必须在加载字体之前!)
        from ui.state import init_dpi
        init_dpi(self.window)

        # 确保字体目录存在
        os.makedirs("fonts", exist_ok=True)

        # 加载配置
        config.load_from_file()

        # 应用主题和字体
        apply_preflight()
        load_fonts(self.renderer)

        # 项目和状态 - 通过 ui_state 管理
        ui_state.set_project(ModProject())

    # ==================== UI 状态代理属性 ====================
    # 向后兼容: 代理到 ui.state.state

    @property
    def project(self) -> ModProject:
        """向后兼容: 代理到 ui_state.project"""
        return ui_state.project

    @project.setter
    def project(self, value: ModProject) -> None:
        ui_state.set_project(value)

    @property
    def active_item_tab(self) -> int:
        return ui_state.active_item_tab

    @active_item_tab.setter
    def active_item_tab(self, value: int) -> None:
        ui_state.active_item_tab = value

    # ==================== 主循环 ====================

    def run(self):
        """主循环"""
        running = True
        while running:
            if glfw.window_should_close(self.window):
                running = False
            glfw.poll_events()
            self.renderer.process_inputs()

            # 检查配置变更标志 - 在 new_frame 之前处理
            # 注意: 字体重载必须在 new_frame() 之前，且不能在渲染过程中
            try:
                if config.needs_font_reload():
                    config.clear_font_reload_flag()  # 先清标志，避免重复触发
                    load_fonts(self.renderer)
            except Exception as e:
                print(f"[main] 配置更新失败: {e}")
                config.clear_font_reload_flag()

            imgui.new_frame()

            draw_main_menu()
            self.draw_main_interface()

            popups.draw()

            imgui.render()
            glClearColor(0, 0, 0, 1)
            glClear(GL_COLOR_BUFFER_BIT)
            self.renderer.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)

        unload_all_textures()
        self.renderer.shutdown()
        glfw.terminate()

    # 注意: draw_main_menu, _draw_font_menu 方法已移动到 ui/menu.py (MenuMixin)

    # ==================== 主界面 ====================

    def draw_main_interface(self):
        """绘制主界面 - 两栏布局 (导航 + 主编辑区)"""
        from ui.panels import draw_two_column_layout
        from ui.navigator import draw_navigator
        from ui.main_editor import draw_main_editor

        io = imgui.get_io()
        display_w, display_h = io.display_size
        toolbar_height = get_toolbar_height()

        imgui.set_next_window_position(0, toolbar_height)
        imgui.set_next_window_size(display_w, display_h - toolbar_height)

        imgui.begin(
            "Main Interface",
            flags=imgui.WINDOW_NO_RESIZE
            | imgui.WINDOW_NO_MOVE
            | imgui.WINDOW_NO_COLLAPSE
            | imgui.WINDOW_NO_TITLE_BAR,
        )

        if not self.project.file_path:
            # 显示欢迎界面 - 居中布局
            _draw_welcome_screen()
        else:
            # 两栏布局: 导航 | 主编辑区
            draw_two_column_layout(
                draw_navigator=draw_navigator,
                draw_main=lambda w, h: draw_main_editor(w, h, self),
            )

        imgui.end()

        # 注意: draw_item_panel, draw_weapon_list, draw_armor_list, draw_hybrid_list,
        #       _draw_item_list, _generate_unique_id 方法已移动到 ui/item_list.py (ItemListMixin)
        # 注意: draw_weapon_editor 方法已移动到 ui/editors/weapon_editor.py (WeaponEditorMixin)
        # 注意: draw_armor_editor 方法已移动到 ui/editors/armor_editor.py (ArmorEditorMixin)
        # 注意: draw_hybrid_editor 及相关方法已移动到 ui/editors/hybrid_editor.py (HybridEditorMixin)
        # 注意: _draw_textures_editor 及相关方法已移动到 ui/editors/texture_editor.py (TextureEditorMixin)

def _draw_welcome_screen():
    """绘制欢迎界面 - 简洁的单卡片设计

    Tailwind 设计思路:
        - 手动居中计算
        - 单卡片包含所有内容
        - 删除快速指南，保持简洁
    """
    from ui import tw
    from ui import layout as ly
    from ui.icons import FA_FOLDER_OPEN, FA_SWORD, FA_SHIELD, FA_FLASK, FA_PLUS

    # 手动居中计算
    avail = imgui.get_content_region_available()
    card_width = ly.sz(120)  # 480px
    card_height = ly.sz(100)  # 400px (减少高度因为删除了快速指南)

    start_x = (avail.x - card_width) / 2
    start_y = (avail.y - card_height) / 2

    if start_x > 0 and start_y > 0:
        imgui.set_cursor_pos((start_x, start_y))

    # 主卡片 - border 必须为 True 且宽度至少 1 才能使 padding 生效
    with tw.bg_abyss_800 | tw.rounded_xl | tw.p_8 | tw.child_rounded_xl | tw.border_abyss_800 | tw.child_border_size(1):
        imgui.begin_child("welcome_card", width=card_width, height=card_height, border=True)

        # ===== 装饰图标 =====
        with tw.text_crystal_500 | tw.text_xl:
            ly.text_center(f"{FA_SWORD}  {FA_SHIELD}  {FA_FLASK}")

        ly.gap_y(4)

        # ===== 主标题 =====
        with tw.text_parchment_50 | tw.text_2xl:
            ly.text_center("Stoneshard 装备模组编辑器")

        ly.gap_y(2)

        # ===== 副标题 =====
        with tw.text_parchment_400 | tw.text_sm:
            ly.text_center("武器、装备、混合物品模组的可视化创建工具")

        ly.gap_y(8)

        # ===== 分隔线 =====
        _draw_simple_divider()

        ly.gap_y(8)

        # ===== 操作标题 =====
        with tw.text_goldrim_500 | tw.text_lg:
            ly.text_center("开始使用")

        ly.gap_y(6)

        # ===== 按钮组 =====
        with ly.auto_hcenter():
            # 按钮样式 - btn_* 已内置合理的 FramePadding
            if (tw.btn_primary | tw.rounded_lg | tw.btn_md)(imgui.button)(f"{FA_PLUS}  新建项目"):
                from ui import dialogs
                if project := dialogs.new_project_dialog():
                    ui_state.set_project(project)

            ly.same_line(3)

            if (tw.btn_secondary | tw.rounded_lg | tw.border_abyss_600 | tw.frame_border_size(1) | tw.btn_md)(imgui.button)(f"{FA_FOLDER_OPEN}  打开项目"):
                if project := open_project_dialog():
                    ui_state.set_project(project)

        ly.gap_y(8)

        # ===== 底部提示 =====
        with tw.text_parchment_600 | tw.text_xs:
            ly.text_center("项目保存为 JSON 文件 • 贴图和配置统一管理")

        imgui.end_child()


def _draw_simple_divider():
    """绘制简单的分隔线"""
    from ui import tw
    from ui.state import dpi_scale

    draw_list = imgui.get_window_draw_list()
    cursor_screen = imgui.get_cursor_screen_pos()
    avail_width = imgui.get_content_region_available().x

    # 水平线
    center_x = cursor_screen.x + avail_width / 2
    y = cursor_screen.y
    line_width = 100 * dpi_scale()
    line_color = imgui.get_color_u32_rgba(*tw.ABYSS_600)

    draw_list.add_line(
        center_x - line_width / 2, y,
        center_x + line_width / 2, y,
        line_color, 1.0
    )

    imgui.dummy(0, 4)


if __name__ == "__main__":
    app = ModGeneratorGUI()
    app.run()
