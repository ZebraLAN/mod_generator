# -*- coding: utf-8 -*-
"""原子 UI 控件

⚠️ LEGACY: 本文件中的大部分组件在 Tailwind 风格设计体系建立之前实现，
   未使用 tw tokens / ly helpers，而是直接调用 imgui API。
   未来重构时应改用 tw.* 和 ly.* 。

提供正交、可组合的 ImGui 风格控件：

帧控制:
    - tab_index: 标签页选择
    - animation_frame: 动画帧控制（自动播放）
    - slider_index: 滑块索引选择

Origin 编辑:
    - origin_input: Origin 坐标输入

贴图选择:
    - single_texture_input: 单张贴图选择
    - frame_strip: 帧条（多帧管理 + 帧选择）

速度设置:
    - loot_speed_input: 战利品动画速度

模型选择:
    - model_combo: 角色模型选择
    - race_combo: 种族选择

预览:
    - texture_preview: 贴图预览（支持 origin、模型叠加、图层选择）
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

import imgui  # type: ignore

from constants import (
    CHAR_MODEL_ORIGIN,
    CHARACTER_MODEL_LABELS,
    CHARACTER_RACE_LABELS,
    CHARACTER_RACES,
    GAME_FPS,
)
from specs import Origin, AbsoluteFps, RelativeSpeed
from ui.dialogs import file_dialog
from ui.layout import tooltip
from ui.state import dpi_scale
from ui.styles import text_secondary, StyleContext

if TYPE_CHECKING:
    from ui.canvas import InfiniteCanvas, CanvasOutput


# ============================================================================
# 隐式状态存储
# ============================================================================

@dataclass
class _TabState:
    index: int = 0


@dataclass
class _AnimationState:
    frame: int = 0
    paused: bool = False
    last_update: float = field(default_factory=time.time)


@dataclass
class _SliderState:
    index: int = 0


@dataclass
class _LayerState:
    selected: str = "sprite"  # "sprite" | "model"


_tab_states: dict[str, _TabState] = {}
_animation_states: dict[str, _AnimationState] = {}
_slider_states: dict[str, _SliderState] = {}
_layer_states: dict[str, _LayerState] = {}


def _get_tab_state(id_suffix: str) -> _TabState:
    if id_suffix not in _tab_states:
        _tab_states[id_suffix] = _TabState()
    return _tab_states[id_suffix]


def _get_animation_state(id_suffix: str) -> _AnimationState:
    if id_suffix not in _animation_states:
        _animation_states[id_suffix] = _AnimationState()
    return _animation_states[id_suffix]


def _get_slider_state(id_suffix: str) -> _SliderState:
    if id_suffix not in _slider_states:
        _slider_states[id_suffix] = _SliderState()
    return _slider_states[id_suffix]


def _get_layer_state(id_suffix: str) -> _LayerState:
    if id_suffix not in _layer_states:
        _layer_states[id_suffix] = _LayerState()
    return _layer_states[id_suffix]


# ============================================================================
# 1. tab_index - 标签页选择
# ============================================================================


def tab_index(
    id_suffix: str,
    labels: list[str],
    current: int = 0,
    *,
    accent_color: tuple[float, float, float, float] | None = None,
) -> int:
    """标签页选择控件

    渲染一排按钮，当前选中的高亮显示。

    Args:
        id_suffix: 唯一标识符
        labels: 标签列表
        current: 当前选中的索引（用于外部状态同步）
        accent_color: 选中按钮的高亮颜色，None 则使用默认

    Returns:
        当前选中的索引 (0-based)，labels 为空时返回 0
    """
    if not labels:
        return 0

    state = _get_tab_state(id_suffix)

    # 同步外部状态
    if current != state.index and 0 <= current < len(labels):
        state.index = current

    # 确保索引在有效范围内
    if state.index >= len(labels):
        state.index = 0

    # 获取 accent 颜色
    if accent_color is None:
        from ui.styles import get_current_theme_colors
        accent_color = get_current_theme_colors().get("accent")

    for i, label in enumerate(labels):
        if i > 0:
            imgui.same_line()

        is_selected = (i == state.index)

        if is_selected and accent_color:
            imgui.push_style_color(imgui.COLOR_BUTTON, *accent_color)

        if imgui.button(f"{label}##{id_suffix}_{i}"):
            state.index = i

        if is_selected and accent_color:
            imgui.pop_style_color()

    return state.index


# ============================================================================
# 2. origin_input - Origin 坐标输入
# ============================================================================


def origin_input(
    id_suffix: str,
    origin: Origin,
    *,
    label: str = "Origin",
    tooltip_text: str | None = None,
) -> Origin:
    """Origin 坐标输入控件

    渲染 X/Y 两个整数输入框。

    Args:
        id_suffix: 唯一标识符
        origin: 当前 Origin 值
        label: 标签文本
        tooltip_text: 悬停提示，None 则使用默认

    Returns:
        更新后的 Origin 对象
    """
    if tooltip_text is None:
        tooltip_text = (
            f"精灵定位点，决定贴图与角色的对齐位置。\n"
            f"默认 ({CHAR_MODEL_ORIGIN[0]}, {CHAR_MODEL_ORIGIN[1]}) 与人体模型对齐。"
        )

    imgui.text(label)
    tooltip(tooltip_text)

    imgui.push_item_width(150)

    changed_x, new_x = imgui.input_int(f"X##{id_suffix}_x", origin.x)
    tooltip(f"默认 {CHAR_MODEL_ORIGIN[0]}。值越小，装备越向右偏移。")

    imgui.same_line()
    imgui.dummy(10, 0)
    imgui.same_line()

    changed_y, new_y = imgui.input_int(f"Y##{id_suffix}_y", origin.y)
    tooltip(f"默认 {CHAR_MODEL_ORIGIN[1]}。值越小，装备越向下偏移。")

    imgui.pop_item_width()

    if changed_x or changed_y:
        return Origin(new_x, new_y)
    return origin


# ============================================================================
# 3. animation_frame - 动画帧控制
# ============================================================================


def animation_frame(
    id_suffix: str,
    count: int,
    fps: float,
    *,
    show_pause: bool = True,
) -> int:
    """动画帧控制器

    自动按 fps 推进帧，可选显示暂停按钮。

    Args:
        id_suffix: 唯一标识符
        count: 帧总数
        fps: 播放帧率
        show_pause: 是否显示暂停按钮

    Returns:
        当前帧索引 (0-based)，count <= 0 时返回 0
    """
    if count <= 0:
        return 0

    state = _get_animation_state(id_suffix)

    # 确保帧索引在有效范围内
    if state.frame >= count:
        state.frame = 0

    # 暂停按钮
    if show_pause:
        pause_label = "⏸" if not state.paused else "▶"
        if imgui.button(f"{pause_label}##{id_suffix}_pause"):
            state.paused = not state.paused
        imgui.same_line()
        text_secondary(f"{state.frame + 1}/{count}")

    # 自动播放
    if not state.paused and fps > 0:
        now = time.time()
        elapsed = now - state.last_update
        if elapsed >= 1.0 / fps:
            state.frame = (state.frame + 1) % count
            state.last_update = now

    return state.frame


# ============================================================================
# 4. single_texture_input - 单张贴图选择
# ============================================================================


def single_texture_input(
    id_suffix: str,
    path: str,
    *,
    importer: Callable[[str], str] | None = None,
    label: str | None = None,
) -> str:
    """单张贴图选择控件

    渲染 [选择...] 或 [更换] [清除] 按钮。

    Args:
        id_suffix: 唯一标识符
        path: 当前贴图路径
        importer: 路径转换函数（用于复制到项目目录）
        label: 可选标签，None 则不显示

    Returns:
        更新后的路径
    """
    if label:
        imgui.text(label)
        imgui.same_line()

    result = path

    if path:
        # 已设置状态
        if imgui.button(f"更换##{id_suffix}"):
            selected = file_dialog([("PNG文件", "*.png")])
            if selected and isinstance(selected, str):
                result = importer(selected) if importer else selected

        imgui.same_line()

        if imgui.button(f"清除##{id_suffix}"):
            result = ""

        imgui.same_line()
        filename = os.path.basename(path)
        text_secondary(filename)
        if imgui.is_item_hovered():
            imgui.set_tooltip(path)
    else:
        # 未设置状态
        if imgui.button(f"选择...##{id_suffix}"):
            selected = file_dialog([("PNG文件", "*.png")])
            if selected and isinstance(selected, str):
                result = importer(selected) if importer else selected

    return result


# ============================================================================
# 5. loot_speed_input - 战利品动画速度
# ============================================================================


def loot_speed_input(
    id_suffix: str,
    speed: AbsoluteFps | RelativeSpeed,
) -> AbsoluteFps | RelativeSpeed:
    """战利品动画速度输入控件

    Args:
        id_suffix: 唯一标识符
        speed: 当前速度设置

    Returns:
        更新后的速度设置
    """
    imgui.text("动画速度设置")
    tooltip("设置战利品贴图的动画播放速度。\n此设置会影响生成的模组代码。")

    is_relative = isinstance(speed, RelativeSpeed)

    if imgui.begin_combo(
        f"速度模式##{id_suffix}_mode",
        "相对速度" if is_relative else "固定帧率 (FPS)"
    ):
        if imgui.selectable("固定帧率 (FPS)", not is_relative)[0] and is_relative:
            speed = AbsoluteFps(fps=10.0)
        if imgui.selectable("相对速度", is_relative)[0] and not is_relative:
            speed = RelativeSpeed(multiplier=0.25)
        imgui.end_combo()

    if isinstance(speed, AbsoluteFps):
        imgui.push_item_width(150)
        changed, new_fps = imgui.input_float(
            f"播放帧率 (FPS)##{id_suffix}_fps",
            speed.fps,
            step=1.0,
            step_fast=5.0,
            format="%.1f",
        )
        if changed:
            speed.fps = max(0.1, new_fps)
        imgui.pop_item_width()
        tooltip("每秒播放的帧数。\n这是一个固定值，不会随游戏速度变化。\n默认值: 10")

    elif isinstance(speed, RelativeSpeed):
        imgui.push_item_width(180)
        changed, new_mult = imgui.input_float(
            f"速度倍率##{id_suffix}_mult",
            speed.multiplier,
            step=0.01,
            step_fast=0.1,
            format="%.3f",
        )
        if changed:
            speed.multiplier = max(0.001, round(new_mult, 3))
        imgui.pop_item_width()
        tooltip(
            f"每个游戏帧内动画前进的帧数。\n\n"
            f"例如:\n  • 值为 0.1 时: 实际播放速度 = {GAME_FPS} × 0.1 = 4 fps\n"
            f"  • 值为 0.25 时: 实际播放速度 = {GAME_FPS} × 0.25 = 10 fps\n"
            f"  • 值为 0.5 时: 实际播放速度 = {GAME_FPS} × 0.5 = 20 fps\n"
            f"  • 值为 1.0 时: 实际播放速度 = {GAME_FPS} × 1.0 = 40 fps\n\n"
            f"提示: 手持贴图默认相对帧率为 0.25 (即 {GAME_FPS // 4} fps)。\n最小值: 0.001"
        )
        text_secondary(f"实际播放速度: {GAME_FPS * speed.multiplier:.3f} fps (游戏 {GAME_FPS} fps 时)")

    return speed


# ============================================================================
# 6. model_combo / race_combo - 模型选择
# ============================================================================


def model_combo(id_suffix: str, current: str) -> str:
    """角色模型选择下拉框

    Args:
        id_suffix: 唯一标识符
        current: 当前选中的模型 key

    Returns:
        选中的模型 key
    """
    current_label = CHARACTER_MODEL_LABELS.get(current, current)

    imgui.push_item_width(120)
    if imgui.begin_combo(f"模特##{id_suffix}", current_label):
        for model_key, model_label in CHARACTER_MODEL_LABELS.items():
            if imgui.selectable(model_label, model_key == current)[0]:
                current = model_key
        imgui.end_combo()
    imgui.pop_item_width()

    return current


def race_combo(id_suffix: str, current: str) -> str:
    """种族选择下拉框

    Args:
        id_suffix: 唯一标识符
        current: 当前选中的种族 key

    Returns:
        选中的种族 key
    """
    current_label = CHARACTER_RACE_LABELS.get(current, current)

    imgui.push_item_width(80)
    if imgui.begin_combo(f"人种##{id_suffix}", current_label):
        for race in CHARACTER_RACES:
            label = CHARACTER_RACE_LABELS.get(race, race)
            if imgui.selectable(label, race == current)[0]:
                current = race
        imgui.end_combo()
    imgui.pop_item_width()

    return current


# ============================================================================
# 7. texture_preview - 贴图预览
# ============================================================================


# 画布实例缓存
_preview_canvases: dict[str, "InfiniteCanvas"] = {}


def _get_preview_canvas(id_suffix: str) -> "InfiniteCanvas":
    """获取或创建预览画布"""
    from ui.canvas import InfiniteCanvas
    if id_suffix not in _preview_canvases:
        _preview_canvases[id_suffix] = InfiniteCanvas(id_suffix)
    return _preview_canvases[id_suffix]


def texture_preview(
    id_suffix: str,
    path: str,
    *,
    origin: Origin | None = None,
    model_path: str | None = None,
    size: tuple[int, int] | None = None,
    draggable: bool = False,
    layer_select: bool = False,
) -> "CanvasOutput":
    """贴图预览控件

    Args:
        id_suffix: 唯一标识符
        path: 贴图路径
        origin: 精灵 Origin（None 则使用居中模式）
        model_path: 角色模型贴图路径（None 则不叠加）
        size: 预览区域尺寸 (width, height)，None 则自动适应
        draggable: 是否可拖拽精灵
        layer_select: 是否启用图层选择

    Returns:
        CanvasOutput 包含交互信息
    """
    from ui.canvas import (
        InfiniteCanvas, CanvasOutput, CanvasItem,
        centered_sprite_item, char_sprite_item, char_model_item,
    )
    from ui.texture_manager import load_texture
    from constants import VALID_AREA_SIZE

    canvas = _get_preview_canvas(id_suffix)
    items: list[CanvasItem] = []
    selected_ids: set[str] = set()

    # 图层选择状态
    if layer_select:
        layer_state = _get_layer_state(id_suffix)
        selected_ids.add(layer_state.selected)

    if origin is not None:
        # 有 origin: 使用角色贴图模式
        # 添加角色模型（如果有）
        if model_path:
            model_item = char_model_item(
                "model", model_path,
                selectable=layer_select,
                draggable=False,
                z_order=0
            )
            if model_item:
                items.append(model_item)

        # 添加装备贴图
        sprite_item = char_sprite_item(
            "sprite", path, origin,
            selectable=layer_select,
            draggable=draggable,
            z_order=10
        )
        if sprite_item:
            items.append(sprite_item)

        # 默认尺寸
        if size is None:
            size = (VALID_AREA_SIZE, VALID_AREA_SIZE)
    else:
        # 无 origin: 使用居中模式
        sprite_item = centered_sprite_item(
            "sprite", path,
            selectable=layer_select,
            draggable=draggable,
        )
        if sprite_item:
            items.append(sprite_item)

        # 默认尺寸：贴图的 4 倍
        if size is None:
            tex = load_texture(path)
            if tex:
                size = (int(tex["width"] * 4), int(tex["height"] * 4))
            else:
                size = (64, 64)

    # 绘制画布
    output = canvas.draw(size[0], size[1], items, selected_ids)

    # 更新图层选择状态
    if layer_select and output.clicked_id:
        layer_state = _get_layer_state(id_suffix)
        layer_state.selected = output.clicked_id

    return output


# ============================================================================
# 8. frame_strip - 帧条
# ============================================================================


def frame_strip(
    id_suffix: str,
    paths: list[str],
    *,
    animated: bool = True,
    fps: float = 10.0,
    importer: Callable[[str], str] | None = None,
) -> tuple[list[str], int]:
    """帧条控件 - 多帧管理 + 帧选择

    渲染帧缩略图条 + 控制按钮：
    - 点击帧：切换预览
    - 悬停帧：显示删除按钮
    - [+] 添加帧
    - [▶/⏸] 播放/暂停（animated=True 时）

    Args:
        id_suffix: 唯一标识符
        paths: 当前路径列表
        animated: 是否自动播放
        fps: 播放帧率（仅 animated=True 时有效）
        importer: 路径转换函数

    Returns:
        (更新后的路径列表, 当前帧索引)
    """
    from ui.texture_manager import load_texture

    result_paths = list(paths)  # 复制以便修改
    state = _get_animation_state(id_suffix)

    # 空列表处理
    if not result_paths:
        if imgui.button(f"选择贴图...##{id_suffix}_add"):
            selected = file_dialog([("PNG文件", "*.png")], multiple=True)
            if selected:
                for p in (selected if isinstance(selected, list) else [selected]):
                    result_paths.append(importer(p) if importer else p)
        return result_paths, 0

    # 确保帧索引有效
    if state.frame >= len(result_paths):
        state.frame = len(result_paths) - 1
    if state.frame < 0:
        state.frame = 0

    # === 帧条区域 ===
    frame_height = 32
    thumb_size = 24

    # 绘制帧缩略图
    to_delete: int | None = None
    to_move: tuple[int, int] | None = None  # (from_idx, to_idx)

    for i, p in enumerate(result_paths):
        if i > 0:
            imgui.same_line()

        is_current = (i == state.frame)

        # 缩略图按钮
        tex = load_texture(p)
        if tex:
            # 有贴图：显示缩略图
            if is_current:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.5, 0.8, 1.0)

            # 使用 image_button
            clicked = imgui.image_button(
                tex["tex_id"],
                thumb_size, thumb_size,
                uv0=(0, 0), uv1=(1, 1),
                frame_padding=2,
            )
            if clicked:
                state.frame = i
                state.paused = True  # 点击时暂停

            if is_current:
                imgui.pop_style_color()
        else:
            # 无贴图：显示序号
            if is_current:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.5, 0.8, 1.0)

            if imgui.button(f"{i+1}##{id_suffix}_frame_{i}", width=thumb_size, height=thumb_size):
                state.frame = i
                state.paused = True

            if is_current:
                imgui.pop_style_color()

        # 右键上下文菜单
        if imgui.begin_popup_context_item(f"frame_ctx_{id_suffix}_{i}"):
            imgui.text(f"帧 {i+1}: {os.path.basename(p)}")
            imgui.separator()

            if i > 0:
                if imgui.selectable("← 左移")[0]:
                    to_move = (i, i - 1)
            else:
                imgui.text_disabled("← 左移")

            if i < len(result_paths) - 1:
                if imgui.selectable("→ 右移")[0]:
                    to_move = (i, i + 1)
            else:
                imgui.text_disabled("→ 右移")

            imgui.separator()

            if imgui.selectable("× 删除")[0]:
                to_delete = i

            imgui.end_popup()

        # 悬停提示
        elif imgui.is_item_hovered():
            imgui.set_tooltip(f"帧 {i+1}: {os.path.basename(p)}\n右键打开菜单")

    # 执行移动
    if to_move is not None:
        from_idx, to_idx = to_move
        result_paths[from_idx], result_paths[to_idx] = result_paths[to_idx], result_paths[from_idx]
        # 跟随移动选中帧
        if state.frame == from_idx:
            state.frame = to_idx
        elif state.frame == to_idx:
            state.frame = from_idx

    # 执行删除
    if to_delete is not None:
        result_paths.pop(to_delete)
        if state.frame >= len(result_paths) and result_paths:
            state.frame = len(result_paths) - 1

    imgui.same_line()

    # 添加按钮
    if imgui.button(f"+##{id_suffix}_add", width=thumb_size, height=thumb_size):
        selected = file_dialog([("PNG文件", "*.png")], multiple=True)
        if selected:
            for p in (selected if isinstance(selected, list) else [selected]):
                result_paths.append(importer(p) if importer else p)
    tooltip("添加帧")

    # 动画控制
    if animated and len(result_paths) > 1:
        imgui.same_line()
        imgui.dummy(8, 0)
        imgui.same_line()

        pause_label = "⏸" if not state.paused else "▶"
        if imgui.button(f"{pause_label}##{id_suffix}_pause"):
            state.paused = not state.paused

        imgui.same_line()
        text_secondary(f"{fps:.0f}fps")

        # 自动播放
        if not state.paused and fps > 0:
            now = time.time()
            elapsed = now - state.last_update
            if elapsed >= 1.0 / fps:
                state.frame = (state.frame + 1) % len(result_paths)
                state.last_update = now

    return result_paths, state.frame


# ============================================================================
# 辅助函数
# ============================================================================


def slider_index(
    id_suffix: str,
    count: int,
    *,
    label: str = "",
) -> int:
    """滑块索引选择

    Args:
        id_suffix: 唯一标识符
        count: 总数量
        label: 可选标签

    Returns:
        当前选中索引 (0-based)，count <= 1 时返回 0
    """
    if count <= 1:
        return 0

    state = _get_slider_state(id_suffix)

    # 确保索引在有效范围内
    if state.index >= count:
        state.index = count - 1

    if label:
        imgui.text(label)
        imgui.same_line()

    imgui.push_item_width(150)
    changed, new_val = imgui.slider_int(
        f"##{id_suffix}_slider",
        state.index,
        0,
        count - 1,
        format=f"%d / {count - 1}",
    )
    if changed:
        state.index = new_val
    imgui.pop_item_width()

    return state.index
