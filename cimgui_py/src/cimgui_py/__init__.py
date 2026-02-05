"""cimgui_py - Python bindings for Dear ImGui via cimgui."""

import os as _os
import sys as _sys
import ctypes as _ctypes

# =============================================================================
# DLL Loading Strategy for Windows
# =============================================================================
# cimgui.dll dynamically links to glfw3.dll. Windows DLL loader may load
# a different glfw3.dll instance than Python's glfw package, causing the
# GLFW backend to fail (window handle not found in its internal state).
#
# Solution:
# 1. Force-load Python glfw's glfw3.dll with ctypes BEFORE importing cimgui
# 2. Windows will reuse the already-loaded DLL when cimgui.dll loads
# =============================================================================

_lib_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), 'lib')

if _sys.platform == 'win32':
    # Add lib directory to DLL search path
    if _os.path.isdir(_lib_dir):
        _os.add_dll_directory(_lib_dir)

    # Pre-load glfw3.dll from Python glfw package
    try:
        import glfw as _glfw
        _glfw_dll_path = _os.path.join(_os.path.dirname(_glfw.__file__), 'glfw3.dll')
        if _os.path.exists(_glfw_dll_path):
            _ctypes.CDLL(_glfw_dll_path)
    except ImportError:
        pass  # glfw is optional

    # Pre-load cimgui.dll before Cython module import
    _cimgui_dll_path = _os.path.join(_lib_dir, 'cimgui.dll')
    if _os.path.exists(_cimgui_dll_path):
        _ctypes.CDLL(_cimgui_dll_path)

# Now safe to import Cython modules
from .core import *

__version__ = "0.1.0"
