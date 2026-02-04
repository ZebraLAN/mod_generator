# -*- coding: utf-8 -*-
"""构建脚本 - Cython 扩展编译

架构说明：
- cimgui 已预编译为 lib/cimgui.dll + lib/cimgui.lib
- Cython 只需要 cimgui.h 头文件 + 链接预编译的库
- 不编译任何 C++ 源文件
"""

import os
import sys
from pathlib import Path

from setuptools import setup, Extension
from Cython.Build import cythonize

# 项目根目录
ROOT = Path(__file__).parent

# cimgui 头文件目录
CIMGUI_DIR = ROOT / "vendor" / "cimgui"

# 预编译库目录
LIB_DIR = ROOT / "lib"

# 检查预编译库是否存在
if not (LIB_DIR / "cimgui.lib").exists():
    print("错误: 找不到预编译的 cimgui 库")
    print("请先编译 cimgui:")
    print("  cd vendor/cimgui")
    print("  mkdir build_dll && cd build_dll")
    print("  cmake .. -G \"Visual Studio 17 2022\" -A x64 -DIMGUI_STATIC=OFF")
    print("  cmake --build . --config Release")
    print("  cp Release/cimgui.dll Release/cimgui.lib ../../lib/")
    sys.exit(1)

# 包含目录 - 只需要 cimgui.h
INCLUDE_DIRS = [
    str(CIMGUI_DIR),
]

# 库目录
LIBRARY_DIRS = [
    str(LIB_DIR),
]

# 链接库
LIBRARIES = ["cimgui"]

# 宏定义 - 让 cimgui.h 自己定义所有类型
DEFINE_MACROS = [
    ("CIMGUI_DEFINE_ENUMS_AND_STRUCTS", None),
]

# 平台特定设置
if sys.platform == "win32":
    EXTRA_COMPILE_ARGS = []  # 纯 C，不需要 C++ 标准
    EXTRA_LINK_ARGS = []
elif sys.platform == "darwin":
    EXTRA_COMPILE_ARGS = []
    EXTRA_LINK_ARGS = []
else:  # Linux
    EXTRA_COMPILE_ARGS = []
    EXTRA_LINK_ARGS = []

# Cython 扩展模块
extensions = [
    Extension(
        "cimgui_py.core",
        sources=["src/imgui_core.pyx"],  # 只有 Cython 源文件！
        include_dirs=INCLUDE_DIRS,
        library_dirs=LIBRARY_DIRS,
        libraries=LIBRARIES,
        define_macros=DEFINE_MACROS,
        extra_compile_args=EXTRA_COMPILE_ARGS,
        extra_link_args=EXTRA_LINK_ARGS,
        language="c",  # 纯 C！不是 C++
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
)
