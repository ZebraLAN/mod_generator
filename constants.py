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

# ============== 属性描述 ==============

ATTRIBUTE_DESCRIPTIONS = {
    "max_hp": ("生命上限", "你~r~死亡~/~之前可以承受这么多伤害。"),
    "Health_Restoration": ("生命自动恢复", "生命自动恢复的速度。"),
    "Healing_Received": ("治疗效果", "生命各类恢复手段实际恢复的比例。"),
    "MP": ("精力", "你有这么多精力可以运用能力和进行游泳等其他行动。"),
    "MP_Restoration": ("精力自动恢复", "精力自动恢复的速度。"),
    "Damage_Received": ("所受伤害", "你实际会受到这么多伤害。"),
    "Lifesteal": ("生命吸取", "通过物理攻击对敌人造成伤害时获得生命。"),
    "Manasteal": ("精力吸取", "通过物理攻击对敌人造成伤害时获得精力。"),
    "Hit_Chance": ("准度", "你的击打、射击有这么大的几率命中目标。"),
    "CRT": ("暴击几率", "你的攻击有这么大的几率造成额外的伤害。"),
    "CRTD": ("暴击效果", "暴击会额外造成这么多伤害。"),
    "PRR": ("格挡几率", "你有这么大的几率挡住近身攻击。"),
    "Block_Power": ("格挡力量", "你的格挡当前和最多分别可以吸收这么多伤害。"),
    "Block_Recovery": ("格挡力量恢复", "格挡力量每回合恢复的数值与上限的比值。"),
    "CTA": ("反击几率", "你受到近身攻击之后，有这么大的几率击打一次。"),
    "FMB": ("失手几率", "你的攻击有这么大的几率只会造成~r~一半~/~的伤害。"),
    "Bonus_Range": ("距离加成", "影响你远程攻击和某些咒法的距离。"),
    "Rng": ("距离", ""),
    "Crit_Avoid": ("暴击避免", "你有这么大的几率将一次暴击变为普通攻击。"),
    "Bodypart_Damage": ("肢体伤害", "你的攻击还会对敌人的身体部位造成这么多伤害。"),
    "Armor_Damage": ("护甲破坏", "你的攻击还会对敌人的护甲造成这么多破坏。"),
    "Armor_Piercing": ("护甲穿透", "你的攻击会无视这么多防护。"),
    "Bleeding_Chance": (
        "出血几率",
        "你的攻击命中目标的身体部位之后，有这么大的几率造成~r~出血~/~。",
    ),
    "Knockback_Chance": (
        "击退几率",
        "你的攻击有这么大的几率令目标~w~后退~/~一个方格。",
    ),
    "Daze_Chance": ("击晕几率", "你的攻击有这么大的几率令目标~w~眩晕~/~。"),
    "Stun_Chance": ("硬直几率", "你的攻击有这么大的几率令目标~w~硬直~/~。"),
    "Immob_Chance": ("限制移动几率", "你的攻击有这么大的几率令目标~w~移动受限~/~。"),
    "Stagger_Chance": ("破衡几率", "你的攻击有这么大的几率令其~w~失衡~/~。"),
    "Spells_Energy_Cost": (
        "咒法精力消耗",
        "这个属性影响咒法实际所耗精力与其正常所耗精力的比值。",
    ),
    "Skills_Energy_Cost": (
        "技能精力消耗",
        "这个属性影响技能实际所耗精力与其正常所耗精力的比值。",
    ),
    "Abilities_Energy_Cost": (
        "能力精力消耗",
        "这是技能和咒法实际所耗精力与其正常所耗精力的比值。",
    ),
    "Cooldown_Reduction": (
        "冷却时间",
        "这是所有能力实际冷却时间与其正常冷却时间的比值。",
    ),
    "Slashing_Damage": ("劈砍伤害", ""),
    "Piercing_Damage": ("穿刺伤害", ""),
    "Blunt_Damage": ("钝击伤害", ""),
    "Rending_Damage": ("撕裂伤害", ""),
    "Frost_Damage": ("霜冻伤害", ""),
    "Shock_Damage": ("电击伤害", ""),
    "Poison_Damage": ("中毒伤害", ""),
    "Fire_Damage": ("灼烧伤害", ""),
    "Caustic_Damage": ("腐蚀伤害", ""),
    "Arcane_Damage": ("秘术伤害", ""),
    "Unholy_Damage": ("邪术伤害", ""),
    "Sacred_Damage": ("神圣伤害", ""),
    "Psionic_Damage": ("灵能伤害", ""),
    "Fatigue_Gain": ("疲劳增益", "影响你疲劳的速度。"),
    "Magic_Power": ("法力", "影响多数法咒的伤害和效果。"),
    "Miracle_Chance": ("奇观几率", ""),
    "Miracle_Power": ("奇观效果", ""),
    "Miscast_Chance": ("失误几率", "你催动法咒有这么大的几率犯错。"),
    "Pyromantic_Power": ("炎术法力", ""),
    "Geomantic_Power": ("地术法力", ""),
    "Venomantic_Power": ("毒术法力", ""),
    "Cryomantic_Power": ("冰术法力", ""),
    "Electromantic_Power": ("电术法力", ""),
    "Arcanistic_Power": ("秘术法力", ""),
    "Astromantic_Power": ("星术法力", ""),
    "Psimantic_Power": ("灵术法力", ""),
    # 护甲专属属性
    "DEF": ("防护", "你的护甲可以吸收这么多伤害。"),
    "EVS": ("闪避", "你有这么大的几率完全避开攻击。"),
    "VSN": ("视野", "你能看到这么远的距离。"),
    "Weapon_Damage": ("武器伤害", "影响你武器造成的伤害。"),
    "Fortitude": ("韧性", "影响你抵抗负面状态的能力。"),
    "Received_XP": ("经验获取", "影响你获得经验值的比例。"),
    "Damage_Returned": ("伤害反射", "将受到的部分伤害反射给攻击者。"),
    # 状态抗性
    "Bleeding_Resistance": ("出血抗性", "抵抗出血状态的能力。"),
    "Knockback_Resistance": ("击退抗性", "抵抗被击退的能力。"),
    "Stun_Resistance": ("硬直抗性", "抵抗硬直状态的能力。"),
    "Pain_Resistance": ("疼痛抗性", "抵抗疼痛的能力。"),
    # 伤害类型抗性
    "Physical_Resistance": ("物理抗性", "减少受到的物理伤害。"),
    "Nature_Resistance": ("自然抗性", "减少受到的自然伤害。"),
    "Magic_Resistance": ("魔法抗性", "减少受到的魔法伤害。"),
    "Slashing_Resistance": ("劈砍抗性", "减少受到的劈砍伤害。"),
    "Piercing_Resistance": ("穿刺抗性", "减少受到的穿刺伤害。"),
    "Blunt_Resistance": ("钝击抗性", "减少受到的钝击伤害。"),
    "Rending_Resistance": ("撕裂抗性", "减少受到的撕裂伤害。"),
    "Fire_Resistance": ("火焰抗性", "减少受到的火焰伤害。"),
    "Shock_Resistance": ("电击抗性", "减少受到的电击伤害。"),
    "Poison_Resistance": ("毒素抗性", "减少受到的毒素伤害。"),
    "Caustic_Resistance": ("腐蚀抗性", "减少受到的腐蚀伤害。"),
    "Frost_Resistance": ("霜冻抗性", "减少受到的霜冻伤害。"),
    "Arcane_Resistance": ("秘术抗性", "减少受到的秘术伤害。"),
    "Unholy_Resistance": ("邪术抗性", "减少受到的邪术伤害。"),
    "Sacred_Resistance": ("神圣抗性", "减少受到的神圣伤害。"),
    "Psionic_Resistance": ("灵能抗性", "减少受到的灵能伤害。"),
}

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

