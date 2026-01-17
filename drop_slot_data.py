# -*- coding: utf-8 -*-
"""
Drop Slot 匹配数据模块

使用预生成的 (category, tier) 索引进行 O(1) 查找。
使用简单的标签子集检查进行匹配。
"""

from functools import lru_cache
from typing import Dict, List, Tuple, Set

from drop_slot_index import SLOT_METADATA, TIER_INDEX, EQ_METADATA, EQ_TIER_INDEX

# ============== 分类常量 ==============

ITEM_CATEGORIES = [
    # 暂不支持的分类已注释
    # "additive", "alcohol", "ammo", "backpack", "bag", "book",
    # "commodity", "flag", "other", "quest", "recipe", "schematic",
    # "scroll", "trophy", "upgrade",
    "beverage", "drug", "food", "ingredient", "junk", "material",
    "medicine", "resource", "tool", "treasure", "valuable"
]

ITEM_SUBCATEGORIES = [
    # 暂不支持: "folio", "treatise", "quest"
    "alchemy", "berry", "beverage", "bird", "dairy", "dish", "fish",
    "fruit", "gem", "herb", "hide", "ingredient", "meat", "meat_large",
    "mushroom", "pastry", "potion", "vegetable"
]

ALL_SUBCATEGORY_OPTIONS = sorted(set(ITEM_CATEGORIES + ITEM_SUBCATEGORIES))

# 分类中文翻译 (来自 items.json["consum_type_hover"])
CATEGORY_TRANSLATIONS: Dict[str, str] = {
    # 主分类
    "additive": "佐料",
    "alcohol": "酒水",
    "ammo": "箭矢",
    "backpack": "背包",
    "bag": "包/筒",
    "beverage": "饮物",
    "book": "书簿",
    "commodity": "商货",
    "drug": "毒品",
    "flag": "旗帜",
    "food": "食物",
    "ingredient": "原料",
    "junk": "废品",
    "material": "材料",
    "medicine": "医药",
    "other": "其他",
    "quest": "任务物品",
    "recipe": "菜谱/配方",
    "resource": "资源",
    "schematic": "图纸",
    "scroll": "卷轴",
    "tool": "工具",
    "trap": "陷阱",
    "treasure": "文物",
    "trophy": "战利品",
    "upgrade": "升级项目",
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
    "herb": "草本植物",
    "hide": "毛皮",
    "meat": "肉",
    "meat_large": "大块肉",
    "mushroom": "蘑菇",
    "pastry": "糕点",
    "potion": "药剂",
    "treatise": "文献",
    "vegetable": "蔬菜",
    # 装备类型
    "weapon": "武器",
    "armor": "防具",
    "jewelry": "首饰",
}


# ============== Tags 常量（值: 中文标签）==============

QUALITY_TAGS: Dict[str, str] = {
    "": "无",
    "common": "普通",
    "uncommon": "不常见",
    "rare": "稀有",
    "unique": "独特",
}

DUNGEON_TAGS: Dict[str, str] = {
    "": "无",
    "crypt": "墓穴",
    "catacombs": "墓道",
    "bastion": "棱堡",
}

# 国家/地区标签（互斥，可为空）
COUNTRY_TAGS: Dict[str, str] = {
    "": "无",
    "aldor": "奥尔多",
    "nistra": "尼斯特拉",
    "skadia": "斯卡迪亚",
    "fjall": "弗约",
    "elven": "精灵",
    "maen": "玛恩",
}

EXTRA_TAGS: Dict[str, str] = {
    "raw": "生的",
    "cooked": "熟的",
    "animal": "动物",
    "alchemy": "炼金",
    "brynn": "布林",
    "aldwynn": "奥尔德温",
    "magic": "魔法",
    "special": "特殊",
}

ALL_TAGS = {**QUALITY_TAGS, **DUNGEON_TAGS, **COUNTRY_TAGS, **EXTRA_TAGS}


# ============== 匹配逻辑 ==============

