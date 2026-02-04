# -*- coding: utf-8 -*-
"""cimgui_py - pyimgui 兼容的 Dear ImGui 绑定

这个包提供与 pyimgui 几乎相同的 API，但基于最新的 cimgui/Dear ImGui，
支持动态字体加载等 pyimgui 缺失的功能。

用法:
    # 替换 pyimgui 的 import
    # 从: import imgui
    # 到: import cimgui_py as imgui
    
    import cimgui_py as imgui
    from cimgui_py.integrations.glfw import GlfwRenderer
    
    # API 完全兼容
    imgui.create_context()
    imgui.button("Click me")
    imgui.text("Hello")
"""

# 版本
__version__ = "0.1.0"

# 尝试导入编译后的核心模块
try:
    from cimgui_py.core import (
        # Context and Frame
        create_context,
        destroy_context,
        get_io,
        get_style,
        new_frame,
        end_frame,
        render,
        get_draw_data,
        
        # Types
        Vec2,
        Vec4,
        
        # Window
        begin,
        end,
        begin_child,
        end_child,
        
        # Widgets: Text
        text,
        text_colored,
        text_disabled,
        text_wrapped,
        bullet_text,
        label_text,
        
        # Widgets: Main
        button,
        small_button,
        invisible_button,
        checkbox,
        radio_button,
        progress_bar,
        bullet,
        image,
        image_button,
        
        # Widgets: Input
        input_text,
        input_text_multiline,
        input_int,
        input_float,
        
        # Widgets: Combo
        begin_combo,
        end_combo,
        selectable,
        
        # Widgets: Slider/Drag
        slider_float,
        slider_int,
        drag_float,
        drag_int,
        
        # Widgets: Trees
        tree_node,
        tree_node_ex,
        tree_pop,
        collapsing_header,
        set_next_item_open,
        
        # Widgets: Tabs
        begin_tab_bar,
        end_tab_bar,
        begin_tab_item,
        end_tab_item,
        
        # Widgets: Tables
        begin_table,
        end_table,
        table_next_row,
        table_next_column,
        table_set_column_index,
        table_setup_column,
        table_headers_row,
        
        # Popups
        begin_popup,
        begin_popup_modal,
        end_popup,
        open_popup,
        close_current_popup,
        begin_popup_context_item,
        begin_popup_context_window,
        is_popup_open,
        
        # Menus
        begin_menu_bar,
        end_menu_bar,
        begin_main_menu_bar,
        end_main_menu_bar,
        begin_menu,
        end_menu,
        menu_item,
        
        # Layout
        separator,
        same_line,
        new_line,
        spacing,
        dummy,
        indent,
        unindent,
        begin_group,
        end_group,
        set_cursor_pos,
        set_cursor_pos_x,
        set_cursor_pos_y,
        get_cursor_pos,
        get_cursor_pos_x,
        get_cursor_pos_y,
        get_cursor_start_pos,
        get_cursor_screen_pos,
        set_cursor_screen_pos,
        align_text_to_frame_padding,
        get_text_line_height,
        get_text_line_height_with_spacing,
        get_frame_height,
        get_frame_height_with_spacing,
        
        # Sizing
        push_item_width,
        pop_item_width,
        set_next_item_width,
        calc_item_width,
        calc_text_size,
        get_content_region_available,
        get_content_region_max,
        get_window_content_region_min,
        get_window_content_region_max,
        
        # Window utilities
        set_next_window_pos,
        set_next_window_size,
        set_next_window_content_size,
        set_next_window_collapsed,
        set_next_window_focus,
        set_next_window_bg_alpha,
        get_window_pos,
        get_window_size,
        get_window_width,
        get_window_height,
        is_window_appearing,
        is_window_collapsed,
        is_window_focused,
        is_window_hovered,
        get_window_draw_list,
        get_foreground_draw_list,
        get_background_draw_list,
        
        # Item utilities
        is_item_hovered,
        is_item_active,
        is_item_focused,
        is_item_clicked,
        is_item_visible,
        is_item_edited,
        is_item_activated,
        is_item_deactivated,
        is_item_deactivated_after_edit,
        is_any_item_hovered,
        is_any_item_active,
        is_any_item_focused,
        get_item_rect_min,
        get_item_rect_max,
        get_item_rect_size,
        set_item_allow_overlap,
        
        # Tooltips
        set_tooltip,
        begin_tooltip,
        end_tooltip,
        
        # Style
        push_style_color,
        pop_style_color,
        push_style_var,
        push_style_var_float,
        push_style_var_vec2,
        pop_style_var,
        get_color_u32,
        get_color_u32_rgba,
        
        # Font
        push_font,
        pop_font,
        get_font,
        get_font_size,
        
        # ID
        push_id,
        pop_id,
        get_id,
        
        # Scrolling
        get_scroll_x,
        get_scroll_y,
        set_scroll_x,
        set_scroll_y,
        get_scroll_max_x,
        get_scroll_max_y,
        set_scroll_here_x,
        set_scroll_here_y,
        
        # Mouse
        is_mouse_down,
        is_mouse_clicked,
        is_mouse_released,
        is_mouse_double_clicked,
        is_mouse_hovering_rect,
        get_mouse_pos,
        is_mouse_dragging,
        get_mouse_drag_delta,
        reset_mouse_drag_delta,
        
        # Keyboard
        is_key_down,
        is_key_pressed,
        is_key_released,
        
        # Clipboard
        get_clipboard_text,
        set_clipboard_text,
        
        # Constants - Colors
        COLOR_TEXT,
        COLOR_TEXT_DISABLED,
        COLOR_WINDOW_BACKGROUND,
        COLOR_CHILD_BACKGROUND,
        COLOR_POPUP_BACKGROUND,
        COLOR_BORDER,
        COLOR_BORDER_SHADOW,
        COLOR_FRAME_BACKGROUND,
        COLOR_FRAME_BACKGROUND_HOVERED,
        COLOR_FRAME_BACKGROUND_ACTIVE,
        COLOR_TITLE_BACKGROUND,
        COLOR_TITLE_BACKGROUND_ACTIVE,
        COLOR_TITLE_BACKGROUND_COLLAPSED,
        COLOR_MENUBAR_BACKGROUND,
        COLOR_SCROLLBAR_BACKGROUND,
        COLOR_SCROLLBAR_GRAB,
        COLOR_SCROLLBAR_GRAB_HOVERED,
        COLOR_SCROLLBAR_GRAB_ACTIVE,
        COLOR_CHECK_MARK,
        COLOR_SLIDER_GRAB,
        COLOR_SLIDER_GRAB_ACTIVE,
        COLOR_BUTTON,
        COLOR_BUTTON_HOVERED,
        COLOR_BUTTON_ACTIVE,
        COLOR_HEADER,
        COLOR_HEADER_HOVERED,
        COLOR_HEADER_ACTIVE,
        COLOR_SEPARATOR,
        COLOR_SEPARATOR_HOVERED,
        COLOR_SEPARATOR_ACTIVE,
        COLOR_RESIZE_GRIP,
        COLOR_RESIZE_GRIP_HOVERED,
        COLOR_RESIZE_GRIP_ACTIVE,
        COLOR_TAB,
        COLOR_TAB_HOVERED,
        COLOR_TAB_ACTIVE,
        COLOR_TAB_UNFOCUSED,
        COLOR_TAB_UNFOCUSED_ACTIVE,
        COLOR_COUNT,
        
        # Constants - Style variables
        STYLE_ALPHA,
        STYLE_DISABLED_ALPHA,
        STYLE_WINDOW_PADDING,
        STYLE_WINDOW_ROUNDING,
        STYLE_WINDOW_BORDER_SIZE,
        STYLE_WINDOW_MIN_SIZE,
        STYLE_WINDOW_TITLE_ALIGN,
        STYLE_CHILD_ROUNDING,
        STYLE_CHILD_BORDER_SIZE,
        STYLE_POPUP_ROUNDING,
        STYLE_POPUP_BORDER_SIZE,
        STYLE_FRAME_PADDING,
        STYLE_FRAME_ROUNDING,
        STYLE_FRAME_BORDER_SIZE,
        STYLE_ITEM_SPACING,
        STYLE_ITEM_INNER_SPACING,
        STYLE_INDENT_SPACING,
        STYLE_CELL_PADDING,
        STYLE_SCROLLBAR_SIZE,
        STYLE_SCROLLBAR_ROUNDING,
        STYLE_GRAB_MIN_SIZE,
        STYLE_GRAB_ROUNDING,
        STYLE_TAB_ROUNDING,
        STYLE_BUTTON_TEXT_ALIGN,
        STYLE_SELECTABLE_TEXT_ALIGN,
        
        # Constants - Window flags
        WINDOW_NONE,
        WINDOW_NO_TITLE_BAR,
        WINDOW_NO_RESIZE,
        WINDOW_NO_MOVE,
        WINDOW_NO_SCROLLBAR,
        WINDOW_NO_SCROLL_WITH_MOUSE,
        WINDOW_NO_COLLAPSE,
        WINDOW_ALWAYS_AUTO_RESIZE,
        WINDOW_NO_BACKGROUND,
        WINDOW_NO_SAVED_SETTINGS,
        WINDOW_NO_MOUSE_INPUTS,
        WINDOW_MENU_BAR,
        WINDOW_HORIZONTAL_SCROLLING_BAR,
        WINDOW_NO_FOCUS_ON_APPEARING,
        WINDOW_NO_BRING_TO_FRONT_ON_FOCUS,
        WINDOW_ALWAYS_VERTICAL_SCROLLBAR,
        WINDOW_ALWAYS_HORIZONTAL_SCROLLBAR,
        WINDOW_ALWAYS_USE_WINDOW_PADDING,
        WINDOW_NO_NAV_INPUTS,
        WINDOW_NO_NAV_FOCUS,
        WINDOW_UNSAVED_DOCUMENT,
        WINDOW_NO_NAV,
        WINDOW_NO_DECORATION,
        WINDOW_NO_INPUTS,
        
        # Constants - Hovered flags
        HOVERED_NONE,
        HOVERED_CHILD_WINDOWS,
        HOVERED_ROOT_WINDOW,
        HOVERED_ANY_WINDOW,
        HOVERED_ALLOW_WHEN_BLOCKED_BY_POPUP,
        HOVERED_ALLOW_WHEN_BLOCKED_BY_ACTIVE_ITEM,
        HOVERED_ALLOW_WHEN_OVERLAPPED,
        HOVERED_ALLOW_WHEN_DISABLED,
        HOVERED_RECT_ONLY,
    )
    
    _COMPILED = True
    
except ImportError as e:
    _COMPILED = False
    _IMPORT_ERROR = str(e)
    
    def _not_compiled(*args, **kwargs):
        raise ImportError(
            f"cimgui_py 尚未编译。请运行: cd cimgui_py && pip install -e .\n"
            f"原始错误: {_IMPORT_ERROR}"
        )
    
    # 占位函数
    create_context = _not_compiled
    button = _not_compiled
    text = _not_compiled


# core 子模块 - 兼容 pyimgui 的 imgui.core.FontConfig 等
class core:
    """兼容 pyimgui 的 imgui.core 模块"""
    
    class FontConfig:
        """字体配置 - 兼容 pyimgui"""
        def __init__(self, merge_mode=False, **kwargs):
            self.merge_mode = merge_mode
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class GlyphRanges:
        """字形范围 - 兼容 pyimgui"""
        def __init__(self, ranges):
            self.ranges = list(ranges)
        
        def __iter__(self):
            return iter(self.ranges)

