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

        cython_type, python_type, conversion = type_map.resolve(c_type)

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
        ret_cython, ret_python, ret_conversion = type_map.resolve(ret_type)

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

    @classmethod
    def from_json(cls, field_def: dict, type_map: "TypeMapping") -> "StructField":
        name = field_def["name"]
        c_type = field_def["type"]
        size = field_def.get("size")

        cython_type, python_type, conversion = type_map.resolve(c_type)

        return cls(
            name=name,
            c_type=c_type,
            cython_type=cython_type,
            python_type=python_type,
            size=size,
            conversion=conversion,
        )


@dataclass
class Struct:
    """结构体定义 - 从 structs_and_enums.json 派生"""

    name: str  # e.g. "ImFont"
    fields: list[StructField] = field(default_factory=list)
    methods: list[Function] = field(default_factory=list)

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
# Type Mapping - 配置驱动的类型转换
# ============================================================================


class TypeMapping:
    """类型映射 - 从 type_mapping.json 加载"""

    def __init__(self, config_path: Path):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        # 合并所有类型映射
        self._map: dict[str, dict] = {}
        for section in [
            "primitives",
            "pointers",
            "imgui_basic",
            "imgui_vectors",
            "imgui_structs",
            "backend_types",
        ]:
            if section in self.config:
                self._map.update(self.config[section])

        # Flags 类型的正则匹配
        flag_pattern = self.config.get("flag_pattern", {})
        self._flag_regex = re.compile(flag_pattern.get("regex", "^$"))
        self._flag_cython = flag_pattern.get("cython", "int")
        self._flag_python = flag_pattern.get("python", "int")

        # 默认值转换
        self._default_map = self.config.get("default_values", {})

    def resolve(self, c_type: str) -> tuple[str, str, str | None]:
        """
        解析 C 类型，返回 (cython_type, python_type, conversion)
        conversion: 转换函数名或 None
        """
        # 清理类型字符串
        c_type = c_type.strip()

        # 直接匹配
        if c_type in self._map:
            entry = self._map[c_type]
            return (
                entry.get("cython", c_type),
                entry.get("python", "Any"),
                entry.get("conversion"),
            )

        # Flags 类型匹配
        # 去掉指针后缀再匹配
        base_type = c_type.rstrip("*").strip()
        if self._flag_regex.match(base_type):
            return self._flag_cython, self._flag_python, None

        # 指针类型 - 尝试匹配带 * 的版本
        if "*" in c_type:
            ptr_type = c_type
            if ptr_type in self._map:
                entry = self._map[ptr_type]
                return (
                    entry.get("cython", ptr_type),
                    entry.get("python", "Any"),
                    entry.get("conversion"),
                )

        # 未知类型 - 保留原样
        return c_type, "Any", None

    def convert_default(self, value: str) -> str:
        """转换默认值 (C -> Python)"""
        if value in self._default_map:
            return self._default_map[value]

        # 数值
        if re.match(r"^-?\d+(\.\d+)?f?$", value):
            return value.rstrip("f")

        # 布尔
        if value in ("true", "false"):
            return value.capitalize()

        return value


# ============================================================================
# Compiler - 核心编译逻辑
# ============================================================================


class Compiler:
    """
    cimgui 绑定编译器

    从 cimgui JSON 自动派生所有元数据，
    只使用 config 控制类型转换和特殊处理。
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

        # 加载配置
        self.type_map = TypeMapping(config_dir / "type_mapping.json")
        self.overrides = self._load_config("overrides.json")

        # Jinja2 环境
        self.jinja = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._register_filters()

        # 解析结果缓存
        self._functions: list[Function] | None = None
        self._methods: dict[str, list[Function]] | None = None
        self._structs: dict[str, Struct] | None = None
        self._enums: list[Enum] | None = None
        self._backend_functions: dict[str, list[Function]] | None = None

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
    # Parse - 从 JSON 自动派生
    # ========================================================================

    def parse_functions(self) -> list[Function]:
        """
        解析所有函数

        自动过滤：
        - 只保留 public API (location 以 "imgui:" 开头且不含 "internal")
        - 跳过标记为 skip 的函数
        - 跳过 vararg 函数 (以 V 结尾的变体)
        """
        if self._functions is not None:
            return self._functions

        functions = []
        seen_names: set[str] = set()
        
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
                    
                # 处理重载：跳过同名函数
                if func.python_name in seen_names:
                    continue
                seen_names.add(func.python_name)

                functions.append(func)

        self._functions = functions
        return functions

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

                stname = func.stname
                
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

        for name, fields_list in struct_data.items():
            fields = [
                StructField.from_json(f, self.type_map) for f in fields_list
            ]
            structs[name] = Struct(name=name, fields=fields)

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
            functions=self.parse_functions(),
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
        )

    def generate_backend(self, backends: list[str] = None) -> str:
        """生成 imgui_backend.pyx (GLFW + OpenGL3 后端绑定)"""
        template = self.jinja.get_template("imgui_backend.pyx.jinja2")
        backend_funcs = self.parse_backend_functions(backends)
        return template.render(
            backends=backend_funcs,
            type_map=self.type_map,
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
    args = parser.parse_args()

    compiler = Compiler()

    if args.stats:
        compiler.print_stats()
    else:
        compiler.compile_all(args.output)


if __name__ == "__main__":
    main()
