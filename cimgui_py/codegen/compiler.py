#!/usr/bin/env python3
"""
cimgui Python Binding Compiler - 真正的数据驱动架构

设计原则：
1. 从 cimgui JSON 自动 derive：
   - 公开/内部 API (location 字段: "imgui:XXX" vs "imgui_internal:XXX")
   - 函数签名 (argsT, ret, defaults)
   - Wrapper 类方法 (stname 字段: "ImFont" -> _Font 类)
   - 结构体字段 (structs_and_enums.json)

2. 只配置稳定的设计决策：
   - type_mapping.json: C->Python 类型转换 (我们的 API 设计)
   - overrides.json: 特殊函数签名 (多返回值、重命名等)

3. 不配置易变数据：
   - 不手动维护 public/internal 列表 (用 location derive)
   - 不手动维护方法归属 (用 stname derive)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

# ============================================================================
# Paths
# ============================================================================

CODEGEN_DIR = Path(__file__).parent
CONFIG_DIR = CODEGEN_DIR / "config"
TEMPLATE_DIR = CODEGEN_DIR / "templates"
CIMGUI_DIR = CODEGEN_DIR.parent / "vendor" / "cimgui" / "generator" / "output"


# ============================================================================
# Data Classes - 从 JSON 自动派生
# ============================================================================


@dataclass
class Argument:
    """函数参数 - 从 argsT 自动派生"""

    name: str
    c_type: str
    cython_type: str = ""
    python_type: str = ""
    default: str | None = None
    conversion: str | None = None  # 如何从 Python 转 C

    @classmethod
    def from_json(cls, arg: dict, defaults: dict, type_map: "TypeMapping") -> "Argument":
        name = arg["name"]
        c_type = arg["type"]
        default = defaults.get(name)

        # Python 保留字重命名
        if name in ("in", "from", "import", "class", "def", "return", "is", "not", "and", "or", "for", "while", "if", "else", "elif", "try", "except", "finally", "with", "as", "lambda", "yield", "global", "nonlocal", "pass", "break", "continue", "raise", "del", "assert", "type"):
            name = name + "_"

        cython_type, python_type, conversion, _ = type_map.resolve(c_type)

        # 转换默认值
        if default is not None:
            default = type_map.convert_default(default)

        return cls(
            name=name,
            c_type=c_type,
            cython_type=cython_type,
            python_type=python_type,
            default=default,
            conversion=conversion,
        )


@dataclass
class Function:
    """函数定义 - 从 definitions.json 自动派生"""

    cimgui_name: str  # e.g. "igBegin", "ImFont_GetDebugName"
    func_name: str  # e.g. "Begin", "GetDebugName"
    python_name: str  # e.g. "begin", "get_debug_name"
    args: list[Argument] = field(default_factory=list)
    ret_type: str = "void"
    ret_cython: str = "void"
    ret_python: str = "None"
    ret_conversion: str | None = None
    ret_wrapper: str | None = None  # wrapper 类名（如 "_DrawList"）
    location: str = ""  # e.g. "imgui:440"
    stname: str = ""  # e.g. "ImFont" for methods, "" for global
    overload_suffix: str = ""  # e.g. "_Str" for overloaded functions
    ov_cimguiname: str = ""  # Full overload name like "igBeginChild_Str"

    # Override 信息
    override: dict = field(default_factory=dict)
    skip: bool = False
    special_handling: str | None = None

    @property
    def is_public(self) -> bool:
        """判断是否为公开 API（非 internal）"""
        if not self.location:
            return False
        # imgui:440 = public, imgui_internal:4002 = internal
        return self.location.startswith("imgui:") and "internal" not in self.location

    @property
    def is_method(self) -> bool:
        """是否为结构体方法"""
        return bool(self.stname)

    @property
    def wrapper_class(self) -> str:
        """对应的 Python wrapper 类名"""
        if not self.stname:
            return ""
        # ImFont -> _Font, ImFontAtlas -> _FontAtlas
        name = self.stname
        if name.startswith("Im"):
            name = name[2:]
        return f"_{name}"

    @classmethod
    def from_json(
        cls,
        cimgui_name: str,
        overload: dict,
        type_map: "TypeMapping",
        overrides: dict,
    ) -> "Function":
        """从 definitions.json 的一个 overload 创建 Function"""
        location = overload.get("location", "")
        stname = overload.get("stname", "")
        func_name = overload.get("funcname", "")

        # 提取 overload 后缀 (e.g. igBeginChild_Str -> _Str)
        ov_name = overload.get("ov_cimguiname", cimgui_name)
        overload_suffix = ""
        if "_" in ov_name and ov_name != cimgui_name:
            # 找到函数名之后的部分
            base = cimgui_name
            if ov_name.startswith(base):
                overload_suffix = ov_name[len(base) :]

        # 计算 python_name
        python_name = _to_snake_case(func_name) if func_name else ""

        # 跳过析构函数 (destroy) 和构造函数 (ImXXX_ImXXX)
        if func_name == "destroy" or not func_name:
            python_name = ""  # 会被跳过

        # 如果 funcname == stname，这是构造函数，跳过
        if stname and func_name == stname:
            python_name = ""  # 会被跳过

        # 解析参数
        args = []
        defaults = overload.get("defaults", {})
        for arg in overload.get("argsT", []):
            # 跳过 self 参数（方法的第一个参数）
            if arg["name"] == "self":
                continue
            args.append(Argument.from_json(arg, defaults, type_map))

        # 解析返回类型
        ret_type = overload.get("ret", "void")
        ret_cython, ret_python, ret_conversion, ret_wrapper = type_map.resolve(ret_type, for_return=True)

        # 查找 override
        override_key = ov_name  # 用完整的 overload 名查找
        override = overrides.get("functions", {}).get(override_key, {})
        if not override and stname:
            # 尝试在 methods 中查找
            override = overrides.get("methods", {}).get(override_key, {})

        # 应用 override
        skip = override.get("skip", False)
        if "python_name" in override:
            python_name = override["python_name"]
        special_handling = override.get("special_handling")

        return cls(
            cimgui_name=cimgui_name,
            func_name=func_name,
            python_name=python_name,
            args=args,
            ret_type=ret_type,
            ret_cython=ret_cython,
            ret_python=ret_python,
            ret_conversion=ret_conversion,
            ret_wrapper=ret_wrapper,
            location=location,
            stname=stname,
            overload_suffix=overload_suffix,
            ov_cimguiname=ov_name,
            override=override,
            skip=skip,
            special_handling=special_handling,
        )


@dataclass
class StructField:
    """结构体字段 - 从 structs_and_enums.json 派生"""

    name: str
    c_type: str
    cython_type: str = ""
    python_type: str = ""
    size: int | None = None  # 数组大小，如 int[4]
    conversion: str | None = None
    skip: bool = False  # 是否跳过此字段（如函数指针）

    @classmethod
    def from_json(cls, field_def: dict, type_map: "TypeMapping") -> "StructField":
        name = field_def["name"]
        c_type = field_def["type"]
        size = field_def.get("size")

        # 跳过函数指针类型、union 类型和 ImVector 类型（Cython 不支持直接声明）
        skip = (
            "(*)" in c_type
            or c_type.endswith("Callback")
            or c_type.startswith("union")
            or c_type.startswith("ImVector_")
            or c_type.startswith("ImPool_")
            or c_type.startswith("ImSpan_")
            or c_type.startswith("ImChunkStream_")
        )

        cython_type, python_type, conversion, _ = type_map.resolve(c_type)

        return cls(
            name=name,
            c_type=c_type,
            cython_type=cython_type,
            python_type=python_type,
            size=size,
            conversion=conversion,
            skip=skip,
        )


@dataclass
class Struct:
    """结构体定义 - 从 structs_and_enums.json 派生"""

    name: str  # e.g. "ImFont"
    fields: list[StructField] = field(default_factory=list)
    methods: list[Function] = field(default_factory=list)
    is_value_type: bool = False  # 按值传递（如 ImVec2, ImTextureRef）

    @property
    def wrapper_class(self) -> str:
        """Python wrapper 类名"""
        name = self.name
        if name.startswith("Im"):
            name = name[2:]
        return f"_{name}"

    @property
    def cython_name(self) -> str:
        """Cython 中的结构体名"""
        return self.name

    @property
    def simple_fields(self) -> list[StructField]:
        """返回可以在 pxd 中声明的简单字段（过滤掉函数指针等）"""
        return [f for f in self.fields if not f.skip]

    @property
    def has_simple_fields(self) -> bool:
        """是否有可声明的简单字段"""
        return bool(self.simple_fields)


@dataclass
class Enum:
    """枚举定义 - 从 structs_and_enums.json 派生"""

    name: str
    values: list[tuple[str, int]] = field(default_factory=list)

    @classmethod
    def from_json(cls, name: str, values: list[dict]) -> "Enum":
        parsed = []
        for v in values:
            enum_name = v["name"]
            # 优先用 calc_value，否则用 value
            value = v.get("calc_value", v.get("value", 0))
            if isinstance(value, str):
                # 可能是表达式，跳过复杂的
                continue
            parsed.append((enum_name, int(value)))
        return cls(name=name, values=parsed)


# ============================================================================
# Type Mapping - 完全自动派生，无需配置文件
# ============================================================================


class TypeMapping:
    """类型映射 - 自动派生，无需 JSON 配置"""

    # 原始类型映射（硬编码）
    PRIMITIVES = {
        "void": ("void", "None", None, None),
        "bool": ("bint", "bool", None, None),
        "int": ("int", "int", None, None),
        "unsigned int": ("unsigned int", "int", None, None),
        "float": ("float", "float", None, None),
        "double": ("double", "float", None, None),
        "size_t": ("size_t", "int", None, None),
        "char": ("char", "str", None, None),
        # 固定宽度整数
        "ImU8": ("unsigned char", "int", None, None),
        "ImU16": ("unsigned short", "int", None, None),
        "ImU32": ("unsigned int", "int", None, None),
        "ImU64": ("unsigned long long", "int", None, None),
        "ImS8": ("signed char", "int", None, None),
        "ImS16": ("short", "int", None, None),
        "ImS32": ("int", "int", None, None),
        "ImS64": ("long long", "int", None, None),
        "ImGuiID": ("unsigned int", "int", None, None),
        "ImWchar": ("unsigned short", "int", None, None),
        "ImWchar16": ("unsigned short", "int", None, None),
        "ImWchar32": ("unsigned int", "int", None, None),
        "ImTextureID": ("unsigned long long", "int", None, None),
        "ImDrawIdx": ("unsigned short", "int", None, None),
    }

    # 字符串类型（需要特殊转换）
    STRING_TYPES = {
        "const char*": ("const char*", "str", "to_bytes", None),
        "char*": ("char*", "str", None, None),  # 可写 buffer，不转换
    }

    # 通用指针类型
    POINTER_TYPES = {
        "void*": ("void*", "int", "ptr", None),
        "const void*": ("const void*", "int", "ptr", None),
        # 原生类型指针（用于输出参数）
        "bool*": ("bint*", "list", "bool_ptr", None),
        "int*": ("int*", "list", "int_ptr", None),
        "float*": ("float*", "list", "float_ptr", None),
        "double*": ("double*", "list", "double_ptr", None),
        "unsigned int*": ("unsigned int*", "list", "uint_ptr", None),
        "size_t*": ("size_t*", "list", "size_t_ptr", None),
        # const 指针是可选输入参数，允许 NULL
        "const float*": ("const float*", "int", "ptr", None),
        "const int*": ("const int*", "int", "ptr", None),
        "const double*": ("const double*", "int", "ptr", None),
        # 字符串数组
        "const char* const[]": ("const char**", "list", "string_array", None),
        "const char**": ("const char**", "list", "string_array", None),
        "char**": ("char**", "list", "string_array", None),
        # Backend opaque pointers (GLFW, etc.)
        "GLFWwindow*": ("size_t", "int", "ptr", None),
        "GLFWmonitor*": ("size_t", "int", "ptr", None),
    }

    # 明确跳过的类型
    SKIP_TYPES = {"va_list", "..."}

    # 需要生成 Wrapper 类的结构体（有方法的）
    # 格式: struct_name -> (wrapper_class_name, has_methods)
    WRAPPER_TYPES = {
        "ImDrawList": ("DrawList", True),
        "ImFontAtlas": ("FontAtlas", True),
        "ImGuiIO": ("IO", True),
        "ImGuiStorage": ("Storage", True),
        "ImFont": ("Font", True),
        "ImGuiTextBuffer": ("TextBuffer", True),
        "ImGuiListClipper": ("ListClipper", True),
        "ImDrawData": ("DrawData", True),
        "ImGuiViewport": ("Viewport", True),
        "ImGuiStyle": ("Style", True),
        "ImGuiContext": ("Context", False),  # 有方法但很少用
        "ImGuiPayload": ("Payload", True),
        "ImFontGlyphRangesBuilder": ("FontGlyphRangesBuilder", True),
        "ImGuiTextFilter": ("TextFilter", True),
        "ImColor": ("Color", True),
    }

    def __init__(self):
        # 动态注册的类型（值类型结构体）
        self._value_types: dict[str, dict] = {}
        # 缓存
        self._cache: dict[str, tuple] = {}

    def register_value_type(self, name: str, fields: list[dict]):
        """注册值类型结构体（从 nonPOD_used 派生）"""
        # 转换名：ImVec2 -> vec2, ImTextureRef -> texture_ref
        if name.startswith("Im"):
            conv_name = _to_snake_case(name[2:])  # 去掉 Im 前缀
        else:
            conv_name = _to_snake_case(name)

        self._value_types[name] = {
            "cython": name,
            "python": "tuple",
            "conversion": conv_name,
            "return_conversion": f"{conv_name}_to_tuple",
            "fields": fields,
        }
        # const 版本
        self._value_types[f"const {name}"] = {
            "cython": name,
            "python": "tuple",
            "conversion": conv_name,
        }

    def resolve(self, c_type: str, for_return: bool = False) -> tuple[str, str, str | None, str | None]:
        """
        解析 C 类型，返回 (cython_type, python_type, conversion, wrapper)

        完全自动派生，无需配置文件。
        """
        c_type = c_type.strip()

        # 缓存
        cache_key = f"{c_type}:{for_return}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._resolve_impl(c_type, for_return)
        self._cache[cache_key] = result
        return result

    def _resolve_impl(self, c_type: str, for_return: bool) -> tuple[str, str, str | None, str | None]:
        """实际的类型解析逻辑"""

        # 1. 明确跳过的类型
        if c_type in self.SKIP_TYPES:
            return ("__UNKNOWN__", "Any", None, None)

        # 2. 原始类型
        if c_type in self.PRIMITIVES:
            return self.PRIMITIVES[c_type]

        # 3. 字符串类型
        if c_type in self.STRING_TYPES:
            return self.STRING_TYPES[c_type]

        # 4. 通用指针类型
        if c_type in self.POINTER_TYPES:
            return self.POINTER_TYPES[c_type]

        # 5. 已注册的值类型结构体
        if c_type in self._value_types:
            entry = self._value_types[c_type]
            if for_return:
                conv = entry.get("return_conversion", entry.get("conversion"))
            else:
                conv = entry.get("conversion")
            return (entry["cython"], entry["python"], conv, None)

        # 5. Flags 类型 (Im*Flags)
        if re.match(r"^Im(Gui)?[A-Z][a-zA-Z]*Flags$", c_type):
            return ("int", "int", None, None)

        # 6. 固定大小数组 float[N], int[N]
        array_match = re.match(r"(int|float|double|bool)\[(\d+)\]", c_type)
        if array_match:
            base, size = array_match.groups()
            return (f"{base}*", "tuple", f"{base}_array_{size}", None)

        # 7. const 版本 -> 尝试非 const
        if c_type.startswith("const "):
            non_const = c_type[6:].strip()
            # 递归解析非 const 版本
            result = self._resolve_impl(non_const, for_return)
            if result[0] != "__UNKNOWN__":
                return result

        # 8. Im* 指针类型 -> void* + ptr 转换，可能有 wrapper
        if c_type.endswith("*"):
            base = c_type[:-1].strip()
            if base.startswith("const "):
                base = base[6:].strip()

            if base.startswith("Im"):
                # 检查是否有 wrapper 类
                if base in self.WRAPPER_TYPES:
                    wrapper_name = self.WRAPPER_TYPES[base][0]
                    return ("void*", wrapper_name, "ptr", wrapper_name)
                # 没有 wrapper 的 ImGui 结构体指针，作为 opaque pointer
                return ("void*", "int", "ptr", None)

        # 9. 回调类型
        if "Callback" in c_type or c_type.endswith("Func"):
            return ("void*", "int", "ptr", None)

        # 10. 函数指针 -> 跳过
        if "(*)" in c_type:
            return ("__UNKNOWN__", "Any", None, None)

        # 11. 模板类型 (ImVector<T>) -> 跳过
        if "ImVector" in c_type or "<" in c_type:
            return ("__UNKNOWN__", "Any", None, None)

        # 12. 其他未知类型
        return ("__UNKNOWN__", "Any", None, None)

    def convert_default(self, value: str) -> str:
        """转换默认值 (C -> Python)"""
        if value is None:
            return None

        # NULL/nullptr -> None
        if value in ("NULL", "nullptr"):
            return "None"

        # true/false -> True/False
        if value == "true":
            return "True"
        if value == "false":
            return "False"

        # ImVec2(x,y) -> (x, y) - 必须在 FLT_MIN/FLT_MAX 之前处理
        vec2_match = re.match(r"ImVec2\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)", value)
        if vec2_match:
            x, y = vec2_match.groups()
            return f"({self.convert_default(x.strip())}, {self.convert_default(y.strip())})"

        # ImVec4(x,y,z,w) -> (x, y, z, w)
        vec4_match = re.match(r"ImVec4\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)", value)
        if vec4_match:
            x, y, z, w = vec4_match.groups()
            return f"({self.convert_default(x.strip())}, {self.convert_default(y.strip())}, {self.convert_default(z.strip())}, {self.convert_default(w.strip())})"

        # 数字后缀 (1.0f -> 1.0, +360.0f -> +360.0)
        if value.endswith("f") and value[:-1].replace(".", "").replace("-", "").replace("+", "").isdigit():
            return value[:-1]

        # FLT_MAX -> 大数
        if "FLT_MAX" in value:
            return value.replace("FLT_MAX", "3.4028235e+38").replace("-", "")

        # FLT_MIN -> 小数
        if "FLT_MIN" in value:
            # -FLT_MIN -> -1.175494e-38
            return value.replace("-FLT_MIN", "-1.175494e-38").replace("FLT_MIN", "1.175494e-38")

        # sizeof(float) -> 4
        if value == "sizeof(float)":
            return "4"
        if value == "sizeof(int)":
            return "4"

        # 字符串字面量 "..." -> "..."
        if value.startswith('"') and value.endswith('"'):
            return value

        return value


# ============================================================================
# Compiler - 核心编译逻辑
# ============================================================================


class Compiler:
    """
    cimgui 绑定编译器

    从 cimgui JSON 自动派生所有元数据，
    无需 type_mapping.json 配置文件。
    """

    def __init__(
        self,
        cimgui_dir: Path = CIMGUI_DIR,
        config_dir: Path = CONFIG_DIR,
        template_dir: Path = TEMPLATE_DIR,
    ):
        self.cimgui_dir = cimgui_dir
        self.config_dir = config_dir
        self.template_dir = template_dir

        # 加载 cimgui JSON
        self.definitions = self._load_json("definitions.json")
        self.impl_definitions = self._load_json("impl_definitions.json")
        self.structs_and_enums = self._load_json("structs_and_enums.json")
        self.typedefs = self._load_json("typedefs_dict.json")

        # TypeMapping - 完全自动派生，无需配置文件
        self.type_map = TypeMapping()
        self.overrides = self._load_config("overrides.json")

        # 自动注册值类型结构体到 TypeMapping
        self._register_value_type_structs()

        # Jinja2 环境
        self.jinja = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._register_filters()

        # 解析结果缓存
        self._all_functions: list[Function] | None = None
        self._functions: list[Function] | None = None
        self._methods: dict[str, list[Function]] | None = None
        self._structs: dict[str, Struct] | None = None
        self._enums: list[Enum] | None = None
        self._backend_functions: dict[str, list[Function]] | None = None

    def _register_value_type_structs(self):
        """自动将值类型结构体注册到 TypeMapping"""
        value_types = self.structs_and_enums.get("nonPOD_used", {})
        struct_data = self.structs_and_enums.get("structs", {})

        for name in value_types:
            # 获取结构体字段来决定如何转换
            fields = struct_data.get(name, [])
            self.type_map.register_value_type(name, fields)

    def _load_json(self, filename: str) -> dict:
        """加载 cimgui JSON 文件"""
        path = self.cimgui_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_config(self, filename: str) -> dict:
        """加载配置文件"""
        path = self.config_dir / filename
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _register_filters(self):
        """注册 Jinja2 过滤器"""
        self.jinja.filters["snake_case"] = _to_snake_case
        self.jinja.filters["strip_im_prefix"] = lambda s: s[2:] if s.startswith("Im") else s

    # ========================================================================
    # Helper - 参数/返回值检查
    # ========================================================================

    # 可处理的结构体指针类型（有 wrapper）
    HANDLABLE_PTR_TYPES = {
        "ImFont*", "ImFontBaked*", "ImFontAtlas*", "ImDrawList*", "ImDrawData*",
        "ImGuiIO*", "ImGuiStyle*", "ImGuiViewport*", "ImTextureData*",
    }

    # 可以直接传递（无需 wrapper）的指针类型
    PASSTHROUGH_PTR_TYPES = {
        "ImGuiContext*",  # 作为 int 传递
    }

    # 原生指针参数类型（有转换函数支持）
    NATIVE_PTR_ARGS = {
        "bool*", "int*", "float*", "double*", "unsigned int*", "size_t*",
    }

    def _is_arg_handlable(self, arg: Argument) -> bool:
        """检查参数是否可以被处理"""
        # 原生指针类型 - 有转换函数
        if arg.c_type in self.NATIVE_PTR_ARGS:
            return arg.conversion is not None
        # 有明确的转换函数
        if arg.conversion is not None:
            return True
        # 是 void* (通用指针) - 有 ptr 转换
        if arg.c_type in ("void*", "const void*"):
            return True
        # 是已知可处理的结构体指针（有 wrapper）
        if arg.c_type in self.HANDLABLE_PTR_TYPES:
            return True
        # 是可直接传递的指针类型
        if arg.c_type in self.PASSTHROUGH_PTR_TYPES:
            return True
        # 是未知类型
        if arg.cython_type == "__UNKNOWN__":
            return False
        # 是其他结构体指针（无 wrapper）
        if arg.c_type.endswith("*") and arg.c_type.startswith("Im"):
            return False
        # 原生类型
        return True

    def _is_func_handlable(self, func: Function) -> bool:
        """检查函数/方法是否可以被处理"""
        # 检查所有参数
        if not all(self._is_arg_handlable(arg) for arg in func.args):
            return False
        # 检查返回值
        if func.ret_cython == "__UNKNOWN__":
            return False
        # 原生指针类型作为返回值无法处理（bool*, int*, float* 等）
        # 它们作为参数可以处理（有 conversion），但作为返回值需要特殊包装
        if func.ret_cython in ("bint*", "int*", "float*", "double*", "char*", "unsigned int*"):
            return False
        # 返回不可处理的指针类型（无 wrapper 且未在 type_mapping 中定义）
        # 注意：ImGuiContext* 虽然没有 wrapper，但可以转换为 int
        if func.ret_cython.endswith("*"):
            # 有 wrapper 的可以处理
            if func.ret_wrapper is not None:
                pass  # OK
            # ret_conversion 有返回转换（如 vec2_to_tuple）
            elif func.ret_conversion is not None:
                pass  # OK
            # ret_python 不是 "Any" 且是简单类型（如 int, str）
            elif func.ret_python not in ("Any",) and not func.ret_python.startswith("list["):
                pass  # OK
            else:
                # 无法处理
                return False
        return True

    # ========================================================================
    # Parse - 从 JSON 自动派生
    # ========================================================================

    def parse_all_functions(self) -> list[Function]:
        """
        解析所有函数（用于 pxd 声明）

        包括被 skip 的函数（因为手写代码需要调用它们），
        但仍然排除：
        - *V 版本的 vararg 函数（如 igTextV）
        - 方法（单独处理）
        - 非 public API

        对于 skip=True 的函数，不检查参数类型是否可处理（手写代码会自己处理）
        """
        if self._all_functions is not None:
            return self._all_functions

        functions = []
        seen_names: set[str] = set()

        for cimgui_name, overloads in self.definitions.items():
            for overload in overloads:
                func = Function.from_json(
                    cimgui_name, overload, self.type_map, self.overrides
                )

                # 基本过滤
                if not func.is_public:
                    continue
                if func.is_method:
                    continue  # 方法单独处理
                if func.cimgui_name.endswith("V"):
                    continue  # 跳过 *V 版本（使用 va_list 的版本）

                # 对于非 skip 的函数，检查类型是否可处理
                if not func.skip:
                    # 跳过包含 vararg (...) 参数的函数
                    if any(arg.c_type == "..." for arg in func.args):
                        continue
                    # 跳过返回类型不可处理的函数
                    if func.ret_cython == "__UNKNOWN__":
                        continue
                    # 跳过参数类型不可处理的函数
                    if any(arg.cython_type == "__UNKNOWN__" for arg in func.args):
                        continue

                # 处理重载：使用 ov_cimguiname 作为唯一标识
                if func.ov_cimguiname in seen_names:
                    continue
                seen_names.add(func.ov_cimguiname)

                functions.append(func)

        self._all_functions = functions
        return functions

    def _get_overload_config(self) -> dict:
        """获取 overrides.json 中的 overloads 配置"""
        return self.overrides.get("overloads", {})

    def _get_func_suffix_from_ov_cimguiname(self, ov_cimguiname: str) -> str:
        """从 ov_cimguiname 提取后缀作为内部函数名后缀
        e.g. igBeginChild_Str -> _str, igGetColorU32_Vec4 -> _vec4
        """
        if "_" in ov_cimguiname:
            # 找到最后一个 _ 后的部分
            parts = ov_cimguiname.split("_")
            if len(parts) > 1:
                return "_" + parts[-1].lower()
        return ""

    def parse_functions(self) -> list[Function]:
        """
        解析所有函数

        自动过滤：
        - 只保留 public API (location 以 "imgui:" 开头且不含 "internal")
        - 跳过标记为 skip 的函数
        - 跳过 vararg 函数 (以 V 结尾的变体)

        对于 overload 组中的函数：
        - 如果配置了 dispatch 策略，生成带后缀的内部函数名
        - 如果配置了 rename 策略，直接使用重命名的名称
        """
        if self._functions is not None:
            return self._functions

        overload_config = self._get_overload_config()
        functions = []
        seen_names: set[str] = set()

        # 先收集所有有效函数（以便检测 overload 组）
        all_valid_funcs: dict[str, list[Function]] = {}
        for cimgui_name, overloads in self.definitions.items():
            for overload in overloads:
                func = Function.from_json(
                    cimgui_name, overload, self.type_map, self.overrides
                )

                # 跳过条件
                if func.skip:
                    continue
                if not func.is_public:
                    continue
                if func.is_method:
                    continue  # 方法单独处理
                if func.cimgui_name.endswith("V"):
                    continue  # 跳过 vararg 版本
                if not func.python_name:
                    continue
                # 跳过包含 vararg (...) 参数的函数
                if any(arg.c_type == "..." for arg in func.args):
                    continue
                # 跳过不可处理的参数或返回值
                if not self._is_func_handlable(func):
                    continue

                if func.python_name not in all_valid_funcs:
                    all_valid_funcs[func.python_name] = []
                all_valid_funcs[func.python_name].append(func)

        # 现在处理每个函数，为 overload 组中的函数添加后缀
        for python_name, funcs in all_valid_funcs.items():
            if len(funcs) == 1:
                # 没有 overload，直接使用原名
                functions.append(funcs[0])
            else:
                # 有 overload，检查配置
                config = overload_config.get(python_name, {})
                dispatch_type = config.get("dispatch", "")

                if dispatch_type == "rename":
                    # rename 策略：每个变体有独立的名称
                    variants = config.get("variants", {})
                    for func in funcs:
                        if func.ov_cimguiname in variants:
                            # 使用配置的名称
                            func.python_name = variants[func.ov_cimguiname]
                            functions.append(func)
                elif dispatch_type in ("by_type", "by_arg_count", "by_optional_arg"):
                    # dispatch 策略：为每个变体生成带后缀的内部函数
                    variants = config.get("variants", {})
                    variant_ov_names = set(variants.values())
                    for func in funcs:
                        if func.ov_cimguiname in variant_ov_names:
                            # 为 dispatch 函数生成内部函数名
                            suffix = self._get_func_suffix_from_ov_cimguiname(func.ov_cimguiname)
                            func.python_name = f"_{python_name}{suffix}"
                            functions.append(func)
                else:
                    # 没有配置，只保留第一个
                    functions.append(funcs[0])

        self._functions = functions
        return functions

    def parse_overload_dispatchers(self) -> list[dict]:
        """
        解析 overload dispatcher 配置

        返回需要生成 dispatch 函数的配置列表。
        每个配置包含：
        - python_name: dispatcher 函数名
        - dispatch: dispatch 类型 (by_type, by_optional_arg)
        - type_arg: 用于类型判断的参数索引 (for by_type)
        - check_arg: 用于检查的可选参数名 (for by_optional_arg)
        - variants: 变体列表
        - merged_args: 合并后的参数签名
        """
        overload_config = self._get_overload_config()
        functions = self.parse_functions()

        # 建立 python_name -> Function 的映射
        func_by_name: dict[str, Function] = {}
        for func in functions:
            func_by_name[func.python_name] = func

        dispatchers = []
        for python_name, config in overload_config.items():
            dispatch_type = config.get("dispatch", "")
            if dispatch_type not in ("by_type", "by_optional_arg"):
                continue  # rename 策略不需要 dispatcher

            variants = config.get("variants", {})
            internal_funcs = []

            for type_or_key, ov_cimguiname in variants.items():
                # 找到对应的内部函数名
                suffix = self._get_func_suffix_from_ov_cimguiname(ov_cimguiname)
                internal_name = f"_{python_name}{suffix}"
                func = func_by_name.get(internal_name)
                if func:
                    internal_funcs.append({
                        "key": type_or_key,
                        "internal_name": internal_name,
                        "func": func,
                    })

            if internal_funcs:
                # 为 dispatch 函数构建合并的参数签名
                merged_args = self._merge_dispatcher_args(dispatch_type, internal_funcs, config)

                # 为每个 variant 预计算调用参数字符串
                check_arg = config.get("check_arg", "")
                for variant in internal_funcs:
                    variant["call_args"] = self._build_variant_call_args(
                        variant, merged_args, check_arg
                    )

                dispatchers.append({
                    "python_name": python_name,
                    "dispatch": dispatch_type,
                    "type_arg": config.get("type_arg", 0),
                    "check_arg": check_arg,
                    "variants": internal_funcs,
                    "default": config.get("default"),
                    "merged_args": merged_args,
                })

        return dispatchers

    def _build_variant_call_args(
        self, variant: dict, merged_args: list[dict], check_arg: str
    ) -> str:
        """
        为 variant 构建调用参数字符串

        将 merged_args 中的参数映射到 variant.func.args
        """
        func = variant["func"]
        call_parts = []

        # 创建 merged arg name -> position 映射
        merged_name_to_idx = {arg["name"]: i for i, arg in enumerate(merged_args)}

        for i, varg in enumerate(func.args):
            # 尝试找到 merged arg 中对应的参数
            # 首先尝试按名称匹配
            if varg.name in merged_name_to_idx:
                call_parts.append(merged_args[merged_name_to_idx[varg.name]]["name"])
            else:
                # 如果不存在，尝试按位置匹配
                # 但要跳过 check_arg（如果 variant 中没有它的话）
                merged_idx = i
                has_check_arg = any(a.name == check_arg for a in func.args)
                if not has_check_arg and check_arg:
                    # 找到 check_arg 在 merged_args 中的位置
                    check_idx = merged_name_to_idx.get(check_arg, -1)
                    if check_idx >= 0 and i >= check_idx:
                        merged_idx = i + 1  # 跳过 check_arg

                if merged_idx < len(merged_args):
                    call_parts.append(merged_args[merged_idx]["name"])
                else:
                    call_parts.append(varg.name)

        return ", ".join(call_parts)

    def _merge_dispatcher_args(self, dispatch_type: str, variants: list[dict], config: dict = None) -> list[dict]:
        """
        合并多个 overload 变体的参数签名

        返回一个参数列表，包含所有变体的参数（合并相同位置的参数）
        """
        if not variants:
            return []

        # 按参数数量从多到少排序，取最长的作为基准
        sorted_variants = sorted(variants, key=lambda v: len(v["func"].args), reverse=True)
        max_func = sorted_variants[0]["func"]
        min_func = sorted_variants[-1]["func"]

        # 对于 by_optional_arg，需要特殊处理参数合并
        check_arg = config.get("check_arg", "") if config else ""

        # 收集所有变体中出现的参数名及其默认值
        all_param_defaults: dict[str, str | None] = {}
        for v in variants:
            for arg in v["func"].args:
                if arg.name not in all_param_defaults:
                    all_param_defaults[arg.name] = arg.default
                elif arg.default is not None:
                    # 优先使用非 None 的默认值
                    all_param_defaults[arg.name] = arg.default

        merged = []
        for i, arg in enumerate(max_func.args):
            # 检查所有变体在此位置是否有相同参数
            all_have = all(i < len(v["func"].args) for v in variants)

            # 获取此位置所有变体的参数名
            names_at_pos = set()
            for v in variants:
                if i < len(v["func"].args):
                    names_at_pos.add(v["func"].args[i].name)

            # 使用第一个变体的参数信息作为基础
            # 对于默认值，从 all_param_defaults 查找
            default_value = all_param_defaults.get(arg.name, arg.default)

            merged_arg = {
                "name": arg.name,
                "names": list(names_at_pos),  # 所有变体在此位置的参数名
                "default": default_value,
                "required": all_have and arg.default is None,
            }

            # 如果不是所有变体都有此参数，需要有默认值
            if not all_have:
                # 如果有已知的默认值就用，否则用 None
                if merged_arg["default"] is None:
                    merged_arg["default"] = "None"

            # 对于 by_optional_arg，check_arg 应该有 None 默认值
            if dispatch_type == "by_optional_arg" and arg.name == check_arg:
                merged_arg["default"] = "None"

            merged.append(merged_arg)

        return merged

    def parse_overloads(self) -> dict[str, list[Function]]:
        """
        收集所有重载函数

        返回 {python_name: [func1, func2, ...]} 字典，
        只包含有多个重载的函数。
        """
        overload_groups: dict[str, list[Function]] = {}

        for cimgui_name, overloads in self.definitions.items():
            for overload in overloads:
                func = Function.from_json(
                    cimgui_name, overload, self.type_map, self.overrides
                )

                # 跳过条件（与 parse_functions 相同）
                if func.skip:
                    continue
                if not func.is_public:
                    continue
                if func.is_method:
                    continue
                if func.cimgui_name.endswith("V"):
                    continue
                if not func.python_name:
                    continue
                if any(arg.c_type == "..." for arg in func.args):
                    continue
                if not self._is_func_handlable(func):
                    continue

                # 收集到对应的组
                if func.python_name not in overload_groups:
                    overload_groups[func.python_name] = []
                overload_groups[func.python_name].append(func)

        # 只返回有多个重载的
        return {k: v for k, v in overload_groups.items() if len(v) > 1}

    def parse_methods(self) -> dict[str, list[Function]]:
        """
        解析所有结构体方法

        按 stname 分组，自动识别：
        - ImFont_* -> _Font 类方法
        - ImFontAtlas_* -> _FontAtlas 类方法
        - etc.
        """
        if self._methods is not None:
            return self._methods

        methods: dict[str, list[Function]] = {}
        seen_methods: dict[str, set[str]] = {}  # stname -> set of python_names

        for cimgui_name, overloads in self.definitions.items():
            for overload in overloads:
                func = Function.from_json(
                    cimgui_name, overload, self.type_map, self.overrides
                )

                # 只处理方法
                if not func.is_method:
                    continue
                if func.skip:
                    continue
                if not func.is_public:
                    continue
                # 跳过析构函数和构造函数
                if not func.python_name:
                    continue
                # 跳过 vararg 方法
                if any(arg.c_type == "..." for arg in func.args):
                    continue
                # 跳过不可处理的参数或返回值
                if not self._is_func_handlable(func):
                    continue

                stname = func.stname

                # 跳过 ImVector 等模板类型的方法（Cython 不支持 C++ 模板）
                if stname in ("ImVector", "ImPool", "ImSpan", "ImChunkStream"):
                    continue

                # 处理重载：如果已有同名方法，加后缀或跳过
                if stname not in seen_methods:
                    seen_methods[stname] = set()

                if func.python_name in seen_methods[stname]:
                    # 已有同名方法，跳过此重载（或可以加后缀）
                    continue

                seen_methods[stname].add(func.python_name)
                if stname not in methods:
                    methods[stname] = []
                methods[stname].append(func)

        self._methods = methods
        return methods

    def parse_structs(self) -> dict[str, Struct]:
        """
        解析所有结构体

        从 structs_and_enums.json 获取字段，
        从 definitions.json 获取方法。
        """
        if self._structs is not None:
            return self._structs

        structs = {}
        struct_data = self.structs_and_enums.get("structs", {})
        # nonPOD_used 标识哪些结构体是按值传递的（需要转换函数）
        value_types = set(self.structs_and_enums.get("nonPOD_used", {}).keys())

        for name, fields_list in struct_data.items():
            fields = [
                StructField.from_json(f, self.type_map) for f in fields_list
            ]
            structs[name] = Struct(
                name=name,
                fields=fields,
                is_value_type=(name in value_types),
            )

        # 附加方法
        methods = self.parse_methods()
        for stname, method_list in methods.items():
            if stname in structs:
                structs[stname].methods = method_list

        self._structs = structs
        return structs

    def parse_enums(self) -> list[Enum]:
        """解析所有枚举"""
        if self._enums is not None:
            return self._enums

        enums = []
        enum_data = self.structs_and_enums.get("enums", {})

        for name, values in enum_data.items():
            # 跳过 private 枚举
            if "Private" in name:
                continue
            enums.append(Enum.from_json(name, values))

        self._enums = enums
        return enums

    def parse_backend_functions(self, backends: list[str] = None) -> dict[str, list[Function]]:
        """
        解析 backend 函数

        backends: 要解析的后端列表，如 ["glfw", "opengl3"]
                 默认为 ["glfw", "opengl3"]

        返回: {backend_name: [Function, ...]}
        """
        if backends is None:
            backends = ["glfw", "opengl3"]

        if self._backend_functions is not None:
            return self._backend_functions

        # 后端名称到函数前缀的映射
        backend_prefixes = {
            "glfw": "ImGui_ImplGlfw_",
            "opengl3": "ImGui_ImplOpenGL3_",
            "opengl2": "ImGui_ImplOpenGL2_",
            "vulkan": "ImGui_ImplVulkan_",
            "sdl2": "ImGui_ImplSDL2_",
            "sdl3": "ImGui_ImplSDL3_",
        }

        result: dict[str, list[Function]] = {}

        for backend in backends:
            prefix = backend_prefixes.get(backend)
            if not prefix:
                continue

            functions = []
            seen_names: set[str] = set()

            for cimgui_name, overloads in self.impl_definitions.items():
                if not cimgui_name.startswith(prefix):
                    continue

                for overload in overloads:
                    func = Function.from_json(
                        cimgui_name, overload, self.type_map, self.overrides
                    )

                    # 重新计算 python_name（从 backend 函数名）
                    # ImGui_ImplGlfw_InitForOpenGL -> init_for_opengl
                    func_part = cimgui_name[len(prefix):]
                    func.python_name = _to_snake_case(func_part)

                    # 跳过条件
                    if func.skip:
                        continue
                    if not func.python_name:
                        continue
                    # 跳过包含 vararg (...) 参数的函数
                    if any(arg.c_type == "..." for arg in func.args):
                        continue
                    # 处理重载
                    if func.python_name in seen_names:
                        continue
                    seen_names.add(func.python_name)

                    functions.append(func)

            result[backend] = functions

        self._backend_functions = result
        return result

    # ========================================================================
    # Generate - 使用模板生成代码
    # ========================================================================

    def generate_pxd(self) -> str:
        """生成 cimgui.pxd (Cython 声明)"""
        template = self.jinja.get_template("cimgui.pxd.jinja2")
        return template.render(
            functions=self.parse_all_functions(),  # 包含 skip 的函数
            methods=self.parse_methods(),
            structs=self.parse_structs(),
            enums=self.parse_enums(),
            typedefs=self.typedefs,
            type_map=self.type_map,
            backend_functions=self.parse_backend_functions(),
        )

    def generate_pyx(self) -> str:
        """生成 imgui_core.pyx (Cython 实现)"""
        template = self.jinja.get_template("imgui_core.pyx.jinja2")
        return template.render(
            functions=self.parse_functions(),
            methods=self.parse_methods(),
            structs=self.parse_structs(),
            enums=self.parse_enums(),
            overrides=self.overrides,
            overloads=self.parse_overloads(),
            dispatchers=self.parse_overload_dispatchers(),
            type_map=self.type_map,
        )

    def generate_pyi(self) -> str:
        """生成 imgui.pyi (类型存根)"""
        template = self.jinja.get_template("imgui.pyi.jinja2")
        return template.render(
            functions=self.parse_functions(),
            methods=self.parse_methods(),
            structs=self.parse_structs(),
            enums=self.parse_enums(),
            overrides=self.overrides,
            type_map=self.type_map,
        )

    def generate_backend(self) -> str:
        """生成 imgui_backend.pyx (GLFW + OpenGL3 后端绑定)"""
        template = self.jinja.get_template("imgui_backend.pyx.jinja2")
        return template.render(
            backends=self.parse_backend_functions(),
        )

    def compile_all(self, output_dir: Path, include_backend: bool = True) -> None:
        """编译所有文件"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件
        (output_dir / "cimgui.pxd").write_text(
            self.generate_pxd(), encoding="utf-8"
        )
        (output_dir / "imgui_core.pyx").write_text(
            self.generate_pyx(), encoding="utf-8"
        )
        (output_dir / "imgui.pyi").write_text(
            self.generate_pyi(), encoding="utf-8"
        )

        if include_backend:
            (output_dir / "imgui_backend.pyx").write_text(
                self.generate_backend(), encoding="utf-8"
            )

        print(f"Generated binding files in {output_dir}")

    # ========================================================================
    # Debug / Analysis
    # ========================================================================

    def print_stats(self) -> None:
        """打印统计信息"""
        functions = self.parse_functions()
        methods = self.parse_methods()
        structs = self.parse_structs()
        enums = self.parse_enums()
        backend_funcs = self.parse_backend_functions()

        print("=== cimgui Binding Compiler Stats ===")
        print(f"Public Functions: {len(functions)}")
        print(f"Wrapper Classes: {len(methods)}")
        for stname, method_list in methods.items():
            wrapper = "_" + stname[2:] if stname.startswith("Im") else stname
            print(f"  {wrapper}: {len(method_list)} methods")
        print(f"Structs: {len(structs)}")
        print(f"Enums: {len(enums)}")
        print(f"Backend Functions:")
        for backend, funcs in backend_funcs.items():
            print(f"  {backend}: {len(funcs)} functions")


# ============================================================================
# Utilities
# ============================================================================


def _to_snake_case(name: str) -> str:
    """CamelCase -> snake_case"""
    # BeginChild -> begin_child
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ============================================================================
# CLI
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="cimgui Python Binding Compiler")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=CODEGEN_DIR.parent / "src",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics only, don't generate files",
    )
    parser.add_argument(
        "--backend",
        action="store_true",
        help="Include backend (GLFW + OpenGL3) bindings",
    )
    args = parser.parse_args()

    compiler = Compiler()

    if args.stats:
        compiler.print_stats()
    else:
        compiler.compile_all(args.output, include_backend=args.backend)


if __name__ == "__main__":
    main()
