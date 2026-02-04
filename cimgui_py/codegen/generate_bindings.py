#!/usr/bin/env python3
"""从 cimgui JSON 定义生成 Cython 绑定

使用 cimgui/generator/output/ 中的 JSON 文件:
- definitions.json: 函数签名
- structs_and_enums.json: 结构体和枚举
- typedefs_dict.json: 类型别名
- impl_definitions.json: 后端实现函数

生成:
- cimgui.pxd: Cython 声明文件
- imgui_core.pyx: Python 绑定
- imgui.pyi: 类型存根
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any

# =============================================================================
# 配置
# =============================================================================

CIMGUI_OUTPUT_DIR = Path(__file__).parent.parent / "vendor/cimgui/generator/output"
SRC_DIR = Path(__file__).parent.parent / "src"
IMGUI_DIR = Path(__file__).parent.parent / "imgui"

# =============================================================================
# 类型映射
# =============================================================================

# C 类型 -> Cython 类型
C_TO_CYTHON = {
    "bool": "bint",
    "char": "char",
    "unsigned char": "unsigned char",
    "short": "short",
    "unsigned short": "unsigned short",
    "int": "int",
    "unsigned int": "unsigned int",
    "float": "float",
    "double": "double",
    "void": "void",
    "size_t": "size_t",
    "const char*": "const char*",
    "char*": "char*",
    "void*": "void*",
    "const void*": "const void*",
    # ImGui 特定类型保持原样
    "ImVec2": "ImVec2_c",
    "ImVec4": "ImVec4_c",
    "ImTextureRef": "ImTextureRef_c",
}

# C 类型 -> Python 类型提示
C_TO_PYTHON = {
    "bool": "bool",
    "bint": "bool",
    "char": "str",
    "int": "int",
    "unsigned int": "int",
    "short": "int",
    "unsigned short": "int",
    "float": "float",
    "double": "float",
    "void": "None",
    "size_t": "int",
    "const char*": "str",
    "char*": "str",
    "void*": "Any",
    "const void*": "Any",
    "ImVec2": "tuple[float, float]",
    "ImVec4": "tuple[float, float, float, float]",
    "ImVec2_c": "tuple[float, float]",
    "ImVec4_c": "tuple[float, float, float, float]",
    "ImGuiID": "int",
    "ImU32": "int",
    "ImTextureID": "int",
    "ImWchar": "int",
    "ImFont*": "_Font",
    "ImFontAtlas*": "_FontAtlas",
    "ImDrawList*": "_DrawList",
    "ImGuiIO*": "_IO",
    "ImGuiStyle*": "_Style",
}

# Python 默认值映射
DEFAULT_MAP = {
    "NULL": "None",
    "((void*)0)": "None",
    "true": "True",
    "false": "False",
    "ImVec2(0,0)": "(0, 0)",
    "ImVec2(0.0f,0.0f)": "(0, 0)",
    "ImVec2(-1,0)": "(-1, 0)",
    "ImVec2(1,0)": "(1, 0)",
    "ImVec2(0,1)": "(0, 1)",
    "ImVec2(1,1)": "(1, 1)",
    "ImVec4(0,0,0,0)": "(0, 0, 0, 0)",
    "ImVec4(1,1,1,1)": "(1, 1, 1, 1)",
    "FLT_MAX": "3.4028235e+38",
    "-FLT_MAX": "-3.4028235e+38",
}

# =============================================================================
# 过滤规则
# =============================================================================

# 排除的函数前缀 (内部 API)
EXCLUDE_PREFIXES = [
    "ImBitArray_", "ImChunkStream_", "ImPool_", "ImSpan_", "ImVector_",
    "ImGuiTextBuffer_", "ImGuiStorage_", "ImGuiListClipper_",
    "ImGuiInputTextState_", "ImGuiMenuColumns_", "ImGuiNavItemData_",
    "ImGuiNextWindowData_", "ImGuiNextItemData_", "ImGuiOldColumns_",
    "ImGuiPopupData_", "ImGuiSettingsHandler_", "ImGuiStackSizes_",
    "ImGuiStyleMod_", "ImGuiTabBar_", "ImGuiTabItem_", "ImGuiTable_",
    "ImGuiTableColumn_", "ImGuiTableInstanceData_", "ImGuiTableSettings_",
    "ImGuiTableColumnsSettings_", "ImGuiTableTempData_", "ImGuiViewportP_",
    "ImGuiWindow_", "ImGuiWindowSettings_", "ImGuiDockContext_",
    "ImGuiDockNode_", "ImGuiPlatformIO_", "ImGuiPlatformMonitor_",
    "ImRect_", "ImBitVector_", "ImDrawDataBuilder_", "ImDrawListSplitter_",
    "ImFontAtlasBuilder_", "ImFontGlyphRangesBuilder_",
    # Debug/Internal
    "igDebug", "igLog", "igIm", "igError", "igFind",
    "igNav", "igScroll", "igTable", "igDock", "igTab",
    "igWindow", "igItem", "igRender", "igBeginColumns", "igEndColumns",
    "igPopColumns", "igPushColumns",
]

# 公共 API 前缀
PUBLIC_PREFIXES = [
    "ig",  # ImGui:: 命名空间
    "ImFont_", "ImFontAtlas_", "ImFontBaked_", "ImFontConfig_",
    "ImDrawList_", "ImDrawData_", "ImDrawCmd_",
    "ImColor_", "ImTextureData_", "ImTextureRef_",
    "ImGuiIO_", "ImGuiStyle_", "ImGuiViewport_",
]

# 必须包含的函数 (覆盖排除规则)
FORCE_INCLUDE = {
    "igGetIO", "igGetStyle", "igGetDrawData", "igGetFont", "igGetFontSize",
    "igGetFontBaked", "igGetWindowDrawList", "igGetForegroundDrawList",
    "igGetBackgroundDrawList", "igGetWindowPos", "igGetWindowSize",
    "igGetCursorPos", "igGetCursorScreenPos", "igGetContentRegionAvail",
    "igGetItemRectMin", "igGetItemRectMax", "igGetItemRectSize",
    "igGetMousePos", "igGetMouseDragDelta", "igGetClipboardText",
    "igSetClipboardText", "igGetColorU32_Col", "igGetColorU32_Vec4",
    "igGetColorU32_U32", "igGetStyleColorVec4", "igGetScrollX", "igGetScrollY",
    "igGetScrollMaxX", "igGetScrollMaxY", "igGetID_Str", "igGetID_Ptr",
    "igGetID_Int", "igGetTime", "igGetFrameCount", "igGetVersion",
    "igSetNextWindowPos", "igSetNextWindowSize", "igSetNextWindowFocus",
    "igSetNextWindowBgAlpha", "igSetCursorPos", "igSetCursorPosX",
    "igSetCursorPosY", "igSetCursorScreenPos", "igSetScrollX", "igSetScrollY",
    "igSetScrollHereX", "igSetScrollHereY", "igSetItemAllowOverlap",
    "igSetTooltip", "igSetItemDefaultFocus", "igGetCursorPosX", "igGetCursorPosY",
}

# 公共枚举
PUBLIC_ENUMS = {
    "ImGuiWindowFlags_", "ImGuiChildFlags_", "ImGuiInputTextFlags_",
    "ImGuiTreeNodeFlags_", "ImGuiPopupFlags_", "ImGuiSelectableFlags_",
    "ImGuiComboFlags_", "ImGuiTabBarFlags_", "ImGuiTabItemFlags_",
    "ImGuiFocusedFlags_", "ImGuiHoveredFlags_", "ImGuiDockNodeFlags_",
    "ImGuiDragDropFlags_", "ImGuiDataType_", "ImGuiDir_",
    "ImGuiSortDirection_", "ImGuiKey_", "ImGuiCol_", "ImGuiStyleVar_",
    "ImGuiButtonFlags_", "ImGuiColorEditFlags_", "ImGuiSliderFlags_",
    "ImGuiMouseButton_", "ImGuiMouseCursor_", "ImGuiCond_",
    "ImGuiTableFlags_", "ImGuiTableColumnFlags_", "ImGuiTableRowFlags_",
    "ImGuiTableBgTarget_", "ImDrawFlags_", "ImDrawListFlags_",
    "ImFontAtlasFlags_", "ImFontFlags_", "ImGuiViewportFlags_",
    "ImGuiBackendFlags_", "ImGuiConfigFlags_", "ImTextureStatus_",
    "ImTextureFormat_", "ImGuiMultiSelectFlags_",
}

# 公共结构体 (需要完整定义)
PUBLIC_STRUCTS = {
    "ImVec2", "ImVec4", "ImFont", "ImFontBaked", "ImFontGlyph",
    "ImFontConfig", "ImFontAtlas", "ImFontAtlasRect",
    "ImDrawCmd", "ImDrawVert", "ImDrawList", "ImDrawData",
    "ImTextureData", "ImTextureRef", "ImTextureRect",
    "ImGuiIO", "ImGuiStyle", "ImGuiViewport",
}


# =============================================================================
# 数据加载
# =============================================================================

def load_json(filename: str) -> dict:
    """加载 JSON 文件"""
    path = CIMGUI_OUTPUT_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# 工具函数
# =============================================================================

def camel_to_snake(name: str) -> str:
    """CamelCase -> snake_case"""
    result = []
    for i, c in enumerate(name):
        if c.isupper():
            if i > 0 and not name[i-1].isupper():
                result.append("_")
            result.append(c.lower())
        else:
            result.append(c)
    return "".join(result)


def cimgui_to_python_name(cname: str) -> str:
    """cimgui 函数名 -> Python 函数名

    igBeginChild_Str -> begin_child
    ImFontAtlas_AddFont -> add_font (方法名)
    """
    # 移除前缀
    if cname.startswith("ig"):
        name = cname[2:]
    elif "_" in cname:
        # ImFontAtlas_AddFont -> AddFont
        name = cname.split("_", 1)[1]
    else:
        name = cname

    # 移除重载后缀
    for suffix in ["_Str", "_ID", "_Ptr", "_Int", "_Float", "_Vec2", "_Vec4",
                   "_Bool", "_BoolPtr", "_IntPtr", "_FloatPtr", "_Nil", "_Col",
                   "_U32", "_TreeNodeFlags"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    return camel_to_snake(name)


def is_public_function(name: str, overload: dict) -> bool:
    """判断函数是否是公共 API"""
    # 强制包含
    if name in FORCE_INCLUDE:
        return True

    # 排除内部 API
    for prefix in EXCLUDE_PREFIXES:
        if name.startswith(prefix):
            return False

    # 排除 vararg
    if "..." in overload.get("args", ""):
        return False

    # 排除 internal 位置
    location = overload.get("location", "")
    if "internal" in location.lower():
        return False

    # 公共前缀
    for prefix in PUBLIC_PREFIXES:
        if name.startswith(prefix):
            return True

    return False


def map_c_type_to_cython(ctype: str) -> str:
    """C 类型 -> Cython 类型"""
    ctype = ctype.strip()

    # 直接映射
    if ctype in C_TO_CYTHON:
        return C_TO_CYTHON[ctype]

    # 处理 const
    if ctype.startswith("const "):
        inner = map_c_type_to_cython(ctype[6:])
        return f"const {inner}"

    # 处理指针
    if ctype.endswith("*"):
        inner = map_c_type_to_cython(ctype[:-1].strip())
        return f"{inner}*"

    # 处理数组 (简化)
    if "[" in ctype:
        base = ctype.split("[")[0].strip()
        return map_c_type_to_cython(base)

    # 保持原样
    return ctype


def map_c_type_to_python(ctype: str) -> str:
    """C 类型 -> Python 类型提示"""
    ctype = ctype.strip()

    # 直接映射
    if ctype in C_TO_PYTHON:
        return C_TO_PYTHON[ctype]

    # 指针类型
    if ctype.endswith("*"):
        base = ctype[:-1].strip()
        if base in C_TO_PYTHON:
            return C_TO_PYTHON[base]
        if base.startswith("Im"):
            return f"_{base}"
        return "Any"

    # ImGui 类型
    if ctype.startswith("ImGui"):
        return "int"  # 通常是 flags
    if ctype.startswith("Im"):
        return "int"  # ImU32, ImGuiID 等

    return "Any"


def map_default_value(default: str) -> str:
    """C 默认值 -> Python 默认值"""
    if default in DEFAULT_MAP:
        return DEFAULT_MAP[default]

    # 数字
    if re.match(r'^-?\d+\.?\d*f?$', default):
        return default.rstrip('f')

    # 十六进制
    if default.startswith("0x"):
        return default

    return default


# =============================================================================
# PXD 生成器
# =============================================================================

class PxdGenerator:
    """生成 cimgui.pxd"""

    def __init__(self):
        self.definitions = load_json("definitions.json")
        self.structs_enums = load_json("structs_and_enums.json")
        self.typedefs = load_json("typedefs_dict.json")
        self.lines: list[str] = []

    def emit(self, line: str = "", indent: int = 0) -> None:
        """添加一行"""
        self.lines.append("    " * indent + line)

    def generate_header(self) -> None:
        """文件头"""
        self.emit("# cython: language_level=3")
        self.emit("# cimgui.pxd - Auto-generated from cimgui JSON definitions")
        self.emit("# Dear ImGui 1.92.x (docking branch)")
        self.emit("#")
        self.emit("# DO NOT EDIT - regenerate with: python codegen/generate_bindings.py --pxd")
        self.emit()
        self.emit("from libc.stdint cimport uint8_t, uint16_t, uint32_t, uint64_t, int8_t, int16_t, int32_t, int64_t")
        self.emit("from libc.stddef cimport size_t")
        self.emit()
        self.emit('cdef extern from "cimgui.h":')

    def generate_typedefs(self) -> None:
        """基础类型别名"""
        self.emit()
        self.emit("# " + "=" * 74, 1)
        self.emit("# Basic Types", 1)
        self.emit("# " + "=" * 74, 1)

        basic_types = [
            ("ImGuiID", "uint32_t"),
            ("ImU8", "uint8_t"),
            ("ImU16", "uint16_t"),
            ("ImU32", "uint32_t"),
            ("ImU64", "uint64_t"),
            ("ImS8", "int8_t"),
            ("ImS16", "int16_t"),
            ("ImS32", "int32_t"),
            ("ImS64", "int64_t"),
            ("ImWchar16", "uint16_t"),
            ("ImWchar32", "uint32_t"),
            ("ImWchar", "ImWchar16"),
            ("ImTextureID", "uint64_t"),
            ("ImDrawIdx", "unsigned short"),
            ("ImFontAtlasRectId", "int"),
        ]

        for name, target in basic_types:
            self.emit(f"ctypedef {target} {name}", 1)

        self.emit()
        self.emit("# Flag types", 1)

        flag_types = sorted([
            name for name, typedef in self.typedefs.items()
            if typedef == "int" and name.startswith("Im")
        ])

        for name in flag_types[:40]:  # 限制数量
            self.emit(f"ctypedef int {name}", 1)

    def generate_forward_decls(self) -> None:
        """前向声明"""
        self.emit()
        self.emit("# " + "=" * 74, 1)
        self.emit("# Forward Declarations", 1)
        self.emit("# " + "=" * 74, 1)

        structs = [
            "ImGuiContext", "ImGuiIO", "ImGuiStyle", "ImGuiViewport",
            "ImGuiPlatformIO", "ImDrawData", "ImDrawList", "ImDrawCmd",
            "ImDrawVert", "ImFont", "ImFontAtlas", "ImFontBaked",
            "ImFontConfig", "ImFontGlyph", "ImFontAtlasRect",
            "ImTextureData", "ImGuiInputTextCallbackData",
            "ImDrawListSharedData", "ImDrawChannel",
        ]

        for name in structs:
            self.emit(f"ctypedef struct {name}", 1)

        self.emit()
        self.emit("# Callback types", 1)
        self.emit("ctypedef int (*ImGuiInputTextCallback)(ImGuiInputTextCallbackData* data)", 1)
        self.emit("ctypedef void (*ImGuiSizeCallback)(void* data)", 1)
        self.emit("ctypedef void (*ImDrawCallback)(const ImDrawList* parent_list, const ImDrawCmd* cmd)", 1)

    def generate_vectors(self) -> None:
        """向量类型"""
        self.emit()
        self.emit("# " + "=" * 74, 1)
        self.emit("# Vector Types", 1)
        self.emit("# " + "=" * 74, 1)

        self.emit("ctypedef struct ImVec2_c:", 1)
        self.emit("float x", 2)
        self.emit("float y", 2)
        self.emit()
        self.emit("ctypedef struct ImVec4_c:", 1)
        self.emit("float x", 2)
        self.emit("float y", 2)
        self.emit("float z", 2)
        self.emit("float w", 2)

    def generate_enums(self) -> None:
        """枚举"""
        self.emit()
        self.emit("# " + "=" * 74, 1)
        self.emit("# Enums", 1)
        self.emit("# " + "=" * 74, 1)

        enums = self.structs_enums.get("enums", {})

        for enum_name in sorted(enums.keys()):
            if enum_name not in PUBLIC_ENUMS:
                continue

            values = enums[enum_name]
            self.emit()
            self.emit(f"cdef enum {enum_name}:", 1)

            for item in values:
                name = item["name"]
                calc_value = item.get("calc_value")
                if calc_value is not None:
                    self.emit(f"{name} = {calc_value}", 2)
                else:
                    self.emit(f"{name}", 2)

    def generate_structs(self) -> None:
        """结构体"""
        self.emit()
        self.emit("# " + "=" * 74, 1)
        self.emit("# Structs", 1)
        self.emit("# " + "=" * 74, 1)

        structs = self.structs_enums.get("structs", {})

        # 1.92 特殊结构体 (手动定义)
        self.emit()
        self.emit("# Texture types (1.92)", 1)
        self.emit("ctypedef struct ImTextureRef_c:", 1)
        self.emit("ImTextureData* _TexData", 2)
        self.emit("ImTextureID _TexID", 2)

        self.emit()
        self.emit("ctypedef struct ImTextureRect:", 1)
        self.emit("unsigned short x, y, w, h", 2)

        self.emit()
        self.emit("ctypedef enum ImTextureStatus_:", 1)
        self.emit("ImTextureStatus_OK = 0", 2)
        self.emit("ImTextureStatus_Destroyed = 1", 2)
        self.emit("ImTextureStatus_WantCreate = 2", 2)
        self.emit("ImTextureStatus_WantUpdates = 3", 2)
        self.emit("ImTextureStatus_WantDestroy = 4", 2)

        self.emit()
        self.emit("ctypedef enum ImTextureFormat_:", 1)
        self.emit("ImTextureFormat_RGBA32 = 0", 2)
        self.emit("ImTextureFormat_Alpha8 = 1", 2)

        # 从 JSON 生成常用结构体
        for struct_name in sorted(PUBLIC_STRUCTS):
            if struct_name in ["ImVec2", "ImVec4"]:  # 已手动定义
                continue
            if struct_name not in structs:
                continue

            fields = structs[struct_name]
            self.emit()
            self.emit(f"ctypedef struct {struct_name}:", 1)

            field_count = 0
            for field in fields:
                fname = field["name"]
                ftype = field["type"]

                # 跳过复杂字段
                if "[" in fname or "(" in fname:
                    continue
                if "ImVector" in ftype or "ImPool" in ftype:
                    continue
                if "callback" in fname.lower():
                    continue

                cython_type = map_c_type_to_cython(ftype)
                self.emit(f"{cython_type} {fname}", 2)
                field_count += 1

                if field_count >= 20:  # 限制每个结构体的字段数
                    self.emit("# ... (truncated)", 2)
                    break

            if field_count == 0:
                self.emit("pass", 2)

    def generate_functions(self) -> None:
        """函数声明"""
        self.emit()
        self.emit("# " + "=" * 74, 1)
        self.emit("# Functions", 1)
        self.emit("# " + "=" * 74, 1)

        # 按类别分组
        categories = {
            "Context": [],
            "Frame": [],
            "Window": [],
            "Child": [],
            "Style": [],
            "Font": [],
            "Cursor": [],
            "Widget": [],
            "Draw": [],
            "Input": [],
            "Other": [],
        }

        for func_name, overloads in sorted(self.definitions.items()):
            for overload in overloads:
                if not is_public_function(func_name, overload):
                    continue

                cimguiname = overload.get("ov_cimguiname", func_name)
                ret = overload.get("ret", "void")
                args_t = overload.get("argsT", [])

                # 转换
                ret_type = map_c_type_to_cython(ret)
                params = []
                for arg in args_t:
                    arg_type = map_c_type_to_cython(arg["type"])
                    arg_name = arg["name"]
                    params.append(f"{arg_type} {arg_name}")

                params_str = ", ".join(params)
                line = f"{ret_type} {cimguiname}({params_str})"

                # 分类
                if "Context" in cimguiname or cimguiname in ["igCreateContext", "igDestroyContext"]:
                    categories["Context"].append(line)
                elif "Frame" in cimguiname or cimguiname in ["igNewFrame", "igEndFrame", "igRender"]:
                    categories["Frame"].append(line)
                elif "Window" in cimguiname and "Child" not in cimguiname:
                    categories["Window"].append(line)
                elif "Child" in cimguiname:
                    categories["Child"].append(line)
                elif "Style" in cimguiname or "Color" in cimguiname:
                    categories["Style"].append(line)
                elif "Font" in cimguiname:
                    categories["Font"].append(line)
                elif "Cursor" in cimguiname or "Scroll" in cimguiname:
                    categories["Cursor"].append(line)
                elif "Draw" in cimguiname:
                    categories["Draw"].append(line)
                elif "Mouse" in cimguiname or "Key" in cimguiname:
                    categories["Input"].append(line)
                else:
                    categories["Widget"].append(line)

        for cat_name, funcs in categories.items():
            if not funcs:
                continue
            self.emit()
            self.emit(f"# {cat_name}", 1)
            for func in funcs:
                self.emit(func, 1)

    def generate_backend(self) -> None:
        """后端声明"""
        self.emit()
        self.emit()
        self.emit("# " + "=" * 78)
        self.emit("# Backend Declarations")
        self.emit("# " + "=" * 78)
        self.emit()
        self.emit('cdef extern from "cimgui_impl.h":')
        self.emit("# GLFW", 1)
        self.emit("bint ImGui_ImplGlfw_InitForOpenGL(void* window, bint install_callbacks)", 1)
        self.emit("bint ImGui_ImplGlfw_InitForVulkan(void* window, bint install_callbacks)", 1)
        self.emit("bint ImGui_ImplGlfw_InitForOther(void* window, bint install_callbacks)", 1)
        self.emit("void ImGui_ImplGlfw_Shutdown()", 1)
        self.emit("void ImGui_ImplGlfw_NewFrame()", 1)
        self.emit()
        self.emit("# OpenGL3", 1)
        self.emit("bint ImGui_ImplOpenGL3_Init(const char* glsl_version)", 1)
        self.emit("void ImGui_ImplOpenGL3_Shutdown()", 1)
        self.emit("void ImGui_ImplOpenGL3_NewFrame()", 1)
        self.emit("void ImGui_ImplOpenGL3_RenderDrawData(ImDrawData* draw_data)", 1)

    def generate(self) -> str:
        """生成完整文件"""
        self.lines = []
        self.generate_header()
        self.generate_typedefs()
        self.generate_forward_decls()
        self.generate_vectors()
        self.generate_enums()
        self.generate_structs()
        self.generate_functions()
        self.generate_backend()
        return "\n".join(self.lines)


# =============================================================================
# PYX 生成器
# =============================================================================

@dataclass
class FunctionInfo:
    """函数信息"""
    c_name: str
    py_name: str
    ret_type: str
    args: list[dict]
    defaults: dict
    is_method: bool = False
    class_name: str = ""


class PyxGenerator:
    """生成 imgui_core.pyx"""

    def __init__(self):
        self.definitions = load_json("definitions.json")
        self.lines: list[str] = []
        self.functions: list[FunctionInfo] = []

    def emit(self, line: str = "", indent: int = 0) -> None:
        self.lines.append("    " * indent + line)

    def collect_functions(self) -> None:
        """收集公共函数"""
        for func_name, overloads in self.definitions.items():
            for overload in overloads:
                if not is_public_function(func_name, overload):
                    continue

                cimguiname = overload.get("ov_cimguiname", func_name)
                py_name = cimgui_to_python_name(cimguiname)
                ret = overload.get("ret", "void")
                args_t = overload.get("argsT", [])
                defaults = overload.get("defaults", {})

                # 判断是否是方法
                is_method = False
                class_name = ""
                if "_" in func_name and not func_name.startswith("ig"):
                    parts = func_name.split("_", 1)
                    if parts[0].startswith("Im"):
                        is_method = True
                        class_name = parts[0]

                self.functions.append(FunctionInfo(
                    c_name=cimguiname,
                    py_name=py_name,
                    ret_type=ret,
                    args=args_t,
                    defaults=defaults,
                    is_method=is_method,
                    class_name=class_name,
                ))

    def generate_header(self) -> None:
        """文件头"""
        self.emit("# cython: language_level=3")
        self.emit("# cython: embedsignature=True")
        self.emit('"""imgui_core.pyx - Auto-generated ImGui bindings')
        self.emit()
        self.emit("DO NOT EDIT - regenerate with: python codegen/generate_bindings.py --pyx")
        self.emit('"""')
        self.emit()
        self.emit("from libc.stdlib cimport malloc, free")
        self.emit("from libc.string cimport memcpy, strlen")
        self.emit("from cpython.bytes cimport PyBytes_AsString")
        self.emit()
        self.emit("cimport cimgui")
        self.emit()

    def generate_helpers(self) -> None:
        """辅助函数"""
        self.emit("# " + "=" * 77)
        self.emit("# Helpers")
        self.emit("# " + "=" * 77)
        self.emit()
        self.emit("cdef inline bytes _to_bytes(s):")
        self.emit('"""str -> bytes"""', 1)
        self.emit("if isinstance(s, bytes):", 1)
        self.emit("return s", 2)
        self.emit("return s.encode('utf-8')", 1)
        self.emit()
        self.emit("cdef inline cimgui.ImVec2_c _vec2(val):")
        self.emit('"""tuple/list -> ImVec2_c"""', 1)
        self.emit("cdef cimgui.ImVec2_c v", 1)
        self.emit("v.x = <float>val[0] if len(val) > 0 else 0", 1)
        self.emit("v.y = <float>val[1] if len(val) > 1 else 0", 1)
        self.emit("return v", 1)
        self.emit()
        self.emit("cdef inline cimgui.ImVec4_c _vec4(val):")
        self.emit('"""tuple/list -> ImVec4_c"""', 1)
        self.emit("cdef cimgui.ImVec4_c v", 1)
        self.emit("v.x = <float>val[0] if len(val) > 0 else 0", 1)
        self.emit("v.y = <float>val[1] if len(val) > 1 else 0", 1)
        self.emit("v.z = <float>val[2] if len(val) > 2 else 0", 1)
        self.emit("v.w = <float>val[3] if len(val) > 3 else 0", 1)
        self.emit("return v", 1)
        self.emit()

    def generate_function(self, func: FunctionInfo) -> None:
        """生成单个函数"""
        # 构建参数列表
        params = []
        call_args = []
        pre_call = []

        for arg in func.args:
            arg_name = arg["name"]
            arg_type = arg["type"]

            # self 参数跳过
            if arg_name == "self":
                continue

            # 默认值
            default = func.defaults.get(arg_name)
            default_str = ""
            if default:
                default_str = f"={map_default_value(default)}"

            # 类型转换
            if "char*" in arg_type:
                params.append(f"str {arg_name}{default_str}")
                pre_call.append(f"cdef bytes b_{arg_name} = _to_bytes({arg_name})")
                call_args.append(f"b_{arg_name}")
            elif arg_type == "ImVec2":
                params.append(f"{arg_name}{default_str}")
                call_args.append(f"_vec2({arg_name})")
            elif arg_type == "ImVec4":
                params.append(f"{arg_name}{default_str}")
                call_args.append(f"_vec4({arg_name})")
            elif arg_type == "bool":
                params.append(f"bint {arg_name}{default_str}")
                call_args.append(arg_name)
            elif arg_type in ("int", "float", "double"):
                params.append(f"{arg_type} {arg_name}{default_str}")
                call_args.append(arg_name)
            elif arg_type.startswith("ImGui") and not arg_type.endswith("*"):
                params.append(f"int {arg_name}{default_str}")
                call_args.append(arg_name)
            else:
                params.append(f"{arg_name}{default_str}")
                call_args.append(arg_name)

        params_str = ", ".join(params)
        call_str = ", ".join(call_args)

        # 函数定义
        self.emit()
        self.emit(f"def {func.py_name}({params_str}):")
        self.emit(f'"""TODO: {func.c_name}"""', 1)

        # 预处理
        for line in pre_call:
            self.emit(line, 1)

        # 调用
        if func.ret_type == "void":
            self.emit(f"cimgui.{func.c_name}({call_str})", 1)
        elif func.ret_type == "bool":
            self.emit(f"return cimgui.{func.c_name}({call_str})", 1)
        elif func.ret_type == "ImVec2":
            self.emit(f"cdef cimgui.ImVec2_c ret = cimgui.{func.c_name}({call_str})", 1)
            self.emit("return (ret.x, ret.y)", 1)
        elif func.ret_type == "ImVec4":
            self.emit(f"cdef cimgui.ImVec4_c ret = cimgui.{func.c_name}({call_str})", 1)
            self.emit("return (ret.x, ret.y, ret.z, ret.w)", 1)
        else:
            self.emit(f"return cimgui.{func.c_name}({call_str})", 1)

    def generate(self) -> str:
        """生成完整文件"""
        self.lines = []
        self.collect_functions()
        self.generate_header()
        self.generate_helpers()

        self.emit()
        self.emit("# " + "=" * 77)
        self.emit("# Functions")
        self.emit("# " + "=" * 77)

        # 只生成 ig* 函数 (不是方法)
        for func in self.functions:
            if func.c_name.startswith("ig") and not func.is_method:
                self.generate_function(func)

        return "\n".join(self.lines)


