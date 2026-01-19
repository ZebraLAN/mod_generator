"""
提取 NPC 商店配置信息脚本 v6

输出格式: Python (.py)
1. NPC_METADATA: object -> {town, town_zh, name_en, name_zh} 的元数据字典
2. SHOP_CONFIGS: {tuple(sorted(objects)): config} 的配置字典
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
import sys

# Paths
sys.path.append(str(Path(__file__).parent.parent))
import paths

GML_DIR = paths.SRC_GML
INHERITANCE_FILE = paths.DATA_META / "object_tree.json"
LOCATIONS_FILE = paths.DATA_TABLES / "locations.json"
NAMES_FILE = paths.DATA_TABLES / "names.json"
OUTPUT_FILE = paths.PROJECT_ROOT / "shop_configs.py"

# 城镇声望 Perk 对应的装备等级加成
TOWN_MAX_TIER_BONUS = {
    "Osbrook": 1,
    "Mannshire": 1,
    "RottenWillow": 2,
    "Denbrie": 1,
    "Brynn": 3,
}


def load_translations():
    """加载翻译数据"""
    locations = {}
    names = {}

    if LOCATIONS_FILE.exists():
        data = json.loads(LOCATIONS_FILE.read_text(encoding='utf-8'))
        titles = data.get("titles", {})
        for key, val in titles.items():
            locations[key] = {
                "en": val.get("English", key),
                "zh": val.get("中文", key),
            }

    if NAMES_FILE.exists():
        data = json.loads(NAMES_FILE.read_text(encoding='utf-8'))
        constant_name = data.get("Constant_Name", {})
        for key, val in constant_name.items():
            names[key] = {
                "en": val.get("English", ""),
                "zh": val.get("中文", ""),
            }

    return locations, names


def build_parent_map(inheritance: dict) -> dict:
    parent_map = {}
    for parent, children in inheritance.items():
        for child in children:
            parent_map[child] = parent
    return parent_map


def get_inheritance_chain(obj_name: str, parent_map: dict) -> list:
    chain = []
    current = obj_name
    while current in parent_map:
        parent = parent_map[current]
        chain.append(parent)
        current = parent
    return chain


def extract_shop_config(content: str, filename: str, names_data: dict) -> dict | None:
    """从 GML 文件内容中提取商店配置"""

    config = {
        "filename": filename,
        "npc_object": None,
        "town": None,
        # 名字相关字段
        "name_id": None,        # ds_list_find_value(global.npc_constant_name, X) 中的 X
        "name_index": None,     # name_index = X 赋值
        "is_quest_npc": None,   # is_quest_npc 布尔值
        "sex": None,            # sex = "male"/"female"
        "race": None,           # race = "human"/"elf" 等
        "name_en": None,
        "name_zh": None,
        # 商店配置字段
        "selling_loot_category": None,
        "equipment_tier_min": None,
        "equipment_tier_max_base": None,
        "material_spec": None,
        "trade_tags": None,
    }

    has_config = False

    # 提取 NPC 对象名
    match = re.search(r'gml_Object_(o_npc_[a-zA-Z0-9_]+?)_(?:Create|Other|Step|Alarm|Draw)', filename, re.IGNORECASE)
    if match:
        config["npc_object"] = match.group(1)
    else:
        match = re.search(r'gml_Object_(o_NPC)_', filename)
        if match:
            config["npc_object"] = match.group(1)

    # 提取 name ID (直接名字查找方式)
    match = re.search(r'name\s*=\s*ds_list_find_value\s*\(\s*global\.npc_constant_name\s*,\s*(\d+)\s*\)', content)
    if match:
        name_id = match.group(1)
        config["name_id"] = name_id
        if name_id in names_data:
            config["name_en"] = names_data[name_id]["en"]
            config["name_zh"] = names_data[name_id]["zh"]
        has_config = True

    # 提取 name_index (间接名字查找方式)
    match = re.search(r'\bname_index\s*=\s*(\d+)', content)
    if match:
        config["name_index"] = int(match.group(1))
        has_config = True

    # 提取 is_quest_npc
    match = re.search(r'\bis_quest_npc\s*=\s*(true|false|1|0)', content, re.IGNORECASE)
    if match:
        val = match.group(1).lower()
        config["is_quest_npc"] = val in ("true", "1")
        has_config = True

    # 提取 sex
    match = re.search(r'\bsex\s*=\s*"([^"]+)"', content)
    if match:
        config["sex"] = match.group(1)
        has_config = True

    # 提取 race
    match = re.search(r'\brace\s*=\s*"([^"]+)"', content)
    if match:
        config["race"] = match.group(1)
        has_config = True

    # 提取 town
    match = re.search(r'\btown\s*=\s*"([^"]+)"', content)
    if match:
        config["town"] = match.group(1)
        has_config = True


    # 提取 selling_loot_category
    match = re.search(r'scr_selling_loot_category\s*\((.+?)\);', content, re.DOTALL)
    if match:
        args_str = match.group(1)
        categories = {}
        pattern = r'"([^"]+)"\s*,\s*(\d+|irandom_range\s*\([^)]+\)|choose\s*\([^)]+\))'
        pairs = re.findall(pattern, args_str)
        for cat, count_expr in pairs:
            categories[cat] = count_expr.strip()
        if categories:
            config["selling_loot_category"] = categories
            has_config = True

    # 提取 Equipment_Tier_Min
    match = re.search(r'Equipment_Tier_Min\s*=\s*(\d+)', content)
    if match:
        config["equipment_tier_min"] = int(match.group(1))
        has_config = True

    # 提取 Equipment_Tier_Max_Base
    match = re.search(r'Equipment_Tier_Max_Base\s*=\s*(\d+)', content)
    if match:
        config["equipment_tier_max_base"] = int(match.group(1))
        has_config = True

    # 提取 Material_Spec
    match = re.search(r'Material_Spec\s*=\s*(\[[^\]]+\]|"[^"]+")', content)
    if match:
        val = match.group(1)
        if val.startswith('['):
            materials = re.findall(r'"([^"]+)"', val)
            config["material_spec"] = sorted(materials)
        else:
            config["material_spec"] = [val.strip('"')]
        has_config = True

    # 提取 trade_tags
    match = re.search(r'trade_tags\s*=\s*"([^"]*)"', content)
    if match:
        tags = match.group(1)
        config["trade_tags"] = sorted(tags.split()) if tags else []
        has_config = True

    return config if has_config else None


def merge_configs(all_configs: list) -> dict:
    merged = {}
    for cfg in all_configs:
        npc = cfg.get("npc_object") or cfg["filename"]
        if npc not in merged:
            merged[npc] = {
                "npc_object": npc,
                "town": None,
                # 名字相关
                "name_id": None,
                "name_index": None,
                "is_quest_npc": None,
                "sex": None,
                "race": None,
                "name_en": None,
                "name_zh": None,
                # 商店配置
                "selling_loot_category": None,
                "equipment_tier_min": None,
                "equipment_tier_max_base": None,
                "material_spec": None,
                "trade_tags": None,
            }

        for key in merged[npc].keys():
            if key != "npc_object" and cfg.get(key) is not None:
                merged[npc][key] = cfg[key]

    return merged


def apply_inheritance(merged: dict, parent_map: dict) -> None:
    """应用继承链来填充缺失字段"""
    fields = [
        "town",
        "name_index", "is_quest_npc", "sex", "race",
        "equipment_tier_min", "equipment_tier_max_base", "material_spec", "trade_tags"
    ]
    for npc, cfg in merged.items():
        chain = get_inheritance_chain(npc, parent_map)
        for field in fields:
            if cfg.get(field) is None:
                for parent in chain:
                    if parent in merged and merged[parent].get(field) is not None:
                        cfg[field] = merged[parent][field]
                        break


def calculate_tier_range(cfg: dict) -> list:
    tier_min = cfg.get("equipment_tier_min") or 1
    tier_max_base = cfg.get("equipment_tier_max_base") or 1
    town = cfg.get("town")
    perk_bonus = TOWN_MAX_TIER_BONUS.get(town, 0)
    tier_max = min(5, tier_max_base + perk_bonus)
    tier_max = max(tier_min, tier_max)
    return [tier_min, tier_max]


def config_to_hashable(cfg: dict) -> tuple:
    """将配置转换为可哈希的元组用于去重"""
    def make_hashable(v):
        if v is None:
            return None
        if isinstance(v, list):
            return tuple(v) if v else ()
        if isinstance(v, dict):
            return tuple(sorted((k, make_hashable(val)) for k, val in v.items()))
        return v

    return (
        make_hashable(cfg.get("selling_loot_category")),
        make_hashable(cfg.get("tier_range")),
        make_hashable(cfg.get("material_spec")),
        make_hashable(cfg.get("trade_tags")),
    )


def build_output(configs: list, locations: dict, names_data: dict) -> tuple[dict, dict]:
    """构建输出结构: (metadata_dict, config_dict)

    Args:
        configs: 合并后的 NPC 配置列表
        locations: 地名翻译字典
        names_data: Constant_Name 名字翻译字典（用于 name_index 查找）
    """

    # 1. 构建元数据字典
    metadata = {}
    for cfg in configs:
        npc = cfg.get("npc_object")
        if not npc:
            continue

        town = cfg.get("town")
        town_zh = locations.get(town, {}).get("zh") if town else None

        meta = {}
        if town:
            meta["town"] = town
            if town_zh:
                meta["town_zh"] = town_zh

        # 优先使用直接设置的名字
        name_en = cfg.get("name_en")
        name_zh = cfg.get("name_zh")

        # 如果没有直接名字，尝试用 name_index 查找
        if not name_en and cfg.get("name_index") is not None:
            name_idx = str(cfg["name_index"])
            # is_quest_npc 决定使用 Constant_Name 还是 Names
            # 由于 Names 池是随机的，只有 is_quest_npc=True 时才能确定显示名字
            if cfg.get("is_quest_npc") and name_idx in names_data:
                name_en = names_data[name_idx]["en"]
                name_zh = names_data[name_idx]["zh"]

        if name_en:
            meta["name_en"] = name_en
        if name_zh:
            meta["name_zh"] = name_zh

        # 添加 sex 和 race（用于理解 NPC 类型）
        if cfg.get("sex"):
            meta["sex"] = cfg["sex"]
        if cfg.get("race"):
            meta["race"] = cfg["race"]

        if meta:
            metadata[npc] = meta

    # 2. 过滤有 selling_loot_category 的配置并计算 tier_range
    valid_configs = []
    for cfg in configs:
        if not cfg.get("selling_loot_category"):
            continue

        cfg["tier_range"] = calculate_tier_range(cfg)
        valid_configs.append(cfg)

    # 3. 按配置内容分组
    groups = defaultdict(list)
    for cfg in valid_configs:
        key = config_to_hashable(cfg)
        groups[key].append(cfg["npc_object"])

    # 4. 构建配置字典 {tuple(sorted(objects)): config}
    config_dict = {}
    for key, objects in groups.items():
        # 找到第一个对应的配置
        sample_cfg = next(c for c in valid_configs if c["npc_object"] in objects)

        config_entry = {
            "selling_loot_category": sample_cfg["selling_loot_category"],
            "tier_range": sample_cfg["tier_range"],
        }
        if sample_cfg.get("material_spec"):
            config_entry["material_spec"] = sample_cfg["material_spec"]
        if sample_cfg.get("trade_tags"):
            config_entry["trade_tags"] = sample_cfg["trade_tags"]

        config_dict[tuple(sorted(objects))] = config_entry

    return metadata, config_dict


def to_python_source(metadata: dict, config_dict: dict) -> str:
    """生成 Python 源代码"""
    lines = [
        '"""',
        'NPC 商店配置数据',
        '',
        '自动生成，请勿手动修改',
        '"""',
        '',
        '# NPC 元数据: object -> {town, town_zh, name_en, name_zh}',
        'NPC_METADATA = {',
    ]

    for npc in sorted(metadata.keys()):
        meta = metadata[npc]
        meta_str = ", ".join(f'"{k}": "{v}"' for k, v in meta.items())
        lines.append(f'    "{npc}": {{{meta_str}}},')

    lines.append('}')
    lines.append('')
    lines.append('# 商店配置: (objects...) -> config')
    lines.append('SHOP_CONFIGS = {')

    for key in sorted(config_dict.keys()):
        cfg = config_dict[key]
        # 格式化 key
        if len(key) == 1:
            key_str = f'("{key[0]}",)'
        else:
            key_str = f'({", ".join(repr(k) for k in key)})'

        lines.append(f'    {key_str}: {{')

        # selling_loot_category
        lines.append('        "selling_loot_category": {')
        for cat, count in cfg["selling_loot_category"].items():
            lines.append(f'            "{cat}": {count!r},')
        lines.append('        },')

        # tier_range
        lines.append(f'        "tier_range": {cfg["tier_range"]!r},')

        # material_spec
        if cfg.get("material_spec"):
            lines.append(f'        "material_spec": {cfg["material_spec"]!r},')

        # trade_tags
        if cfg.get("trade_tags"):
            lines.append(f'        "trade_tags": {cfg["trade_tags"]!r},')

        lines.append('    },')

    lines.append('}')
    lines.append('')

    return '\n'.join(lines)


