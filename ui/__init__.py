# -*- coding: utf-8 -*-
"""UI 模块 - Stoneshard 装备模组编辑器

使用惰性加载优化启动性能。子模块在首次访问时才导入。

模块结构：
- styles.py: 核心样式系统 (StyleContext, 颜色/尺寸函数, ThemeMixin)
- tw.py: Tailwind-style tokens (bg_slate_800, text_white, p_4, ...)
- config.py: 全局配置状态 (get_font_scale, ...)
- grid.py: 布局工具 (GridLayout, item_width, tooltip)
- fonts.py: 字体管理 (load_fonts, 字体路径常量)
- texture_manager.py: 贴图加载与缓存
- dialogs.py: 对话框模块函数
- popups.py: 弹窗服务
- menu.py: 主菜单 (MenuMixin)
- item_list.py: 物品列表 (ItemListMixin)
- protocols.py: 类型协议 (GUIProtocol)

[已废弃，保留向后兼容]:
- style.py: 旧 Primer token 系统 → 使用 tw.py
- sizing.py: 尺寸常量 → 已合并到 styles.py
- theme.py: 主题 Mixin → 已合并到 styles.py

使用方式：
    from ui import tw
    with tw.bg_slate_800 | tw.text_white | tw.p_4:
        imgui.text("Hello!")
"""

from typing import TYPE_CHECKING

# =============================================================================
# 惰性加载映射
# =============================================================================
# 模块名 -> 导入路径
_LAZY_MODULES = {
    'config': 'ui.config',
    'style': 'ui.style',      # [已废弃] 保留向后兼容
    'styles': 'ui.styles',
    'tw': 'ui.tw',            # Tailwind-style tokens
    'sizing': 'ui.sizing',    # [已废弃] 保留向后兼容
    'grid': 'ui.grid',
    'theme': 'ui.theme',      # [已废弃] 保留向后兼容
    'fonts': 'ui.fonts',
    'texture_manager': 'ui.texture_manager',
    'menu': 'ui.menu',
    'item_list': 'ui.item_list',
    'popups': 'ui.popups',
    'dialogs': 'ui.dialogs',
    'components': 'ui.components',  # Styled UI components
}

# 属性名 -> (模块路径, 属性名)
# 现在从 styles.py 导入 sizing 和 theme 相关内容
_LAZY_ATTRS = {
    # sizing 常量和函数 (从 styles.py 导入)
    'em': ('ui.styles', 'em'),
    'span': ('ui.styles', 'span'),
    'INPUT_XS': ('ui.styles', 'INPUT_XS'),
    'INPUT_S': ('ui.styles', 'INPUT_S'),
    'INPUT_M': ('ui.styles', 'INPUT_M'),
    'INPUT_L': ('ui.styles', 'INPUT_L'),
    'INPUT_XL': ('ui.styles', 'INPUT_XL'),
    'GRID_COL': ('ui.styles', 'GRID_COL'),
    'GRID_GAP': ('ui.styles', 'GRID_GAP'),
    'GRID_DEBUG': ('ui.styles', 'GRID_DEBUG'),
    'SPAN_INPUT': ('ui.styles', 'SPAN_INPUT'),
    'SPAN_BADGE': ('ui.styles', 'SPAN_BADGE'),
    'SPAN_ID': ('ui.styles', 'SPAN_ID'),
    'GAP_XS': ('ui.styles', 'GAP_XS'),
    'GAP_S': ('ui.styles', 'GAP_S'),
    'GAP_M': ('ui.styles', 'GAP_M'),
    'GAP_L': ('ui.styles', 'GAP_L'),
    'input_xs': ('ui.styles', 'input_xs'),
    'input_s': ('ui.styles', 'input_s'),
    'input_m': ('ui.styles', 'input_m'),
    'input_l': ('ui.styles', 'input_l'),
    'input_xl': ('ui.styles', 'input_xl'),
    'grid_col': ('ui.styles', 'grid_col'),
    'grid_gap': ('ui.styles', 'grid_gap'),
    'gap_xs': ('ui.styles', 'gap_xs'),
    'gap_s': ('ui.styles', 'gap_s'),
    'gap_m': ('ui.styles', 'gap_m'),
    'gap_l': ('ui.styles', 'gap_l'),
    # grid
    'GridLayout': ('ui.grid', 'GridLayout'),
    'item_width': ('ui.grid', 'item_width'),
    'tooltip': ('ui.grid', 'tooltip'),
    # fonts
    'load_fonts': ('ui.fonts', 'load_fonts'),
    # theme (从 styles.py 导入)
    'ThemeMixin': ('ui.styles', 'ThemeMixin'),
    'text_secondary': ('ui.styles', 'text_secondary'),
    'text_success': ('ui.styles', 'text_success'),
    'text_warning': ('ui.styles', 'text_warning'),
    'text_error': ('ui.styles', 'text_error'),
    'text_accent': ('ui.styles', 'text_accent'),
    'get_current_theme_colors': ('ui.styles', 'get_current_theme_colors'),
    'apply_global_style': ('ui.styles', 'apply_global_style'),
    # menu
    'MenuMixin': ('ui.menu', 'MenuMixin'),
    # item_list
    'ItemListMixin': ('ui.item_list', 'ItemListMixin'),
    # texture_manager
    'load_texture': ('ui.texture_manager', 'load_texture'),
    'unload_all_textures': ('ui.texture_manager', 'unload_all_textures'),
    'draw_checkerboard': ('ui.texture_manager', 'draw_checkerboard'),
}

