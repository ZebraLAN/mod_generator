#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
预处理 drops.json 生成优化的静态索引

包含两种索引:
1. 非装备路径: slot1-slot9 (物品分类)
2. 装备路径: eq1-eq5 (weapon/armor/jewelry)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ============== 容器名翻译表 ==============
CONTAINER_TRANSLATIONS = {
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


def translate_entry_id(entry_id: str) -> str:
    """将容器名翻译为中文"""
    base_name = re.sub(r'\d+$', '', entry_id)
    suffix = entry_id[len(base_name):]
    if base_name in CONTAINER_TRANSLATIONS:
        return CONTAINER_TRANSLATIONS[base_name] + suffix
    return entry_id


def parse_tags(tags_str: str) -> str:
    """标准化 tags 字符串（空格分隔）"""
    if not tags_str:
        return ""
    return " ".join(t.strip() for t in tags_str.replace(",", " ").split() if t.strip())


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


def build_index(drops_path: Path) -> Tuple[Dict, Dict, Dict, Dict]:
    """构建索引结构
    
    Returns:
        slot_metadata: 非装备槽位元数据
        tier_index: 非装备 (category, tier) 索引
        eq_metadata: 装备槽位元数据
        eq_tier_index: 装备 (eq_category, tier) 索引
    """
    slot_metadata: Dict[Tuple[str, int], dict] = {}
    tier_index: Dict[Tuple[str, int], List[Tuple[str, int]]] = {}
    eq_metadata: Dict[Tuple[str, int], dict] = {}
    eq_tier_index: Dict[Tuple[str, int], List[Tuple[str, int]]] = {}
    
    with open(drops_path, "r", encoding="utf-8") as f:
        drops_data = json.load(f)
    
    for entry_id, entry in drops_data.get("default", {}).items():
        if not entry_id or entry_id.startswith("//"):
            continue
        
        tier_mod = entry.get("tierMod", "") or ""
        entry_tier = entry.get("tier", "") or ""
        tier_min, tier_max = parse_tier_mod(tier_mod, entry_tier)
        entry_name_cn = translate_entry_id(entry_id)
        
        # ===== 非装备槽位 (slot1-slot9) =====
        for slot_num in range(1, 10):
            slot_key = f"slot{slot_num}"
            slot_val = entry.get(slot_key, "") or ""
            
            if not slot_val or slot_val.startswith("o_inv_"):
                continue
            
            slot_tags = parse_tags(entry.get(f"{slot_key}_tags", "") or "")
            chance_str = entry.get(f"{slot_key}_chance", "") or "0"
            count_str = entry.get(f"{slot_key}_count", "") or "1"
            
            try:
                chance = int(chance_str)
            except ValueError:
                chance = 0
            try:
                slot_count = int(count_str)
            except ValueError:
                slot_count = 1
            
            slot_id = (entry_id, slot_num)
            
            slot_metadata[slot_id] = {
                "category": slot_val,
                "slot_tags": slot_tags,
                "chance": chance,
                "slot_count": slot_count,
                "tier_min": tier_min,
                "tier_max": tier_max,
                "entry_name_cn": entry_name_cn,
            }
            
            for cat in slot_val.split(", "):
                cat = cat.strip()
                if not cat:
                    continue
                # tier=0 通配符
                key_wildcard = (cat, 0)
                if key_wildcard not in tier_index:
                    tier_index[key_wildcard] = []
                if slot_id not in tier_index[key_wildcard]:
                    tier_index[key_wildcard].append(slot_id)
                
                for tier in range(tier_min, tier_max + 1):
                    key = (cat, tier)
                    if key not in tier_index:
                        tier_index[key] = []
                    if slot_id not in tier_index[key]:
                        tier_index[key].append(slot_id)
        
        # ===== 装备槽位 (eq1-eq5) =====
        for eq_num in range(1, 6):
            eq_key = f"eq{eq_num}"
            eq_val = entry.get(eq_key, "") or ""
            
            if not eq_val:
                continue
            
            eq_tags = parse_tags(entry.get(f"{eq_key}_tags", "") or "")
            eq_rarity = parse_tags(entry.get(f"{eq_key}_rarity", "") or "")
            eq_dur = entry.get(f"{eq_key}_dur", "") or ""
            eq_chance_str = entry.get(f"{eq_key}_chance", "") or "0"
            
            try:
                eq_chance = int(eq_chance_str)
            except ValueError:
                eq_chance = 0
            
            eq_slot_id = (entry_id, eq_num)
            
            eq_metadata[eq_slot_id] = {
                "eq_category": eq_val,  # weapon, armor, jewelry
                "eq_tags": eq_tags,
                "eq_rarity": eq_rarity,
                "eq_dur": eq_dur,
                "chance": eq_chance,
                "tier_min": tier_min,
                "tier_max": tier_max,
                "entry_name_cn": entry_name_cn,
            }
            
            # 按装备类别和 tier 索引
            for eq_cat in eq_val.split(", "):
                eq_cat = eq_cat.strip()
                if not eq_cat:
                    continue
                
                # tier=0 通配符
                key_wildcard = (eq_cat, 0)
                if key_wildcard not in eq_tier_index:
                    eq_tier_index[key_wildcard] = []
                if eq_slot_id not in eq_tier_index[key_wildcard]:
                    eq_tier_index[key_wildcard].append(eq_slot_id)
                
                for tier in range(tier_min, tier_max + 1):
                    key = (eq_cat, tier)
                    if key not in eq_tier_index:
                        eq_tier_index[key] = []
                    if eq_slot_id not in eq_tier_index[key]:
                        eq_tier_index[key].append(eq_slot_id)
    
    return slot_metadata, tier_index, eq_metadata, eq_tier_index


def generate_python_file(slot_metadata: Dict, tier_index: Dict, 
                         eq_metadata: Dict, eq_tier_index: Dict, 
                         output_path: Path):
    """生成 Python 模块文件"""
    
    lines = [
        '# -*- coding: utf-8 -*-',
        '"""',
        '预生成的 drop slot 索引（由 preprocess_drops.py 生成）',
        '',
        '不要手动编辑此文件，修改 drops.json 后重新运行 preprocess_drops.py',
        '"""',
        '',
    ]
    
    # ===== 非装备槽位元数据 =====
    lines.append('# 非装备槽位元数据: {(entry_id, slot_num): {...}}')
    lines.append('SLOT_METADATA = {')
    for slot_id in sorted(slot_metadata.keys()):
        meta = slot_metadata[slot_id]
        lines.append(
            f'    ("{slot_id[0]}", {slot_id[1]}): '
            f'{{"category": "{meta["category"]}", "slot_tags": "{meta["slot_tags"]}", '
            f'"chance": {meta["chance"]}, "slot_count": {meta["slot_count"]}, '
            f'"tier_min": {meta["tier_min"]}, "tier_max": {meta["tier_max"]}, '
            f'"entry_name_cn": "{meta["entry_name_cn"]}"}},'
        )
    lines.append('}')
    lines.append('')
    
    # ===== 非装备 Tier 索引 =====
    lines.append('# 非装备 (category, tier) 索引')
    lines.append('TIER_INDEX = {')
    for key in sorted(tier_index.keys()):
        slots = tier_index[key]
        slots_str = ", ".join(f'("{s[0]}", {s[1]})' for s in sorted(slots))
        lines.append(f'    ("{key[0]}", {key[1]}): [{slots_str}],')
    lines.append('}')
    lines.append('')
    
    # ===== 装备槽位元数据 =====
    lines.append('# 装备槽位元数据: {(entry_id, eq_num): {...}}')
    lines.append('EQ_METADATA = {')
    for eq_id in sorted(eq_metadata.keys()):
        meta = eq_metadata[eq_id]
        lines.append(
            f'    ("{eq_id[0]}", {eq_id[1]}): '
            f'{{"eq_category": "{meta["eq_category"]}", "eq_tags": "{meta["eq_tags"]}", '
            f'"eq_rarity": "{meta["eq_rarity"]}", "eq_dur": "{meta["eq_dur"]}", '
            f'"chance": {meta["chance"]}, '
            f'"tier_min": {meta["tier_min"]}, "tier_max": {meta["tier_max"]}, '
            f'"entry_name_cn": "{meta["entry_name_cn"]}"}},'
        )
    lines.append('}')
    lines.append('')
    
    # ===== 装备 Tier 索引 =====
    lines.append('# 装备 (eq_category, tier) 索引')
    lines.append('EQ_TIER_INDEX = {')
    for key in sorted(eq_tier_index.keys()):
        slots = eq_tier_index[key]
        slots_str = ", ".join(f'("{s[0]}", {s[1]})' for s in sorted(slots))
        lines.append(f'    ("{key[0]}", {key[1]}): [{slots_str}],')
    lines.append('}')
    lines.append('')
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Generated {output_path}")
    print(f"  - {len(slot_metadata)} non-equipment slots")
    print(f"  - {len(tier_index)} non-equipment index entries")
    print(f"  - {len(eq_metadata)} equipment slots")
    print(f"  - {len(eq_tier_index)} equipment index entries")


def main():
    base_dir = Path(__file__).parent.parent  # codegen -> project root
    drops_path = base_dir / "game_data" / "drops.json"
    output_path = base_dir / "drop_slot_index.py"
    
    if not drops_path.exists():
        print(f"Error: {drops_path} not found")
        return
    
    slot_metadata, tier_index, eq_metadata, eq_tier_index = build_index(drops_path)
    generate_python_file(slot_metadata, tier_index, eq_metadata, eq_tier_index, output_path)


if __name__ == "__main__":
    main()
