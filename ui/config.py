# -*- coding: utf-8 -*-
"""UI 配置管理

全局 UI 配置状态，包括字体缩放等设置。
"""

import json
import os

# ==================== 配置状态 ====================

_font_scale: float = 1.0  # 全局字体缩放
_needs_font_reload: bool = False


# ==================== Font Scale ====================


def get_font_scale() -> float:
    """获取全局字体缩放因子"""
    return _font_scale


def set_font_scale(scale: float) -> None:
    """设置全局字体缩放 (需要重载字体)"""
    global _font_scale, _needs_font_reload
    if _font_scale != scale:
        _font_scale = max(0.5, min(2.0, scale))  # 限制范围
        _needs_font_reload = True


# ==================== 重载标志 ====================


def needs_font_reload() -> bool:
    """检查是否需要重载字体"""
    return _needs_font_reload


def clear_font_reload_flag() -> None:
    """清除字体重载标志"""
    global _needs_font_reload
    _needs_font_reload = False


# ==================== 配置文件 ====================

DEFAULT_CONFIG_PATH = "config.json"


def load_from_file(path: str = DEFAULT_CONFIG_PATH) -> None:
    """从文件加载配置"""
    global _font_scale

    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _font_scale = data.get("font_scale", 1.0)
    except Exception as e:
        print(f"加载配置失败: {e}")


def save_to_file(path: str = DEFAULT_CONFIG_PATH) -> None:
    """保存配置到文件"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"font_scale": _font_scale}, f, indent=4)
    except Exception as e:
        print(f"保存配置失败: {e}")
