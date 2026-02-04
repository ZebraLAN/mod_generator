# -*- coding: utf-8 -*-
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""贴图管理模块

提供 GPU 纹理加载、缓存管理和棋盘格背景绘制功能。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, TypedDict

import imgui  # type: ignore
from OpenGL.GL import (  # type: ignore
    GL_NEAREST,
    GL_RGBA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_UNSIGNED_BYTE,
    glBindTexture,
    glDeleteTextures,
    glGenTextures,
    glTexImage2D,
    glTexParameteri,
)

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

try:
    from PIL import Image
except ImportError:
    Image = None


class TextureInfo(TypedDict):
    """纹理信息字典类型"""

    tex_id: int
    width: int
    height: int
    mtime: float


# ============================================================================
# 纹理缓存
# ============================================================================

_texture_cache: dict[str, TextureInfo] = {}


def load_texture(path: str) -> TextureInfo | None:
    """加载纹理到 GPU 并缓存

    Args:
        path: 贴图文件路径

    Returns:
        包含 tex_id, width, height, mtime 的字典，或 None
    """
    if not path or not os.path.exists(path) or Image is None:
        return None

    mtime = os.path.getmtime(path)
    cached = _texture_cache.get(path)

    if cached and cached["mtime"] == mtime:
        return cached

    # 缓存失效，释放旧纹理
    if cached:
        glDeleteTextures(int(cached["tex_id"]))

    try:
        with Image.open(path) as img:
            rgba_img: PILImage = img.convert("RGBA")
            width: int
            height: int
            width, height = rgba_img.size
            image_data: bytes = rgba_img.tobytes()
    except Exception as exc:
        print(f"无法加载贴图预览 {path}: {exc}")
        return None

    tex_id: int = glGenTextures(1)
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

    preview: TextureInfo = {"tex_id": tex_id, "width": width, "height": height, "mtime": mtime}
    _texture_cache[path] = preview
    return preview


def unload_all_textures() -> None:
    """释放所有 GPU 纹理资源并清空缓存"""
    for preview in _texture_cache.values():
        glDeleteTextures(int(preview["tex_id"]))
    _texture_cache.clear()


# ============================================================================
# 绘图工具
# ============================================================================

def draw_checkerboard(
    draw_list: Any, p_min: tuple[float, float], p_max: tuple[float, float], cell_size: int = 24
) -> None:
    """绘制棋盘格背景

    Args:
        draw_list: ImGui draw list
        p_min: 左上角坐标 (x, y)
        p_max: 右下角坐标 (x, y)
        cell_size: 格子大小（像素）
    """
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
