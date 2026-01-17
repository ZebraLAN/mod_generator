# -*- coding: utf-8 -*-
"""
常量定义模块

包含所有枚举、标签、属性描述、配置映射等静态数据。
"""

# ============== 通用枚举类型 ==============

# 等级（武器/护甲共用）
TIER = ["Tier1", "Tier2", "Tier3", "Tier4", "Tier5"]
TIER_LABELS = {tier: str(idx + 1) for idx, tier in enumerate(TIER)}

# 稀有度标签
RARITY_LABELS = {"Common": "普通", "Unique": "独特"}

# ============== 武器相关枚举 ==============

# 武器槽位标签
SLOT_LABELS = {
    "dagger": "匕首",
    "mace": "单手锤棒",
    "sword": "单手刀剑",
    "axe": "单手斧",
    "bow": "弓",
    "crossbow": "弩",
    "twohandedmace": "双手锤棒",
    "twohandedsword": "双手刀剑",
    "twohandedaxe": "双手斧",
    "spear": "长杆刃器",
    "twohandedstaff": "长杖",
    "chain": "锁链",
    "lute": "鲁特琴",
}

# 武器材料标签
WEAPON_MATERIAL_LABELS = {"wood": "木", "metal": "金属", "leather": "皮"}

# 通用标签（武器/护甲共用）
TAG_LABELS = {
    "aldor": "奥尔多",
    "elven": "精灵",
    "fjall": "弗约",
    "magic": "魔法",
    "nistra": "尼斯特拉",
    "skadia": "斯卡迪亚",
    "special": "特殊",
    "unique": "独特",
    "special exc": "特殊（新英雄）",
}

# 武器槽位平衡值
SLOT_BALANCE = {
    "twohandedaxe": 0,
    "twohandedmace": 0,
    "twohandedstaff": 2,
    "twohandedsword": 0,
    "axe": 3,
    "bow": 0,
    "crossbow": 0,
    "dagger": 4,
    "mace": 1,
    "sword": 2,
    "lute": 2,
    "chain": 2,
}

# 支持左手持握的槽位 (单手武器)
LEFT_HAND_SLOTS = ["dagger", "mace", "sword", "axe"]

# ============== 护甲/装备相关枚举 ==============

# 护甲钩子标签
ARMOR_HOOK_LABELS = {
    "SHIELDS": "盾牌",
    "HELMETS": "头盔",
    "CHESTPIECES": "胸甲",
    "GLOVES": "手套",
    "BOOTS": "靴子",
    "BELTS": "腰带",
    "RINGS": "戒指",
    "NECKLACES": "项链",
    "CLOAKS": "披风",
}

# 护甲槽位标签
ARMOR_SLOT_LABELS = {
    "shield": "盾牌",
    "Head": "头部",
    "Chest": "胸部",
    "Arms": "手臂",
    "Legs": "腿部",
    "Waist": "腰部",
    "Ring": "戒指",
    "Amulet": "护身符",
    "Back": "背部",
}

# Hook 和 Slot 的绑定关系
ARMOR_HOOK_TO_SLOT = {
    "SHIELDS": "shield",
    "HELMETS": "Head",
    "CHESTPIECES": "Chest",
    "GLOVES": "Arms",
    "BOOTS": "Legs",
    "BELTS": "Waist",
    "RINGS": "Ring",
    "NECKLACES": "Amulet",
    "CLOAKS": "Back",
}

ARMOR_SLOT_TO_HOOK = {v: k for k, v in ARMOR_HOOK_TO_SLOT.items()}

# 护甲类别标签
ARMOR_CLASS_LABELS = {
    "Light": "轻甲",
    "Medium": "中甲",
    "Heavy": "重甲",
}

# 护甲材料标签
ARMOR_MATERIAL_LABELS = {
    "wood": "木",
    "leather": "皮",
    "metal": "金属",
    "cloth": "布料",
    "silver": "银",
    "gold": "金",
    "gem": "宝石",
}

# 需要角色贴图预览的槽位
ARMOR_SLOTS_WITH_CHAR_PREVIEW = ["shield", "Head", "Chest", "Arms", "Legs", "Back"]

# 需要多姿势穿戴贴图的装备槽位 (头/身/手/腿/背)
# 游戏姿势系统：
# - 站立姿势0: 单手武器/盾牌/长杆 → s_char_{id}_0.png (帧序列第0帧)
# - 站立姿势1: 其他双手武器 → s_char_{id}_1.png (帧序列第1帧，可选)
# - 休息姿势: 休息状态 → s_char3_{id}.png (独立贴图槽)
# 注：游戏用 s_char 帧序列的两帧存储站立姿势，导致这些装备无法支持动画
ARMOR_SLOTS_MULTI_POSE = ["Head", "Chest", "Arms", "Legs", "Back"]

# ============== 渲染与动画常量 ==============

# 游戏实际帧率 (Stoneshard 运行在约 40fps)
GAME_FPS = 40

# 预览动画帧率 (游戏帧率的 1/4，手持贴图在游戏中默认以此速度播放)
PREVIEW_ANIMATION_FPS = GAME_FPS // 4  # = 10 fps

# 渲染坐标系常量
GML_ANCHOR_X = 22  # 游戏内默认原点 X
GML_ANCHOR_Y = 34  # 游戏内默认原点 Y
CHAR_IMG_W = 48  # 人物贴图宽
CHAR_IMG_H = 40  # 人物贴图高