# ============== 属性分组 ==============

# 武器属性分组
WEAPON_ATTRIBUTE_GROUPS = {
    "伤害类型": [
        "Slashing_Damage",
        "Piercing_Damage",
        "Blunt_Damage",
        "Rending_Damage",
        "Fire_Damage",
        "Shock_Damage",
        "Poison_Damage",
        "Caustic_Damage",
        "Frost_Damage",
        "Arcane_Damage",
        "Unholy_Damage",
        "Sacred_Damage",
        "Psionic_Damage",
    ],
    "战斗属性": [
        "Hit_Chance",
        "CRT",
        "CRTD",
        "CTA",
        "PRR",
        "Block_Power",
        "Block_Recovery",
        "FMB",
    ],
    "穿透破坏": ["Armor_Piercing", "Armor_Damage", "Bodypart_Damage"],
    "状态效果": [
        "Bleeding_Chance",
        "Knockback_Chance",
        "Daze_Chance",
        "Stun_Chance",
        "Immob_Chance",
        "Stagger_Chance",
    ],
    "吸血回复": ["Lifesteal", "Manasteal"],
    "生存属性": [
        "max_hp",
        "Health_Restoration",
        "Healing_Received",
        "Crit_Avoid",
        "Damage_Received",
    ],
    "精力相关": ["MP", "MP_Restoration"],
    "能量消耗": [
        "Abilities_Energy_Cost",
        "Skills_Energy_Cost",
        "Spells_Energy_Cost",
        "Cooldown_Reduction",
    ],
    "魔法属性": ["Magic_Power", "Miscast_Chance", "Miracle_Chance", "Miracle_Power"],
    "元素法力": [
        "Pyromantic_Power",
        "Geomantic_Power",
        "Venomantic_Power",
        "Cryomantic_Power",
        "Electromantic_Power",
        "Arcanistic_Power",
        "Astromantic_Power",
        "Psimantic_Power",
    ],
    "距离相关": ["Bonus_Range"],
    "其他": ["Fatigue_Gain"],
}

