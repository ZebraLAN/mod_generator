# -*- coding: utf-8 -*-
"""对话框模块

提供文件对话框、目录对话框和导入对话框功能。
"""

import os
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING

from ui import popups

if TYPE_CHECKING:
    from models import ModProject


def file_dialog(
    file_types: list[tuple[str, str]] | None = None, multiple: bool = False
) -> list[str] | str:
    """文件对话框

    Args:
        file_types: 文件类型过滤器列表，格式为 [("描述", "*.ext")]
        multiple: 是否允许多选

    Returns:
        单选时返回文件路径字符串，多选时返回路径列表
    """
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # type: ignore[call-overload]

        ftypes: list[tuple[str, str]] = file_types if file_types else [("All files", "*.*")]

        if multiple:
            file_paths = filedialog.askopenfilenames(filetypes=ftypes)
            return list(file_paths) if file_paths else []
        else:
            file_path = filedialog.askopenfilename(filetypes=ftypes)
            return file_path
    except Exception as e:
        print(f"文件对话框错误: {e}")
        result: list[str] | str = [] if multiple else ""
        return result
    finally:
        if root:
            root.destroy()


def select_directory_dialog() -> str:
    """选择目录对话框

    Returns:
        选择的目录路径字符串，取消则返回空字符串
    """
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # type: ignore[call-overload]
        return filedialog.askdirectory()
    except Exception as e:
        print(f"目录选择错误: {e}")
        return ""
    finally:
        if root:
            root.destroy()


def new_project(directory: str) -> "ModProject | None":
    """创建新项目

    Args:
        directory: 项目目录路径

    Returns:
        成功时返回创建的 ModProject 对象，失败时返回 None
    """
    from models import ModProject

    if not directory:
        return None

    project_file = os.path.join(directory, "project.json")
    assets_dir = os.path.join(directory, "assets")

    project = ModProject()
    project.file_path = project_file

    try:
        os.makedirs(assets_dir, exist_ok=True)
        project.save()
        return project
    except Exception as e:
        popups.error(f"创建项目失败: {e}")
        return None


def new_project_dialog() -> "ModProject | None":
    """新建项目对话框

    显示目录选择对话框，创建项目并重置状态。

    Returns:
        成功时返回创建的 ModProject 对象，取消或失败时返回 None
    """
    directory = select_directory_dialog()
    if not directory:
        return None
    return new_project(directory)


def open_project_dialog() -> "ModProject | None":
    """打开项目对话框

    显示目录选择对话框，加载项目并重置状态。

    Returns:
        成功时返回加载的 ModProject 对象，取消或失败时返回 None
    """
    from models import ModProject
    from migrations import MigrationError, FutureVersionError

    directory = select_directory_dialog()
    if not directory:
        return None

    file_path = os.path.join(directory, "project.json")
    if not os.path.exists(file_path):
        popups.error(f"在 {directory} 中未找到 project.json")
        return None

    try:
        project, migrated = ModProject.load(file_path)
    except FutureVersionError as e:
        popups.error(str(e))
        return None
    except MigrationError as e:
        popups.error(f"项目迁移失败:\n{e}")
        return None

    if project is None:
        popups.error("无法加载项目文件，文件可能已损坏")
        return None

    if migrated:
        # 迁移后自动保存
        project.save()
        popups.success("项目已从旧版本迁移并保存")

    return project