# 护甲穿戴贴图预览区域尺寸 (与人物贴图相同)
ARMOR_PREVIEW_WIDTH = CHAR_IMG_W  # 48
ARMOR_PREVIEW_HEIGHT = CHAR_IMG_H  # 40
CHAR_CENTER_X = CHAR_IMG_W // 2  # 人物中心 X (24)
CHAR_CENTER_Y = CHAR_IMG_H // 2  # 人物中心 Y (20)
VALID_AREA_SIZE = 64  # 有效显示区域边长 (64x64)

# 有效区域相对于人物贴图左上角的坐标
VALID_MIN_X = CHAR_CENTER_X - VALID_AREA_SIZE // 2  # -8
VALID_MAX_X = CHAR_CENTER_X + VALID_AREA_SIZE // 2  # 56
VALID_MIN_Y = CHAR_CENTER_Y - VALID_AREA_SIZE // 2  # -12
VALID_MAX_Y = CHAR_CENTER_Y + VALID_AREA_SIZE // 2  # 52

# 视口绘制时人物相对于64x64框左上角的偏移
VIEWPORT_CHAR_OFFSET_X = VALID_AREA_SIZE // 2 - CHAR_CENTER_X  # = 8
VIEWPORT_CHAR_OFFSET_Y = VALID_AREA_SIZE // 2 - CHAR_CENTER_Y  # = 12

# Byte类型的属性 (需要限制为 0-255)
BYTE_ATTRIBUTES = {
    "Bleeding_Chance",
    "Daze_Chance",
    "Stun_Chance",
    "Knockback_Chance",
    "Immob_Chance",
    "Stagger_Chance",
    "DEF",
    "PRR",
    "Block_Power",
    "Crit_Avoid",
}

# 负面属性 (这些属性的正值表示减益，负值表示增益)
NEGATIVE_ATTRIBUTES = {
    "FMB",
    "Cooldown_Reduction",
    "Abilities_Energy_Cost",
    "Skills_Energy_Cost",
    "Spells_Energy_Cost",
    "Miscast_Chance",
    "Fatigue_Gain",
    "Damage_Received",
}

# 伤害类型属性（用于武器伤害计算）
DAMAGE_ATTRIBUTES = {
    "Slashing_Damage", "Piercing_Damage", "Blunt_Damage", "Rending_Damage",
    "Fire_Damage", "Shock_Damage", "Poison_Damage", "Caustic_Damage",
    "Frost_Damage", "Arcane_Damage", "Unholy_Damage", "Sacred_Damage", "Psionic_Damage",
}

# 消耗品浮点数属性（基于 items_stats.json 分析）
# 这些属性在游戏数据中存在小数值，编辑器应使用 float 输入
CONSUMABLE_FLOAT_ATTRIBUTES = {
    "Condition",
    "Health_Restoration",
    "Immunity_Change",
    "MoraleDiet",
}

# 效果持续时间属性（控制其他属性是否生效的核心属性）
# 独立提取以便在编辑器中突出显示
CONSUMABLE_DURATION_ATTRIBUTE = "Duration"

# 消耗品分组前缀（用于自动区分即时效果和持续效果）
# 基于 CONSUMABLE_ATTRIBUTE_GROUPS 的命名约定
CONSUMABLE_INSTANT_GROUP_PREFIX = "即时效果"
CONSUMABLE_DURATION_GROUP_PREFIX = "持续效果"

# 混合物品 Weight 选项
HYBRID_WEIGHT_LABELS = {
    "Light": "轻",
    "Medium": "中",
    "VeryLight": "非常轻",
    "Heavy": "重",
}

# ============== 统一属性分组映射 ==============
# 每个属性只有一个分组归属（单一来源）
# 基于游戏逻辑：
#   - 抗性层级来自 scr_atr_calc.gml
#   - 属性归类基于功能用途

