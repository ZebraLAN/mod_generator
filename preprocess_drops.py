#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
预处理 drops.json 生成优化的静态索引

优化策略：
1. 按 (category, tier) 分组索引，支持 O(1) 精确查找
2. 元数据与索引分离，减少重复存储
3. Tags 使用 bit flags，加速匹配
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ============== Tag Bit Flags ==============
# 只有9个有效 tag，用 bit flags 表示
TAG_TO_BIT = {
    "common": 1 << 0,
    "uncommon": 1 << 1,
    "rare": 1 << 2,
    "raw": 1 << 3,
    "cooked": 1 << 4,
    "animal": 1 << 5,
    "alchemy": 1 << 6,
    "crypt": 1 << 7,
    "catacombs": 1 << 8,
    "bastion": 1 << 9,
    "elven": 1 << 10,
}

# ============== 容器名翻译表 ==============
# 使用前缀匹配，按长度降序排列以优先匹配更长的模式
CONTAINER_TRANSLATIONS = {
    # 复合词（优先匹配）
    "bastionBarrels": "棱堡木桶",
    "bastionBossChest": "棱堡首领宝箱",
    "bastionChest": "棱堡宝箱",
    "bastionNightstand": "棱堡床头柜",
    "bastionShelf": "棱堡架子",
    "bastionWardrobe": "棱堡衣柜",
    "cartCommodity": "商品推车",
    "catacombsBookshelf": "墓道书架",
    "catacombsBossChest": "墓道首领宝箱",
    "catacombsCabinet": "墓道柜子",
    "catacombsMedishelf": "墓道药架",
    "catacombsScrollshelf": "墓道卷轴架",
    "catacombsShelf": "墓道架子",
    "caveChest": "洞穴宝箱",
    "caveSecretForge": "洞穴密室锻炉",
    "caveSecretGeneric": "洞穴密室",
    "caveSecretShrine": "洞穴密室神龛",
    "caveSecretTomb": "洞穴密室墓室",
    "contractSeal": "悬赏封印",
    "cryptBossChest": "墓穴首领宝箱",
    "cryptSecret": "墓穴密室",
    "cryptTreasureTomb": "墓穴宝藏墓室",
    "cryptTomb": "墓穴墓室",
    "deadBodyCave": "洞穴死尸",
    "deadBody": "死尸",
    "genericChest": "普通宝箱",
    "graveSurface": "地表坟墓",
    "graveyardTomb": "墓地墓室",
    "offeringChest": "祭品宝箱",
    "osbrookMillBarn": "奥斯布鲁克磨坊谷仓",
    "ruinedManorChest": "废弃庄园宝箱",
    "secretStash": "密室藏匿处",
    "shipWreck": "船只残骸",
    "villageFood": "村庄食物",
    "villageGeneric": "村庄普通",
    "villageRich": "村庄富人",
}

import re

def translate_entry_id(entry_id: str) -> str:
    """将容器名翻译为中文
    
    使用前缀匹配，去掉末尾数字后在翻译表中查找
    """
    # 去掉末尾数字
    base_name = re.sub(r'\d+$', '', entry_id)
    suffix = entry_id[len(base_name):]
    
    # 查找翻译
    if base_name in CONTAINER_TRANSLATIONS:
        return CONTAINER_TRANSLATIONS[base_name] + suffix
    
    # 如果没找到，返回原名
    return entry_id


def tags_to_bits(tags_str: str) -> int:
    """将 tags 字符串转为 bit flags"""
    if not tags_str:
        return 0
    bits = 0
    for tag in tags_str.replace(",", " ").split():
        tag = tag.strip()
        if tag in TAG_TO_BIT:
            bits |= TAG_TO_BIT[tag]
    return bits


def parse_tier_mod(tier_mod: str, entry_tier: str) -> Tuple[int, int]:
    """解析 tierMod 字段，返回 (min_tier, max_tier)"""
    if not tier_mod:
        try:
            loc_tier = int(entry_tier) if entry_tier.isdigit() else 5
        except ValueError:
            loc_tier = 5
        return (1, loc_tier)
    
    if "," not in tier_mod:
        try:
            val = int(tier_mod)
            return (val, val)
        except ValueError:
            return (1, 5)
    
    parts = [p.strip() for p in tier_mod.split(",")]
    try:
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
        elif len(parts) >= 3:
            return (int(parts[0]), int(parts[2]))
    except ValueError:
        pass
    return (1, 5)