def main():
    print(f"扫描目录: {GML_DIR}")

    locations, names = load_translations()
    print(f"加载翻译: {len(locations)} 地点, {len(names)} 名称")

    if INHERITANCE_FILE.exists():
        inheritance = json.loads(INHERITANCE_FILE.read_text(encoding='utf-8'))
        parent_map = build_parent_map(inheritance)
        print(f"加载继承关系: {len(parent_map)} 个对象")
    else:
        parent_map = {}

    all_configs = []
    patterns = ["gml_Object_o_npc_*.gml", "gml_Object_o_NPC_*.gml"]

    for pattern in patterns:
        for gml_file in GML_DIR.glob(pattern):
            content = gml_file.read_text(encoding='utf-8', errors='ignore')
            config = extract_shop_config(content, gml_file.name, names)
            if config:
                all_configs.append(config)

    print(f"提取了 {len(all_configs)} 个原始配置")

    merged = merge_configs(all_configs)
    print(f"合并后 {len(merged)} 个 NPC")

    apply_inheritance(merged, parent_map)

    metadata, config_dict = build_output(list(merged.values()), locations, names)

    print(f"元数据: {len(metadata)} 个 NPC")
    print(f"配置: {len(config_dict)} 个唯一配置组")

    # 统计 NPC 数量
    total_npcs = sum(len(k) for k in config_dict.keys())
    print(f"涵盖 {total_npcs} 个有 selling_loot_category 的 NPC")

    py_source = to_python_source(metadata, config_dict)
    OUTPUT_FILE.write_text(py_source, encoding='utf-8')

    print(f"\n结果已保存到: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
