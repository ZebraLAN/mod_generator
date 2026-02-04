# -*- coding: utf-8 -*-
"""字体管理服务

集中管理字体路径、加载逻辑和可用字体列表。
从 ui.config 和 ui.state 获取配置，支持多字号预加载和图标字体合并。

架构:
    - 预加载 typography tokens 中定义的所有字号
    - 每个字号同时包含: 英文 + 中文 + 图标
    - 字号应用 DPI 缩放和 CJK/Latin scale
    - 返回字体映射表供 UI 层按需切换

字号命名 (与 style.text 一致):
    xs  = 12px  说明文字、caption
    sm  = 14px  正文 (默认)
    md  = 16px  大正文
    lg  = 20px  标题
    xl  = 32px  大标题
    2xl = 40px  超大标题 (未预加载)

使用方式:
    from ui import fonts, style

    # 初始化时加载
    font_map = fonts.load_fonts(renderer)

    # 渲染时切换字号
    imgui.push_font(font_map["sm"])  # 或 fonts.get_font("sm")
    imgui.text("Hello 你好")
    imgui.pop_font()

    # 获取对应字号的像素值 (已应用 DPI)
    size = style.text.sm()  # 14.0 * dpi_scale
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import imgui  # type: ignore

from ui import config
from ui.state import dpi_scale

if TYPE_CHECKING:
    pass  # 预留类型导入


# ==================== 字号常量 ====================

# Tailwind CSS v3.4.17 字号 (px)
# Source: https://tailwindcss.com/docs/font-size
FONT_SIZES: dict[str, float] = {
    "xs": 12.0,     # 0.75rem - caption, hints
    "sm": 14.0,     # 0.875rem - small text
    "base": 16.0,   # 1rem - body text (DEFAULT)
    "lg": 18.0,     # 1.125rem - large body
    "xl": 20.0,     # 1.25rem - heading
    "2xl": 24.0,    # 1.5rem - h3
    "3xl": 30.0,    # 1.875rem - h2
    "4xl": 36.0,    # 2.25rem - h1
    "5xl": 48.0,    # 3rem - display
    "6xl": 60.0,    # 3.75rem - hero
    "7xl": 72.0,    # 4.5rem
    "8xl": 96.0,    # 6rem
    "9xl": 128.0,   # 8rem
}

# 别名: md = base (向后兼容)
FONT_SIZES["md"] = FONT_SIZES["base"]


# ==================== 从生成配置导入 ====================
# 字体路径和 baseline 偏移由 codegen/generate_font_config.py 自动测定
# 修改字体请编辑 codegen 中的 FONT_PATHS，然后运行 python codegen/generate_font_config.py

from ui.font_config import (
    ENGLISH_FONT,
    CHINESE_FONT,
    ICON_FONT,
    BASE_FONT_SIZE,
    CHINESE_GLYPH_OFFSET_Y,
    ICON_GLYPH_OFFSET_Y,
    ICON_SCALE,
    ICON_RANGE_START,
    ICON_RANGE_END,
)


# ==================== 额外符号范围 ====================
# 这些符号会合并到中文字体中，解决 GB2312 不包含的常用符号

EXTRA_SYMBOL_RANGES: list[int] = [
    # 拉丁扩展 (欧洲语言常用)
    0x0100, 0x017F,  # Latin Extended-A (Ā ā Ē ē Ī ī Ō ō Ū ū)
    # 通用标点
    0x2000, 0x206F,  # General Punctuation (— – … ′ ″ ‰ ※)
    # 上标下标
    0x2070, 0x209F,  # Superscripts/Subscripts (⁰ ¹ ² ³ ⁴ ₀ ₁ ₂)
    # 货币符号
    0x20A0, 0x20CF,  # Currency Symbols (€ ₤ ₩ ₪ ₹)
    # 箭头
    0x2190, 0x21FF,  # Arrows (← ↑ → ↓ ↔ ↕ ⇒ ⇔)
    # 数学运算符
    0x2200, 0x22FF,  # Mathematical Operators (∀ ∃ ∅ ∈ ∉ ≤ ≥ ≠ ≈)
    # 制表符
    0x2500, 0x257F,  # Box Drawing (─ │ ┌ ┐ └ ┘ ├ ┤)
    # 方块元素
    0x2580, 0x259F,  # Block Elements (▀ ▄ █ ░ ▒ ▓)
    # 几何形状
    0x25A0, 0x25FF,  # Geometric Shapes (■ □ ▲ △ ● ○ ◆ ◇)
    # 杂项符号
    0x2600, 0x26FF,  # Miscellaneous Symbols (☀ ☁ ☂ ★ ☆ ☎ ♠ ♥ ♦ ♣)
    # Dingbats
    0x2700, 0x27BF,  # Dingbats (✓ ✔ ✕ ✖ ✗ ✘ ✙ ✚)
    # CJK 符号和标点
    0x3000, 0x303F,  # CJK Symbols and Punctuation (、。〈 〉《 》「 」『 』)
    # 带圈数字
    0x2460, 0x24FF,  # Enclosed Alphanumerics (① ② ③ ④ ⑤ Ⓐ Ⓑ Ⓒ)
    # 终止符
    0,
]

# Stoneshard/游戏相关的额外汉字 (GB2312 可能不包含的)
# 可以根据需要添加
EXTRA_CJK_CHARS: str = (
    # 生僻字 (如果游戏里有用到)
    "鑫焱淼"
    # 可继续添加...
)


# ==================== CJK 字符集配置 ====================
# 控制加载多少中文字符，影响启动速度和字体纹理大小
#
# 字符集大小对照:
#   - "minimal":  ~3000 字 (通用规范汉字表一级字 + 常用标点) - 最快
#   - "standard": ~6000 字 (通用规范汉字表一二级) - 推荐
#   - "full":     ~8000 字 (CJK 基本区常用部分) - 覆盖最广
#
# 性能参考 (2 字号, DPI=1.5):
#   - minimal:  ~0.8-1.0 秒
#   - standard: ~1.2-1.5 秒
#   - full:     ~1.8-2.2 秒

CJK_CHARSET: str = "standard"  # "minimal" | "standard" | "full"

# CJK 字符范围定义
CJK_RANGES: dict[str, list[int]] = {
    # 最小集: 通用规范汉字表一级字 (~3500字)
    # 覆盖 99.48% 日常用字
    "minimal": [
        0x4E00, 0x9FA5,  # 只加载常用部分，依靠字体本身过滤
        0,  # 终止符
    ],
    # 标准集: 通用规范汉字表一二级 (~6500字)
    # 覆盖 99.99% 日常用字
    "standard": [
        0x4E00, 0x9FA5,  # CJK 统一汉字基本区常用部分
        0,  # 终止符
    ],
    # 完整集: CJK 基本区全部 (~20000字)
    # 包括生僻字、古汉语用字
    "full": [
        0x4E00, 0x9FFF,  # CJK 统一汉字基本区
        0,  # 终止符
    ],
}


# ==================== 字号预设 ====================

# 预加载的字号 - 只加载最常用的 2 个以加快启动速度
# 注意: ImGui 需要将所有字形烘焙到纹理，字号越多纹理越大
# 2 个字号 + CJK 常用字符集 是启动速度和功能的平衡点
# ⚠️ 顺序重要：ImGui 以第一个加载的字体为默认字体
#
# 性能参考 (4K DPI=1.5, ~6000 CJK 字符):
#   - 4 字号: ~3-4 秒
#   - 2 字号: ~1.5-2 秒
PRELOAD_SIZES: list[str] = [
    "base",  # 16px - body (DEFAULT) ← 必须第一个！
    "sm",    # 14px - small text, captions
    # 以下字号被移除以加快启动，会回退到 base:
    # "lg",  # 18px - large body, emphasis
    # "xl",  # 20px - headings
]

# 默认字号 (Tailwind 默认 = base = 16px)
DEFAULT_SIZE_TOKEN = "base"


# ==================== 字体映射 ====================

@dataclass
class FontSet:
    """一组字号的字体引用

    只预加载 2 个常用字号以加快启动速度，其他字号回退到最接近的字号。
    如需更多字号，可在 PRELOAD_SIZES 中添加，但会增加启动时间。
    """
    sm: Any = None     # 14px
    base: Any = None   # 16px (DEFAULT)
    lg: Any = None     # 18px (回退到 base)
    xl: Any = None     # 20px (回退到 base)

    # 别名
    @property
    def md(self) -> Any:
        """md = base (向后兼容)"""
        return self.base

    @property
    def xs(self) -> Any:
        """回退到 sm"""
        return self.sm

    def get(self, size: str) -> Any:
        """按 token 获取字体，不存在则回退"""
        # 直接尝试获取
        font = getattr(self, size, None)
        if font is not None:
            return font

        # 回退逻辑: 大字号回退到 xl，小字号回退到 sm
        if size in ("2xl", "3xl", "4xl", "5xl", "6xl", "7xl", "8xl", "9xl"):
            return self.xl
        if size == "xs":
            return self.sm

        return self.base

    def __getitem__(self, size: str) -> Any:
        """支持字典访问: font_map["sm"]"""
        return self.get(size)

    def default(self) -> Any:
        """获取默认字体 (base = 16px)"""
        return self.base


# 全局字体集 (load_fonts 后可用)
_fonts: FontSet | None = None


def get_fonts() -> FontSet:
    """获取已加载的字体集"""
    if _fonts is None:
        raise RuntimeError("Fonts not loaded. Call load_fonts() first.")
    return _fonts


def get_font(size: str = "sm") -> Any:
    """获取指定字号的字体

    Args:
        size: 字号，可以是:
            - 简写: "xs", "sm", "md", "lg", "xl"
            - 完整 token: "base.text.size.sm"

    Returns:
        ImGui 字体对象
    """
    return get_fonts().get(size)


# ==================== 字体工具函数 ====================


def _compute_glyph_offset(base_offset: float, font_size: float) -> float:
    """计算实际的 glyph offset (按字号比例缩放)

    Args:
        base_offset: 基准字号 (16px) 下的 offset
        font_size: 实际字号

    Returns:
        缩放后的 offset
    """
    return base_offset * (font_size / BASE_FONT_SIZE)


# ==================== 字体加载 ====================


def _compute_font_size(token: str) -> float:
    """计算实际字号 (应用 DPI 和全局 scale)

    Args:
        token: 字号 token

    Returns:
        像素值
    """
    base_size = FONT_SIZES.get(token, 14.0)
    dpi = dpi_scale()
    return base_size * dpi * config.get_font_scale()


def _load_font_for_size(
    io: Any,
    size_token: str,
    en_path: str,
    cn_path: str,
    icon_path: str,
) -> Any:
    """加载单个字号的完整字体 (英文 + 中文 + 图标)

    使用 font_config.py 中的 glyph_offset 补偿 baseline 差异。

    返回字体对象 (第一个加载的字体)
    """
    font = None
    font_size = _compute_font_size(size_token)

    # 计算各字体的 glyph offset (按字号比例缩放)
    cn_offset_y = _compute_glyph_offset(CHINESE_GLYPH_OFFSET_Y, font_size)
    icon_offset_y = _compute_glyph_offset(ICON_GLYPH_OFFSET_Y, font_size)

    # 1. 英文字体 (主字体，决定 baseline)
    if en_path:
        try:
            font = io.fonts.add_font_from_file_ttf(en_path, font_size)

            # 1b. 额外符号范围 (从英文字体合并)
            # 包括: 箭头、数学符号、几何形状、制表符等
            # 使用英文字体确保符号宽度一致性
            extra_cfg = imgui.core.FontConfig(
                merge_mode=True,
                glyph_offset_y=0,  # 英文字体不需要 baseline 补偿
            )
            extra_ranges = imgui.core.GlyphRanges(EXTRA_SYMBOL_RANGES)
            io.fonts.add_font_from_file_ttf(
                en_path,
                font_size,
                font_config=extra_cfg,
                glyph_ranges=extra_ranges,
            )
        except Exception as e:
            print(f"[fonts] 英文字体加载失败 ({size_token}): {e}")

    if font is None:
        font = io.fonts.add_font_default()

    # 2. 中文字体 (合并模式，带 baseline 补偿)
    if cn_path:
        try:
            # 使用 glyph_offset_y 补偿 baseline 差异
            font_cfg = imgui.core.FontConfig(
                merge_mode=True,
                glyph_offset_y=cn_offset_y,
            )
            # 使用配置的 CJK 字符集
            cjk_range = CJK_RANGES.get(CJK_CHARSET, CJK_RANGES["standard"])
            ranges = imgui.core.GlyphRanges(cjk_range)
            io.fonts.add_font_from_file_ttf(
                cn_path,
                font_size,
                font_config=font_cfg,
                glyph_ranges=ranges,
            )

            # 2c. 额外 CJK 字符 (GB2312 不包含的)
            if EXTRA_CJK_CHARS:
                cjk_cfg = imgui.core.FontConfig(
                    merge_mode=True,
                    glyph_offset_y=cn_offset_y,
                )
                # 构建字符码点列表
                cjk_codepoints = []
                for char in EXTRA_CJK_CHARS:
                    cp = ord(char)
                    cjk_codepoints.extend([cp, cp])  # 单字符范围
                cjk_codepoints.append(0)  # 终止符
                cjk_ranges = imgui.core.GlyphRanges(cjk_codepoints)
                io.fonts.add_font_from_file_ttf(
                    cn_path,
                    font_size,
                    font_config=cjk_cfg,
                    glyph_ranges=cjk_ranges,
                )
        except Exception as e:
            print(f"[fonts] 中文字体加载失败 ({size_token}): {e}")

    # 3. 图标字体 (合并模式，带 baseline 补偿和缩放)
    # 参考: https://github.com/ocornut/imgui/issues/1869
    if icon_path:
        try:
            icon_size = font_size * ICON_SCALE
            icon_cfg = imgui.core.FontConfig(
                merge_mode=True,
                pixel_snap_h=True,
                glyph_offset_y=icon_offset_y,
                glyph_min_advance_x=icon_size,  # 等宽，保证图标对齐
            )
            icon_ranges = imgui.core.GlyphRanges([ICON_RANGE_START, ICON_RANGE_END, 0])
            io.fonts.add_font_from_file_ttf(
                icon_path,
                icon_size,
                font_config=icon_cfg,
                glyph_ranges=icon_ranges,
            )
        except Exception as e:
            print(f"[fonts] 图标字体加载失败 ({size_token}): {e}")

    return font


def load_fonts(renderer: Any) -> FontSet:
    """加载所有预设字号的字体

    使用 font_config.py 中的配置（由 codegen 生成）。
    预加载所有 typography token 定义的字号。

    Args:
        renderer: GlfwRenderer 实例

    Returns:
        FontSet 包含所有字号的字体引用
    """
    global _fonts

    io = imgui.get_io()
    io.fonts.clear()

    # 字体纹理尺寸
    # 4 个字号 + GB2312 字符集 = 4096 足够
    io.fonts.texture_desired_width = 4096

    # 使用 font_config.py 中的固定路径
    en_path = ENGLISH_FONT if os.path.exists(ENGLISH_FONT) else ""
    cn_path = CHINESE_FONT if os.path.exists(CHINESE_FONT) else ""
    icon_path = ICON_FONT if os.path.exists(ICON_FONT) else ""

    if not en_path:
        print(f"[fonts] 警告: 未找到英文字体 {ENGLISH_FONT}，使用默认字体")
    if not cn_path:
        print(f"[fonts] 警告: 未找到中文字体 {CHINESE_FONT}")
    if not icon_path:
        print(f"[fonts] 警告: 未找到图标字体 {ICON_FONT}")

    # 加载每个字号
    fonts = FontSet()
    for size_name in PRELOAD_SIZES:
        font = _load_font_for_size(io, size_name, en_path, cn_path, icon_path)
        setattr(fonts, size_name, font)

    # 刷新纹理
    try:
        renderer.refresh_font_texture()
    except Exception as e:
        print(f"[fonts] 刷新字体纹理失败: {e}")

    _fonts = fonts
    print(f"[fonts] 已加载 {len(PRELOAD_SIZES)} 个字号, 默认={DEFAULT_SIZE_TOKEN}")

    # 同步到 styles 模块
    try:
        from ui import styles
        styles.set_font_set(fonts)
    except ImportError:
        pass  # styles 模块可能未加载

    return fonts


def reload_fonts(renderer: Any) -> FontSet:
    """重新加载字体 (DPI 或配置变更后调用)"""
    return load_fonts(renderer)
