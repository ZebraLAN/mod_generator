# -*- coding: utf-8 -*-
"""
HybridItem V2 - 使用 Tagged Union 重构的混合物品类

设计原则：
- 使用 specs 模块的 Tagged Union 类型替代平铺字段
- 模型层保证自身一致性
- 计算属性由 Spec 类型直接推导，无需 UI 维护

序列化由 serde 模块处理，本模块只定义数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from specs import (
    # Literal 类型
    Weight, Material,
    QualitySpec, CommonQuality, quality_to_int, quality_to_rarity, quality_has_durability,
    # Equipment
    EquipmentSpec, NotEquipable, WeaponEquip, ArmorEquip, CharmEquip,
    equipment_slot, equipment_is_equipable, equipment_hands,
    needs_char_texture, needs_left_texture, needs_multi_pose,
    # Trigger
    TriggerSpec, NoTrigger, EffectTrigger, SkillTrigger,
    ChargeSpec, NoCharges, LimitedCharges, UnlimitedCharges,
    ChargeRecoverySpec, NoRecovery, IntervalRecovery,
    NoDurability, HasDurability,
    durability_has_durability, SpawnSpec, SpawnRuleType, ExcludedFromRandom, RandomSpawn,
    spawn_effective_tags, spawn_is_excluded,
    # Textures (V2)
    ItemTexturesV2,
)
from models import ItemLocalization


# ============================================================================
# HybridItemV2 - 使用 Tagged Union 的混合物品
# ============================================================================


@dataclass
class HybridItemV2:
    """混合物品 V2 - 使用 Tagged Union 重构

    核心设计：
    - quality: QualitySpec (替代 quality: int + rarity: str)
    - equipment: EquipmentSpec (替代 equipment_mode + weapon_type + armor_type + ...)
    - trigger: TriggerSpec (替代 trigger_mode + skill_object + consumable_attributes + ...)
    - charges: ChargeSpec (替代 charge_mode + charge + draw_charges)
    - charge_recovery: ChargeRecoverySpec (替代 has_charge_recovery + charge_recovery_interval)
    - durability: DurabilitySpec (嵌入 equipment，替代 has_durability + duration_max + ...)
    - spawn: SpawnSpec (替代 exclude_from_random + container_spawn + shop_spawn + tags)
    """

    # ====== 基础信息 ======
    id: str = ""

    # 本地化
    localization: ItemLocalization = field(default_factory=ItemLocalization)

    # 父对象
    parent_object: str = "o_inv_consum"

    # ====== Tagged Union 规格 ======
    quality: QualitySpec = field(default_factory=CommonQuality)
    equipment: EquipmentSpec = field(default_factory=NotEquipable)
    trigger: TriggerSpec = field(default_factory=NoTrigger)
    charges: ChargeSpec = field(default_factory=NoCharges)
    charge_recovery: ChargeRecoverySpec = field(default_factory=NoRecovery)
    # 注: durability 已嵌入 WeaponEquip/ArmorEquip，非装备无需耐久
    spawn: SpawnSpec = field(default_factory=ExcludedFromRandom)

    # ====== 分类元数据 ======
    cat: str = ""
    subcats: list[str] = field(default_factory=list[str])

    # ====== 通用属性 ======
    attributes: dict[str, Any] = field(default_factory=dict[str, Any])

    # ====== 拆解碎片 ======
    fragments: dict[str, int] = field(default_factory=dict[str, int])

    # ====== 顶层字段：所有物品都需要 (InjectItemStats) ======
    weight: Weight = "Light"
    tier: int = 1                   # 等级 1-5
    material: Material = "organic"  # 材质，默认 organic (非装备)

    # ====== 价格与音效 ======
    base_price: int = 100
    drop_sound: int = 911
    pickup_sound: int = 907

    # ====== 使用次数耗尽删除 ======
    delete_on_charge_zero: bool = False

    # ====== 贴图 (V2 Tagged Union) ======
    textures: ItemTexturesV2 = field(default_factory=ItemTexturesV2)

    # ====== 计算属性：从 Spec 类型直接推导 ======

    @property
    def quality_int(self) -> int:
        """品质整数值"""
        return quality_to_int(self.quality)

    @property
    def rarity(self) -> str:
        """稀有度字符串"""
        return quality_to_rarity(self.quality)

    @property
    def slot(self) -> str:
        """装备槽位"""
        return equipment_slot(self.equipment)

    @property
    def equipable(self) -> bool:
        """是否可装备"""
        return equipment_is_equipable(self.equipment)

    @property
    def hands(self) -> int:
        """手数"""
        return equipment_hands(self.equipment)

    # ====== 兼容性别名 (保留：与 Weapon/Armor 接口兼容) ======
    @property
    def name(self) -> str:
        """别名：返回 id"""
        return self.id

    @name.setter
    def name(self, value: str):
        """别名：设置 id"""
        object.__setattr__(self, "id", value)

    # ====== 计算属性 ======

    @property
    def armor_class(self) -> str:
        """护甲类别 - 仅护甲模式有意义

        映射规则 (weight → armor_class):
        - Very Light / Light → "Light"
        - Medium → "Medium"
        - Heavy → "Heavy"

        游戏来源: scr_atr_calc.gml 中 armor_class 用于抗性计算
        """
        return {"Very Light": "Light", "Light": "Light",
                "Medium": "Medium", "Heavy": "Heavy"}.get(self.weight, "Light")

    @property
    def has_durability(self) -> bool:
        """是否有耐久系统

        耐久系统需要满足:
        1. 品质允许 (非 ArtifactQuality)
        2. 是装备 (WeaponEquip 或 ArmorEquip)
        3. 装备内嵌的 durability 为 HasDurability
        """
        if not quality_has_durability(self.quality):
            return False
        match self.equipment:
            case WeaponEquip(durability=d):
                return durability_has_durability(d)
            case ArmorEquip(durability=d):
                return durability_has_durability(d)
            case _:
                return False

    @property
    def exclude_from_random(self) -> bool:
        """是否排除随机生成"""
        return spawn_is_excluded(self.spawn)

    @property
    def effective_tags(self) -> str:
        """有效 tags 字符串"""
        return spawn_effective_tags(self.spawn)

    @property
    def container_spawn(self) -> SpawnRuleType:
        """容器生成规则"""
        match self.spawn:
            case RandomSpawn(container_spawn=r):
                return r
            case _:
                return SpawnRuleType.NONE

    @property
    def shop_spawn(self) -> SpawnRuleType:
        """商店生成规则"""
        match self.spawn:
            case RandomSpawn(shop_spawn=r):
                return r
            case _:
                return SpawnRuleType.NONE

    # ====== 标签读写属性 (兼容 UI) ======

    @property
    def quality_tag(self) -> str:
        """品质标签 (仅 RandomSpawn 时有效)"""
        match self.spawn:
            case RandomSpawn(quality_tag=t):
                return t
            case _:
                return ""

    @quality_tag.setter
    def quality_tag(self, value: str):
        """设置品质标签"""
        if isinstance(self.spawn, RandomSpawn):
            object.__setattr__(self.spawn, "quality_tag", value)

    @property
    def dungeon_tag(self) -> str:
        """地牢标签 (仅 RandomSpawn 时有效)"""
        match self.spawn:
            case RandomSpawn(dungeon_tag=t):
                return t
            case _:
                return ""

    @dungeon_tag.setter
    def dungeon_tag(self, value: str):
        """设置地牢标签"""
        if isinstance(self.spawn, RandomSpawn):
            object.__setattr__(self.spawn, "dungeon_tag", value)

    @property
    def country_tag(self) -> str:
        """国家/地区标签 (仅 RandomSpawn 时有效)"""
        match self.spawn:
            case RandomSpawn(country_tag=t):
                return t
            case _:
                return ""

    @country_tag.setter
    def country_tag(self, value: str):
        """设置国家/地区标签"""
        if isinstance(self.spawn, RandomSpawn):
            object.__setattr__(self.spawn, "country_tag", value)

    @property
    def extra_tags(self) -> list[str]:
        """额外标签列表 (仅 RandomSpawn 时有效)"""
        match self.spawn:
            case RandomSpawn(extra_tags=t):
                return t
            case _:
                return []

    @extra_tags.setter
    def extra_tags(self, value: list[str]):
        """设置额外标签列表"""
        if isinstance(self.spawn, RandomSpawn):
            object.__setattr__(self.spawn, "extra_tags", value)

    # ====== 贴图需求方法 ======

    def needs_char_texture(self) -> bool:
        """是否需要角色贴图"""
        return needs_char_texture(self.equipment)

    def needs_left_texture(self) -> bool:
        """是否需要左手贴图"""
        return needs_left_texture(self.equipment)

    def needs_multi_pose_textures(self) -> bool:
        """是否需要多姿势贴图"""
        return needs_multi_pose(self.equipment)

    # ====== 辅助方法 ======

    def get_quality_label(self) -> str:
        """获取品质显示文本"""
        from constants import HYBRID_QUALITY_LABELS
        return HYBRID_QUALITY_LABELS.get(self.quality_int, "普通")

    def get_loot_parent(self) -> str:
        """获取 Loot 对象的父类"""
        return "o_consument_loot"

    @property
    def has_equipment_spawn(self) -> bool:
        """是否有任何场景使用装备规则"""
        return SpawnRuleType.EQUIPMENT in (self.container_spawn, self.shop_spawn)

    @property
    def has_item_spawn(self) -> bool:
        """是否有任何场景使用道具规则"""
        return SpawnRuleType.ITEM in (self.container_spawn, self.shop_spawn)

    @property
    def needs_registration(self) -> bool:
        """是否需要注册到混合物品系统"""
        if self.exclude_from_random:
            return False
        if self.has_equipment_spawn:
            return True
        return self.shop_spawn != SpawnRuleType.ITEM or self.container_spawn != SpawnRuleType.ITEM

    @classmethod
    def get_type_key(cls) -> str:
        return "hybrid"

    @classmethod
    def get_config(cls) -> dict:
        from constants import ITEM_TYPE_CONFIG
        return ITEM_TYPE_CONFIG[cls.get_type_key()]