# =============================================================================
# PYI 生成器
# =============================================================================

class PyiGenerator:
    """生成 imgui.pyi 类型存根"""

    def __init__(self):
        self.definitions = load_json("definitions.json")
        self.structs_enums = load_json("structs_and_enums.json")
        self.lines: list[str] = []

    def emit(self, line: str = "") -> None:
        self.lines.append(line)

    def generate_header(self) -> None:
        self.emit('"""Type stubs for imgui module')
        self.emit()
        self.emit("DO NOT EDIT - regenerate with: python codegen/generate_bindings.py --pyi")
        self.emit('"""')
        self.emit()
        self.emit("from typing import Any, Optional, Tuple, Union, overload")
        self.emit()

    def generate_constants(self) -> None:
        """生成常量"""
        self.emit("# " + "=" * 77)
        self.emit("# Constants")
        self.emit("# " + "=" * 77)
        self.emit()

        enums = self.structs_enums.get("enums", {})

        for enum_name in sorted(PUBLIC_ENUMS):
            if enum_name not in enums:
                continue

            self.emit(f"# {enum_name}")
            for item in enums[enum_name]:
                name = item["name"]
                value = item.get("calc_value", 0)
                self.emit(f"{name}: int = {value}")
            self.emit()

    def generate_classes(self) -> None:
        """生成类存根"""
        self.emit("# " + "=" * 77)
        self.emit("# Classes")
        self.emit("# " + "=" * 77)
        self.emit()

        # Vec2
        self.emit("class Vec2:")
        self.emit("    x: float")
        self.emit("    y: float")
        self.emit("    def __init__(self, x: float = 0, y: float = 0) -> None: ...")
        self.emit()

        # Vec4
        self.emit("class Vec4:")
        self.emit("    x: float")
        self.emit("    y: float")
        self.emit("    z: float")
        self.emit("    w: float")
        self.emit("    def __init__(self, x: float = 0, y: float = 0, z: float = 0, w: float = 0) -> None: ...")
        self.emit()

        # _Font
        self.emit("class _Font:")
        self.emit("    @property")
        self.emit("    def legacy_size(self) -> float: ...")
        self.emit("    @property")
        self.emit("    def font_id(self) -> int: ...")
        self.emit("    def is_loaded(self) -> bool: ...")
        self.emit("    def get_debug_name(self) -> str: ...")
        self.emit("    def get_font_baked(self, size: float, density: float = 1.0) -> _FontBaked: ...")
        self.emit()

        # _FontBaked
        self.emit("class _FontBaked:")
        self.emit("    @property")
        self.emit("    def size(self) -> float: ...")
        self.emit("    @property")
        self.emit("    def ascent(self) -> float: ...")
        self.emit("    @property")
        self.emit("    def descent(self) -> float: ...")
        self.emit("    def find_glyph(self, codepoint: int) -> Optional[dict]: ...")
        self.emit("    def get_char_advance(self, codepoint: int) -> float: ...")
        self.emit("    def is_glyph_loaded(self, codepoint: int) -> bool: ...")
        self.emit()

        # _FontAtlas
        self.emit("class _FontAtlas:")
        self.emit("    def add_font_default(self) -> _Font: ...")
        self.emit("    def add_font_from_file_ttf(self, filename: str, size_pixels: float, glyph_ranges: Optional[list] = None, merge_mode: bool = False) -> _Font: ...")
        self.emit("    def build(self) -> bool: ...")
        self.emit("    def clear_fonts(self) -> None: ...")
        self.emit("    def clear(self) -> None: ...")
        self.emit("    def remove_font(self, font: _Font) -> None: ...")
        self.emit("    def compact_cache(self) -> None: ...")
        self.emit("    def get_tex_data_as_rgba32(self) -> Tuple[bytes, int, int]: ...")
        self.emit("    def set_tex_id(self, tex_id: int) -> None: ...")
        self.emit("    def get_glyph_ranges_default(self) -> list: ...")
        self.emit("    def get_glyph_ranges_chinese_full(self) -> list: ...")
        self.emit("    def get_glyph_ranges_chinese_simplified_common(self) -> list: ...")
        self.emit()

        # _IO
        self.emit("class _IO:")
        self.emit("    @property")
        self.emit("    def display_size(self) -> Vec2: ...")
        self.emit("    @display_size.setter")
        self.emit("    def display_size(self, value: Tuple[float, float]) -> None: ...")
        self.emit("    @property")
        self.emit("    def delta_time(self) -> float: ...")
        self.emit("    @delta_time.setter")
        self.emit("    def delta_time(self, value: float) -> None: ...")
        self.emit("    @property")
        self.emit("    def fonts(self) -> _FontAtlas: ...")
        self.emit()

        # _Style
        self.emit("class _Style:")
        self.emit("    @property")
        self.emit("    def alpha(self) -> float: ...")
        self.emit("    @alpha.setter")
        self.emit("    def alpha(self, value: float) -> None: ...")
        self.emit("    @property")
        self.emit("    def window_padding(self) -> Vec2: ...")
        self.emit("    @window_padding.setter")
        self.emit("    def window_padding(self, value: Tuple[float, float]) -> None: ...")
        self.emit("    # ... more properties")
        self.emit()

        # _DrawList
        self.emit("class _DrawList:")
        self.emit("    def add_line(self, p1: Tuple[float, float], p2: Tuple[float, float], col: int, thickness: float = 1.0) -> None: ...")
        self.emit("    def add_rect(self, p_min: Tuple[float, float], p_max: Tuple[float, float], col: int, rounding: float = 0, flags: int = 0, thickness: float = 1.0) -> None: ...")
        self.emit("    def add_rect_filled(self, p_min: Tuple[float, float], p_max: Tuple[float, float], col: int, rounding: float = 0, flags: int = 0) -> None: ...")
        self.emit("    def add_circle(self, center: Tuple[float, float], radius: float, col: int, num_segments: int = 0, thickness: float = 1.0) -> None: ...")
        self.emit("    def add_circle_filled(self, center: Tuple[float, float], radius: float, col: int, num_segments: int = 0) -> None: ...")
        self.emit("    def add_text(self, pos: Tuple[float, float], col: int, text: str) -> None: ...")
        self.emit("    def add_image(self, tex_id: int, p_min: Tuple[float, float], p_max: Tuple[float, float], uv_min: Tuple[float, float] = (0, 0), uv_max: Tuple[float, float] = (1, 1), col: int = 0xFFFFFFFF) -> None: ...")
        self.emit()

    def generate_functions(self) -> None:
        """生成函数存根"""
        self.emit("# " + "=" * 77)
        self.emit("# Functions")
        self.emit("# " + "=" * 77)
        self.emit()

        # Core
        self.emit("# Core")
        self.emit("def create_context() -> None: ...")
        self.emit("def destroy_context() -> None: ...")
        self.emit("def get_io() -> _IO: ...")
        self.emit("def get_style() -> _Style: ...")
        self.emit("def new_frame() -> None: ...")
        self.emit("def end_frame() -> None: ...")
        self.emit("def render() -> None: ...")
        self.emit()

        # Window
        self.emit("# Window")
        self.emit("def begin(name: str, closable: Optional[bool] = None, flags: int = 0) -> Union[bool, Tuple[bool, bool]]: ...")
        self.emit("def end() -> None: ...")
        self.emit("def begin_child(label: str, width: float = 0, height: float = 0, child_flags: int = 0, window_flags: int = 0) -> bool: ...")
        self.emit("def end_child() -> None: ...")
        self.emit()

        # Widgets
        self.emit("# Widgets")
        self.emit("def text(s: str) -> None: ...")
        self.emit("def text_colored(color: Tuple[float, float, float, float], s: str) -> None: ...")
        self.emit("def text_disabled(s: str) -> None: ...")
        self.emit("def text_wrapped(s: str) -> None: ...")
        self.emit("def button(label: str, width: float = 0, height: float = 0) -> bool: ...")
        self.emit("def small_button(label: str) -> bool: ...")
        self.emit("def invisible_button(str_id: str, width: float, height: float, flags: int = 0) -> bool: ...")
        self.emit("def checkbox(label: str, state: bool) -> Tuple[bool, bool]: ...")
        self.emit("def radio_button(label: str, active: bool) -> bool: ...")
        self.emit()

        # Input
        self.emit("# Input")
        self.emit("def input_text(label: str, value: str, buffer_size: int = 256, flags: int = 0) -> Tuple[bool, str]: ...")
        self.emit("def input_text_multiline(label: str, value: str, width: float = 0, height: float = 0, buffer_size: int = 4096, flags: int = 0) -> Tuple[bool, str]: ...")
        self.emit("def input_int(label: str, value: int, step: int = 1, step_fast: int = 100, flags: int = 0) -> Tuple[bool, int]: ...")
        self.emit("def input_float(label: str, value: float, step: float = 0, step_fast: float = 0, format: str = '%.3f', flags: int = 0) -> Tuple[bool, float]: ...")
        self.emit()

        # Sliders
        self.emit("# Sliders")
        self.emit("def slider_float(label: str, value: float, v_min: float, v_max: float, format: str = '%.3f', flags: int = 0) -> Tuple[bool, float]: ...")
        self.emit("def slider_int(label: str, value: int, v_min: int, v_max: int, format: str = '%d', flags: int = 0) -> Tuple[bool, int]: ...")
        self.emit("def drag_float(label: str, value: float, v_speed: float = 1.0, v_min: float = 0, v_max: float = 0, format: str = '%.3f', flags: int = 0) -> Tuple[bool, float]: ...")
        self.emit("def drag_int(label: str, value: int, v_speed: float = 1.0, v_min: int = 0, v_max: int = 0, format: str = '%d', flags: int = 0) -> Tuple[bool, int]: ...")
        self.emit()

        # Combo/List
        self.emit("# Combo/List")
        self.emit("def begin_combo(label: str, preview_value: str, flags: int = 0) -> bool: ...")
        self.emit("def end_combo() -> None: ...")
        self.emit("def selectable(label: str, selected: bool = False, flags: int = 0, width: float = 0, height: float = 0) -> Tuple[bool, bool]: ...")
        self.emit()

        # Tree
        self.emit("# Tree")
        self.emit("def tree_node(label: str) -> bool: ...")
        self.emit("def tree_node_ex(label: str, flags: int = 0) -> bool: ...")
        self.emit("def tree_pop() -> None: ...")
        self.emit("def collapsing_header(label: str, visible: Optional[bool] = None, flags: int = 0) -> Union[bool, Tuple[bool, bool]]: ...")
        self.emit()

        # Tab
        self.emit("# Tab")
        self.emit("def begin_tab_bar(str_id: str, flags: int = 0) -> bool: ...")
        self.emit("def end_tab_bar() -> None: ...")
        self.emit("def begin_tab_item(label: str, opened: Optional[bool] = None, flags: int = 0) -> Tuple[bool, bool]: ...")
        self.emit("def end_tab_item() -> None: ...")
        self.emit()

        # Table
        self.emit("# Table")
        self.emit("def begin_table(str_id: str, column: int, flags: int = 0, outer_size: Tuple[float, float] = (0, 0), inner_width: float = 0) -> bool: ...")
        self.emit("def end_table() -> None: ...")
        self.emit("def table_next_row(row_flags: int = 0, min_row_height: float = 0) -> None: ...")
        self.emit("def table_next_column() -> bool: ...")
        self.emit("def table_set_column_index(column_n: int) -> bool: ...")
        self.emit("def table_setup_column(label: str, flags: int = 0, init_width_or_weight: float = 0, user_id: int = 0) -> None: ...")
        self.emit("def table_headers_row() -> None: ...")
        self.emit()

        # Popup
        self.emit("# Popup")
        self.emit("def begin_popup(str_id: str, flags: int = 0) -> bool: ...")
        self.emit("def begin_popup_modal(name: str, opened: Optional[bool] = None, flags: int = 0) -> Union[bool, Tuple[bool, bool]]: ...")
        self.emit("def end_popup() -> None: ...")
        self.emit("def open_popup(str_id: str, popup_flags: int = 0) -> None: ...")
        self.emit("def close_current_popup() -> None: ...")
        self.emit("def begin_popup_context_item(str_id: str = '', popup_flags: int = 1) -> bool: ...")
        self.emit("def begin_popup_context_window(str_id: str = '', popup_flags: int = 1) -> bool: ...")
        self.emit("def is_popup_open(str_id: str, flags: int = 0) -> bool: ...")
        self.emit()

        # Menu
        self.emit("# Menu")
        self.emit("def begin_menu_bar() -> bool: ...")
        self.emit("def end_menu_bar() -> None: ...")
        self.emit("def begin_main_menu_bar() -> bool: ...")
        self.emit("def end_main_menu_bar() -> None: ...")
        self.emit("def begin_menu(label: str, enabled: bool = True) -> bool: ...")
        self.emit("def end_menu() -> None: ...")
        self.emit("def menu_item(label: str, shortcut: str = '', selected: bool = False, enabled: bool = True) -> Tuple[bool, bool]: ...")
        self.emit()

        # Layout
        self.emit("# Layout")
        self.emit("def separator() -> None: ...")
        self.emit("def same_line(offset_from_start_x: float = 0, spacing: float = -1) -> None: ...")
        self.emit("def new_line() -> None: ...")
        self.emit("def spacing() -> None: ...")
        self.emit("def dummy(width: float, height: float) -> None: ...")
        self.emit("def indent(indent_w: float = 0) -> None: ...")
        self.emit("def unindent(indent_w: float = 0) -> None: ...")
        self.emit("def begin_group() -> None: ...")
        self.emit("def end_group() -> None: ...")
        self.emit()

        # Cursor
        self.emit("# Cursor")
        self.emit("def get_cursor_pos() -> Vec2: ...")
        self.emit("def get_cursor_pos_x() -> float: ...")
        self.emit("def get_cursor_pos_y() -> float: ...")
        self.emit("def set_cursor_pos(pos: Tuple[float, float]) -> None: ...")
        self.emit("def set_cursor_pos_x(local_x: float) -> None: ...")
        self.emit("def set_cursor_pos_y(local_y: float) -> None: ...")
        self.emit("def get_cursor_screen_pos() -> Vec2: ...")
        self.emit("def set_cursor_screen_pos(pos: Tuple[float, float]) -> None: ...")
        self.emit()

        # Window Utilities
        self.emit("# Window Utilities")
        self.emit("def set_next_window_pos(pos: Tuple[float, float], cond: int = 0, pivot: Tuple[float, float] = (0, 0)) -> None: ...")
        self.emit("def set_next_window_size(size: Tuple[float, float], cond: int = 0) -> None: ...")
        self.emit("def set_next_window_focus() -> None: ...")
        self.emit("def set_next_window_bg_alpha(alpha: float) -> None: ...")
        self.emit("def get_window_pos() -> Vec2: ...")
        self.emit("def get_window_size() -> Vec2: ...")
        self.emit("def get_window_width() -> float: ...")
        self.emit("def get_window_height() -> float: ...")
        self.emit("def is_window_focused(flags: int = 0) -> bool: ...")
        self.emit("def is_window_hovered(flags: int = 0) -> bool: ...")
        self.emit("def get_window_draw_list() -> _DrawList: ...")
        self.emit()

        # Content Region
        self.emit("# Content Region")
        self.emit("def get_content_region_available() -> Vec2: ...")
        self.emit("def push_item_width(item_width: float) -> None: ...")
        self.emit("def pop_item_width() -> None: ...")
        self.emit("def set_next_item_width(item_width: float) -> None: ...")
        self.emit("def calc_item_width() -> float: ...")
        self.emit("def calc_text_size(text: str, hide_text_after_double_hash: bool = False, wrap_width: float = -1) -> Vec2: ...")
        self.emit()

        # Item Utilities
        self.emit("# Item Utilities")
        self.emit("def is_item_hovered(flags: int = 0) -> bool: ...")
        self.emit("def is_item_active() -> bool: ...")
        self.emit("def is_item_focused() -> bool: ...")
        self.emit("def is_item_clicked(mouse_button: int = 0) -> bool: ...")
        self.emit("def is_item_visible() -> bool: ...")
        self.emit("def is_item_edited() -> bool: ...")
        self.emit("def is_item_activated() -> bool: ...")
        self.emit("def is_item_deactivated() -> bool: ...")
        self.emit("def is_item_deactivated_after_edit() -> bool: ...")
        self.emit("def get_item_rect_min() -> Vec2: ...")
        self.emit("def get_item_rect_max() -> Vec2: ...")
        self.emit("def get_item_rect_size() -> Vec2: ...")
        self.emit()

        # Tooltip
        self.emit("# Tooltip")
        self.emit("def begin_tooltip() -> None: ...")
        self.emit("def end_tooltip() -> None: ...")
        self.emit("def set_tooltip(text: str) -> None: ...")
        self.emit()

        # Style
        self.emit("# Style")
        self.emit("def push_style_color(idx: int, color: Union[int, Tuple[float, float, float, float]]) -> None: ...")
        self.emit("def pop_style_color(count: int = 1) -> None: ...")
        self.emit("def push_style_var(idx: int, val: Union[float, Tuple[float, float]]) -> None: ...")
        self.emit("def pop_style_var(count: int = 1) -> None: ...")
        self.emit("def get_color_u32(idx_or_color: Union[int, Tuple[float, float, float, float]], alpha_mul: float = 1.0) -> int: ...")
        self.emit()

        # Font
        self.emit("# Font (1.92 API)")
        self.emit("def push_font(font: Optional[_Font], size: float = 0) -> None: ...")
        self.emit("def pop_font() -> None: ...")
        self.emit("def get_font() -> _Font: ...")
        self.emit("def get_font_size() -> float: ...")
        self.emit("def get_font_baked() -> _FontBaked: ...")
        self.emit()

        # ID
        self.emit("# ID")
        self.emit("def push_id(id_val: Union[str, int]) -> None: ...")
        self.emit("def pop_id() -> None: ...")
        self.emit("def get_id(str_id: str) -> int: ...")
        self.emit()

        # Mouse/Keyboard
        self.emit("# Mouse/Keyboard")
        self.emit("def is_mouse_down(button: int) -> bool: ...")
        self.emit("def is_mouse_clicked(button: int, repeat: bool = False) -> bool: ...")
        self.emit("def is_mouse_released(button: int) -> bool: ...")
        self.emit("def is_mouse_double_clicked(button: int) -> bool: ...")
        self.emit("def is_mouse_hovering_rect(r_min: Tuple[float, float], r_max: Tuple[float, float], clip: bool = True) -> bool: ...")
        self.emit("def get_mouse_pos() -> Vec2: ...")
        self.emit("def is_mouse_dragging(button: int, lock_threshold: float = -1) -> bool: ...")
        self.emit("def get_mouse_drag_delta(button: int = 0, lock_threshold: float = -1) -> Vec2: ...")
        self.emit("def is_key_down(key: int) -> bool: ...")
        self.emit("def is_key_pressed(key: int, repeat: bool = True) -> bool: ...")
        self.emit("def is_key_released(key: int) -> bool: ...")
        self.emit()

        # Clipboard
        self.emit("# Clipboard")
        self.emit("def get_clipboard_text() -> str: ...")
        self.emit("def set_clipboard_text(text: str) -> None: ...")

    def generate(self) -> str:
        """生成完整文件"""
        self.lines = []
        self.generate_header()
        self.generate_constants()
        self.generate_classes()
        self.generate_functions()
        return "\n".join(self.lines)