ATTRIBUTE_TO_GROUP = {
    # === 伤害类型 ===
    "Slashing_Damage": "伤害类型",
    "Piercing_Damage": "伤害类型",
    "Blunt_Damage": "伤害类型",
    "Rending_Damage": "伤害类型",
    "Fire_Damage": "伤害类型",
    "Shock_Damage": "伤害类型",
    "Poison_Damage": "伤害类型",
    "Caustic_Damage": "伤害类型",
    "Frost_Damage": "伤害类型",
    "Arcane_Damage": "伤害类型",
    "Unholy_Damage": "伤害类型",
    "Sacred_Damage": "伤害类型",
    "Psionic_Damage": "伤害类型",

    # === 状态效果（施加） ===
    "Bleeding_Chance": "状态效果",
    "Knockback_Chance": "状态效果",
    "Daze_Chance": "状态效果",
    "Stun_Chance": "状态效果",
    "Immob_Chance": "状态效果",
    "Stagger_Chance": "状态效果",

    # === 防护属性 ===
    "DEF": "防护属性",
    "PRR": "防护属性",
    "Block_Power": "防护属性",
    "Block_Recovery": "防护属性",
    "BlockPowerBonus": "防护属性",
    "EVS": "防护属性",
    "Crit_Avoid": "防护属性",
    "Fortitude": "防护属性",

    # === 战斗属性 ===
    "Hit_Chance": "战斗属性",
    "CRT": "战斗属性",
    "CRTD": "战斗属性",
    "CTA": "战斗属性",
    "FMB": "战斗属性",
    "Weapon_Damage": "战斗属性",
    "Armor_Piercing": "战斗属性",
    "Armor_Damage": "战斗属性",
    "Bodypart_Damage": "战斗属性",
    "Mainhand_Efficiency": "战斗属性",
    "Offhand_Efficiency": "战斗属性",

    # === 生存属性 ===
    "max_hp": "生存属性",
    "HP": "生存属性",
    "Health_Restoration": "生存属性",
    "Healing_Received": "生存属性",
    "Health_Threshold": "生存属性",
    "Pain_Limit": "生存属性",
    "Damage_Received": "生存属性",
    "Damage_Returned": "生存属性",
    "Lifesteal": "生存属性",
    "Manasteal": "生存属性",

    # === 精力相关 ===
    "max_mp": "精力相关",
    "MP": "精力相关",
    "MP_Restoration": "精力相关",
    "Max_Energy_Threshold": "精力相关",
    "Abilities_Energy_Cost": "精力相关",
    "Skills_Energy_Cost": "精力相关",
    "Spells_Energy_Cost": "精力相关",
    "Cooldown_Reduction": "精力相关",
    "Fatigue_Gain": "精力相关",
    "Swimming_Cost": "精力相关",

    # === 魔法属性 ===
    "Magic_Power": "魔法属性",
    "Miscast_Chance": "魔法属性",
    "Miracle_Chance": "魔法属性",
    "Miracle_Power": "魔法属性",
    "Backfire_Damage": "魔法属性",
    "Backfire_Damage_Change": "魔法属性",

    # === 元素法力 ===
    "Pyromantic_Power": "元素法力",
    "Geomantic_Power": "元素法力",
    "Venomantic_Power": "元素法力",
    "Electromantic_Power": "元素法力",
    "Cryomantic_Power": "元素法力",
    "Arcanistic_Power": "元素法力",
    "Astromantic_Power": "元素法力",
    "Psimantic_Power": "元素法力",

    # === 元素法力失误 ===
    "Pyromantic_Miscast_Chance": "元素法力失误",
    "Geomantic_Miscast_Chance": "元素法力失误",
    "Venomantic_Miscast_Chance": "元素法力失误",
    "Electromantic_Miscast_Chance": "元素法力失误",
    "Cryomantic_Miscast_Chance": "元素法力失误",
    "Arcanistic_Miscast_Chance": "元素法力失误",
    "Astromantic_Miscast_Chance": "元素法力失误",
    "Psimantic_Miscast_Chance": "元素法力失误",

    # === 抗性（综合）- 基于 scr_atr_calc.gml ===
    "Physical_Resistance": "抗性（综合）",
    "Nature_Resistance": "抗性（综合）",
    "Magic_Resistance": "抗性（综合）",

    # === 抗性（物理）===
    "Slashing_Resistance": "抗性（物理）",
    "Piercing_Resistance": "抗性（物理）",
    "Blunt_Resistance": "抗性（物理）",
    "Rending_Resistance": "抗性（物理）",

    # === 抗性（元素）===
    "Fire_Resistance": "抗性（元素）",
    "Frost_Resistance": "抗性（元素）",
    "Shock_Resistance": "抗性（元素）",
    "Caustic_Resistance": "抗性（元素）",
    "Poison_Resistance": "抗性（元素）",

    # === 抗性（魔法）===
    "Arcane_Resistance": "抗性（魔法）",
    "Unholy_Resistance": "抗性（魔法）",
    "Sacred_Resistance": "抗性（魔法）",
    "Psionic_Resistance": "抗性（魔法）",

    # === 抗性（状态）===
    "Bleeding_Resistance": "抗性（状态）",
    "Knockback_Resistance": "抗性（状态）",
    "Stun_Resistance": "抗性（状态）",
    "Pain_Resistance": "抗性（状态）",

    # === 生理变化 ===
    "Hunger_Change": "生理变化",
    "Hunger_Resistance": "生理变化",
    "Thirst_Change": "生理变化",
    "Toxicity_Change": "生理变化",
    "Toxicity_Resistance": "生理变化",
    "Pain_Change": "生理变化",
    "Immunity_Change": "生理变化",
    "Immunity_Influence": "生理变化",

    # === 心理变化 ===
    "Sanity_Change": "心理变化",
    "Morale_Change": "心理变化",
    "MoraleTemporary": "心理变化",

    # === 角色属性 ===
    "STR": "角色属性",
    "AGL": "角色属性",
    "PRC": "角色属性",
    "Vitality": "角色属性",
    "WIL": "角色属性",

    # === 其他 ===
    "VSN": "其他",
    "Bonus_Range": "其他",
    "Range": "其他",
    "Received_XP": "其他",
    "Noise_Produced": "其他",
    "ReputationGainContract": "其他",
    "ReputationGainGlobal": "其他",
    "STL": "其他",
    "Savvy": "其他",

    # === Buff专属（仅消耗品持续效果可用）===
    "HP_turn": "Buff专属",
    "MP_turn": "Buff专属",
    "Fatigue_Change": "Buff专属",
    "Charge_Distance": "Buff专属",
    "Arcanistic_Distance": "Buff专属",
    "Duration_Resistance": "Buff专属",
    "Avoiding_Trap": "Buff专属",
    "Trade_Favorability": "Buff专属",
    "Head_DEF": "Buff专属",
    "Body_DEF": "Buff专属",
    "Arms_DEF": "Buff专属",
    "Legs_DEF": "Buff专属",
    "CRTD_Main": "Buff专属",
    "CRTD_Off": "Buff专属",
    "CRT_Main": "Buff专属",
    "CRT_Off": "Buff专属",
    "Weapon_Damage_Main": "Buff专属",
    "Weapon_Damage_Off": "Buff专属",
    "Bleeding_Chance_Main": "Buff专属",
    "Bleeding_Chance_Off": "Buff专属",
    "Bleeding_Resistance_Head": "Buff专属",
    "Bleeding_Resistance_Tors": "Buff专属",
    "Bleeding_Resistance_Hands": "Buff专属",
    "Bleeding_Resistance_Legs": "Buff专属",
}


