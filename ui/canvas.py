# -*- coding: utf-8 -*-
"""无限画布组件

提供类似专业绘图软件的可缩放、可平移画布，支持：
- 鼠标滚轮缩放（以鼠标位置为中心）
- 中键拖拽平移视口
- 空格+左键拖拽平移（备选）
- 项的点击选中
- 项的拖拽移动（释放时提交）
- 穿透点击循环选择堆叠项

精灵 Helpers (GML 语义):
- char_model_item: 角色模型项 (Origin 固定为 CHAR_MODEL_ORIGIN)
- char_sprite_item: 角色穿戴贴图项 (武器/盾牌/护甲)
- centered_sprite_item: 居中贴图项 (loot/inv 预览)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, TYPE_CHECKING

import imgui  # type: ignore

from constants import CHAR_MODEL_ORIGIN

if TYPE_CHECKING:
    from specs import Origin


# ============================================================================
# 数据类型
# ============================================================================


# 渲染函数类型
ItemRenderer = Callable[[Any, "CanvasItem", "ScreenRect", float], None]


@dataclass
class CanvasItem:
    """画布项 - 一个可交互的矩形区域

    Attributes:
        id: 稳定唯一标识符（业务层提供）
        x, y: 世界坐标位置
        width, height: 尺寸
        render: 渲染函数，签名为 (draw_list, item, rect, zoom) -> None
        selectable: 是否可被点击选中
        draggable: 是否可被拖动移动
        visible: 是否可见
        z_order: 绘制顺序（大的在上）
        user_data: 业务层数据，画布不解释
    """

    id: str
    x: float
    y: float
    width: float
    height: float
    render: ItemRenderer | None = None
    selectable: bool = True
    draggable: bool = True
    visible: bool = True
    z_order: int = 0
    user_data: Any = None


@dataclass
class ScreenRect:
    """屏幕坐标矩形"""

    x: float
    y: float
    width: float
    height: float

    @property
    def min(self) -> tuple[float, float]:
        return (self.x, self.y)

    @property
    def max(self) -> tuple[float, float]:
        return (self.x + self.width, self.y + self.height)


@dataclass
class CanvasOutput:
    """画布输出 - 交互结果

    类似 imgui.input_xxx 的返回值模式。
    """

    # 点击选择
    clicked_id: str | None = None

    # 拖拽
    dragging_id: str | None = None  # 正在拖拽的项 ID
    drag_x: float | None = None  # 新 X 位置
    drag_y: float | None = None  # 新 Y 位置
    drag_committed: bool = False  # True = 鼠标释放（提交）

    # 视口
    view_changed: bool = False  # 视口发生了变化（缩放/平移）


# ============================================================================
# 无限画布
# ============================================================================


class InfiniteCanvas:
    """无限画布组件

    一个类似专业绘图软件的可缩放、可平移画布。
    采用无状态设计，items 每帧由业务层传入。

    用法：
        canvas = InfiniteCanvas("my_canvas")

        def my_renderer(draw_list, item, rect, zoom):
            tex = load_texture(item.user_data["path"])
            draw_list.add_image(tex["tex_id"], rect.min, rect.max)

        items = [
            CanvasItem(id="bg", x=0, y=0, width=64, height=64,
                       render=my_renderer, draggable=False, user_data={"path": bg_path}),
            CanvasItem(id="sprite", x=10, y=20, width=32, height=32,
                       render=my_renderer, user_data={"path": sprite_path}),
        ]

        output = canvas.draw(300, 400, items, selected_ids={"sprite"})

        if output.clicked_id:
            # 处理选择
            ...

        if output.drag_committed and output.dragging_id == "sprite":
            # 提交位置更新
            data.x = output.drag_x
            data.y = output.drag_y
    """

    def __init__(self, canvas_id: str):
        """
        Args:
            canvas_id: 唯一标识符，用于 imgui ID
        """
        self.id = canvas_id

        # === 视口状态 ===
        self.center_x: float = 0.0  # 视口中心的世界坐标
        self.center_y: float = 0.0
        self.zoom: float = 4.0  # 缩放级别
        self.zoom_min: float = 0.5
        self.zoom_max: float = 16.0

        # === 显示选项 ===
        self.checker_cell_size: int = 8  # 棋盘格基础格子大小（世界坐标/像素）
        # Photoshop 风格浅色棋盘格 (#CCCCCC 和 #FFFFFF)
        self.checker_color_dark: tuple = (0.8, 0.8, 0.8, 1.0)   # #CCCCCC
        self.checker_color_light: tuple = (1.0, 1.0, 1.0, 1.0)  # #FFFFFF
        self.selection_color: tuple = (0.0, 0.6, 1.0, 1.0)  # 选中框颜色（蓝色更专业）
        self.selection_thickness: float = 1.0

        # === 内部状态 ===
        # 视口信息（每帧更新）
        self._viewport_pos: tuple[float, float] = (0, 0)
        self._viewport_size: tuple[float, float] = (0, 0)
        self._viewport_center: tuple[float, float] = (0, 0)

        # 平移状态
        self._is_panning: bool = False
        self._pan_start_mouse: tuple[float, float] | None = None
        self._pan_start_center: tuple[float, float] | None = None

        # 拖拽状态（用 ID 保证稳定性）
        self._dragging_id: str | None = None
        self._drag_start_world: tuple[float, float] | None = None
        self._drag_item_origin: tuple[float, float] | None = None
        self._current_drag_pos: tuple[float, float] | None = None

        # 穿透点击
        self._last_click_pos: tuple[float, float] | None = None
        self._click_cycle_ids: list[str] = []
        self._click_cycle_index: int = 0

    # ========================================================================
    # 坐标变换
    # ========================================================================

    def world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
        """世界坐标 → 屏幕坐标"""
        screen_x = self._viewport_center[0] + (world_x - self.center_x) * self.zoom
        screen_y = self._viewport_center[1] + (world_y - self.center_y) * self.zoom
        return (screen_x, screen_y)

    def screen_to_world(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        """屏幕坐标 → 世界坐标"""
        world_x = self.center_x + (screen_x - self._viewport_center[0]) / self.zoom
        world_y = self.center_y + (screen_y - self._viewport_center[1]) / self.zoom
        return (world_x, world_y)

    def _world_to_screen_rect(
        self, x: float, y: float, width: float, height: float
    ) -> ScreenRect:
        """世界坐标矩形 → 屏幕坐标矩形"""
        sx, sy = self.world_to_screen(x, y)
        return ScreenRect(sx, sy, width * self.zoom, height * self.zoom)

    # ========================================================================
    # 视口控制
    # ========================================================================

    def reset_view(self) -> None:
        """重置视口到原点，默认缩放"""
        self.center_x = 0.0
        self.center_y = 0.0
        self.zoom = 4.0

    def fit_content(self, items: list[CanvasItem], padding: float = 20.0) -> None:
        """调整视口以适应所有项

        Args:
            items: 画布项列表
            padding: 边距（屏幕像素）
        """
        if not items:
            self.reset_view()
            return

        # 计算包围盒
        visible_items = [it for it in items if it.visible]
        if not visible_items:
            self.reset_view()
            return

        min_x = min(it.x for it in visible_items)
        min_y = min(it.y for it in visible_items)
        max_x = max(it.x + it.width for it in visible_items)
        max_y = max(it.y + it.height for it in visible_items)

        content_w = max_x - min_x
        content_h = max_y - min_y

        if content_w <= 0 or content_h <= 0:
            self.reset_view()
            return

        # 计算适应的缩放
        available_w = self._viewport_size[0] - padding * 2
        available_h = self._viewport_size[1] - padding * 2

        if available_w <= 0 or available_h <= 0:
            return

        zoom_x = available_w / content_w
        zoom_y = available_h / content_h
        self.zoom = max(self.zoom_min, min(self.zoom_max, min(zoom_x, zoom_y)))

        # 居中
        self.center_x = (min_x + max_x) / 2
        self.center_y = (min_y + max_y) / 2

    def center_on(self, x: float, y: float) -> None:
        """将视口中心移动到指定世界坐标"""
        self.center_x = x
        self.center_y = y

    # ========================================================================
    # 绘制
    # ========================================================================

    def draw(
        self,
        width: float,
        height: float,
        items: list[CanvasItem],
        selected_ids: set[str] | None = None,
    ) -> CanvasOutput:
        """绘制画布

        Args:
            width: 画布宽度（屏幕像素）
            height: 画布高度（屏幕像素）
            items: 要显示的项列表（每个 item 自带 render 函数）
            selected_ids: 当前选中的项 ID 集合

        Returns:
            CanvasOutput: 交互结果
        """
        output = CanvasOutput()
        selected_ids = selected_ids or set()

        # 构建 ID 映射
        id_to_item = {item.id: item for item in items}

        # 验证拖拽状态
        if self._dragging_id and self._dragging_id not in id_to_item:
            self._cancel_drag()

        # 创建子窗口
        # 注意：移除 WINDOW_NO_SCROLL_WITH_MOUSE 以便子窗口能捕获滚轮事件
        imgui.begin_child(
            f"canvas_{self.id}",
            width,
            height,
            border=True,
            flags=imgui.WINDOW_NO_SCROLLBAR,
        )

        # 更新视口信息
        # 关键：用 get_window_position() 而不是 get_cursor_screen_pos()
        # 前者不受滚动影响，后者会随滚动变化
        self._viewport_pos = imgui.get_window_position()
        self._viewport_size = (width, height)
        self._viewport_center = (
            self._viewport_pos[0] + width / 2,
            self._viewport_pos[1] + height / 2,
        )

        draw_list = imgui.get_window_draw_list()

        # 强制固定光标位置，不受滚动影响
        imgui.set_cursor_screen_pos(self._viewport_pos)

        # 添加不可见按钮覆盖整个画布区域
        imgui.invisible_button(f"canvas_capture_{self.id}", width, height)
        is_hovered = imgui.is_item_hovered()

        draw_list.push_clip_rect(
            self._viewport_pos[0],
            self._viewport_pos[1],
            self._viewport_pos[0] + width,
            self._viewport_pos[1] + height,
        )

        # 绘制棋盘格背景
        self._draw_checkerboard(draw_list)

        # 按 z_order 排序绘制
        sorted_items = sorted(
            [it for it in items if it.visible], key=lambda it: it.z_order
        )

        for item in sorted_items:
            # 确定渲染位置（拖拽中用覆盖位置）
            if item.id == self._dragging_id and self._current_drag_pos:
                render_x, render_y = self._current_drag_pos
            else:
                render_x, render_y = item.x, item.y

            rect = self._world_to_screen_rect(render_x, render_y, item.width, item.height)

            # 调用 item 自己的渲染函数
            if item.render:
                item.render(draw_list, item, rect, self.zoom)

            # 绘制选中框
            if item.id in selected_ids:
                self._draw_selection_box(draw_list, rect)

        draw_list.pop_clip_rect()

        # 处理交互
        if is_hovered:
            # 关键：设置窗口焦点，配合 Dummy 吐掉滚轮事件
            imgui.set_window_focus()
            self._handle_pan_zoom(output)
            self._handle_click_drag(items, id_to_item, output)

        # Scroll Fix: 添加超大 Dummy 撑开内容，诱骗 ImGui 认为此窗口可滚动，从而吞噬滚轮事件
        imgui.set_cursor_pos((0, height + 10))
        imgui.dummy(0, 1000)

        imgui.end_child()

        return output

    # ========================================================================
    # 内部方法 - 绘制
    # ========================================================================

    def _draw_checkerboard(self, draw_list: Any) -> None:
        """绘制无限棋盘格背景"""
        cell_size_screen = self.checker_cell_size * self.zoom

        # 计算可见区域的世界坐标范围
        world_left, world_top = self.screen_to_world(
            self._viewport_pos[0], self._viewport_pos[1]
        )
        world_right, world_bottom = self.screen_to_world(
            self._viewport_pos[0] + self._viewport_size[0],
            self._viewport_pos[1] + self._viewport_size[1],
        )

        # 对齐到格子边界
        cell = self.checker_cell_size
        start_col = int(world_left // cell) - 1
        start_row = int(world_top // cell) - 1
        end_col = int(world_right // cell) + 1
        end_row = int(world_bottom // cell) + 1

        col_dark = imgui.get_color_u32_rgba(*self.checker_color_dark)
        col_light = imgui.get_color_u32_rgba(*self.checker_color_light)

        # 先填充深色背景
        draw_list.add_rect_filled(
            self._viewport_pos[0],
            self._viewport_pos[1],
            self._viewport_pos[0] + self._viewport_size[0],
            self._viewport_pos[1] + self._viewport_size[1],
            col_dark,
        )

        # 绘制浅色格子
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                if (row + col) % 2 == 0:
                    continue

                sx, sy = self.world_to_screen(col * cell, row * cell)
                draw_list.add_rect_filled(
                    sx,
                    sy,
                    sx + cell_size_screen,
                    sy + cell_size_screen,
                    col_light,
                )

    def _draw_selection_box(self, draw_list: Any, rect: ScreenRect) -> None:
        """绘制选中框"""
        col = imgui.get_color_u32_rgba(*self.selection_color)
        draw_list.add_rect(
            rect.x - 1,
            rect.y - 1,
            rect.x + rect.width + 1,
            rect.y + rect.height + 1,
            col,
            thickness=self.selection_thickness,
        )

    # ========================================================================
    # 内部方法 - 交互
    # ========================================================================

    def _handle_pan_zoom(self, output: CanvasOutput) -> None:
        """处理视口平移和缩放"""
        io = imgui.get_io()
        mouse_pos = imgui.get_mouse_pos()

        # 滚轮缩放（以鼠标位置为中心）
        wheel = io.mouse_wheel
        if wheel != 0:
            # 缩放前的鼠标世界坐标
            world_x, world_y = self.screen_to_world(*mouse_pos)

            # 更新缩放
            old_zoom = self.zoom
            factor = 1.15 if wheel > 0 else 1 / 1.15
            self.zoom = max(self.zoom_min, min(self.zoom_max, self.zoom * factor))

            if self.zoom != old_zoom:
                # 调整视口中心，使鼠标位置的世界坐标保持不变
                self.center_x = world_x - (mouse_pos[0] - self._viewport_center[0]) / self.zoom
                self.center_y = world_y - (mouse_pos[1] - self._viewport_center[1]) / self.zoom
                output.view_changed = True

        # 中键拖拽平移
        if imgui.is_mouse_clicked(2):  # 中键按下
            self._is_panning = True
            self._pan_start_mouse = mouse_pos
            self._pan_start_center = (self.center_x, self.center_y)

        # 空格 + 左键拖拽平移（备选）
        # 使用 imgui.is_key_down() 检测空格键 (KEY_SPACE = 32)
        space_pressed = imgui.is_key_down(32)
        if space_pressed and not self._dragging_id and not self._is_panning:
            if imgui.is_mouse_clicked(0):
                self._is_panning = True
                self._pan_start_mouse = mouse_pos
                self._pan_start_center = (self.center_x, self.center_y)

        # 平移进行中
        if self._is_panning:
            # 中键或左键持续按下
            panning_active = imgui.is_mouse_down(2) or (space_pressed and imgui.is_mouse_down(0))
            if panning_active:
                if self._pan_start_mouse and self._pan_start_center:
                    # 计算平移量
                    dx = (mouse_pos[0] - self._pan_start_mouse[0]) / self.zoom
                    dy = (mouse_pos[1] - self._pan_start_mouse[1]) / self.zoom
                    self.center_x = self._pan_start_center[0] - dx
                    self.center_y = self._pan_start_center[1] - dy
                    output.view_changed = True
            else:
                self._is_panning = False
                self._pan_start_mouse = None
                self._pan_start_center = None

    def _handle_click_drag(
        self,
        items: list[CanvasItem],
        id_to_item: dict[str, CanvasItem],
        output: CanvasOutput,
    ) -> None:
        """处理点击和拖拽"""
        if self._is_panning:
            return

        mouse_pos = imgui.get_mouse_pos()
        mouse_world = self.screen_to_world(*mouse_pos)

        # 拖拽进行中
        if self._dragging_id and imgui.is_mouse_down(0):
            if self._drag_start_world and self._drag_item_origin:
                delta_x = mouse_world[0] - self._drag_start_world[0]
                delta_y = mouse_world[1] - self._drag_start_world[1]
                self._current_drag_pos = (
                    self._drag_item_origin[0] + delta_x,
                    self._drag_item_origin[1] + delta_y,
                )

                output.dragging_id = self._dragging_id
                output.drag_x = self._current_drag_pos[0]
                output.drag_y = self._current_drag_pos[1]
                output.drag_committed = False
            return

        # 拖拽结束
        if self._dragging_id and imgui.is_mouse_released(0):
            output.dragging_id = self._dragging_id
            output.drag_x = self._current_drag_pos[0] if self._current_drag_pos else None
            output.drag_y = self._current_drag_pos[1] if self._current_drag_pos else None
            output.drag_committed = True

            self._cancel_drag()
            return

        # 左键点击
        if imgui.is_mouse_clicked(0):
            # 获取该位置下的所有可交互项（从上到下）
            hit_items = self._get_items_at_point(items, mouse_world)

            if not hit_items:
                # 点击空白处
                self._last_click_pos = None
                self._click_cycle_ids = []
                return

            # 穿透点击循环
            selected_item = self._cycle_click_selection(hit_items, mouse_pos)

            if selected_item:
                if selected_item.selectable:
                    output.clicked_id = selected_item.id

                # 开始拖拽（如果可拖拽）
                if selected_item.draggable:
                    self._dragging_id = selected_item.id
                    self._drag_start_world = mouse_world
                    self._drag_item_origin = (selected_item.x, selected_item.y)
                    self._current_drag_pos = None

    def _get_items_at_point(
        self, items: list[CanvasItem], world_pos: tuple[float, float]
    ) -> list[CanvasItem]:
        """获取某点下的所有项（按 z_order 从高到低）"""
        wx, wy = world_pos
        hit = []

        for item in items:
            if not item.visible:
                continue
            if not (item.selectable or item.draggable):
                continue

            # 如果正在拖拽，用拖拽位置判断
            if item.id == self._dragging_id and self._current_drag_pos:
                ix, iy = self._current_drag_pos
            else:
                ix, iy = item.x, item.y

            if ix <= wx < ix + item.width and iy <= wy < iy + item.height:
                hit.append(item)

        # 按 z_order 从高到低排序
        hit.sort(key=lambda it: it.z_order, reverse=True)
        return hit

    def _cycle_click_selection(
        self, hit_items: list[CanvasItem], mouse_pos: tuple[float, float]
    ) -> CanvasItem | None:
        """穿透点击循环选择"""
        if not hit_items:
            return None

        # 判断是否在同一位置连续点击
        is_same_spot = (
            self._last_click_pos
            and abs(mouse_pos[0] - self._last_click_pos[0]) < 5
            and abs(mouse_pos[1] - self._last_click_pos[1]) < 5
        )

        hit_ids = [it.id for it in hit_items]

        if is_same_spot and hit_ids == self._click_cycle_ids:
            # 同位置，循环到下一个
            self._click_cycle_index = (self._click_cycle_index + 1) % len(hit_items)
        else:
            # 新位置，从最上层开始
            self._click_cycle_ids = hit_ids
            self._click_cycle_index = 0

        self._last_click_pos = mouse_pos
        return hit_items[self._click_cycle_index]

    def _cancel_drag(self) -> None:
        """取消拖拽"""
        self._dragging_id = None
        self._drag_start_world = None
        self._drag_item_origin = None
        self._current_drag_pos = None


# ============================================================================
# 预设渲染器
# ============================================================================


def image_renderer(
    draw_list: Any, item: CanvasItem, rect: ScreenRect, zoom: float
) -> None:
    """渲染贴图

    user_data 格式:
        - str: 直接作为路径
        - dict: {"path": str}
    """
    from ui.texture_manager import load_texture

    if isinstance(item.user_data, dict):
        path = item.user_data.get("path", "")
    else:
        path = item.user_data or ""

    if path:
        tex = load_texture(path)
        if tex:
            draw_list.add_image(tex["tex_id"], rect.min, rect.max)


def rect_outline_renderer(
    draw_list: Any, item: CanvasItem, rect: ScreenRect, zoom: float
) -> None:
    """渲染矩形边框

    user_data 格式:
        {"color": (r, g, b, a), "thickness": float}
    """
    data = item.user_data if isinstance(item.user_data, dict) else {}
    color = data.get("color", (1.0, 1.0, 0.0, 1.0))
    thickness = data.get("thickness", 2.0)
    col = imgui.get_color_u32_rgba(*color)
    draw_list.add_rect(
        rect.min[0], rect.min[1], rect.max[0], rect.max[1], col, thickness=thickness
    )


def rect_filled_renderer(
    draw_list: Any, item: CanvasItem, rect: ScreenRect, zoom: float
) -> None:
    """渲染填充矩形

    user_data 格式:
        {"color": (r, g, b, a)}
    """
    data = item.user_data if isinstance(item.user_data, dict) else {}
    color = data.get("color", (0.5, 0.5, 0.5, 0.5))
    col = imgui.get_color_u32_rgba(*color)
    draw_list.add_rect_filled(rect.min[0], rect.min[1], rect.max[0], rect.max[1], col)


# ============================================================================
# 工厂函数
# ============================================================================


@lru_cache(maxsize=256)
def image_item(
    id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    path: str,
    *,
    selectable: bool = True,
    draggable: bool = True,
    visible: bool = True,
    z_order: int = 0,
) -> CanvasItem:
    """创建贴图项

    Args:
        id: 唯一标识符
        x, y: 世界坐标位置
        width, height: 尺寸
        path: 贴图文件路径
        selectable: 是否可选中
        draggable: 是否可拖动
        visible: 是否可见
        z_order: 绘制顺序
    """
    return CanvasItem(
        id=id,
        x=x,
        y=y,
        width=width,
        height=height,
        render=image_renderer,
        selectable=selectable,
        draggable=draggable,
        visible=visible,
        z_order=z_order,
        user_data={"path": path},
    )


@lru_cache(maxsize=128)
def outline_item(
    id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    color: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 1.0),
    thickness: float = 2.0,
    *,
    selectable: bool = False,
    draggable: bool = False,
    visible: bool = True,
    z_order: int = 100,
) -> CanvasItem:
    """创建矩形边框项

    Args:
        id: 唯一标识符
        x, y: 世界坐标位置
        width, height: 尺寸
        color: 边框颜色 (r, g, b, a)
        thickness: 线宽
        selectable: 是否可选中（默认否）
        draggable: 是否可拖动（默认否）
        visible: 是否可见
        z_order: 绘制顺序（默认 100，在其他项之上）
    """
    return CanvasItem(
        id=id,
        x=x,
        y=y,
        width=width,
        height=height,
        render=rect_outline_renderer,
        selectable=selectable,
        draggable=draggable,
        visible=visible,
        z_order=z_order,
        user_data={"color": color, "thickness": thickness},
    )


@lru_cache(maxsize=64)
def filled_rect_item(
    id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    color: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5),
    *,
    selectable: bool = False,
    draggable: bool = False,
    visible: bool = True,
    z_order: int = -100,
) -> CanvasItem:
    """创建填充矩形项

    Args:
        id: 唯一标识符
        x, y: 世界坐标位置
        width, height: 尺寸
        color: 填充颜色 (r, g, b, a)
        selectable: 是否可选中（默认否）
        draggable: 是否可拖动（默认否）
        visible: 是否可见
        z_order: 绘制顺序（默认 -100，在其他项之下）
    """
    return CanvasItem(
        id=id,
        x=x,
        y=y,
        width=width,
        height=height,
        render=rect_filled_renderer,
        selectable=selectable,
        draggable=draggable,
        visible=visible,
        z_order=z_order,
        user_data={"color": color},
    )


# ============================================================================
# GML 精灵 Helpers
# ============================================================================
# 这些 helpers 使用 GML 的 Origin 语义：
# - 精灵的 Origin 点对齐到世界坐标原点 (0, 0)
# - 精灵左上角绘制在 (-origin_x, -origin_y)
# ============================================================================


def char_model_item(
    id: str,
    path: str,
    *,
    selectable: bool = False,
    draggable: bool = False,
    visible: bool = True,
    z_order: int = 0,
) -> CanvasItem | None:
    """创建角色模型项

    角色模型的 Origin 固定为 CHAR_MODEL_ORIGIN (22, 34)。
    精灵的 Origin 点对齐到世界原点 (0, 0)。

    Args:
        id: 唯一标识符
        path: 贴图文件路径
        selectable: 是否可选中（默认否）
        draggable: 是否可拖动（默认否）
        visible: 是否可见
        z_order: 绘制顺序

    Returns:
        CanvasItem 或 None（路径无效时）
    """
    from ui.texture_manager import load_texture

    tex = load_texture(path)
    if not tex:
        return None

    # Origin 对齐到世界原点，左上角在 (-origin_x, -origin_y)
    origin_x, origin_y = CHAR_MODEL_ORIGIN
    return CanvasItem(
        id=id,
        x=-origin_x,
        y=-origin_y,
        width=tex["width"],
        height=tex["height"],
        render=image_renderer,
        selectable=selectable,
        draggable=draggable,
        visible=visible,
        z_order=z_order,
        user_data={"path": path},
    )


def char_sprite_item(
    id: str,
    path: str,
    origin: "Origin",
    *,
    selectable: bool = False,
    draggable: bool = False,
    visible: bool = True,
    z_order: int = 10,
) -> CanvasItem | None:
    """创建角色穿戴贴图项 (武器/盾牌/护甲)

    精灵的 Origin 点对齐到世界原点 (0, 0)。
    当 origin 为默认值 (22, 34) 时，装备与角色模型完美重叠。

    Args:
        id: 唯一标识符
        path: 贴图文件路径
        origin: 精灵 Origin (决定与角色的对齐)
        selectable: 是否可选中（默认否）
        draggable: 是否可拖动（默认否）
        visible: 是否可见
        z_order: 绘制顺序（默认 10，在角色模型之上）

    Returns:
        CanvasItem 或 None（路径无效时）
    """
    from ui.texture_manager import load_texture

    tex = load_texture(path)
    if not tex:
        return None

    # Origin 对齐到世界原点，左上角在 (-origin.x, -origin.y)
    return CanvasItem(
        id=id,
        x=-origin.x,
        y=-origin.y,
        width=tex["width"],
        height=tex["height"],
        render=image_renderer,
        selectable=selectable,
        draggable=draggable,
        visible=visible,
        z_order=z_order,
        user_data={"path": path},
    )


def centered_sprite_item(
    id: str,
    path: str,
    *,
    selectable: bool = True,
    draggable: bool = False,
    visible: bool = True,
    z_order: int = 0,
) -> CanvasItem | None:
    """创建居中贴图项

    精灵中心对齐到世界原点 (0, 0)。
    用于 loot/inv 等无需对齐角色的预览。

    Args:
        id: 唯一标识符
        path: 贴图文件路径
        selectable: 是否可选中
        draggable: 是否可拖动（默认否）
        visible: 是否可见
        z_order: 绘制顺序

    Returns:
        CanvasItem 或 None（路径无效时）
    """
    from ui.texture_manager import load_texture

    tex = load_texture(path)
    if not tex:
        return None

    w, h = tex["width"], tex["height"]
    return CanvasItem(
        id=id,
        x=-w / 2,
        y=-h / 2,
        width=w,
        height=h,
        render=image_renderer,
        selectable=selectable,
        draggable=draggable,
        visible=visible,
        z_order=z_order,
        user_data={"path": path},
    )