# 已加载的缓存
_loaded_modules: dict = {}
_loaded_attrs: dict = {}


def __getattr__(name: str):
    """惰性加载模块和属性

    Python 3.7+ 模块级 __getattr__，在访问未定义属性时调用。
    """
    # 先检查模块
    if name in _LAZY_MODULES:
        if name not in _loaded_modules:
            import importlib
            _loaded_modules[name] = importlib.import_module(_LAZY_MODULES[name])
        return _loaded_modules[name]

    # 再检查属性
    if name in _LAZY_ATTRS:
        if name not in _loaded_attrs:
            import importlib
            module_path, attr_name = _LAZY_ATTRS[name]
            module = importlib.import_module(module_path)
            _loaded_attrs[name] = getattr(module, attr_name)
        return _loaded_attrs[name]

    raise AttributeError(f"module 'ui' has no attribute {name!r}")


def __dir__():
    """支持自动补全"""
    return list(_LAZY_MODULES.keys()) + list(_LAZY_ATTRS.keys())


# 类型协议（仅用于类型检查，不影响运行时）
if TYPE_CHECKING:
    from ui.protocols import GUIProtocol
    from ui import config as config
    from ui import styles as styles
    from ui.styles import (
        em as em, span as span,
        INPUT_XS as INPUT_XS, INPUT_S as INPUT_S, INPUT_M as INPUT_M,
        INPUT_L as INPUT_L, INPUT_XL as INPUT_XL,
        GRID_COL as GRID_COL, GRID_GAP as GRID_GAP, GRID_DEBUG as GRID_DEBUG,
        SPAN_INPUT as SPAN_INPUT, SPAN_BADGE as SPAN_BADGE, SPAN_ID as SPAN_ID,
        GAP_XS as GAP_XS, GAP_S as GAP_S, GAP_M as GAP_M, GAP_L as GAP_L,
        input_xs as input_xs, input_s as input_s, input_m as input_m,
        input_l as input_l, input_xl as input_xl,
        grid_col as grid_col, grid_gap as grid_gap,
        gap_xs as gap_xs, gap_s as gap_s, gap_m as gap_m, gap_l as gap_l,
        ThemeMixin as ThemeMixin,
        text_secondary as text_secondary, text_success as text_success,
        text_warning as text_warning, text_error as text_error,
        text_accent as text_accent, get_current_theme_colors as get_current_theme_colors,
        apply_global_style as apply_global_style,
    )
    from ui.grid import GridLayout as GridLayout, item_width as item_width, tooltip as tooltip
    from ui.fonts import load_fonts as load_fonts
    from ui.texture_manager import (
        load_texture as load_texture,
        unload_all_textures as unload_all_textures,
        draw_checkerboard as draw_checkerboard,
    )
    from ui.menu import MenuMixin as MenuMixin
    from ui.item_list import ItemListMixin as ItemListMixin


__all__ = [
    # 子模块
    'config', 'styles', 'tw', 'grid', 'fonts',
    'texture_manager', 'menu', 'item_list', 'popups', 'dialogs',
    # sizing 常量
    'INPUT_XS', 'INPUT_S', 'INPUT_M', 'INPUT_L', 'INPUT_XL',
    'GRID_COL', 'GRID_GAP', 'GRID_DEBUG',
    'SPAN_INPUT', 'SPAN_BADGE', 'SPAN_ID',
    'GAP_XS', 'GAP_S', 'GAP_M', 'GAP_L',
    # sizing 函数
    'em', 'span',
    'input_xs', 'input_s', 'input_m', 'input_l', 'input_xl',
    'grid_col', 'grid_gap',
    'gap_xs', 'gap_s', 'gap_m', 'gap_l',
    # grid
    'GridLayout', 'item_width', 'tooltip',
    # fonts
    'load_fonts',
    # theme (从 styles.py)
    'ThemeMixin', 'text_secondary', 'text_success', 'text_warning',
    'text_error', 'text_accent', 'get_current_theme_colors', 'apply_global_style',
    # Mixins
    'MenuMixin', 'ItemListMixin',
    # texture_manager
    'load_texture', 'unload_all_textures', 'draw_checkerboard',
]