# ============== 各编辑器支持的属性列表 ==============

# 武器属性（来自 C# API）
WEAPON_ATTRIBUTES = [
    # 伤害类型
    "Slashing_Damage", "Piercing_Damage", "Blunt_Damage", "Rending_Damage",
    "Fire_Damage", "Shock_Damage", "Poison_Damage", "Caustic_Damage",
    "Frost_Damage", "Arcane_Damage", "Unholy_Damage", "Sacred_Damage", "Psionic_Damage",
    # 战斗属性
    "Hit_Chance", "CRT", "CRTD", "CTA", "PRR", "Block_Power", "Block_Recovery", "FMB",
    "Armor_Piercing", "Armor_Damage", "Bodypart_Damage",
    # 状态效果
    "Bleeding_Chance", "Knockback_Chance", "Daze_Chance", "Stun_Chance", "Immob_Chance", "Stagger_Chance",
    # 生存属性
    "max_hp", "Health_Restoration", "Healing_Received", "Crit_Avoid", "Damage_Received", "Lifesteal", "Manasteal",
    # 精力相关
    "MP", "MP_Restoration", "Abilities_Energy_Cost", "Skills_Energy_Cost", "Spells_Energy_Cost", "Cooldown_Reduction",
    # 魔法属性
    "Magic_Power", "Miscast_Chance", "Miracle_Chance", "Miracle_Power",
    # 元素法力
    "Pyromantic_Power", "Geomantic_Power", "Venomantic_Power", "Cryomantic_Power",
    "Electromantic_Power", "Arcanistic_Power", "Astromantic_Power", "Psimantic_Power",
    # 其他
    "Bonus_Range", "Fatigue_Gain",
]

# 护甲属性（来自 C# API）
ARMOR_ATTRIBUTES = [
    # 防护属性
    "DEF", "PRR", "Block_Power", "Block_Recovery", "EVS", "Crit_Avoid",
    # 战斗属性
    "FMB", "Hit_Chance", "Weapon_Damage", "Armor_Piercing", "Armor_Damage", "CRT", "CRTD", "CTA",
    # 生存属性
    "Damage_Received", "Fortitude", "max_hp", "Health_Restoration", "Healing_Received", "Lifesteal", "Manasteal", "Damage_Returned",
    # 精力相关
    "MP", "MP_Restoration", "Abilities_Energy_Cost", "Skills_Energy_Cost", "Spells_Energy_Cost",
    # 魔法属性
    "Magic_Power", "Miscast_Chance", "Miracle_Chance", "Miracle_Power", "Cooldown_Reduction",
    # 元素法力
    "Pyromantic_Power", "Geomantic_Power", "Venomantic_Power", "Electromantic_Power",
    "Cryomantic_Power", "Arcanistic_Power", "Astromantic_Power", "Psimantic_Power",
    # 抗性（状态）
    "Bleeding_Resistance", "Knockback_Resistance", "Stun_Resistance", "Pain_Resistance", "Fatigue_Gain",
    # 抗性（综合）
    "Physical_Resistance", "Nature_Resistance", "Magic_Resistance",
    # 抗性（物理）
    "Slashing_Resistance", "Piercing_Resistance", "Blunt_Resistance", "Rending_Resistance",
    # 抗性（元素）
    "Fire_Resistance", "Shock_Resistance", "Poison_Resistance", "Caustic_Resistance", "Frost_Resistance",
    # 抗性（魔法）
    "Arcane_Resistance", "Unholy_Resistance", "Sacred_Resistance", "Psionic_Resistance",
    # 其他
    "VSN", "Bonus_Range", "Received_XP",
]


# ============== 混合物品槽位属性 ==============

