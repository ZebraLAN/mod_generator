# -*- coding: utf-8 -*-
"""
数据模型模块

包含所有数据类：Item, Weapon, Armor, HybridItem, ModProject, ItemTextures, ItemLocalization
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from constants import (
    ARMOR_HOOK_TO_SLOT,
    ARMOR_SLOT_TO_HOOK,
    ARMOR_SLOTS_MULTI_POSE,
    ARMOR_SLOTS_WITH_CHAR_PREVIEW,
    HYBRID_SLOT_LABELS,
    ITEM_TYPE_CONFIG,
    LEFT_HAND_SLOTS,
    PRIMARY_LANGUAGE,
)


# ============== 枚举类型 ==============


class SpawnRule(Enum):
    """生成规则 - 物品如何参与随机生成

    EQUIPMENT: 按装备规则生成（走 scr_find_weapon_params / scr_find_weapon）
    ITEM: 按道具规则生成（走 scr_weapon_array_get_consum）
    NONE: 不参与该场景的随机生成
    """
    EQUIPMENT = "equipment"
    ITEM = "item"
    NONE = "none"


# 保留旧的 SpawnMode 别名用于数据迁移
class SpawnMode(Enum):
    """已废弃，使用 SpawnRule 代替"""
    EQUIPMENT = "equipment"
    NON_EQUIPMENT = "non_equipment"


class EquipmentMode(Enum):
    """装备形态

    NONE: 普通背包物品
    WEAPON: 武器 - 可装备到手部，具有伤害和武器属性
    ARMOR: 护甲 - 可装备到身体槽位，提供防御和属性加成（含饰品）
    CHARM: 护符 - 存在于背包即可生效的被动效果（类似暗黑2的charm）
    """
    NONE = "none"
    WEAPON = "weapon"
    ARMOR = "armor"
    CHARM = "charm"  # 原 passive


class TriggerMode(Enum):
    """触发效果模式 - 使用物品时触发什么

    NONE: 无触发效果
    EFFECT: 应用效果 - 像喝药水那样应用一组属性变化
    SKILL: 技能释放 - 释放指定技能
    """
    NONE = "none"
    EFFECT = "effect"  # 原 consumable
    SKILL = "skill"


class ChargeMode(Enum):
    """使用次数模式

    LIMITED: 有限次数 - 每次使用减少1次
    UNLIMITED: 无限次数 - 次数永不减少
    """
    LIMITED = "limited"  # 原 normal
    UNLIMITED = "unlimited"


# ============== 辅助函数 ==============


def get_relative_path(path: str, project_dir: str) -> str:
    """将绝对路径转换为相对于项目目录的路径"""
    return os.path.relpath(path, project_dir) if path else ""


def resolve_path(path: str, project_dir: str) -> str:
    """将相对路径转换为绝对路径"""
    return os.path.normpath(os.path.join(project_dir, path)) if path else ""


# ============== 本地化数据 ==============


@dataclass
class ItemLocalization:
    """物品本地化数据，格式: {"Chinese": {"name": "...", "description": "..."}, ...}"""

    languages: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def _ensure_lang(self, lang: str) -> Dict[str, str]:
        return self.languages.setdefault(lang, {"name": "", "description": ""})

    def get_name(self, lang: str) -> str:
        return self.languages.get(lang, {}).get("name", "")

    def set_name(self, lang: str, value: str) -> None:
        self._ensure_lang(lang)["name"] = value

    def get_description(self, lang: str) -> str:
        return self.languages.get(lang, {}).get("description", "")

    def set_description(self, lang: str, value: str) -> None:
        self._ensure_lang(lang)["description"] = value

    def has_language(self, lang: str) -> bool:
        return lang in self.languages

    def get_display_name(self) -> str:
        """获取用于显示的名称（优先主语言，其次英语）"""
        return self.get_name(PRIMARY_LANGUAGE) or self.get_name("English") or "未命名"


# ============== 贴图数据 ==============


@dataclass
class ItemTextures:
    """物品贴图数据（武器/护甲通用）

    游戏姿势系统：
    - 姿势0: 站立-单手（单手武器/盾牌/长杆）
    - 姿势1: 站立-双手（其他双手武器）
    - 姿势2: 休息状态

    s_char_{id} 序列的含义因装备类型而异：

    【武器/盾牌】character 字段存储动画帧序列
    - 长度为 1：静态贴图
    - 长度 > 1：动画帧序列
    - 输出：s_char_{id}.png 或 s_char_{id}_0.png, s_char_{id}_1.png, ...

    【头/身/手/腿/背装备】需要为站立和休息状态各准备贴图
    - character[0]: 站立姿势0 (必须) → 输出 s_char_{id}_0.png
    - character_standing1: 站立姿势1 (可选) → 输出 s_char_{id}_1.png
    - character_rest: 休息姿势 (必须) → 输出 s_char3_{id}.png

    注：游戏用 s_char 帧序列的第0/1帧存储站立两姿势，导致这些装备无法支持动画
    """

    # 武器/盾牌：动画帧序列；多姿势装备：站立姿势0贴图
    character: List[str] = field(default_factory=list)
    # 多姿势装备专用：站立姿势1 (可选，未设置时游戏可能回退到姿势0)
    character_standing1: str = ""
    # 多姿势装备专用：休息姿势 (必须)
    character_rest: str = ""
    # 左手贴图 (仅武器/盾牌)
    character_left: List[str] = field(default_factory=list)
    # 物品栏贴图列表
    inventory: List[str] = field(default_factory=list)
    # 战利品贴图
    loot: List[str] = field(default_factory=list)

    # 偏移设置 - 武器/盾牌/站立姿势0
    offset_x: int = 0  # 水平偏移 (右手/默认/站立0)
    offset_y: int = 0  # 垂直偏移 (右手/默认/站立0)
    offset_x_left: int = 0  # 水平偏移 (左手)
    offset_y_left: int = 0  # 垂直偏移 (左手)

    # 多姿势装备专用偏移 - 站立姿势1
    offset_x_standing1: int = 0
    offset_y_standing1: int = 0
    # 多姿势装备专用偏移 - 休息姿势
    offset_x_rest: int = 0
    offset_y_rest: int = 0

    # ====== 女性版贴图（多姿势装备专用，可选） ======
    # 游戏会检查是否存在女性版贴图，若不存在则使用默认/男性版
    # 女性版贴图各姿势独立设置，可只为部分姿势提供女性版

    # 女性版站立姿势0
    character_female: str = ""
    offset_x_female: int = 0
    offset_y_female: int = 0

    # 女性版站立姿势1（仅当男性版站立姿势1已设置时才允许设置）
    character_standing1_female: str = ""
    offset_x_standing1_female: int = 0
    offset_y_standing1_female: int = 0

    # 女性版休息姿势
    character_rest_female: str = ""
    offset_x_rest_female: int = 0
    offset_y_rest_female: int = 0

    # 战利品贴图动画设置
    loot_fps: float = 10.0
    loot_use_relative_speed: bool = False

    def clear_left(self):
        """清理左手贴图数据"""
        self.character_left.clear()
        self.offset_x_left = 0
        self.offset_y_left = 0

    def clear_char(self):
        """清理角色贴图数据"""
        self.character.clear()
        self.character_standing1 = ""
        self.character_rest = ""
        self.offset_x = 0
        self.offset_y = 0
        self.offset_x_standing1 = 0
        self.offset_y_standing1 = 0
        self.offset_x_rest = 0
        self.offset_y_rest = 0
        # 清理女性版贴图
        self.character_female = ""
        self.offset_x_female = 0
        self.offset_y_female = 0
        self.character_standing1_female = ""
        self.offset_x_standing1_female = 0
        self.offset_y_standing1_female = 0
        self.character_rest_female = ""
        self.offset_x_rest_female = 0
        self.offset_y_rest_female = 0

    def has_char(self) -> bool:
        """是否有角色贴图 (武器动画/装备站立姿势0)"""
        return len(self.character) > 0

    def has_standing1(self) -> bool:
        """是否有站立姿势1贴图 (仅多姿势装备)"""
        return bool(self.character_standing1)

    def has_rest(self) -> bool:
        """是否有休息姿势贴图 (仅多姿势装备)"""
        return bool(self.character_rest)

    def has_female(self) -> bool:
        """是否有任何女性版贴图"""
        return bool(
            self.character_female
            or self.character_standing1_female
            or self.character_rest_female
        )

    def has_female_standing0(self) -> bool:
        """是否有女性版站立姿势0贴图"""
        return bool(self.character_female)

    def has_female_standing1(self) -> bool:
        """是否有女性版站立姿势1贴图"""
        return bool(self.character_standing1_female)

    def has_female_rest(self) -> bool:
        """是否有女性版休息姿势贴图"""
        return bool(self.character_rest_female)

    def clear_female_standing0(self):
        """清理女性版站立姿势0贴图"""
        self.character_female = ""
        self.offset_x_female = 0
        self.offset_y_female = 0

    def clear_female_standing1(self):
        """清理女性版站立姿势1贴图"""
        self.character_standing1_female = ""
        self.offset_x_standing1_female = 0
        self.offset_y_standing1_female = 0

    def clear_female_rest(self):
        """清理女性版休息姿势贴图"""
        self.character_rest_female = ""
        self.offset_x_rest_female = 0
        self.offset_y_rest_female = 0

    def has_char_left(self) -> bool:
        """是否有左手贴图"""
        return len(self.character_left) > 0

    def has_loot(self) -> bool:
        """是否有战利品贴图"""
        return len(self.loot) > 0

    def is_animated(self, field_name: str) -> bool:
        """指定字段是否为动画"""
        data = getattr(self, field_name, [])
        return len(data) > 1


# ============== 物品基类 ==============


@dataclass
class Item:
    """物品基类 - 武器和护甲的公共数据字段"""

    name: str = ""  # 系统ID
    tier: str = "Tier2"
    slot: str = ""  # 由子类设置默认值
    rarity: str = "Common"
    mat: str = ""  # 由子类设置默认值
    tags: str = "aldor"
    price: int = 100
    markup: int = 1  # 固定为 1
    max_duration: int = 100

    # 属性字段
    attributes: Dict[str, Any] = field(default_factory=dict)

    # 本地化
    localization: ItemLocalization = field(default_factory=ItemLocalization)

    # 贴图
    textures: ItemTextures = field(default_factory=ItemTextures)

    # 布尔属性
    fireproof: bool = False
    no_drop: bool = False

    @property
    def id(self) -> str:
        """根据name自动生成id"""
        return self.name.lower().replace(" ", "").replace("'", "")

    @classmethod
    def get_type_key(cls) -> str:
        """返回物品类型键（子类必须重写）"""
        raise NotImplementedError

    @classmethod
    def get_config(cls) -> dict:
        """返回物品类型配置"""
        return ITEM_TYPE_CONFIG[cls.get_type_key()]

    def needs_char_texture(self) -> bool:
        """判断是否需要角色贴图（子类重写）"""
        return True

    def needs_left_texture(self) -> bool:
        """判断是否需要左手贴图（子类重写）"""
        return False


# ============== 护甲类 ==============


@dataclass
class Armor(Item):
    """护甲/装备数据类"""

    slot: str = "Head"
    mat: str = "leather"
    armor_class: str = "Light"

    # 拆解材料 (护甲特有)
    fragments: Dict[str, int] = field(default_factory=dict)

    # 护甲特有布尔属性
    is_open: bool = False

    @classmethod
    def get_type_key(cls) -> str:
        return "armor"

    @property
    def hook(self) -> str:
        """根据slot自动获取hook"""
        return ARMOR_SLOT_TO_HOOK.get(self.slot, "HELMETS")

    def needs_char_texture(self) -> bool:
        return self.slot in ARMOR_SLOTS_WITH_CHAR_PREVIEW

    def needs_left_texture(self) -> bool:
        return self.slot == "shield"

    def needs_multi_pose_textures(self) -> bool:
        """判断是否需要多姿势穿戴贴图 (头/身/手/腿/背)"""
        return self.slot in ARMOR_SLOTS_MULTI_POSE

    def needs_pose2_texture(self) -> bool:
        """判断是否需要姿势2贴图"""
        return self.needs_multi_pose_textures()


# ============== 武器类 ==============


@dataclass
class Weapon(Item):
    """武器数据类"""

    slot: str = "sword"
    mat: str = "metal"

    # 武器特有字段
    rng: int = 1  # 射程，弓弩专用

    @classmethod
    def get_type_key(cls) -> str:
        return "weapon"

    def needs_char_texture(self) -> bool:
        return True

    def needs_left_texture(self) -> bool:
        return self.slot in LEFT_HAND_SLOTS


# ============== 混合物品类 ==============

# 品质常量 <- named
QUALITY_COMMON = 1
QUALITY_UNIQUE = 6
QUALITY_ARTIFACT = 7


@dataclass
class HybridItem:
    """混合物品数据类 - 灵活的模块化物品类型

    混合物品由两个独立维度组合而成：

    1. 装备形态 (equipment_mode: EquipmentMode)：
       - NONE：普通背包物品
       - WEAPON：武器 - 可装备到手部，具有伤害和武器属性
       - ARMOR：护甲 - 可装备到身体槽位，提供防御和属性加成（含饰品）
       - CHARM：护符 - 存在于背包即可生效的被动效果

    2. 触发效果模式 (trigger_mode: TriggerMode)：
       - NONE：无触发效果
       - EFFECT：应用效果 - 像喝药水那样应用一组属性变化
       - SKILL：技能释放 - 释放指定技能

    这种组合允许创建多种物品类型，如可释放技能的武器、带消耗品效果的护甲等。
    """

    # ====== 基础信息 ======
    id: str = ""  # 系统ID (直接设置)

    # 本地化
    localization: ItemLocalization = field(default_factory=ItemLocalization)

    # 父对象（决定基本行为）
    parent_object: str = "o_inv_consum"

    # ====== 品质 ======
    quality: int = 1  # 1=普通, 6=独特, 7=文物

    # ====== 槽位与装备 ======
    # ====== 装备设置 ======
    # equipable 已删除，由 equipment_mode 计算
    slot: str = "heal"  # hand/Head/Chest/Arms/Legs/Waist/Back/Ring/Amulet/heal
    # hands 已删除，由 weapon_type 计算

    # ====== 装备形态 ======
    equipment_mode: EquipmentMode = EquipmentMode.NONE

    # ====== 武器设置（仅 equipment_mode="weapon" 时使用）======
    weapon_type: str = "sword"  # 武器类型
    # damage_type 和 primary_damage 字段已删除，伤害通过 attributes 设置
    material: str = "metal"  # 材质（武器和护甲共用）
    tier: int = 1  # 等级 1-5
    balance: int = 2  # 平衡性
    # weapon_range 字段已删除，使用 attributes["Range"] 代替

    # ====== 护甲设置（仅 equipment_mode="armor" 时使用）======
    armor_type: str = "Head"  # 护甲类型
    # armor_material 已删除，使用 material 代替
    # armor_class 已删除，由 weight 计算
    # defense 字段已删除，使用 attributes["DEF"] 代替

    # ====== 触发效果 ======
    trigger_mode: TriggerMode = TriggerMode.NONE

    # ====== 技能设置（仅 trigger_mode=SKILL 时使用）======
    skill_object: str = ""  # 技能对象名称，如 "o_skill_fire_barrage"

    # ====== 注释：has_passive 字段已删除，使用 equipment_mode == CHARM 代替 ======

    # ====== 使用次数 ======
    # has_charges 改为计算属性（见下方 property）
    charge: int = 1  # 使用次数（仅 charge_mode="normal" 时使用）
    draw_charges: bool = False  # 是否绘制次数条

    # ====== 使用次数模式 ======
    charge_mode: ChargeMode = ChargeMode.LIMITED

    # ====== 使用次数恢复 ======
    has_charge_recovery: bool = False  # 是否启用使用次数恢复
    charge_recovery_interval: int = 10  # 恢复间隔（回合数）

    # ====== 耐久系统 ======
    # has_durability 改为计算属性（见下方 property）
    # duration_init 已删除，初始耐久固定等于最大耐久
    duration_max: int = 100  # 最大耐久
    wear_per_use: int = 0  # 每次使用磨损耐久百分比（linked 模式下也用于计算 max_charge）
    destroy_on_durability_zero: bool = True  # 耐久耗尽时是否删除物品
    delete_on_charge_zero: bool = False  # 使用次数耗尽后是否删除（仅当有次数、无耐久、非文物时生效）
    durability_affects_stats: bool = False  # 耐久是否影响属性

    # ====== 价格与音效 ======
    base_price: int = 100  # 基础价格
    drop_sound: int = 911  # 放下音效ID
    pickup_sound: int = 907  # 拾取音效ID

    # ====== 分类元数据（用于 drop/shop 随机选取）======
    cat: str = ""  # 主分类（单选）
    subcats: List[str] = field(default_factory=list)  # 子分类（多选）

    # ====== Tags 设置 ======
    exclude_from_random: bool = True  # True 时添加 "special" 标签排除随机生成
    quality_tag: str = ""  # 品质 tag: common/uncommon/rare/unique/""
    dungeon_tag: str = ""  # 地牢 tag: crypt/catacombs/bastion/""
    country_tag: str = ""  # 国家/地区 tag: aldor/nistra/skadia/fjall/elven/maen/"" (互斥)
    extra_tags: List[str] = field(default_factory=list)  # 其他 tags（多选）

    # ====== 生成规则配置 ======
    # 分别控制容器、商店、击杀三个场景的生成规则
    # EQUIPMENT: 按装备规则生成（被 tier/material/tags 筛选）
    # ITEM: 按道具规则生成（被 cat/tags 筛选，仅容器和商店支持）
    # NONE: 不参与该场景的随机生成
    container_spawn: SpawnRule = SpawnRule.NONE  # 容器生成规则
    shop_spawn: SpawnRule = SpawnRule.NONE       # 商店生成规则

    # ====== 其他元数据 ======
    rarity: str = ""  # 稀有度（由品质自动决定）
    weight: str = "Light"  # Light/Medium/VeryLight/Heavy（护甲由 armor_class 自动决定）

    # ====== 消耗品特殊属性 ======
    poison_duration: int = 0  # 中毒持续时间（仅当 Poisoning_Chance > 0 时有效）

    # ====== 属性 ======
    attributes: Dict[str, Any] = field(default_factory=dict)
    consumable_attributes: Dict[str, Any] = field(default_factory=dict)

    # ====== 拆解碎片 (护甲/饰品用) ======
    fragments: Dict[str, int] = field(default_factory=dict)

    # ====== 贴图 ======
    textures: ItemTextures = field(default_factory=ItemTextures)

    # id 现在是直接字段，不再是计算属性

    @classmethod
    def get_type_key(cls) -> str:
        return "hybrid"

    @classmethod
    def get_config(cls) -> dict:
        """返回物品类型配置"""
        return ITEM_TYPE_CONFIG[cls.get_type_key()]

    def needs_char_texture(self) -> bool:
        """判断是否需要角色/穿戴贴图"""
        # 手持槽位或可装备的身体槽位需要角色贴图
        if self.slot == "hand" and self.equipable:
            return True
        if self.slot in ["Head", "Chest", "Arms", "Legs", "Back"] and self.equipable:
            return True
        return False

    def needs_left_texture(self) -> bool:
        """判断是否需要左手贴图"""
        if self.slot == "hand" and self.equipable and self.hands == 1:
            # 单手武器需要左手贴图
            return self.weapon_type in ["sword", "axe", "mace", "dagger"]
        return False

    def needs_multi_pose_textures(self) -> bool:
        """判断是否需要多姿势穿戴贴图 (头/身/手/腿/背)"""
        return self.init_armor_stats and self.slot in ARMOR_SLOTS_MULTI_POSE


    def get_quality_label(self) -> str:
        """获取品质显示文本"""
        from constants import HYBRID_QUALITY_LABELS
        return HYBRID_QUALITY_LABELS.get(self.quality, "普通")

    def get_loot_parent(self) -> str:
        """获取 Loot 对象的父类"""
        # if self.is_weapon:
        #     return "o_weapon_loot"
        return "o_consument_loot"

    # ====== 双手武器类型 ======
    TWO_HAND_WEAPONS = {"2hsword", "2haxe", "2hmace", "2hStaff", "bow", "crossbow", "spear"}

    # ====== Weight 到 ArmorClass 的映射 ======
    WEIGHT_TO_ARMOR_CLASS = {"Light": "Light", "Medium": "Medium", "Heavy": "Heavy", "VeryLight": "Light"}

    # ====== 装备相关计算属性 ======
    @property
    def equipable(self) -> bool:
        """是否可装备（武器和护甲形态可装备）"""
        return self.equipment_mode in (EquipmentMode.WEAPON, EquipmentMode.ARMOR)

    @property
    def hands(self) -> int:
        """手数（1=单手, 2=双手）

        - 武器模式: 由 weapon_type 决定（双手武器返回 2）
        - 护甲模式: 始终返回 1（包括盾牌，因为盾牌是 armor 模式的单手装备）
        - 其他模式: 返回 1
        """
        if self.equipment_mode == EquipmentMode.WEAPON and self.weapon_type in self.TWO_HAND_WEAPONS:
            return 2
        return 1

    @property
    def is_weapon(self) -> bool:
        """是否标记为 is_weapon（武器和护甲类均为 true）

        注意：此属性名称与语义不完全匹配。在游戏中，护甲类物品（o_inv_slot 子类）
        也设置 is_weapon=true，这是游戏机制决定的。
        """
        return self.equipment_mode in (EquipmentMode.WEAPON, EquipmentMode.ARMOR)

    @property
    def armor_class(self) -> str:
        """护甲类别（Light/Medium/Heavy）- 由 weight 决定"""
        return self.WEIGHT_TO_ARMOR_CLASS.get(self.weight, "Light")

    # ====== 装备形态计算属性 ======
    @property
    def init_weapon_stats(self) -> bool:
        """是否初始化武器数值"""
        return self.equipment_mode == EquipmentMode.WEAPON

    @property
    def init_armor_stats(self) -> bool:
        """是否初始化护甲数值"""
        return self.equipment_mode == EquipmentMode.ARMOR

    @property
    def has_passive(self) -> bool:
        """是否有护符效果（装备形态为护符时）"""
        return self.equipment_mode == EquipmentMode.CHARM

    @property
    def has_durability(self) -> bool:
        """品质非文物且物品类型为武器/护甲时自动有耐久"""
        return self.quality != QUALITY_ARTIFACT and (self.init_weapon_stats or self.init_armor_stats)  # <- use constant

    @property
    def has_charges(self) -> bool:
        """触发效果模式非'无'时自动有使用次数"""
        return self.trigger_mode != TriggerMode.NONE

    @property
    def effective_charge(self) -> int:
        """实际最大使用次数（根据 charge_mode 计算）"""
        if self.charge_mode == ChargeMode.UNLIMITED:
            return 1
        else:  # LIMITED
            return self.charge

    def _build_tags_list(self, prefix: list = None) -> list:  # <- extracted helper
        """构建 tags 列表（内部方法）"""
        parts = list(prefix) if prefix else []
        if self.quality_tag:
            parts.append(self.quality_tag)
        if self.dungeon_tag:
            parts.append(self.dungeon_tag)
        if self.country_tag:
            parts.append(self.country_tag)
        parts.extend(self.extra_tags)
        return parts

    @property
    def effective_tags(self) -> str:
        """组合所有 tags 为空格分隔的字符串

        排除随机生成时：在现有标签前添加 'special' 前缀
        """
        prefix = ["special"] if self.exclude_from_random else []
        return " ".join(self._build_tags_list(prefix))

    @property
    def tags_tuple(self) -> tuple:
        """获取 tags 元组（用于预览匹配等）

        排除随机生成时：包含 'special' 前缀
        """
        prefix = ["special"] if self.exclude_from_random else []
        return tuple(self._build_tags_list(prefix))

    @property
    def has_equipment_spawn(self) -> bool:
        """是否有任何场景使用装备规则"""
        return SpawnRule.EQUIPMENT in (self.container_spawn, self.shop_spawn)

    @property
    def has_item_spawn(self) -> bool:
        """是否有任何场景使用道具规则"""
        return SpawnRule.ITEM in (self.container_spawn, self.shop_spawn)

    @property
    def needs_registration(self) -> bool:
        """是否需要注册到混合物品系统

        需要注册的情况：
        1. 有装备规则 (has_equipment_spawn)
        2. 商店或容器规则不是纯 ITEM (即包含 NONE 或 EQUIPMENT 或自定义规则)
           注：如果两处都是 ITEM，则走游戏原生道具生成系统，不需要注册
        """
        if self.exclude_from_random:
            return False

        if self.has_equipment_spawn:
            return True

        # Register if any spawn rule is NON-STANDARD (i.e., not ITEM)
        # If both are ITEM, we don't need registration (handled by standard system)
        return self.shop_spawn != SpawnRule.ITEM or self.container_spawn != SpawnRule.ITEM




# ============== 验证函数 ==============


def validate_item(
    item: Item, project=None, include_warnings: bool = False
) -> List[str]:
    """验证物品数据的完整性"""
    config = item.get_config()
    type_name = config["type_name"]
    slot_labels = config["slot_labels"]
    slot_name = slot_labels.get(item.slot, item.slot)

    errors = []
    item.name = item.name.strip()

    # ID 格式检查
    if not item.name:
        errors.append(f"{type_name}系统ID不能为空")
    elif not re.match(r"^[A-Za-z][A-Za-z0-9 ]*$", item.name):
        errors.append(
            f"{type_name}系统ID格式错误: 必须以字母开头，只能包含字母、数字和空格"
        )

    # ID 唯一性检查
    if project:
        item_list = project.weapons if isinstance(item, Weapon) else project.armors
        if sum(1 for i in item_list if i.id == item.id) > 1:
            errors.append(
                f"{type_name}系统ID '{item.name}' (ID: {item.id}) 重复，请确保唯一"
            )

    # 贴图检查
    if item.needs_char_texture() and not item.textures.has_char():
        errors.append(f"槽位为 '{slot_name}' 的{type_name}必须提供穿戴/手持状态贴图")
    if item.needs_left_texture() and not item.textures.has_char_left():
        errors.append(f"槽位为 '{slot_name}' 的{type_name}必须提供左手贴图")

    # 多姿势装备贴图检查（头/身/手/腿/背需要休息姿势贴图）
    if isinstance(item, Armor) and item.needs_multi_pose_textures():
        if not item.textures.has_rest():
            errors.append(f"槽位为 '{slot_name}' 的装备必须提供休息姿势贴图")

    if not item.textures.has_loot():
        errors.append("必须提供战利品贴图")
    if not item.textures.inventory:
        errors.append("至少需要提供一张常规贴图")

    # 过滤 WARNING
    if not include_warnings:
        errors = [e for e in errors if not e.startswith("WARNING:")]

    if not errors:
        return []

    # 格式化输出
    formatted = [f"{type_name} {item.name} ({item.id}):"]
    formatted.extend(f"  • {err}" for err in errors)
    return formatted


def validate_hybrid_item(
    item: HybridItem, project=None, include_warnings: bool = False
) -> List[str]:
    """验证混合物品数据的完整性"""
    errors = []
    item.id = item.id.strip()

    # ID 格式检查
    if not item.id:
        errors.append("混合物品ID不能为空")
    elif not re.match(r"^[a-z][a-z0-9_]*$", item.id):
        errors.append(
            "混合物品ID格式错误: 必须以小写字母开头，只能包含小写字母、数字和下划线"
        )

    # ID 唯一性检查
    if project:
        all_ids = []
        for w in project.weapons:
            all_ids.append(w.id)
        for a in project.armors:
            all_ids.append(a.id)
        for h in project.hybrid_items:
            all_ids.append(h.id)
        if all_ids.count(item.id) > 1:
            errors.append(
                f"混合物品ID '{item.id}' 与其他物品重复，请确保唯一"
            )

    # 槽位与装备一致性检查
    if item.equipable and item.slot == "heal":
        errors.append("可装备物品的槽位不能是 'heal'（背包道具）")

    if not item.equipable and item.slot != "heal":
        errors.append("WARNING: 不可装备物品的槽位应为 'heal'（背包道具）")

    # 武器属性初始化检查
    if item.init_weapon_stats:
        if not item.equipable:
            errors.append("WARNING: 初始化武器属性通常需要物品可装备")
        if item.slot != "hand":
            errors.append("WARNING: 武器类型物品的槽位通常应为 'hand'")
        # 检查 attributes 中是否有伤害值
        from constants import DAMAGE_ATTRIBUTES
        has_damage = any(item.attributes.get(attr, 0) > 0 for attr in DAMAGE_ATTRIBUTES)
        if not has_damage:
            errors.append("武器应在属性中设置至少一种伤害类型")

    # 护甲属性初始化检查
    if item.init_armor_stats:
        if not item.equipable:
            errors.append("WARNING: 初始化护甲属性通常需要物品可装备")
        if item.slot == "hand" or item.slot == "heal":
            errors.append("WARNING: 护甲类型物品的槽位不应为 'hand' 或 'heal'")

    # 互斥检查已不再需要（由 equipment_mode 枚举保证）

    # 技能检查
    if item.trigger_mode == TriggerMode.SKILL and not item.skill_object:
        errors.append("WARNING: 启用了技能触发模式但未设置技能对象")

    # charge_mode 检查
    if item.charge_mode == ChargeMode.LIMITED:
        if item.has_charges and item.charge <= 0:
            errors.append("使用次数应大于0")

    # 耐久检查
    if item.has_durability:
        if item.duration_max <= 0:
            errors.append("耐久度应大于0")

    # 贴图检查
    if not item.textures.has_loot():
        errors.append("必须提供战利品贴图")
    if not item.textures.inventory:
        errors.append("至少需要提供一张常规贴图")

    # 角色贴图检查
    if item.needs_char_texture() and not item.textures.has_char():
        slot_labels = HYBRID_SLOT_LABELS
        slot_name = slot_labels.get(item.slot, item.slot)
        errors.append(f"槽位为 '{slot_name}' 的物品必须提供穿戴/手持状态贴图")

    # 过滤 WARNING
    if not include_warnings:
        errors = [e for e in errors if not e.startswith("WARNING:")]

    if not errors:
        return []

    # 格式化输出
    formatted = [f"混合物品 {item.id}:"]
    formatted.extend(f"  • {err}" for err in errors)
    return formatted


# ============== 项目类 ==============


@dataclass
class ModProject:
    """模组项目数据类"""

    name: str = "我的新模组"
    code_name: str = "MyNewMod"
    author: str = ""
    description: str = "使用 Stoneshard Mod Editor 生成"
    version: str = "1.0.0"
    target_version: str = "0.9.3.13"
    weapons: List[Weapon] = field(default_factory=list)
    armors: List[Armor] = field(default_factory=list)
    hybrid_items: List[HybridItem] = field(default_factory=list)
    file_path: str = ""

    def validate(self) -> List[str]:
        errors = []
        if not self.code_name.strip():
            errors.append("模组代号不能为空")
        elif not re.match(r"^[A-Za-z][A-Za-z0-9]*$", self.code_name.strip()):
            errors.append("模组代号只能包含英文字母和数字，且不能以数字开头")
        return errors

    def save(self, file_path: str = None):
        """保存项目到文件夹结构"""
        if file_path:
            if not file_path.endswith("project.json"):
                if os.path.isdir(file_path):
                    file_path = os.path.join(file_path, "project.json")
                else:
                    file_path = os.path.join(os.path.dirname(file_path), "project.json")
            self.file_path = file_path

        if not self.file_path:
            return False

        project_dir = os.path.dirname(self.file_path)
        assets_dir = os.path.join(project_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        data = {
            "name": self.name,
            "code_name": self.code_name,
            "author": self.author,
            "description": self.description,
            "version": self.version,
            "target_version": self.target_version,
            "weapons": [],
            "armors": [],
            "hybrid_items": [],
        }

        for weapon in self.weapons:
            weapon.name = weapon.name.strip()
            data["weapons"].append(self._serialize_item(weapon, project_dir))

        for armor in self.armors:
            armor.name = armor.name.strip()
            data["armors"].append(self._serialize_item(armor, project_dir))

        for hybrid in self.hybrid_items:
            hybrid.id = hybrid.id.strip()
            data["hybrid_items"].append(self._serialize_hybrid_item(hybrid, project_dir))

        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True

    def _serialize_item(self, item: Item, project_dir: str) -> dict:
        """序列化物品数据为字典"""
        item_data = {
            "name": item.name,
            "tier": item.tier,
            "slot": item.slot,
            "rarity": item.rarity,
            "mat": item.mat,
            "tags": item.tags,
            "price": item.price,
            "markup": item.markup,
            "max_duration": item.max_duration,
            "attributes": item.attributes,
            "fireproof": item.fireproof,
            "no_drop": item.no_drop,
            "localization": item.localization.languages,
            "textures": self._serialize_textures(item.textures, project_dir),
        }
        if isinstance(item, Weapon):
            item_data["rng"] = item.rng
        elif isinstance(item, Armor):
            item_data["armor_class"] = item.armor_class
            item_data["fragments"] = item.fragments
            item_data["is_open"] = item.is_open
        return item_data

    def _serialize_hybrid_item(self, item: HybridItem, project_dir: str) -> dict:
        """序列化混合物品数据为字典"""
        return {
            "id": item.id,
            "localization": item.localization.languages,
            "parent_object": item.parent_object,
            "quality": item.quality,
            # equipable, hands, mark_as_weapon, armor_class 现在是计算属性
            "slot": item.slot,
            "equipment_mode": item.equipment_mode.value,
            "weapon_type": item.weapon_type,
            # damage_type 和 primary_damage 字段已删除，伤害通过 attributes 设置
            "material": item.material,  # 武器和护甲共用
            "tier": item.tier,
            "balance": item.balance,
            # weapon_range 字段已删除，使用 attributes["Range"] 代替
            "armor_type": item.armor_type,
            # armor_material 已删除，使用 material 代替
            # defense 字段已删除，使用 attributes["DEF"] 代替
            "trigger_mode": item.trigger_mode.value,
            "skill_object": item.skill_object,
            # init_weapon_stats, init_armor_stats, has_passive 现在是计算属性
            # has_charges 现在是计算属性，不需要保存
            "charge": item.charge,
            "draw_charges": item.draw_charges,
            "charge_mode": item.charge_mode.value,
            "has_charge_recovery": item.has_charge_recovery,
            "charge_recovery_interval": item.charge_recovery_interval,
            # has_durability 现在是计算属性，不需要保存
            # duration_init 已删除，初始耐久固定等于最大耐久
            "duration_max": item.duration_max,
            "wear_per_use": item.wear_per_use,
            "destroy_on_durability_zero": item.destroy_on_durability_zero,
            "delete_on_charge_zero": item.delete_on_charge_zero,
            "durability_affects_stats": item.durability_affects_stats,
            "base_price": item.base_price,
            "drop_sound": item.drop_sound,
            "pickup_sound": item.pickup_sound,
            # 分类元数据（新字段）
            "cat": item.cat,
            "subcats": item.subcats,
            "exclude_from_random": item.exclude_from_random,
            "quality_tag": item.quality_tag,
            "dungeon_tag": item.dungeon_tag,
            "country_tag": item.country_tag,
            "extra_tags": item.extra_tags,
            # 其他元数据
            "rarity": item.rarity,
            "weight": item.weight,
            "poison_duration": item.poison_duration,
            "attributes": item.attributes,
            "consumable_attributes": item.consumable_attributes,
            "textures": self._serialize_textures(item.textures, project_dir),
            # 生成规则配置
            "container_spawn": item.container_spawn.value,
            "shop_spawn": item.shop_spawn.value,
        }


    def _serialize_textures(self, textures: ItemTextures, project_dir: str) -> dict:
        """序列化贴图数据"""
        return {
            "character": [
                get_relative_path(p, project_dir) for p in textures.character
            ],
            # 多姿势装备专用字段
            "character_standing1": get_relative_path(
                textures.character_standing1, project_dir
            ),
            "character_rest": get_relative_path(textures.character_rest, project_dir),
            "character_left": [
                get_relative_path(p, project_dir) for p in textures.character_left
            ],
            "inventory": [
                get_relative_path(p, project_dir) for p in textures.inventory
            ],
            "loot": [get_relative_path(p, project_dir) for p in textures.loot],
            # 偏移设置
            "offset_x": textures.offset_x,
            "offset_y": textures.offset_y,
            "offset_x_left": textures.offset_x_left,
            "offset_y_left": textures.offset_y_left,
            # 多姿势装备偏移
            "offset_x_standing1": textures.offset_x_standing1,
            "offset_y_standing1": textures.offset_y_standing1,
            "offset_x_rest": textures.offset_x_rest,
            "offset_y_rest": textures.offset_y_rest,
            # 女性版贴图（多姿势装备专用）
            "character_female": get_relative_path(
                textures.character_female, project_dir
            ),
            "offset_x_female": textures.offset_x_female,
            "offset_y_female": textures.offset_y_female,
            "character_standing1_female": get_relative_path(
                textures.character_standing1_female, project_dir
            ),
            "offset_x_standing1_female": textures.offset_x_standing1_female,
            "offset_y_standing1_female": textures.offset_y_standing1_female,
            "character_rest_female": get_relative_path(
                textures.character_rest_female, project_dir
            ),
            "offset_x_rest_female": textures.offset_x_rest_female,
            "offset_y_rest_female": textures.offset_y_rest_female,
            # 动画设置
            "loot_fps": round(textures.loot_fps, 3),
            "loot_use_relative_speed": textures.loot_use_relative_speed,
        }

    def _deserialize_textures(
        self, tex_data: dict, project_dir: str
    ) -> ItemTextures:
        """反序列化贴图数据"""

        def to_path_list(val):
            """将列表中的相对路径转换为绝对路径"""
            if isinstance(val, list):
                return [resolve_path(p, project_dir) for p in val if p]
            return []

        def to_path(val):
            """将相对路径转换为绝对路径"""
            if val:
                return resolve_path(val, project_dir)
            return ""

        return ItemTextures(
            character=to_path_list(tex_data.get("character", [])),
            character_standing1=to_path(tex_data.get("character_standing1", "")),
            character_rest=to_path(tex_data.get("character_rest", "")),
            character_left=to_path_list(tex_data.get("character_left", [])),
            inventory=to_path_list(tex_data.get("inventory", [])),
            loot=to_path_list(tex_data.get("loot", [])),
            # 偏移设置
            offset_x=tex_data.get("offset_x", 0),
            offset_y=tex_data.get("offset_y", 0),
            offset_x_left=tex_data.get("offset_x_left", 0),
            offset_y_left=tex_data.get("offset_y_left", 0),
            # 多姿势装备偏移
            offset_x_standing1=tex_data.get("offset_x_standing1", 0),
            offset_y_standing1=tex_data.get("offset_y_standing1", 0),
            offset_x_rest=tex_data.get("offset_x_rest", 0),
            offset_y_rest=tex_data.get("offset_y_rest", 0),
            # 女性版贴图
            character_female=to_path(tex_data.get("character_female", "")),
            offset_x_female=tex_data.get("offset_x_female", 0),
            offset_y_female=tex_data.get("offset_y_female", 0),
            character_standing1_female=to_path(tex_data.get("character_standing1_female", "")),
            offset_x_standing1_female=tex_data.get("offset_x_standing1_female", 0),
            offset_y_standing1_female=tex_data.get("offset_y_standing1_female", 0),
            character_rest_female=to_path(tex_data.get("character_rest_female", "")),
            offset_x_rest_female=tex_data.get("offset_x_rest_female", 0),
            offset_y_rest_female=tex_data.get("offset_y_rest_female", 0),
            # 动画设置
            loot_fps=round(tex_data.get("loot_fps", 10), 3),
            loot_use_relative_speed=tex_data.get("loot_use_relative_speed", False),
        )


    def _deserialize_item(
        self, item_data: dict, project_dir: str, is_weapon: bool
    ) -> Item:
        """反序列化物品数据"""
        slot = item_data.get("slot", "sword" if is_weapon else "Head")

        common_kwargs = {
            "name": item_data.get("name", ""),
            "tier": item_data.get("tier", "Tier2"),
            "slot": slot,
            "rarity": item_data.get("rarity", "Common"),
            "mat": item_data.get("mat", "metal" if is_weapon else "leather"),
            "tags": item_data.get("tags", "aldor"),
            "price": item_data.get("price", 100),
            "max_duration": item_data.get("max_duration", 100),
            "attributes": item_data.get("attributes", {}),
        }

        if is_weapon:
            item = Weapon(**common_kwargs, rng=item_data.get("rng", 1))
            item.localization = ItemLocalization(
                languages=item_data.get("localization", {})
            )
            item.textures = self._deserialize_textures(
                item_data.get("textures", {}), project_dir
            )
        else:
            item = Armor(
                **common_kwargs,
                armor_class=item_data.get("armor_class", "Light"),
                fragments=item_data.get("fragments", {}),
            )
            item.is_open = item_data.get("is_open", False)
            item.localization = ItemLocalization(
                languages=item_data.get("localization", {})
            )
            item.textures = self._deserialize_textures(
                item_data.get("textures", {}), project_dir
            )

        item.fireproof = item_data.get("fireproof", False)
        item.no_drop = item_data.get("no_drop", False)
        return item

    def _deserialize_hybrid_item(self, item_data: dict, project_dir: str) -> HybridItem:
        """反序列化混合物品数据"""
        item = HybridItem(
            id=item_data.get("id", ""),
            parent_object=item_data.get("parent_object", "o_inv_consum"),
            quality=item_data.get("quality", 1),
            slot=item_data.get("slot", "heal"),
            equipment_mode=EquipmentMode(item_data.get("equipment_mode", "none")),
            weapon_type=item_data.get("weapon_type", "sword"),
            material=item_data.get("material", "metal"),
            tier=item_data.get("tier", 1),
            balance=item_data.get("balance", 2),
            armor_type=item_data.get("armor_type", "Head"),
            trigger_mode=TriggerMode(item_data.get("trigger_mode", "none")),
            skill_object=item_data.get("skill_object", ""),
            charge=item_data.get("charge", 1),
            draw_charges=item_data.get("draw_charges", False),
            charge_mode=ChargeMode(item_data.get("charge_mode", "limited")),
            has_charge_recovery=item_data.get("has_charge_recovery", False),
            charge_recovery_interval=item_data.get("charge_recovery_interval", 10),
            duration_max=item_data.get("duration_max", 100),
            wear_per_use=item_data.get("wear_per_use", 0),
            destroy_on_durability_zero=item_data.get("destroy_on_durability_zero", True),
            delete_on_charge_zero=item_data.get("delete_on_charge_zero", False),
            durability_affects_stats=item_data.get("durability_affects_stats", False),
            base_price=item_data.get("base_price", 100),
            drop_sound=item_data.get("drop_sound", 911),
            pickup_sound=item_data.get("pickup_sound", 907),
            cat=item_data.get("cat", ""),
            subcats=item_data.get("subcats", []),
            exclude_from_random=item_data.get("exclude_from_random", True),
            quality_tag=item_data.get("quality_tag", ""),
            dungeon_tag=item_data.get("dungeon_tag", ""),
            country_tag=item_data.get("country_tag", ""),
            extra_tags=item_data.get("extra_tags", []),
            rarity=item_data.get("rarity", ""),
            weight=item_data.get("weight", "Light"),
            poison_duration=item_data.get("poison_duration", 0),
            attributes=item_data.get("attributes", {}),
            consumable_attributes=item_data.get("consumable_attributes", {}),
            container_spawn=SpawnRule(item_data.get("container_spawn", "none")),
            shop_spawn=SpawnRule(item_data.get("shop_spawn", "none")),
        )

        item.localization = ItemLocalization(
            languages=item_data.get("localization", {})
        )
        item.textures = self._deserialize_textures(
            item_data.get("textures", {}), project_dir
        )

        return item


    def load(self, file_path: str):
        """从文件加载项目"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"项目文件不存在: {file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"项目文件格式错误: {e}")
            return False
        except Exception as e:
            print(f"加载项目文件失败: {e}")
            return False

        self.file_path = file_path
        project_dir = os.path.dirname(file_path)

        self.name = data.get("name", "MyNewMod")
        self.code_name = data.get("code_name", "MyNewMod")
        self.author = data.get("author", "")
        self.description = data.get(
            "description", "使用 Stoneshard Weapon Mod Editor 生成"
        )
        self.version = data.get("version", "1.0.0")
        self.target_version = data.get("target_version", "0.9.3.13")

        self.weapons = [
            self._deserialize_item(w, project_dir, is_weapon=True)
            for w in data.get("weapons", [])
        ]
        self.armors = [
            self._deserialize_item(a, project_dir, is_weapon=False)
            for a in data.get("armors", [])
        ]
        self.hybrid_items = [
            self._deserialize_hybrid_item(h, project_dir)
            for h in data.get("hybrid_items", [])
        ]

        self.clean_invalid_data()
        self.clean_unused_assets()

        return True

    def clean_invalid_data(self):
        """清理无效的武器/装备/混合物品数据"""
        for item in self.weapons + self.armors:
            if not item.needs_char_texture():
                item.textures.clear_char()
            if not item.needs_left_texture():
                item.textures.clear_left()

        for hybrid in self.hybrid_items:
            if not hybrid.needs_char_texture():
                hybrid.textures.clear_char()
            if not hybrid.needs_left_texture():
                hybrid.textures.clear_left()

    def _collect_texture_paths(self, textures: ItemTextures, project_dir: str) -> set:
        """收集物品的所有贴图路径"""
        used_files = set()
        all_paths = (
            textures.character
            + textures.character_left
            + textures.inventory
            + textures.loot
        )
        # 添加多姿势装备贴图
        if textures.character_standing1:
            all_paths = list(all_paths) + [textures.character_standing1]
        if textures.character_rest:
            all_paths = list(all_paths) + [textures.character_rest]
        # 添加女性版贴图
        if textures.character_female:
            all_paths = list(all_paths) + [textures.character_female]
        if textures.character_standing1_female:
            all_paths = list(all_paths) + [textures.character_standing1_female]
        if textures.character_rest_female:
            all_paths = list(all_paths) + [textures.character_rest_female]

        for p in all_paths:
            if p:
                full_p = os.path.join(project_dir, p) if not os.path.isabs(p) else p
                used_files.add(os.path.normpath(full_p).lower())
        return used_files

    def clean_unused_assets(self):
        """清理未使用的资源文件"""
        if not self.file_path:
            return

        project_dir = os.path.dirname(self.file_path)
        assets_dir = os.path.join(project_dir, "assets")

        if not os.path.exists(assets_dir):
            return

        used_files = set()
        for item in self.weapons + self.armors:
            used_files.update(self._collect_texture_paths(item.textures, project_dir))
        for hybrid in self.hybrid_items:
            used_files.update(self._collect_texture_paths(hybrid.textures, project_dir))

        cleaned_count = 0
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                file_path = os.path.join(root, file)
                norm_path = os.path.normpath(file_path).lower()

                if norm_path not in used_files:
                    try:
                        os.remove(file_path)
                        cleaned_count += 1
                        print(f"已清理未使用资源: {file}")
                    except Exception as e:
                        print(f"无法清理资源 {file}: {e}")

        if cleaned_count > 0:
            print(f"共清理了 {cleaned_count} 个未使用文件")

    def import_texture(self, source_path: str) -> str:
        """将外部贴图复制到项目 assets 目录并返回相对路径"""
        if not source_path or not os.path.exists(source_path):
            return ""

        if not self.file_path:
            return source_path

        project_dir = os.path.dirname(self.file_path)
        assets_dir = os.path.join(project_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        file_name = os.path.basename(source_path)
        dest_path = os.path.join(assets_dir, file_name)

        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            try:
                shutil.copy2(source_path, dest_path)
            except Exception as e:
                print(f"复制贴图失败: {e}")
                return source_path

        return os.path.relpath(dest_path, project_dir)

    def import_project(self, other_project_path: str):
        """导入另一个项目"""
        other_project = ModProject()
        if not other_project.load(other_project_path):
            return False, "无法加载项目文件", []

        imported_count = 0
        conflicts = []

        for weapon in other_project.weapons:
            original_name = weapon.name
            new_name = weapon.name
            suffix = 1

            while any(w.name == new_name for w in self.weapons):
                new_name = f"{original_name}_{suffix}"
                suffix += 1

            if new_name != original_name:
                conflicts.append(f"'{original_name}' 重命名为 '{new_name}'")
                weapon.name = new_name

            self.weapons.append(weapon)
            imported_count += 1

        return True, f"成功导入 {imported_count} 把武器", conflicts