# =============================================================================
# 主程序
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Cython bindings from cimgui JSON")
    parser.add_argument("--pxd", action="store_true", help="Generate cimgui.pxd")
    parser.add_argument("--pyx", action="store_true", help="Generate imgui_core.pyx")
    parser.add_argument("--pyi", action="store_true", help="Generate imgui.pyi")
    parser.add_argument("--all", action="store_true", help="Generate all files")
    parser.add_argument("--output", "-o", help="Output file (default: write to src/)")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing files")
    args = parser.parse_args()

    if args.all:
        args.pxd = args.pyx = args.pyi = True

    if not any([args.pxd, args.pyx, args.pyi]):
        parser.print_help()
        return

    if args.pxd:
        gen = PxdGenerator()
        output = gen.generate()
        if args.dry_run:
            print("=" * 80)
            print("cimgui.pxd")
            print("=" * 80)
            print(output[:4000] + "\n... (truncated)")
        else:
            path = SRC_DIR / "cimgui.pxd"
            path.write_text(output, encoding="utf-8")
            print(f"✅ Written: {path}")

    if args.pyx:
        gen = PyxGenerator()
        output = gen.generate()
        if args.dry_run:
            print("=" * 80)
            print("imgui_core.pyx (skeleton)")
            print("=" * 80)
            print(output[:3000] + "\n... (truncated)")
        else:
            path = SRC_DIR / "imgui_core_generated.pyx"  # 生成到单独文件避免覆盖手写代码
            path.write_text(output, encoding="utf-8")
            print(f"✅ Written: {path}")

    if args.pyi:
        gen = PyiGenerator()
        output = gen.generate()
        if args.dry_run:
            print("=" * 80)
            print("imgui.pyi")
            print("=" * 80)
            print(output[:3000] + "\n... (truncated)")
        else:
            IMGUI_DIR.mkdir(parents=True, exist_ok=True)
            path = IMGUI_DIR / "__init__.pyi"
            path.write_text(output, encoding="utf-8")
            print(f"✅ Written: {path}")


if __name__ == "__main__":
    main()