# 所有装备共享的通用属性
HYBRID_COMMON_ATTRS = [
    # 基础属性
    "STR", "AGL", "PRC", "Vitality", "WIL",
    # 防护
    "PRR", "Block_Power", "BlockPowerBonus", "Block_Recovery",
    "EVS", "CTA", "STL", "Savvy", "VSN", "Bonus_Range",
    # 生存
    "max_hp", "Health_Restoration", "Healing_Received",  # "HP" 已移除，与 max_hp 重复
    "Damage_Received", "Damage_Returned", "Fortitude", "Pain_Resistance",
    "Crit_Avoid", "Knockback_Resistance", "Stun_Resistance",
    # 精力
    "max_mp", "MP_Restoration", "Max_Energy_Threshold",  # "MP" 已移除，与 max_mp 重复
    "Abilities_Energy_Cost", "Skills_Energy_Cost", "Spells_Energy_Cost",
    "Cooldown_Reduction", "Fatigue_Gain", "Swimming_Cost",
    # 魔法
    "Magic_Power", "Miscast_Chance", "Miracle_Chance", "Miracle_Power",
    "Backfire_Damage", "Backfire_Damage_Change",
    # 元素法力
    "Pyromantic_Power", "Geomantic_Power", "Venomantic_Power", "Cryomantic_Power",
    "Electromantic_Power", "Arcanistic_Power", "Astromantic_Power", "Psimantic_Power",
    "Pyromantic_Miscast_Chance", "Geomantic_Miscast_Chance", "Venomantic_Miscast_Chance",
    "Cryomantic_Miscast_Chance", "Electromantic_Miscast_Chance", "Arcanistic_Miscast_Chance",
    "Astromantic_Miscast_Chance", "Psimantic_Miscast_Chance",
    # 生理/心理
    "Hunger_Change", "Hunger_Resistance", "Thirst_Change",
    "Toxicity_Change", "Toxicity_Resistance", "Pain_Change",
    "Immunity_Change", "Immunity_Influence",
    "Sanity_Change", "Morale_Change", "MoraleTemporary",
    # 其他
    "Mainhand_Efficiency", "Offhand_Efficiency",
    "Received_XP", "Noise_Produced", "ReputationGainGlobal", "ReputationGainContract",
    "Range",
]

# 武器战斗属性（所有装备都有，但武器有效率加成）
HYBRID_COMBAT_ATTRS = [
    "Hit_Chance", "CRT", "CRTD", "FMB", "Weapon_Damage",
    "Armor_Damage", "Armor_Piercing", "Bodypart_Damage",
    "Lifesteal", "Manasteal",
    "Bleeding_Chance", "Daze_Chance", "Stun_Chance",
    "Knockback_Chance", "Immob_Chance", "Stagger_Chance",
]

# 伤害类型属性（仅武器槽位）
HYBRID_DAMAGE_ATTRS = [
    "Slashing_Damage", "Piercing_Damage", "Blunt_Damage", "Rending_Damage",
    "Fire_Damage", "Frost_Damage", "Shock_Damage", "Poison_Damage", "Caustic_Damage",
    "Arcane_Damage", "Unholy_Damage", "Sacred_Damage", "Psionic_Damage",
]

# 抗性属性
HYBRID_RESISTANCE_ATTRS = [
    "Physical_Resistance", "Nature_Resistance", "Magic_Resistance",
    "Slashing_Resistance", "Piercing_Resistance", "Blunt_Resistance", "Rending_Resistance",
    "Fire_Resistance", "Frost_Resistance", "Shock_Resistance", "Caustic_Resistance", "Poison_Resistance",
    "Arcane_Resistance", "Unholy_Resistance", "Sacred_Resistance", "Psionic_Resistance",
    "Bleeding_Resistance", "Health_Threshold",
]

# DEF 属性（仅头/胸/手/腿）
HYBRID_DEF_ATTRS = ["DEF"]

# Buff专属属性（仅消耗品持续效果可用，装备无法提供）
HYBRID_BUFF_ONLY_ATTRS = [
    "HP_turn", "MP_turn", "Fatigue_Change",
    "Charge_Distance", "Arcanistic_Distance",
    "Duration_Resistance", "Avoiding_Trap", "Trade_Favorability",
    "DEF", "Head_DEF", "Body_DEF", "Arms_DEF", "Legs_DEF",
    "CRTD_Main", "CRTD_Off", "CRT_Main", "CRT_Off",
    "Weapon_Damage_Main", "Weapon_Damage_Off",
    "Bleeding_Chance_Main", "Bleeding_Chance_Off",
    "Bleeding_Resistance_Head", "Bleeding_Resistance_Tors",
    "Bleeding_Resistance_Hands", "Bleeding_Resistance_Legs",
]


def get_hybrid_attrs_for_slot(slot: str, has_passive: bool = False) -> list[str]:
    """根据槽位返回可编辑的装备属性列表

    Args:
        slot: 装备槽位 ("hand", "Head", "Chest", "Arms", "Legs", "Ring", "Amulet", "Waist", "Back", "heal")
        has_passive: 是否为被动携带物品 (check_inventory_data=true)
    """
    result = list(HYBRID_COMMON_ATTRS) + list(HYBRID_COMBAT_ATTRS)

    if slot == "hand":
        result.extend(HYBRID_DAMAGE_ATTRS)
        result.extend(HYBRID_RESISTANCE_ATTRS)
    elif slot in ("Head", "Chest", "Arms", "Legs"):
        result.extend(HYBRID_DEF_ATTRS)
        result.extend(HYBRID_RESISTANCE_ATTRS)
    elif slot in ("Ring", "Amulet", "Waist", "Back"):
        result.extend(HYBRID_RESISTANCE_ATTRS)
    elif slot == "heal" and has_passive:
        # 被动携带物品：与普通装备相同，可以使用抗性
        result.extend(HYBRID_RESISTANCE_ATTRS)
    # else: 纯消耗品 (slot=heal, has_passive=false): 仅通用 + 战斗，不需要更多装备属性

    return result


def get_consumable_duration_attrs() -> list[str]:
    """获取消耗品持续效果属性 = 装备通用 + 战斗 + 伤害 + 抗性 + Buff专属"""
    return (list(HYBRID_COMMON_ATTRS) + list(HYBRID_COMBAT_ATTRS) +
            list(HYBRID_DAMAGE_ATTRS) + list(HYBRID_RESISTANCE_ATTRS) +
            list(HYBRID_BUFF_ONLY_ATTRS))


