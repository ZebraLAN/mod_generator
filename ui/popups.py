# -*- coding: utf-8 -*-
"""弹窗服务 - 模块即单例

使用方式:
    from ui import popups
    popups.error("发生错误")
    popups.success("/path/to/mod")
    popups.save_prompt(on_confirm=my_callback)

主循环中调用 popups.draw()
"""

import os
from typing import Callable

import imgui

from ui.styles import text_error, text_secondary, text_success, text_warning


# ==================== 模块级状态 ====================

_error_msg: str | None = None
_success_dir: str | None = None
_save_callback: Callable[[], None] | None = None


# ==================== 公开 API ====================


def error(message: str) -> None:
    """显示错误弹窗"""
    global _error_msg
    print(f"错误: {message.split(chr(10))[0]}")
    _error_msg = message
    imgui.open_popup("错误")


def success(mod_dir: str) -> None:
    """显示生成成功弹窗"""
    global _success_dir
    _success_dir = mod_dir
    imgui.open_popup("生成成功")


def save_prompt(on_confirm: Callable[[], None] | None = None) -> None:
    """显示保存确认弹窗"""
    global _save_callback
    _save_callback = on_confirm
    imgui.open_popup("保存项目")


def draw() -> None:
    """绘制弹窗（主循环每帧调用）"""
    _draw_error_popup()
    _draw_success_popup()
    _draw_save_popup()


# ==================== 内部实现 ====================


def _draw_error_popup() -> None:
    global _error_msg
    imgui.set_next_window_size(450, 0, imgui.ONCE)
    if imgui.begin_popup_modal("错误", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
        imgui.dummy(0, 4)
        text_error("[X] 发生错误")
        imgui.dummy(0, 8)
        imgui.text_wrapped(_error_msg or "发生未知错误")
        imgui.dummy(0, 12)

        button_width = 80
        imgui.set_cursor_pos_x(imgui.get_window_width() - button_width - 12)
        if imgui.button("确定", width=button_width):
            _error_msg = None
            imgui.close_current_popup()
        imgui.end_popup()


def _draw_success_popup() -> None:
    global _success_dir
    imgui.set_next_window_size(450, 180, imgui.ONCE)
    if imgui.begin_popup_modal("生成成功", flags=imgui.WINDOW_NO_RESIZE)[0]:
        mod_dir = _success_dir or "."

        imgui.dummy(0, 8)
        text_success("[OK] 模组生成成功！")
        imgui.dummy(0, 8)

        text_secondary("输出目录:")
        imgui.text_wrapped(mod_dir)

        imgui.dummy(0, 16)

        button_width = 100
        imgui.set_cursor_pos_x(imgui.get_window_width() - button_width * 2 - 24)
        if imgui.button("打开目录", width=button_width):
            try:
                os.startfile(mod_dir)
            except Exception:
                pass

        imgui.same_line()
        if imgui.button("确定", width=button_width):
            _success_dir = None
            imgui.close_current_popup()
        imgui.end_popup()


def _draw_save_popup() -> None:
    global _save_callback
    imgui.set_next_window_size(350, 0, imgui.ONCE)
    if imgui.begin_popup_modal("保存项目", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
        imgui.dummy(0, 4)
        text_warning("[!] 需要保存项目")
        imgui.dummy(0, 8)
        imgui.text("生成模组前需要先保存项目。")
        imgui.text("是否现在保存？")
        imgui.dummy(0, 12)

        button_width = 80
        imgui.set_cursor_pos_x(imgui.get_window_width() - button_width * 2 - 20)
        if imgui.button("保存", width=button_width):
            callback = _save_callback
            _save_callback = None
            imgui.close_current_popup()
            if callback:
                callback()

        imgui.same_line()
        if imgui.button("取消", width=button_width):
            _save_callback = None
            imgui.close_current_popup()

        imgui.end_popup()