# 护甲属性分组
ARMOR_ATTRIBUTE_GROUPS = {
    "防护属性": ["DEF", "PRR", "Block_Power", "Block_Recovery", "EVS", "Crit_Avoid"],
    "战斗属性": [
        "FMB",
        "Hit_Chance",
        "Weapon_Damage",
        "Armor_Piercing",
        "Armor_Damage",
        "CRT",
        "CRTD",
        "CTA",
    ],
    "生存属性": [
        "Damage_Received",
        "Fortitude",
        "max_hp",
        "Health_Restoration",
        "Healing_Received",
        "Lifesteal",
        "Manasteal",
    ],
    "精力相关": [
        "MP",
        "MP_Restoration",
        "Abilities_Energy_Cost",
        "Skills_Energy_Cost",
        "Spells_Energy_Cost",
    ],
    "魔法属性": [
        "Magic_Power",
        "Miscast_Chance",
        "Miracle_Chance",
        "Miracle_Power",
        "Cooldown_Reduction",
    ],
    "元素法力": [
        "Pyromantic_Power",
        "Geomantic_Power",
        "Venomantic_Power",
        "Electromantic_Power",
        "Cryomantic_Power",
        "Arcanistic_Power",
        "Astromantic_Power",
        "Psimantic_Power",
    ],
    "状态抗性": [
        "Bleeding_Resistance",
        "Knockback_Resistance",
        "Stun_Resistance",
        "Pain_Resistance",
        "Fatigue_Gain",
    ],
    "物理伤害抗性": [
        "Physical_Resistance",
        "Slashing_Resistance",
        "Piercing_Resistance",
        "Blunt_Resistance",
        "Rending_Resistance",
    ],
    "元素伤害抗性": [
        "Fire_Resistance",
        "Shock_Resistance",
        "Poison_Resistance",
        "Caustic_Resistance",
        "Frost_Resistance",
    ],
    "魔法伤害抗性": [
        "Nature_Resistance",
        "Magic_Resistance",
        "Arcane_Resistance",
        "Unholy_Resistance",
        "Sacred_Resistance",
        "Psionic_Resistance",
    ],
    "其他": ["VSN", "Bonus_Range", "Received_XP", "Damage_Returned"],
}

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
    "Steel": "钢",
    "Iron": "铁",
    "Wood": "木",
    "Bone": "骨",
    "Leather": "皮革",
    "Cloth": "布料",
    "Silver": "银",
    "Gold": "金",
}

# 混合物品护甲类型
HYBRID_ARMOR_TYPES = {
    "Chest": "胸甲",
    "Head": "头盔",
    "Arms": "手套",
    "Legs": "靴子",
    "Waist": "腰带",
    "Back": "披风",
    "shield": "盾牌",
}

# 混合物品护甲材质
HYBRID_ARMOR_MATERIALS = {
    "metal": "金属",
    "leather": "皮革",
    "cloth": "布料",
    "wood": "木",
    "silver": "银",
    "gold": "金",
}

# 混合物品护甲类别
HYBRID_ARMOR_CLASSES = {
    "Light": "轻甲",
    "Medium": "中甲",
    "Heavy": "重甲",
}