# 即时效果属性（独立case处理，不需要duration）
CONSUMABLE_INSTANT_ATTRS = {
    "即时效果（生理）": ["Hunger", "Thirsty", "Intoxication", "Pain", "Fatigue"],
    "即时效果（心理）": ["SanitySituational", "MoraleSituational", "MoraleDiet"],
    "即时效果（恢复）": ["max_hp_res", "max_mp_res", "Immunity", "Condition"],
    "即时效果（负面几率）": ["Poisoning_Chance", "Nausea_Chance"],
}


def get_attribute_groups(attr_list: list, group_order: list = None) -> dict:
    """根据属性列表动态生成分组

    Args:
        attr_list: 属性名列表
        group_order: 可选的分组排序列表

    Returns:
        {分组名: [属性列表]}，按 group_order 排序（如提供）
    """
    groups = {}
    for attr in attr_list:
        group = ATTRIBUTE_TO_GROUP.get(attr, "其他")
        groups.setdefault(group, []).append(attr)

    # 如果提供了排序，按顺序返回
    if group_order:
        sorted_groups = {}
        for group in group_order:
            if group in groups:
                sorted_groups[group] = groups.pop(group)
        # 添加剩余未排序的组
        sorted_groups.update(groups)
        return sorted_groups

    return groups


# 推荐的分组顺序
DEFAULT_GROUP_ORDER = [
    "伤害类型", "状态效果", "防护属性", "战斗属性", "生存属性", "精力相关",
    "魔法属性", "元素法力", "元素法力失误",
    "抗性（综合）", "抗性（物理）", "抗性（元素）", "抗性（魔法）", "抗性（状态）",
    "生理变化", "心理变化", "角色属性", "Buff专属", "其他",
]

# ATTRIBUTE_TO_GROUP 中不在游戏 order lists 的额外属性
# 这些属性需要追加到扩展 order list 中才能在 hover 中显示
EXTRA_ORDER_ATTRS = (
    "AGL", "Arcanistic_Distance", "Arcanistic_Miscast_Chance", "Arms_DEF",
    "Astromantic_Miscast_Chance", "Avoiding_Trap", "Bleeding_Chance_Main",
    "Bleeding_Chance_Off", "Bleeding_Resistance_Hands", "Bleeding_Resistance_Head",
    "Bleeding_Resistance_Legs", "Bleeding_Resistance_Tors", "BlockPowerBonus",
    "Body_DEF", "CRTD_Main", "CRTD_Off", "CRT_Main", "CRT_Off", "Charge_Distance",
    "Cryomantic_Miscast_Chance", "Duration_Resistance", "Electromantic_Miscast_Chance",
    "Geomantic_Miscast_Chance", "Head_DEF", "Immunity_Influence", "Legs_DEF",
    "MoraleTemporary", "PRC", "Psimantic_Miscast_Chance", "Pyromantic_Miscast_Chance",
    "Range", "STR", "Venomantic_Miscast_Chance", "Vitality", "WIL",
    "Weapon_Damage_Main", "Weapon_Damage_Off",
)

# ============== 拆解材料 ==============


ARMOR_FRAGMENT_LABELS = {
    "fragment_cloth01": "布料碎片 1",
    "fragment_cloth02": "布料碎片 2",
    "fragment_cloth03": "布料碎片 3",
    "fragment_cloth04": "布料碎片 4",
    "fragment_leather01": "皮革碎片 1",
    "fragment_leather02": "皮革碎片 2",
    "fragment_leather03": "皮革碎片 3",
    "fragment_leather04": "皮革碎片 4",
    "fragment_metal01": "金属碎片 1",
    "fragment_metal02": "金属碎片 2",
    "fragment_metal03": "金属碎片 3",
    "fragment_metal04": "金属碎片 4",
    "fragment_gold": "金块碎片",
}

# ============== 角色模型 ==============

# 角色模型 - 每个模型有3个姿势: 0=单手, 1=双手, 2=护甲专用
CHARACTER_MODELS = {
    "Human Male": ["s_human_male_0.png", "s_human_male_1.png", "s_human_male_2.png"],
    "Human Female": [
        "s_human_female_0.png",
        "s_human_female_1.png",
        "s_human_female_2.png",
    ],
    "Dwarf Male": ["s_dwarf_male_0.png", "s_dwarf_male_1.png", "s_dwarf_male_2.png"],
    "Dwarf Female": [
        "s_dwarf_female_0.png",
        "s_dwarf_female_1.png",
        "s_dwarf_female_2.png",
    ],
    "Elf Male": ["s_elf_male_0.png", "s_elf_male_1.png", "s_elf_male_2.png"],
    "Elf Female": [
        "s_elf_female_0.png",
        "s_elf_female_1.png",
        "s_elf_female_2.png",
    ],
}

CHARACTER_MODEL_LABELS = {
    "Human Male": "人类男性",
    "Human Female": "人类女性",
    "Dwarf Male": "矮人男性",
    "Dwarf Female": "矮人女性",
    "Elf Male": "精灵男性",
    "Elf Female": "精灵女性",
}

# 人种列表（用于多姿势装备编辑器中的模特选择）
CHARACTER_RACES = ["Human", "Dwarf", "Elf"]
CHARACTER_RACE_LABELS = {
    "Human": "人类",
    "Dwarf": "矮人",
    "Elf": "精灵",
}


