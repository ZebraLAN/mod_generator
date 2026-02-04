# -*- coding: utf-8 -*-
"""全局 UI 状态管理

集中管理 UI 运行时状态，避免状态分散在各个 Mixin 中。
包括：
- DPI 缩放 (从系统读取，只读)
- 物品索引
- 编辑器状态
- 当前项目引用
"""

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models import ModProject


# ==================== DPI 状态 (模块级) ====================

_dpi_scale: float = 1.0


def init_dpi(window: Any) -> None:
    """初始化 DPI 缩放 (启动时调用一次)

    Args:
        window: GLFW window 对象
    """
    global _dpi_scale
    try:
        import glfw  # type: ignore
        scale = glfw.get_window_content_scale(window)
        _dpi_scale = scale[0] if scale else 1.0
        print(f"[DPI] 检测到缩放: {_dpi_scale * 100:.0f}%")
    except Exception as e:
        print(f"[DPI] 检测失败: {e}, 使用默认 100%")
        _dpi_scale = 1.0


def dpi_scale() -> float:
    """获取 DPI 缩放因子"""
    return _dpi_scale


@dataclass
class UIState:
    """全局 UI 状态

    使用 dataclass 自动生成 __init__ 和 __repr__。
    所有 UI 相关的索引和临时状态都集中在这里。
    """

    # ==================== 导航状态 ====================
    # 当前激活的物品类型: "weapon" | "armor" | "hybrid" | None
    # None 表示没有选中任何物品，此时显示项目编辑器
    nav_item_type: str | None = None

    # 各类型物品的当前索引 (-1 表示未选中)
    current_weapon_index: int = -1
    current_armor_index: int = -1
    current_hybrid_index: int = -1

    # ==================== 贴图编辑器状态 ====================
    current_texture_field: str = ""
    preview_states: dict[str, Any] = field(default_factory=dict)

    # ==================== 模型/种族选择 ====================
    selected_model: str = "Human Male"
    selected_race: str = "Human"
    gender_tab_index: int = 0  # 0=男性, 1=女性

    # ==================== 标签页状态 (向后兼容) ====================
    active_item_tab: int = 0

    # ==================== 属性搜索缓冲 ====================
    attr_search_buffers: dict[str, str] = field(default_factory=dict)

    # ==================== 项目引用 ====================
    _project: "ModProject | None" = field(default=None, repr=False)

    @property
    def project(self) -> "ModProject":
        """获取当前项目（如果未设置会抛出异常）"""
        if self._project is None:
            raise RuntimeError("No project loaded")
        return self._project

    def set_project(self, project: "ModProject") -> None:
        """设置当前项目并重置相关状态"""
        self._project = project
        self.reset_navigation()

    def import_texture(self, source_path: str) -> str:
        """导入贴图到项目，返回最终路径

        这是 project.import_texture 的便捷包装，
        自动处理相对路径转绝对路径。
        """
        if self._project is None or not self._project.file_path:
            return source_path
        rel_path = self._project.import_texture(source_path)
        return os.path.join(os.path.dirname(self._project.file_path), rel_path)

    # ==================== 导航辅助方法 ====================

    def select_item(self, item_type: str, index: int) -> None:
        """选中指定类型的物品

        Args:
            item_type: "weapon" | "armor" | "hybrid"
            index: 物品索引
        """
        # 清除其他类型的选中
        self.current_weapon_index = -1
        self.current_armor_index = -1
        self.current_hybrid_index = -1

        # 设置当前类型和索引
        self.nav_item_type = item_type
        if item_type == "weapon":
            self.current_weapon_index = index
        elif item_type == "armor":
            self.current_armor_index = index
        elif item_type == "hybrid":
            self.current_hybrid_index = index

    def clear_selection(self) -> None:
        """清除物品选中状态（显示项目编辑器）"""
        self.nav_item_type = None
        self.current_weapon_index = -1
        self.current_armor_index = -1
        self.current_hybrid_index = -1

    def has_selection(self) -> bool:
        """是否有选中的物品"""
        return self.nav_item_type is not None and self.get_current_index() >= 0

    def get_current_index(self) -> int:
        """获取当前类型的选中索引"""
        if self.nav_item_type == "weapon":
            return self.current_weapon_index
        elif self.nav_item_type == "armor":
            return self.current_armor_index
        elif self.nav_item_type == "hybrid":
            return self.current_hybrid_index
        return -1

    def reset_navigation(self) -> None:
        """重置导航状态（用于新建/打开项目时）"""
        self.nav_item_type = None
        self.current_weapon_index = -1
        self.current_armor_index = -1
        self.current_hybrid_index = -1

    def reset_item_indices(self) -> None:
        """重置所有物品索引（向后兼容）"""
        self.reset_navigation()

    def reset_all(self) -> None:
        """重置所有状态到默认值"""
        self.reset_navigation()
        self.current_texture_field = ""
        self.preview_states.clear()
        self.attr_search_buffers.clear()
        self.selected_model = "Human Male"
        self.selected_race = "Human"
        self.gender_tab_index = 0
        self.active_item_tab = 0


# 全局单例
state = UIState()
