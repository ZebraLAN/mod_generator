# -*- coding: utf-8 -*-
"""
Tagged Union 规格类型模块

使用 Python 的 Union + dataclass 模式实现类似 Rust enum / OCaml tagged union 的效果。
每个"变体"是一个独立的 dataclass，通过 Union 类型组合。

设计原则：
- 非法状态不可表达 (Make illegal states unrepresentable)
- 每个变体只包含该变体有意义的字段
- 模型层保证自身一致性，UI 层无需维护联动逻辑
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Union, Literal


# ============================================================================
# Literal 类型定义 - 合法值的唯一真相来源
# ============================================================================
# 这些类型既用于静态类型检查，也可运行时获取合法值列表
# 使用 get_args(WeaponType) 可获取所有合法值的元组
# ============================================================================

# 武器类型 (weapon_type)
# 来源: references/gml/gml_GlobalScript_table_weapons.gml 的 Slot 列
# ⚠️ GML 命名，与 C# API 不同 (如 GML "2hsword" vs C# "twohandedsword")
WeaponType = Literal[
    "sword", "dagger", "axe", "mace",           # 单手武器
    "bow", "crossbow",                           # 远程武器
    "2hsword", "2haxe", "2hmace", "2hStaff",    # 双手武器 (GML 命名)
    "spear",                                      # 长杆
    "chain", "lute",                              # 特殊武器
]

# 护甲类型/槽位 (armor_type)
# 来源: ARMOR_SLOT_LABELS, HYBRID_ARMOR_TYPES
ArmorType = Literal[
    "Head", "Chest", "Arms", "Legs", "Back",    # 多姿势护甲
    "Waist", "Ring", "Amulet",                   # 饰品
    "shield",                                     # 盾牌
]

# 重量 (weight)
# 来源: references/gml/gml_GlobalScript_table_items_stats.gml 的 Weight 列
# ⚠️ GML 使用带空格的 "Very Light"，C# API 使用 "VeryLight"
# 注: GML 还有 "Net" 值 (用于渔网等)，暂不支持，待后续需求明确后添加
Weight = Literal["Very Light", "Light", "Medium", "Heavy"]

# 材质 (material)
# 来源: references/gml/gml_GlobalScript_table_items_stats.gml 的 Mat 列
# ⚠️ GML 全部小写
Material = Literal[
    "wood", "metal", "leather",      # 武器常用
    "cloth", "silver", "gold", "gem", # 护甲常用
    "glass", "organic", "paper",      # 消耗品常用
    "pottery", "stone",               # 其他
]

# 护甲类别 (armor_class) - 由 weight 推导，这里仅作文档
ArmorClass = Literal["Light", "Medium", "Heavy"]

# 品质标签 (quality_tag)
QualityTag = Literal["", "common", "uncommon", "rare", "unique"]

# 地牢标签 (dungeon_tag)
DungeonTag = Literal["", "crypt", "catacombs", "bastion"]

# 国家/地区标签 (country_tag)
CountryTag = Literal["", "aldor", "nistra", "skadia", "fjall", "elven", "maen"]


# ============================================================================
# QualitySpec - 品质规格
# ============================================================================
# 品质决定: quality 整数值, 是否有耐久, parent_object 的选择建议
#
# 设计说明:
# - Common: 普通品质，quality=1
# - Unique: 独特品质，quality=6
# - Artifact: 文物品质，quality=7，无耐久
#
# 注: rarity 字段 (GML 中仅有 "Common"/"Unique" 两值) 在游戏中作用不明确，
#      暂不处理。当前 quality_to_rarity() 返回的值仅供参考，待后续研究明确后再调整。
# ============================================================================


@dataclass(frozen=True)
class CommonQuality:
    """普通品质 - quality=1"""
    pass


@dataclass(frozen=True)
class UniqueQuality:
    """独特品质 - quality=6"""
    pass


@dataclass(frozen=True)
class ArtifactQuality:
    """文物品质 - quality=7, 无耐久"""
    pass


QualitySpec = Union[CommonQuality, UniqueQuality, ArtifactQuality]


def quality_to_int(spec: QualitySpec) -> int:
    """QualitySpec -> quality 整数值"""
    match spec:
        case CommonQuality():
            return 1
        case UniqueQuality():
            return 6
        case ArtifactQuality():
            return 7


def quality_to_rarity(spec: QualitySpec) -> str:
    """QualitySpec -> rarity 字符串"""
    match spec:
        case CommonQuality():
            return ""
        case UniqueQuality() | ArtifactQuality():
            return "Unique"


def quality_from_int(value: int) -> QualitySpec:
    """从整数值创建 QualitySpec"""
    if value == 6:
        return UniqueQuality()
    elif value == 7:
        return ArtifactQuality()
    else:
        return CommonQuality()


def quality_has_durability(spec: QualitySpec) -> bool:
    """品质是否允许耐久系统"""
    return not isinstance(spec, ArtifactQuality)


# ============================================================================
# DurabilitySpec - 耐久规格
# ============================================================================
# 决定: 物品的耐久度机制
#
# 变体:
# - NoDurability: 无耐久 (文物或纯消耗品)
# - HasDurability: 有耐久
#
# 注: 该 spec 定义在 EquipmentSpec 之前，因为 WeaponEquip/ArmorEquip 需要
#     在 default_factory 中引用 NoDurability
# ============================================================================


@dataclass
class NoDurability:
    """无耐久系统"""
    pass


@dataclass
class HasDurability:
    """有耐久系统

    Attributes:
        duration_max: 最大耐久
        wear_per_use: 每次使用磨损百分比
        destroy_on_zero: 耐久耗尽时是否删除物品
        affects_stats: 耐久是否影响属性
    """
    duration_max: int = 100
    wear_per_use: int = 0
    destroy_on_zero: bool = True
    affects_stats: bool = False


DurabilitySpec = Union[NoDurability, HasDurability]


def durability_has_durability(spec: DurabilitySpec) -> bool:
    """是否有耐久系统"""
    return isinstance(spec, HasDurability)


def durability_max(spec: DurabilitySpec) -> int:
    """获取最大耐久"""
    match spec:
        case NoDurability():
            return 0
        case HasDurability(duration_max=d):
            return d


# ============================================================================
# EquipmentSpec - 装备形态规格
# ============================================================================
# 决定: 是否可装备, 装备到哪个槽位, 相关的特殊属性
#
# 变体:
# - NotEquipable: 普通背包物品 (slot="heal")
# - WeaponEquip: 武器装备 (slot="hand")
# - ArmorEquip: 护甲装备 (slot=Head/Chest/Arms/Legs/Back/Waist/Ring/Amulet/shield)
# - CharmEquip: 护符装备 (slot="heal", 但有被动效果)
# ============================================================================


@dataclass
class NotEquipable:
    """不可装备 - 普通背包物品"""
    pass


@dataclass
class WeaponEquip:
    """武器装备 - 装备到手部槽位

    Attributes:
        weapon_type: 武器类型
        balance: 平衡性
        durability: 耐久规格 (嵌入，非装备无此字段)

    注意: tier 和 material 已移至 HybridItemV2 顶层，因为 InjectItemStats 对所有物品都需要这些字段
    """
    weapon_type: WeaponType = "sword"
    balance: int = 2
    durability: DurabilitySpec = field(default_factory=NoDurability)

    # 双手武器类型集合 (GML 命名)
    TWO_HAND_WEAPONS: frozenset[str] = frozenset({
        "2hsword", "2haxe", "2hmace", "2hStaff",  # 双手近战/法杖
        "bow", "crossbow", "spear"                 # 远程和长杆
    })

    # 支持左手贴图的武器 (单手武器)
    LEFT_HAND_WEAPONS: frozenset[str] = frozenset({"sword", "dagger", "axe", "mace"})

    @property
    def hands(self) -> int:
        """手数 (1=单手, 2=双手)"""
        return 2 if self.weapon_type in self.TWO_HAND_WEAPONS else 1

    @property
    def slot(self) -> str:
        """装备槽位 - 武器始终为 hand"""
        return "hand"


@dataclass
class ArmorEquip:
    """护甲装备 - 装备到身体槽位

    Attributes:
        armor_type: 护甲槽位
        durability: 耐久规格 (嵌入，非装备无此字段)

    注意: material 已移至 HybridItemV2 顶层，因为 InjectItemStats 对所有物品都需要该字段
    """
    armor_type: ArmorType = "Head"
    durability: DurabilitySpec = field(default_factory=NoDurability)

    # 需要多姿势贴图的护甲槽位
    MULTI_POSE_SLOTS: frozenset[str] = frozenset({"Head", "Chest", "Arms", "Legs", "Back"})

    @property
    def slot(self) -> str:
        """装备槽位 - 等于 armor_type"""
        return self.armor_type


@dataclass
class CharmEquip:
    """护符装备 - 存在于背包即生效的被动效果

    类似暗黑2的charm，放在背包里就有效果。
    """
    pass

    @property
    def slot(self) -> str:
        """装备槽位 - 护符为 heal (背包)"""
        return "heal"


EquipmentSpec = Union[NotEquipable, WeaponEquip, ArmorEquip, CharmEquip]


def equipment_slot(spec: EquipmentSpec) -> str:
    """获取装备槽位"""
    match spec:
        case NotEquipable():
            return "heal"
        case WeaponEquip() as w:
            return w.slot
        case ArmorEquip() as a:
            return a.slot
        case CharmEquip():
            return "heal"


def equipment_is_equipable(spec: EquipmentSpec) -> bool:
    """是否可装备"""
    return isinstance(spec, (WeaponEquip, ArmorEquip))


def equipment_hands(spec: EquipmentSpec) -> int:
    """获取手数"""
    match spec:
        case WeaponEquip() as w:
            return w.hands
        case _:
            return 1


# equipment_material 已删除 - material 现在是 HybridItemV2 的顶层字段


# ============================================================================
# TriggerSpec - 触发效果规格
# ============================================================================
# 决定: 使用物品时触发什么效果
#
# 变体:
# - NoTrigger: 无触发效果
# - EffectTrigger: 应用效果 (像喝药水)
# - SkillTrigger: 释放技能
# ============================================================================


@dataclass
class NoTrigger:
    """无触发效果"""
    pass


@dataclass
class EffectTrigger:
    """效果触发 - 应用一组属性变化

    Attributes:
        consumable_attributes: 消耗品效果属性
        poison_duration: 中毒持续时间 (仅当 Poisoning_Chance > 0 时有效)
    """
    consumable_attributes: dict[str, Any] = field(default_factory=dict[str, Any])
    poison_duration: int = 0


@dataclass
class SkillTrigger:
    """技能触发 - 释放指定技能

    Attributes:
        skill_object: 技能对象名称，如 "o_skill_fire_barrage"
    """
    skill_object: str = ""


TriggerSpec = Union[NoTrigger, EffectTrigger, SkillTrigger]


def trigger_has_effect(spec: TriggerSpec) -> bool:
    """是否有触发效果"""
    return not isinstance(spec, NoTrigger)


# ============================================================================
# ChargeSpec - 使用次数规格
# ============================================================================
# 决定: 物品的使用次数机制
#
# 变体:
# - NoCharges: 无使用次数 (不可主动使用，或使用不消耗次数)
# - LimitedCharges: 有限次数
# - UnlimitedCharges: 无限次数
# ============================================================================


@dataclass
class NoCharges:
    """无使用次数系统"""
    pass


@dataclass
class LimitedCharges:
    """有限使用次数

    Attributes:
        max_charges: 最大使用次数
        draw_charges: 是否绘制次数条
    """
    max_charges: int = 1
    draw_charges: bool = False


@dataclass
class UnlimitedCharges:
    """无限使用次数

    Attributes:
        draw_charges: 是否绘制次数条 (通常为 False)
    """
    draw_charges: bool = False


ChargeSpec = Union[NoCharges, LimitedCharges, UnlimitedCharges]


def charge_effective_value(spec: ChargeSpec) -> int:
    """获取实际使用次数值"""
    match spec:
        case NoCharges():
            return 0
        case LimitedCharges(max_charges=n):
            return n
        case UnlimitedCharges():
            return 1  # 游戏中无限次数表示为 1


def charge_has_charges(spec: ChargeSpec) -> bool:
    """是否有使用次数系统"""
    return not isinstance(spec, NoCharges)


def charge_draw_charges(spec: ChargeSpec) -> bool:
    """是否绘制次数条"""
    match spec:
        case NoCharges():
            return False
        case LimitedCharges(draw_charges=d):
            return d
        case UnlimitedCharges(draw_charges=d):
            return d


# ============================================================================
# ChargeRecoverySpec - 使用次数恢复规格
# ============================================================================
# 决定: 使用次数是否自动恢复
#
# 变体:
# - NoRecovery: 不恢复
# - IntervalRecovery: 按间隔恢复
# ============================================================================


@dataclass
class NoRecovery:
    """无恢复"""
    pass


@dataclass
class IntervalRecovery:
    """按间隔恢复

    Attributes:
        interval: 恢复间隔 (回合数)
    """
    interval: int = 10


ChargeRecoverySpec = Union[NoRecovery, IntervalRecovery]


def recovery_has_recovery(spec: ChargeRecoverySpec) -> bool:
    """是否有恢复"""
    return isinstance(spec, IntervalRecovery)


def recovery_interval(spec: ChargeRecoverySpec) -> int:
    """获取恢复间隔"""
    match spec:
        case NoRecovery():
            return 0
        case IntervalRecovery(interval=i):
            return i


# ============================================================================
# ChargeRecoverySpec - 使用次数恢复规格
# ============================================================================
# (注: DurabilitySpec 已移到 EquipmentSpec 之前，因为 WeaponEquip/ArmorEquip
#      需要在 default_factory 中引用 NoDurability)


# ============================================================================
# SpawnSpec - 生成规则规格
# ============================================================================
# 决定: 物品在各场景的生成规则
#
# 变体:
# - ExcludedFromRandom: 排除随机生成 (tags = "special")
# - RandomSpawn: 参与随机生成，配置各场景规则
# ============================================================================


class SpawnRuleType(Enum):
    """单个场景的生成规则类型"""
    NONE = "none"        # 不参与该场景
    EQUIPMENT = "equipment"  # 按装备规则
    ITEM = "item"        # 按道具规则


@dataclass
class ExcludedFromRandom:
    """排除随机生成 - tags 固定为 "special" """
    pass


@dataclass
class RandomSpawn:
    """参与随机生成

    Attributes:
        container_spawn: 容器生成规则
        shop_spawn: 商店生成规则
        quality_tag: 品质 tag
        dungeon_tag: 地牢 tag
        country_tag: 国家/地区 tag
        extra_tags: 其他 tags
    """
    container_spawn: SpawnRuleType = SpawnRuleType.NONE
    shop_spawn: SpawnRuleType = SpawnRuleType.NONE
    quality_tag: str = ""
    dungeon_tag: str = ""
    country_tag: str = ""
    extra_tags: list[str] = field(default_factory=list[str])

    def build_tags(self) -> str:
        """构建 tags 字符串"""
        parts: list[str] = []
        if self.quality_tag:
            parts.append(self.quality_tag)
        if self.dungeon_tag:
            parts.append(self.dungeon_tag)
        if self.country_tag:
            parts.append(self.country_tag)
        parts.extend(self.extra_tags)
        return " ".join(parts)


SpawnSpec = Union[ExcludedFromRandom, RandomSpawn]


def spawn_effective_tags(spec: SpawnSpec) -> str:
    """获取实际 tags 字符串"""
    match spec:
        case ExcludedFromRandom():
            return "special"
        case RandomSpawn() as s:
            return s.build_tags()


def spawn_is_excluded(spec: SpawnSpec) -> bool:
    """是否排除随机生成"""
    return isinstance(spec, ExcludedFromRandom)


# ============================================================================
# 辅助函数: Spec 类型判断
# ============================================================================


def is_weapon_mode(equipment: EquipmentSpec) -> bool:
    """是否为武器模式"""
    return isinstance(equipment, WeaponEquip)


def is_armor_mode(equipment: EquipmentSpec) -> bool:
    """是否为护甲模式"""
    return isinstance(equipment, ArmorEquip)


def is_charm_mode(equipment: EquipmentSpec) -> bool:
    """是否为护符模式"""
    return isinstance(equipment, CharmEquip)


def needs_char_texture(equipment: EquipmentSpec) -> bool:
    """是否需要角色贴图"""
    match equipment:
        case WeaponEquip():
            return True
        case ArmorEquip(armor_type="shield"):  # 盾牌需要角色贴图
            return True
        case ArmorEquip(armor_type=t) if t in ArmorEquip.MULTI_POSE_SLOTS:
            return True
        case _:
            return False


def needs_left_texture(equipment: EquipmentSpec) -> bool:
    """是否需要左手贴图"""
    match equipment:
        case WeaponEquip(weapon_type=t) if t in WeaponEquip.LEFT_HAND_WEAPONS:
            return True
        case _:
            return False


def needs_multi_pose(equipment: EquipmentSpec) -> bool:
    """是否需要多姿势贴图"""
    match equipment:
        case ArmorEquip(armor_type=t) if t in ArmorEquip.MULTI_POSE_SLOTS:
            return True
        case _:
            return False


# ============================================================================
# Origin - 精灵定位点
# ============================================================================
# 直接对应 GML 的 sprite_set_offset(sprite, x, y)
# 详见: references/docs/doc_sprite_rendering_system.md
# ============================================================================

from constants import CHAR_MODEL_ORIGIN


@dataclass
class Origin:
    """精灵 Origin (定位点)

    与 GML sprite_set_offset 完全对应。
    Origin 决定精灵的哪个像素对齐到绘制位置。

    默认值 CHAR_MODEL_ORIGIN (22, 34) 与人体模型 s_human_male 的 Origin 一致，
    使用此值的装备贴图会与角色身体完美对齐。

    坐标语义:
    - Origin 值越大，装备相对于身体越往左上偏移
    - Origin 值越小，装备相对于身体越往右下偏移

    示例:
        Origin()            # 默认，与角色模型对齐
        Origin(24, 36)      # 装备向左上偏移 2 像素
        Origin(20, 32)      # 装备向右下偏移 2 像素
        Origin.char_model() # 语义化：明确表示角色模型 Origin
    """

    x: int = CHAR_MODEL_ORIGIN[0]
    y: int = CHAR_MODEL_ORIGIN[1]

    @classmethod
    def char_model(cls) -> "Origin":
        """角色模型的 Origin (游戏资源硬编码)

        所有角色模型精灵 (s_*_male, s_*_female) 均使用此 Origin。
        语义化工厂方法，用于明确表达"这是角色的锚点"。
        """
        return cls()

    @property
    def is_aligned_to_char(self) -> bool:
        """是否与角色模型对齐 (无需注入 customizationAnchors)"""
        return (self.x, self.y) == CHAR_MODEL_ORIGIN

    # 保留 is_default 作为别名，避免破坏现有代码
    @property
    def is_default(self) -> bool:
        """是否为默认 Origin (is_aligned_to_char 的别名)"""
        return self.is_aligned_to_char

    @property
    def adjustment(self) -> tuple[int, int]:
        """用户友好的调整量视图 (正值=装备向左/上移动)

        用于 UI 显示，让用户更直观地理解偏移方向。
        """
        return (self.x - CHAR_MODEL_ORIGIN[0], self.y - CHAR_MODEL_ORIGIN[1])

    @classmethod
    def from_offset(cls, offset_x: int, offset_y: int) -> "Origin":
        """从旧版 offset 值迁移

        旧版 offset 语义: 正值 = 装备向左/上移动 (增加 Origin)
        转换公式: origin = char_model + offset
        """
        return cls(CHAR_MODEL_ORIGIN[0] + offset_x, CHAR_MODEL_ORIGIN[1] + offset_y)

    def to_offset(self) -> tuple[int, int]:
        """转换为旧版 offset 值 (用于兼容)

        offset = origin - char_model
        """
        return (self.x - CHAR_MODEL_ORIGIN[0], self.y - CHAR_MODEL_ORIGIN[1])


# ============================================================================
# CharTextureSpec - 角色贴图规格 (Tagged Union)
# ============================================================================
# 根据装备类型决定角色贴图的结构：
# - NoCharTexture: 无角色贴图 (腰带/戒指/项链/护符/普通物品)
# - WeaponCharTexture: 武器/盾牌贴图 (支持动画帧序列)
# - MultiPoseCharTexture: 多姿势护甲贴图 (头/身/手/腿/背，不支持动画)
# ============================================================================

@dataclass
class AnimatedSlot:
    """动画贴图槽 - 支持多帧动画，速度由游戏固定

    用于武器手持贴图，游戏硬编码动画速度，无需 fps 设置。
    """
    paths: list[str] = field(default_factory=list[str])
    origin: Origin = field(default_factory=Origin)

    @property
    def is_animated(self) -> bool:
        """是否为动画"""
        return len(self.paths) > 1

    @property
    def path(self) -> str:
        """单帧时的便捷访问"""
        return self.paths[0] if self.paths else ""

    def has_texture(self) -> bool:
        """是否有贴图"""
        return len(self.paths) > 0


# ===== LootAnimationSpeed - 战利品动画速度 (Tagged Union) =====


@dataclass
class AbsoluteFps:
    """绝对帧率 - 固定每秒播放帧数

    不受游戏速度影响，始终以固定帧率播放。
    """
    fps: float = 10.0


@dataclass
class RelativeSpeed:
    """相对速度 - 基于游戏帧的倍率

    每个游戏帧内动画前进的帧数。
    例如 multiplier=0.25 表示每 4 个游戏帧前进 1 动画帧。
    """
    multiplier: float = 0.25


LootAnimationSpeed = Union[AbsoluteFps, RelativeSpeed]


def loot_speed_to_preview_fps(speed: LootAnimationSpeed, game_fps: float = 40.0) -> float:
    """计算预览用的实际 FPS"""
    match speed:
        case AbsoluteFps(fps=f):
            return f
        case RelativeSpeed(multiplier=m):
            return game_fps * m


@dataclass
class LootSlot:
    """战利品贴图槽 - 支持动画且可配置速度

    战利品贴图可以通过 GML 设置动画速度。
    使用 Tagged Union LootAnimationSpeed 表示两种互斥的速度模式。
    """
    paths: list[str] = field(default_factory=list[str])
    speed: LootAnimationSpeed = field(default_factory=AbsoluteFps)

    @property
    def is_animated(self) -> bool:
        """是否为动画"""
        return len(self.paths) > 1

    def has_texture(self) -> bool:
        """是否有贴图"""
        return len(self.paths) > 0


@dataclass
class StaticSlot:
    """静态贴图槽 - 仅单帧

    用于多姿势护甲的各个姿势，游戏限制无法支持动画。
    """
    path: str = ""
    origin: Origin = field(default_factory=Origin)

    def has_texture(self) -> bool:
        """是否有贴图"""
        return bool(self.path)


# ===== CharTextureSpec 变体 =====


@dataclass
class NoCharTexture:
    """无角色贴图

    适用于：腰带、戒指、项链、护符、普通背包物品
    """
    pass


@dataclass
class WeaponCharTexture:
    """武器/盾牌角色贴图

    支持动画帧序列，动画速度由游戏硬编码。
    单手武器可选配左手贴图。
    """
    main: AnimatedSlot = field(default_factory=AnimatedSlot)
    left: AnimatedSlot = field(default_factory=AnimatedSlot)


@dataclass
class MultiPoseCharTexture:
    """多姿势护甲角色贴图 (头/身/手/腿/背)

    游戏使用 s_char 帧序列的两帧存储站立姿势，导致无法支持动画。

    游戏姿势系统：
    ┌─────────────┬──────────────────────────────────────────┐
    │ 姿势        │ 触发条件                                 │
    ├─────────────┼──────────────────────────────────────────┤
    │ standing0   │ 手持单手武器/盾牌/长杆时                 │
    │ standing1   │ 手持其他双手武器时 (无则 fallback 到 0)  │
    │ rest        │ 角色进入休息状态时                       │
    └─────────────┴──────────────────────────────────────────┘

    性别版本说明：
    - 默认版 (standing0/standing1/rest): 男性角色使用，也作为女性的 fallback
    - 女性版 (*_female): 可选，女性角色优先使用，未设置则 fallback 到默认版

    领域规则详见 FALLBACK_CHAIN / UI_ENABLE_REQUIRES / CASCADE_CLEAR 三个 ClassVar。
    """

    # ===== 字段定义 =====
    standing0: StaticSlot = field(default_factory=StaticSlot)
    standing1: StaticSlot = field(default_factory=StaticSlot)
    rest: StaticSlot = field(default_factory=StaticSlot)
    # 女性版
    standing0_female: StaticSlot = field(default_factory=StaticSlot)
    standing1_female: StaticSlot = field(default_factory=StaticSlot)
    rest_female: StaticSlot = field(default_factory=StaticSlot)

    # =========================================================================
    # 领域规则 (声明式，不可变)
    # =========================================================================

    # Fallback 规则：游戏渲染时如何选择实际贴图
    # key = 请求的贴图, value = fallback 链 (按优先级顺序尝试)
    # 注: standing0 和 rest 无 fallback，必须由 mod 作者提供
    FALLBACK_CHAIN: ClassVar[dict[str, tuple[str, ...]]] = {
        "standing1": ("standing0",),
        "standing0_female": ("standing0",),
        "standing1_female": ("standing0_female", "standing1", "standing0"),
        "rest_female": ("rest",),
    }

    # UI 启用前置条件：编辑器中某字段的"选择"按钮何时可点击
    # key = 目标字段, value = 必须全部有贴图的字段列表
    # 这是 UX 优化，避免用户设置"永远不会被游戏使用"的贴图
    # 例: standing1_female 需要 standing1 和 standing0_female 都已设置才有意义
    #     - 如果 standing1 不存在 → 游戏永远不会触发"双手武器站立"姿势
    #     - 如果 standing0_female 不存在 → 女性角色整体 fallback 到男性版
    UI_ENABLE_REQUIRES: ClassVar[dict[str, tuple[str, ...]]] = {
        "standing1_female": ("standing1", "standing0_female"),
    }

    # 级联清除规则：清除某字段时应连带清除哪些依赖字段
    # 避免留下"孤儿"贴图 (依赖的基础贴图被删了，但派生贴图还在)
    CASCADE_CLEAR: ClassVar[dict[str, tuple[str, ...]]] = {
        "standing1": ("standing1_female",),  # 男版没了，女版也没意义
        "standing0_female": ("standing1_female",),  # 女版基础没了，女版姿势1也没意义
    }

    # =========================================================================
    # 数据驱动方法
    # =========================================================================

    def resolve(self, slot_name: str) -> tuple[StaticSlot, str | None]:
        """解析实际使用的贴图 (考虑 fallback 链)

        Args:
            slot_name: 字段名，如 "standing1_female"

        Returns:
            (贴图槽, fallback来源字段名 or None)
            - 如果该字段本身有贴图，返回 (贴图, None)
            - 如果 fallback 到其他字段，返回 (贴图, 来源字段名)
            - 如果整条链都没有，返回 (空StaticSlot, None)
        """
        slot: StaticSlot = getattr(self, slot_name)
        if slot.has_texture():
            return (slot, None)
        for fallback_name in self.FALLBACK_CHAIN.get(slot_name, ()):
            fallback_slot: StaticSlot = getattr(self, fallback_name)
            if fallback_slot.has_texture():
                return (fallback_slot, fallback_name)
        return (StaticSlot(), None)

    def is_ui_enabled(self, slot_name: str) -> bool:
        """检查编辑器中某字段是否应该启用

        Args:
            slot_name: 字段名，如 "standing1_female"

        Returns:
            True 如果没有前置条件，或所有前置条件都满足
        """
        requires = self.UI_ENABLE_REQUIRES.get(slot_name, ())
        return all(getattr(self, req).has_texture() for req in requires)

    def clear_with_cascade(self, slot_name: str) -> list[str]:
        """清除字段并级联清除依赖字段

        Args:
            slot_name: 要清除的字段名

        Returns:
            被清除的所有字段名列表 (包括级联清除的)
        """
        cleared: list[str] = [slot_name]
        setattr(self, slot_name, StaticSlot())

        for cascade_name in self.CASCADE_CLEAR.get(slot_name, ()):
            if getattr(self, cascade_name).has_texture():
                setattr(self, cascade_name, StaticSlot())
                cleared.append(cascade_name)

        return cleared


CharTextureSpec = Union[NoCharTexture, WeaponCharTexture, MultiPoseCharTexture]


# ============================================================================
# ItemTexturesV2 - 使用 Tagged Union 的物品贴图
# ============================================================================


@dataclass
class ItemTexturesV2:
    """物品贴图 V2 - 使用 Tagged Union 重构

    核心改进：
    - char 字段使用 CharTextureSpec Tagged Union
    - 消除语义重载和 ghost 字段
    - 每种装备类型只有该类型需要的字段
    """

    # ===== 通用字段 (所有物品都需要) =====
    inventory: list[str] = field(default_factory=list[str])
    loot: LootSlot = field(default_factory=LootSlot)

    # ===== 角色贴图 (Tagged Union) =====
    char: CharTextureSpec = field(default_factory=NoCharTexture)

    # ===== 辅助方法 (兼容 ItemTextures 接口) =====

    def has_char(self) -> bool:
        """是否有主角色贴图"""
        match self.char:
            case WeaponCharTexture() as w:
                return bool(w.main.paths)
            case MultiPoseCharTexture() as m:
                return bool(m.standing0.path)
            case _:
                return False

    def has_char_left(self) -> bool:
        """是否有左手贴图（仅武器）"""
        if isinstance(self.char, WeaponCharTexture):
            return bool(self.char.left.paths)
        return False

    def has_rest(self) -> bool:
        """是否有休息姿势贴图（仅多姿势护甲）"""
        if isinstance(self.char, MultiPoseCharTexture):
            return bool(self.char.rest.path)
        return False

    def has_loot(self) -> bool:
        """是否有战利品贴图"""
        return bool(self.loot.paths)

    def clear_char(self) -> None:
        """清除角色贴图"""
        match self.char:
            case WeaponCharTexture() as w:
                w.main.paths.clear()
                w.main.origin = Origin()
            case MultiPoseCharTexture() as m:
                m.standing0.path = ""
                m.standing0.origin = Origin()
                m.standing1.path = ""
                m.standing1.origin = Origin()
                m.rest.path = ""
                m.rest.origin = Origin()
                # 清除女性版
                m.standing0_female.path = ""
                m.standing0_female.origin = Origin()
                m.standing1_female.path = ""
                m.standing1_female.origin = Origin()
                m.rest_female.path = ""
                m.rest_female.origin = Origin()

    def clear_left(self) -> None:
        """清除左手贴图（仅武器）"""
        if isinstance(self.char, WeaponCharTexture):
            self.char.left.paths.clear()
            self.char.left.origin = Origin()


# ============================================================================
# CharTextureSpec 辅助函数
# ============================================================================


def char_texture_for_equipment(equipment: EquipmentSpec) -> CharTextureSpec:
    """根据装备类型创建对应的空 CharTextureSpec"""
    match equipment:
        case WeaponEquip():
            return WeaponCharTexture()
        case ArmorEquip(armor_type="shield"):  # 盾牌使用武器贴图格式
            return WeaponCharTexture()
        case ArmorEquip(armor_type=t) if t in ArmorEquip.MULTI_POSE_SLOTS:
            return MultiPoseCharTexture()
        case _:
            return NoCharTexture()