# 根据人种和性别获取模型键名
def get_model_key(race: str, is_female: bool) -> str:
    """根据人种和性别获取角色模型键名"""
    gender = "Female" if is_female else "Male"
    return f"{race} {gender}"


# ============== 语言配置 ==============

# 主语言配置
PRIMARY_LANGUAGE = "Chinese"

# 语言显示标签
LANGUAGE_LABELS = {
    "Chinese": "中文",
    "English": "English",
    "Русский": "Русский",
    "Deutsch": "Deutsch",
    "Español (LATAM)": "Español (LATAM)",
    "Français": "Français",
    "Italiano": "Italiano",
    "Português": "Português",
    "Polski": "Polski",
    "Türkçe": "Türkçe",
    "日本語": "日本語",
    "한국어": "한국어",
}

# 语言名称到 C# 枚举的映射
LANGUAGE_TO_ENUM_MAP = {
    "Chinese": "ModLanguage.Chinese",
    "English": "ModLanguage.English",
    "Русский": "ModLanguage.Russian",
    "Deutsch": "ModLanguage.German",
    "Español (LATAM)": "ModLanguage.Spanish",
    "Français": "ModLanguage.French",
    "Italiano": "ModLanguage.Italian",
    "Português": "ModLanguage.Portuguese",
    "Polski": "ModLanguage.Polish",
    "Türkçe": "ModLanguage.Turkish",
    "日本語": "ModLanguage.Japanese",
    "한국어": "ModLanguage.Korean",
}

# ============== 混合物品相关枚举 ==============

# 混合物品父对象
HYBRID_PARENT_OBJECTS = {
    "o_inv_consum": "基础消耗品",
    "o_inv_consum_active": "主动技能消耗品",
    "o_inv_consum_passive": "被动效果消耗品",
    "o_inv_consum_technical": "工具类消耗品",
    "o_inv_timer_consum": "自动触发消耗品",
}

# 混合物品槽位标签
HYBRID_SLOT_LABELS = {
    "hand": "手持",
    "Head": "头部",
    "Chest": "胸部",
    "Arms": "手臂",
    "Legs": "腿部",
    "Waist": "腰部",
    "Back": "背部",
    "Ring": "戒指",
    "Amulet": "护身符",
    "heal": "背包道具",
}

# 混合物品品质标签
HYBRID_QUALITY_LABELS = {
    1: "普通",
    6: "独特",
    7: "文物",
}

# 触发效果模式（UI 标签映射）
TRIGGER_MODES = {
    "none": "无",
    "effect": "效果",
    "skill": "技能",
}

# 混合物品武器类型
HYBRID_WEAPON_TYPES = {
    "sword": "单手剑",
    "axe": "单手斧",
    "mace": "单手锤",
    "dagger": "匕首",
    "spear": "长杆",
    "bow": "弓",
    "crossbow": "弩",
    "2hsword": "双手剑",
    "2haxe": "双手斧",
    "2hmace": "双手锤",
    "2hStaff": "双手杖",
    "shield": "盾牌",
    "tool": "工具",
    "pick": "镐",
    "chain": "锁链",
    "lute": "鲁特琴",
}

# 混合物品伤害类型
HYBRID_DAMAGE_TYPES = {
    "Slashing_Damage": "劈砍",
    "Piercing_Damage": "穿刺",
    "Blunt_Damage": "钝击",
    "Rending_Damage": "撕裂",
    "Fire_Damage": "火焰",
    "Shock_Damage": "电击",
    "Poison_Damage": "毒素",
    "Caustic_Damage": "腐蚀",
    "Frost_Damage": "霜冻",
    "Arcane_Damage": "秘术",
    "Unholy_Damage": "邪术",
    "Sacred_Damage": "神圣",
    "Psionic_Damage": "灵能",
}

# 混合物品材质
HYBRID_MATERIALS = {
    "cloth": "布料",
    "gem": "宝石",
    "glass": "玻璃",
    "gold": "金",
    "leather": "皮革",
    "metal": "金属",
    "organic": "有机物",
    "paper": "纸",
    "pottery": "陶器",
    "silver": "银",
    "stone": "石",
    "wood": "木",
}

# 混合物品护甲类型 (Slot 字段)
HYBRID_ARMOR_TYPES = {
    "Chest": "胸甲",
    "Head": "头盔",
    "Arms": "手套",
    "Legs": "靴子",
    "Waist": "腰带",
    "Back": "披风",
    "Ring": "戒指",
    "Amulet": "护身符",
    "shield": "盾牌",
}

# 混合物品护甲类别
HYBRID_ARMOR_CLASSES = {
    "Light": "轻甲",
    "Medium": "中甲",
    "Heavy": "重甲",
}


# 常用技能对象 ID（旧版，保留兼容）
HYBRID_SKILL_IDS = {
    -4: "无技能",
    6096: "修理工具使用 (o_skill_use_tinker)",
    6094: "修理物品 (o_skill_repair_item)",
    6076: "开锁 (o_skill_open_door_quest)",
    6073: "撬锁 (o_skill_break_lock)",
    6062: "放置陷阱 (o_skill_set_trap)",
    6876: "放置营火 (o_skill_set_campfire)",
    6085: "放血 (o_skill_leech)",
    4509: "打开书籍 (o_open_book)",
    4510: "打开笔记 (o_open_note)",
    138: "灭火/倒水 (o_skill_douse)",
}