# 混合物品属性分组（综合武器和护甲属性）
HYBRID_ATTRIBUTE_GROUPS = {
    "战斗属性": [
        "Hit_Chance",
        "CRT",
        "CRTD",
        "CTA",
        "PRR",
        "Block_Power",
        "Block_Recovery",
        "FMB",
        "EVS",
        "Crit_Avoid",
        "Weapon_Damage",
        "Armor_Piercing",
        "Armor_Damage",
        "Bodypart_Damage",
    ],
    "伤害类型": [
        "Slashing_Damage",
        "Piercing_Damage",
        "Blunt_Damage",
        "Rending_Damage",
        "Fire_Damage",
        "Shock_Damage",
        "Poison_Damage",
        "Caustic_Damage",
        "Frost_Damage",
        "Arcane_Damage",
        "Unholy_Damage",
        "Sacred_Damage",
        "Psionic_Damage",
    ],
    "状态效果": [
        "Bleeding_Chance",
        "Knockback_Chance",
        "Daze_Chance",
        "Stun_Chance",
        "Immob_Chance",
        "Stagger_Chance",
    ],
    "生存属性": [
        "max_hp",
        "Health_Restoration",
        "Healing_Received",
        "Lifesteal",
        "Manasteal",
        "Damage_Received",
        "Damage_Returned",
        "Fortitude",
        "DEF",
    ],
    "精力相关": [
        "MP",
        "MP_Restoration",
        "Abilities_Energy_Cost",
        "Skills_Energy_Cost",
        "Spells_Energy_Cost",
        "Fatigue_Gain",
    ],
    "魔法属性": [
        "Magic_Power",
        "Miscast_Chance",
        "Miracle_Chance",
        "Miracle_Power",
        "Cooldown_Reduction",
        "Bonus_Range",
    ],
    "元素法力": [
        "Pyromantic_Power",
        "Geomantic_Power",
        "Venomantic_Power",
        "Electromantic_Power",
        "Cryomantic_Power",
        "Arcanistic_Power",
        "Astromantic_Power",
        "Psimantic_Power",
    ],
    "抗性（综合）": [
        "Physical_Resistance",
        "Nature_Resistance",
        "Magic_Resistance",
    ],
    "抗性（元素）": [
        "Slashing_Resistance",
        "Piercing_Resistance",
        "Blunt_Resistance",
        "Rending_Resistance",
        "Fire_Resistance",
        "Shock_Resistance",
        "Poison_Resistance",
        "Caustic_Resistance",
        "Frost_Resistance",
        "Arcane_Resistance",
        "Unholy_Resistance",
        "Sacred_Resistance",
        "Psionic_Resistance",
    ],
    "状态抗性": [
        "Bleeding_Resistance",
        "Knockback_Resistance",
        "Stun_Resistance",
        "Pain_Resistance",
    ],
    "其他": [
        "VSN",
        "Received_XP",
    ],
}

# 常用技能对象 ID
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

# 耐久使用策略
HYBRID_DURABILITY_POLICIES = {
    "allow_to_one": "不足消耗时允许最后一次，耐久变为 1 留存",
    "destroy": "不足消耗时允许最后一次，用后删除道具",
}
# ============== 物品类型配置 ==============

ITEM_TYPE_CONFIG = {
    "weapon": {
        "type_name": "武器",
        "slot_labels": SLOT_LABELS,
        "material_labels": WEAPON_MATERIAL_LABELS,
        "tag_labels": TAG_LABELS,
        "rarity_labels": RARITY_LABELS,
        "attributes_config": WEAPON_ATTRIBUTE_GROUPS,
    },
    "armor": {
        "type_name": "装备",
        "slot_labels": ARMOR_SLOT_LABELS,
        "material_labels": ARMOR_MATERIAL_LABELS,
        "tag_labels": TAG_LABELS,
        "rarity_labels": RARITY_LABELS,
        "attributes_config": ARMOR_ATTRIBUTE_GROUPS,
    },
    "hybrid": {
        "type_name": "混合物品",
        "slot_labels": HYBRID_SLOT_LABELS,
        "material_labels": HYBRID_MATERIALS,
        "tag_labels": TAG_LABELS,
        "rarity_labels": RARITY_LABELS,
        "attributes_config": HYBRID_ATTRIBUTE_GROUPS,
    },
}
