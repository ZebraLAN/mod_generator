# -*- coding: utf-8 -*-
"""构建脚本 - Cython 扩展编译"""

import os
import sys
from pathlib import Path

from setuptools import setup, Extension
from Cython.Build import cythonize

# 项目根目录
ROOT = Path(__file__).parent

# cimgui 源码目录
CIMGUI_DIR = ROOT / "vendor" / "cimgui"
IMGUI_DIR = CIMGUI_DIR / "imgui"
BACKENDS_DIR = CIMGUI_DIR / "imgui" / "backends"

# 检查 cimgui 是否存在
if not CIMGUI_DIR.exists():
    print("错误: 请先获取 cimgui 源码")
    print("  git submodule add https://github.com/cimgui/cimgui vendor/cimgui")
    print("  cd vendor/cimgui && git submodule update --init")
    sys.exit(1)

# ImGui 源文件
IMGUI_SOURCES = [
    str(IMGUI_DIR / "imgui.cpp"),
    str(IMGUI_DIR / "imgui_demo.cpp"),
    str(IMGUI_DIR / "imgui_draw.cpp"),
    str(IMGUI_DIR / "imgui_tables.cpp"),
    str(IMGUI_DIR / "imgui_widgets.cpp"),
    str(CIMGUI_DIR / "cimgui.cpp"),
    # 后端
    str(BACKENDS_DIR / "imgui_impl_glfw.cpp"),
    str(BACKENDS_DIR / "imgui_impl_opengl3.cpp"),
]

# 包含目录
INCLUDE_DIRS = [
    str(CIMGUI_DIR),
    str(IMGUI_DIR),
    str(BACKENDS_DIR),
]

# 平台特定设置
if sys.platform == "win32":
    LIBRARIES = ["opengl32", "glfw3"]
    EXTRA_COMPILE_ARGS = ["/std:c++17"]
    EXTRA_LINK_ARGS = []
elif sys.platform == "darwin":
    LIBRARIES = ["glfw"]
    EXTRA_COMPILE_ARGS = ["-std=c++17"]
    EXTRA_LINK_ARGS = ["-framework", "OpenGL"]
else:  # Linux
    LIBRARIES = ["GL", "glfw"]
    EXTRA_COMPILE_ARGS = ["-std=c++17"]
    EXTRA_LINK_ARGS = []

# Cython 扩展模块
extensions = [
    Extension(
        "cimgui_py.core",
        sources=["src/imgui_core.pyx"] + IMGUI_SOURCES,
        include_dirs=INCLUDE_DIRS,
        libraries=LIBRARIES,
        extra_compile_args=EXTRA_COMPILE_ARGS,
        extra_link_args=EXTRA_LINK_ARGS,
        language="c++",
    ),
    Extension(
        "cimgui_py.backend",
        sources=["src/imgui_backend.pyx"],  # 不需要重复 IMGUI_SOURCES
        include_dirs=INCLUDE_DIRS,
        libraries=LIBRARIES,
        extra_compile_args=EXTRA_COMPILE_ARGS,
        extra_link_args=EXTRA_LINK_ARGS,
        language="c++",
    ),
]

setup(
    name="cimgui_py",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "embedsignature": True,
        },
    ),
    packages=["cimgui_py", "cimgui_py.integrations"],
    package_dir={"cimgui_py": "imgui"},
)