# 混合物品音效选项
# 格式: (音效ID, 音效名称)
# 音效分为拾取(pickup)和放下(drop)两类
HYBRID_PICKUP_SOUNDS = {
    # 消耗品默认
    907: "默认消耗品拾取",
    # 武器拾取
    813: "单手剑拾取 (金属)",
    814: "单手剑拾取 (木)",
    794: "单手斧拾取 (金属)",
    795: "匕首拾取 (金属)",
    817: "单手锤拾取 (金属)",
    818: "单手锤拾取 (木)",
    821: "长杆拾取 (金属)",
    822: "长杆拾取 (木)",
    800: "弓拾取 (木)",
    791: "弩拾取 (木)",
    798: "双手剑拾取 (金属)",
    801: "双手锤拾取 (金属)",
    803: "双手斧拾取 (金属)",
    811: "双手杖拾取 (金属)",
    282: "双手杖拾取 (木)",
    # 盾牌拾取
    825: "轻盾拾取 (木)",
    836: "轻盾拾取 (皮)",
    828: "轻盾拾取 (金属)",
    826: "中盾拾取 (皮)",
    827: "中盾拾取 (木)",
    407: "中盾拾取 (金属)",
    829: "重盾拾取 (木)",
    830: "重盾拾取 (金属)",
    # 护甲拾取
    839: "头盔拾取 (轻金属)",
    840: "头盔拾取 (中金属)",
    843: "头盔拾取 (重金属)",
    850: "胸甲拾取 (轻皮)",
    851: "胸甲拾取 (轻金属)",
    852: "胸甲拾取 (中金属)",
    854: "胸甲拾取 (重金属)",
    862: "手套拾取 (轻皮)",
    864: "手套拾取 (中金属)",
    868: "手套拾取 (重金属)",
    438: "靴子拾取 (轻金属)",
    93: "靴子拾取 (中金属)",
    878: "靴子拾取 (重金属)",
    883: "腰带拾取 (轻皮)",
    885: "腰带拾取 (轻金属)",
    893: "披风拾取 (轻布)",
    # 饰品拾取
    104: "护身符拾取 (宝石)",
    508: "护身符拾取 (金)",
    975: "护身符拾取 (金属)",
    976: "护身符拾取 (木)",
    384: "戒指拾取 (银)",
    1457: "戒指拾取 (金)",
    971: "戒指拾取 (金属)",
    2009: "戒指拾取 (宝石)",
    # 其他
    944: "钥匙拾取",
    956: "背包拾取",
    193: "工具拾取 (木)",
    435: "工具拾取 (金属)",
}

HYBRID_DROP_SOUNDS = {
    # 消耗品默认
    911: "默认消耗品放下",
    # 武器放下
    816: "单手剑放下 (金属)",
    815: "单手剑放下 (木)",
    793: "单手斧放下 (金属)",
    796: "匕首放下 (金属)",
    819: "单手锤放下 (金属)",
    820: "单手锤放下 (木)",
    824: "长杆放下 (金属)",
    823: "长杆放下 (木)",
    799: "弓放下 (木)",
    792: "弩放下 (木)",
    797: "双手剑放下 (金属)",
    805: "双手锤放下 (金属)",
    804: "双手斧放下 (金属)",
    812: "双手杖放下 (金属)",
    2134: "双手杖放下 (木)",
    # 盾牌放下
    831: "轻盾放下 (木)",
    837: "轻盾放下 (皮)",
    834: "轻盾放下 (金属)",
    833: "中盾放下 (皮)",
    832: "中盾放下 (木)",
    2099: "中盾放下 (金属)",
    835: "重盾放下 (木)",
    838: "重盾放下 (金属)",
    # 护甲放下
    844: "头盔放下 (轻金属)",
    846: "头盔放下 (中金属)",
    847: "头盔放下 (重金属)",
    856: "胸甲放下 (轻皮)",
    857: "胸甲放下 (轻金属)",
    858: "胸甲放下 (中金属)",
    860: "胸甲放下 (重金属)",
    869: "手套放下 (轻皮)",
    871: "手套放下 (中金属)",
    874: "手套放下 (重金属)",
    2198: "靴子放下 (轻金属)",
    2195: "靴子放下 (中金属)",
    882: "靴子放下 (重金属)",
    888: "腰带放下 (轻皮)",
    890: "腰带放下 (轻金属)",
    894: "披风放下 (轻布)",
    # 饰品放下
    161: "护身符放下 (宝石)",
    1212: "护身符放下 (金)",
    973: "护身符放下 (金属)",
    974: "护身符放下 (木)",
    451: "戒指放下 (银)",
    249: "戒指放下 (金)",
    972: "戒指放下 (金属)",
    496: "戒指放下 (宝石)",
    # 其他
    48: "钥匙放下",
    958: "背包放下",
    2139: "工具放下 (木)",
    2173: "工具放下 (金属)",
}

# ============== 物品类型配置 ==============

ITEM_TYPE_CONFIG = {
    "weapon": {
        "type_name": "武器",
        "slot_labels": SLOT_LABELS,
    },
    "armor": {
        "type_name": "装备",
        "slot_labels": ARMOR_SLOT_LABELS,
    },
    "hybrid": {
        "type_name": "混合物品",
        "slot_labels": HYBRID_SLOT_LABELS,
    },
}
