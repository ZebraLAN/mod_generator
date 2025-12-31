# -*- coding: utf-8 -*-
"""
Drop Slot 匹配数据模块（优化版 v3）

使用预生成的 (category, tier) 索引和 bit flag tags 进行 O(1) 查找。
"""

from functools import lru_cache
from typing import Dict, List, Tuple

from drop_slot_index import SLOT_METADATA, TIER_INDEX, TAG_BITS

# ============== 分类常量 ==============

ITEM_CATEGORIES = [
    "additive", "alcohol", "ammo", "backpack", "bag", "beverage", "book",
    "commodity", "drug", "flag", "food", "ingredient", "junk", "material",
    "medicine", "other", "quest", "recipe", "resource", "schematic",
    "scroll", "tool", "treasure", "trophy", "upgrade", "valuable"
]

ITEM_SUBCATEGORIES = [
    "alchemy", "berry", "beverage", "bird", "dairy", "dish", "fish", "folio",
    "fruit", "gem", "herb", "hide", "ingredient", "meat", "meat_large",
    "mushroom", "pastry", "potion", "quest", "treatise", "vegetable"
]

ALL_SUBCATEGORY_OPTIONS = sorted(set(ITEM_CATEGORIES + ITEM_SUBCATEGORIES))

# 分类中文翻译
CATEGORY_TRANSLATIONS: Dict[str, str] = {
    # 主分类
    "additive": "添加剂",
    "alcohol": "酒",
    "ammo": "弹药",
    "backpack": "背包",
    "bag": "袋子",
    "beverage": "饮料",
    "book": "书籍",
    "commodity": "商品",
    "drug": "药品",
    "flag": "旗帜",
    "food": "食物",
    "ingredient": "原料",
    "junk": "垃圾",
    "material": "材料",
    "medicine": "药物",
    "other": "其他",
    "quest": "任务物品",
    "recipe": "配方",
    "resource": "资源",
    "schematic": "图纸",
    "scroll": "卷轴",
    "tool": "工具",
    "treasure": "文物",
    "trophy": "战利品",
    "upgrade": "升级材料",
    "valuable": "贵重物品",
    # 子分类
    "alchemy": "炼金",
    "berry": "浆果",
    "bird": "禽类",
    "dairy": "乳制品",
    "dish": "菜肴",
    "fish": "鱼",
    "folio": "卷宗",
    "fruit": "水果",
    "gem": "宝石",
    "herb": "草药",
    "hide": "兽皮",
    "meat": "肉",
    "meat_large": "大块肉",
    "mushroom": "蘑菇",
    "pastry": "糕点",
    "potion": "药剂",
    "treatise": "论著",
    "vegetable": "蔬菜",
}

# ============== Tags 常量（值: 中文标签）==============

QUALITY_TAGS: Dict[str, str] = {
    "": "无",
    "common": "普通",
    "uncommon": "不常见",
    "rare": "稀有",
}

DUNGEON_TAGS: Dict[str, str] = {
    "": "无",
    "crypt": "墓穴",
    "catacombs": "墓道",
    "bastion": "棱堡",
}

EXTRA_TAGS: Dict[str, str] = {
    "raw": "生的",
    "cooked": "熟的",
    "animal": "动物",
    "alchemy": "炼金",
    "elven": "精灵",
}


# ============== 匹配逻辑 ==============

def tags_to_bits(tags: Tuple[str, ...]) -> int:
    """将 tags 元组转为 bit flags"""
    bits = 0
    for tag in tags:
        if tag in TAG_BITS:
            bits |= TAG_BITS[tag]
    return bits


def _tags_match_bits(item_tags_bits: int, slot_tags_bits: int) -> bool:
    """使用 bit flags 检查 tags 匹配"""
    if slot_tags_bits == 0 or item_tags_bits == 0:
        return True
    return (item_tags_bits & slot_tags_bits) == item_tags_bits


@lru_cache(maxsize=256)
def find_matching_slots(cat: str, subcats: Tuple[str, ...], tags_bits: int, tier: int) -> Tuple[dict, ...]:
    """查询物品可能出现的所有 drop slots
    
    Returns:
        Tuple of dicts: {"entry_id", "slot_num", "chance", "slot_tags", "tier_range"}
    """
    matches: List[dict] = []
    seen = set()
    
    for check_cat in {cat} | set(subcats):
        if not check_cat:
            continue
        
        key = (check_cat, tier)
        if key not in TIER_INDEX:
            continue
        
        for slot_id in TIER_INDEX[key]:
            if slot_id in seen:
                continue
            
            meta = SLOT_METADATA.get(slot_id)
            if not meta or not _tags_match_bits(tags_bits, meta["slot_tags_bits"]):
                continue
            
            seen.add(slot_id)
            tier_range = f"{meta['tier_min']}-{meta['tier_max']}" if meta["tier_min"] != meta["tier_max"] else str(meta["tier_min"])
            matches.append({
                "entry_id": slot_id[0],
                "entry_name_cn": meta.get("entry_name_cn", slot_id[0]),
                "slot_num": slot_id[1],
                "category": meta["category"],
                "chance": meta["chance"],
                "slot_count": meta.get("slot_count", 1),
                "slot_tags": meta["slot_tags"],
                "tier_range": tier_range,
            })
    
    matches.sort(key=lambda m: (m["entry_id"], m["slot_num"]))
    return tuple(matches)


def clear_cache():
    """清除查询缓存"""
    find_matching_slots.cache_clear()