def _tags_match_non_equipment(item_tags: Set[str], slot_tags_str: str) -> bool:
    """非装备路径标签匹配（宽松模式）
    
    规则:
    1. 如果槽位没有标签，允许所有物品
    2. 如果槽位有标签但物品没有标签，允许（非装备不强制要求标签）
    3. 如果槽位有标签且物品有标签，物品的所有标签须在槽位标签中（子集）
    """
    if not slot_tags_str:
        return True
    if not item_tags:
        return True  # 非装备路径：物品没有标签时也允许
    slot_tags = set(slot_tags_str.split())
    return item_tags.issubset(slot_tags)


def _tags_match_equipment(item_tags: Set[str], slot_tags_str: str) -> bool:
    """装备路径标签匹配（严格模式，参考 scr_weapon_tags_compare）
    
    规则:
    1. 如果槽位没有标签，允许所有物品
    2. 如果槽位有标签但物品没有标签，不匹配
    3. 如果槽位有标签且物品有标签，物品的所有标签须在槽位标签中（子集）
    """
    if not slot_tags_str:
        return True
    # 槽位有标签要求，但物品没有标签 -> 不匹配
    if not item_tags:
        return False
    slot_tags = set(slot_tags_str.split())
    return item_tags.issubset(slot_tags)


@lru_cache(maxsize=256)
def find_matching_slots(cat: str, subcats: Tuple[str, ...], item_tags: Tuple[str, ...], tier: int) -> Tuple[dict, ...]:
    """查询非装备物品可能出现的所有 drop slots
    
    Args:
        cat: 主分类
        subcats: 子分类元组
        item_tags: 物品标签元组
        tier: 物品等级
    
    Returns:
        Tuple of dicts: {entry_id, slot_num, category, chance, slot_tags, tier_range, ...}
    """
    if not cat and not subcats:
        return ()
    
    matches: List[dict] = []
    seen = set()
    item_tags_set = set(item_tags) if item_tags else set()
    
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
            if not meta:
                continue
            
            # 使用非装备路径的宽松匹配
            if not _tags_match_non_equipment(item_tags_set, meta["slot_tags"]):
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


@lru_cache(maxsize=256)
def find_matching_eq_slots(eq_category: str, item_tags: Tuple[str, ...], tier: int) -> Tuple[dict, ...]:
    """查询装备物品可能出现的所有 equipment drop slots
    
    Args:
        eq_category: 装备类别 (weapon/armor/jewelry)
        item_tags: 物品标签元组
        tier: 物品等级
    
    Returns:
        Tuple of dicts: {entry_id, eq_num, eq_category, eq_tags, eq_rarity, chance, tier_range, ...}
    """
    if not eq_category:
        return ()
    
    matches: List[dict] = []
    seen = set()
    item_tags_set = set(item_tags) if item_tags else set()
    
    key = (eq_category, tier)
    if key not in EQ_TIER_INDEX:
        return ()
    
    for eq_id in EQ_TIER_INDEX[key]:
        if eq_id in seen:
            continue
        
        meta = EQ_METADATA.get(eq_id)
        if not meta:
            continue
        
        # 使用装备路径的严格匹配 (scr_weapon_tags_compare)
        if not _tags_match_equipment(item_tags_set, meta["eq_tags"]):
            continue
        
        seen.add(eq_id)
        tier_range = f"{meta['tier_min']}-{meta['tier_max']}" if meta["tier_min"] != meta["tier_max"] else str(meta["tier_min"])
        matches.append({
            "entry_id": eq_id[0],
            "entry_name_cn": meta.get("entry_name_cn", eq_id[0]),
            "eq_num": eq_id[1],
            "eq_category": meta["eq_category"],
            "eq_tags": meta["eq_tags"],
            "eq_rarity": meta["eq_rarity"],
            "eq_dur": meta.get("eq_dur", ""),
            "chance": meta["chance"],
            "tier_range": tier_range,
        })
    
    matches.sort(key=lambda m: (m["entry_id"], m["eq_num"]))
    return tuple(matches)


def clear_cache():
    """清除查询缓存"""
    find_matching_slots.cache_clear()
    find_matching_eq_slots.cache_clear()