def build_index(drops_path: Path) -> Tuple[Dict, Dict]:
    """构建优化的索引结构
    
    Returns:
        slot_metadata: {(entry_id, slot_num): {category, slot_tags_bits, chance}}
        tier_index: {(category, tier): [(entry_id, slot_num), ...]}
    """
    slot_metadata: Dict[Tuple[str, int], dict] = {}
    tier_index: Dict[Tuple[str, int], List[Tuple[str, int]]] = {}
    
    with open(drops_path, "r", encoding="utf-8") as f:
        drops_data = json.load(f)
    
    for entry_id, entry in drops_data.get("default", {}).items():
        if not entry_id or entry_id.startswith("//"):
            continue
        
        tier_mod = entry.get("tierMod", "") or ""
        entry_tier = entry.get("tier", "") or ""
        tier_min, tier_max = parse_tier_mod(tier_mod, entry_tier)
        
        for slot_num in range(1, 10):
            slot_key = f"slot{slot_num}"
            slot_val = entry.get(slot_key, "") or ""
            
            if not slot_val or slot_val.startswith("o_inv_"):
                continue
            
            slot_tags = entry.get(f"{slot_key}_tags", "") or ""
            slot_tags_bits = tags_to_bits(slot_tags)
            chance_str = entry.get(f"{slot_key}_chance", "") or "0"
            try:
                chance = int(chance_str)
            except ValueError:
                chance = 0
            
            # 获取 slot_count
            count_str = entry.get(f"{slot_key}_count", "") or "1"
            try:
                slot_count = int(count_str)
            except ValueError:
                slot_count = 1
            
            slot_id = (entry_id, slot_num)
            
            # 存储元数据（只存一次）
            slot_metadata[slot_id] = {
                "category": slot_val,
                "slot_tags": slot_tags,
                "slot_tags_bits": slot_tags_bits,
                "chance": chance,
                "slot_count": slot_count,
                "tier_min": tier_min,
                "tier_max": tier_max,
                "entry_name_cn": translate_entry_id(entry_id),
            }
            
            # 按 (category, tier) 分组索引
            # 一个 slot 会出现在其 tier 范围内的每个 tier 级别
            for cat in slot_val.split(", "):
                cat = cat.strip()
                if not cat:
                    continue
                # tier=0 通配符：收集该 category 的所有 slots
                key_wildcard = (cat, 0)
                if key_wildcard not in tier_index:
                    tier_index[key_wildcard] = []
                if slot_id not in tier_index[key_wildcard]:
                    tier_index[key_wildcard].append(slot_id)
                
                # 按具体 tier 分组
                for tier in range(tier_min, tier_max + 1):
                    key = (cat, tier)
                    if key not in tier_index:
                        tier_index[key] = []
                    if slot_id not in tier_index[key]:
                        tier_index[key].append(slot_id)
    
    return slot_metadata, tier_index


def generate_python_file(slot_metadata: Dict, tier_index: Dict, output_path: Path):
    """生成格式化的 Python 模块文件"""
    
    lines = [
        '# -*- coding: utf-8 -*-',
        '"""',
        '预生成的 drop slot 索引（由 preprocess_drops.py 生成）',
        '',
        '不要手动编辑此文件，修改 drops.json 后重新运行 preprocess_drops.py',
        '"""',
        '',
        '# Tag bit flags 定义',
        'TAG_BITS = {',
    ]
    for tag, bit in sorted(TAG_TO_BIT.items(), key=lambda x: x[1]):
        lines.append(f'    "{tag}": {bit},')
    lines.append('}')
    lines.append('')
    
    # 元数据字典
    lines.append('# Slot 元数据: {(entry_id, slot_num): {...}}')
    lines.append('SLOT_METADATA = {')
    for slot_id in sorted(slot_metadata.keys()):
        meta = slot_metadata[slot_id]
        lines.append(
            f'    ("{slot_id[0]}", {slot_id[1]}): '
            f'{{"category": "{meta["category"]}", "slot_tags": "{meta["slot_tags"]}", '
            f'"slot_tags_bits": {meta["slot_tags_bits"]}, "chance": {meta["chance"]}, '
            f'"slot_count": {meta["slot_count"]}, '
            f'"tier_min": {meta["tier_min"]}, "tier_max": {meta["tier_max"]}, '
            f'"entry_name_cn": "{meta["entry_name_cn"]}"}},'
        )
    lines.append('}')
    lines.append('')
    
    # Tier 索引
    lines.append('# 按 (category, tier) 分组的索引: {(cat, tier): [(entry_id, slot_num), ...]}')
    lines.append('TIER_INDEX = {')
    for key in sorted(tier_index.keys()):
        slots = tier_index[key]
        slots_str = ", ".join(f'("{s[0]}", {s[1]})' for s in sorted(slots))
        lines.append(f'    ("{key[0]}", {key[1]}): [{slots_str}],')
    lines.append('}')
    lines.append('')
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Generated {output_path}")
    print(f"  - {len(slot_metadata)} slots with metadata")
    print(f"  - {len(tier_index)} (category, tier) index entries")


def main():
    base_dir = Path(__file__).parent
    drops_path = base_dir / "output_json" / "drops.json"
    output_path = base_dir / "drop_slot_index.py"
    
    if not drops_path.exists():
        print(f"Error: {drops_path} not found")
        return
    
    slot_metadata, tier_index = build_index(drops_path)
    generate_python_file(slot_metadata, tier_index, output_path)


if __name__ == "__main__":
    main()
