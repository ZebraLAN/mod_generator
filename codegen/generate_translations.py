# -*- coding: utf-8 -*-
"""
翻译生成脚本

从 output_json/attributes.json 提取翻译和描述，生成可直接导入的 Python 模块。
生成的模块位于 attribute_data.py，可直接 import 使用。
"""

import json
import os

# 需要提取翻译的属性列表（按分组整理）
ATTRIBUTES_TO_EXTRACT = {
    # 伤害类型
    "Slashing_Damage", "Piercing_Damage", "Blunt_Damage", "Rending_Damage",
    "Fire_Damage", "Shock_Damage", "Poison_Damage", "Caustic_Damage",
    "Frost_Damage", "Arcane_Damage", "Unholy_Damage", "Sacred_Damage", "Psionic_Damage",

    # 战斗属性
    "Hit_Chance", "CRT", "CRTD", "CTA", "PRR", "Block_Power", "Block_Recovery",
    "FMB", "EVS", "Crit_Avoid", "Weapon_Damage", "DEF",

    # 穿透破坏
    "Armor_Piercing", "Armor_Damage", "Bodypart_Damage",

    # 状态效果
    "Bleeding_Chance", "Knockback_Chance", "Daze_Chance", "Stun_Chance",
    "Immob_Chance", "Stagger_Chance",

    # 生存属性
    "max_hp", "HP", "Health_Restoration", "Healing_Received", "Damage_Received",
    "Damage_Returned", "Lifesteal", "Manasteal", "Fortitude", "Health_Threshold", "Pain_Limit",

    # 精力相关
    "max_mp", "MP", "MP_Restoration", "Abilities_Energy_Cost",
    "Skills_Energy_Cost", "Spells_Energy_Cost", "Cooldown_Reduction", "Fatigue_Gain",
    "Max_Energy_Threshold", "Swimming_Cost",

    # 魔法属性
    "Magic_Power", "Miscast_Chance", "Miracle_Chance", "Miracle_Power",
    "Backfire_Damage", "Backfire_Damage_Change",

    # 元素法力
    "Pyromantic_Power", "Geomantic_Power", "Venomantic_Power", "Cryomantic_Power",
    "Electromantic_Power", "Arcanistic_Power", "Astromantic_Power", "Psimantic_Power",

    # 元素法力失误
    "Pyromantic_Miscast_Chance", "Geomantic_Miscast_Chance", "Venomantic_Miscast_Chance",
    "Cryomantic_Miscast_Chance", "Electromantic_Miscast_Chance", "Arcanistic_Miscast_Chance",
    "Astromantic_Miscast_Chance", "Psimantic_Miscast_Chance",

    # 抗性
    "Bleeding_Resistance", "Knockback_Resistance", "Stun_Resistance", "Pain_Resistance",
    "Physical_Resistance", "Slashing_Resistance", "Piercing_Resistance",
    "Blunt_Resistance", "Rending_Resistance",
    "Fire_Resistance", "Shock_Resistance", "Poison_Resistance", "Caustic_Resistance",
    "Frost_Resistance",
    "Nature_Resistance", "Magic_Resistance", "Arcane_Resistance",
    "Unholy_Resistance", "Sacred_Resistance", "Psionic_Resistance",

    # 其他
    "VSN", "Bonus_Range", "Received_XP", "Range", "Noise_Produced",
    "Mainhand_Efficiency", "Offhand_Efficiency", "BlockPowerBonus",
    "Immunity_Change", "Immunity_Influence",
    "ReputationGainContract", "ReputationGainGlobal",
    "STL", "Savvy", "Trade_Favorability",
    "Head_DEF", "Body_DEF", "Arms_DEF", "Legs_DEF",

    # 消耗品专用
    "Hunger", "Hunger_Change", "Hunger_Resistance", "Thirsty", "Thirst_Change",
    "Intoxication", "Toxicity_Change", "Toxicity_Resistance",
    "Pain", "Pain_Change", "Sanity", "Sanity_Change", "Morale", "Morale_Change",
    "Condition", "Immunity", "Fatigue", "Fatigue_Change",
    "max_hp_res", "max_mp_res", "HP_turn", "MP_turn",
    "Nausea_Chance", "Poisoning_Chance", "Duration",
    "SanitySituational", "MoraleSituational", "MoraleDiet", "MoraleTemporary",

    # 角色属性
    "STR", "AGL", "PRC", "Vitality", "WIL",
}

# JSON 中不存在的属性的手动翻译（仅中英文，其他语言保持英文）
# 这些属性在游戏代码中存在，但官方翻译文件中没有
MANUAL_TRANSLATIONS = {
    "Arcanistic_Distance": {"Chinese": "秘术距离", "English": "Arcanistic Distance"},
    "Arcanistic_Miscast_Chance": {"Chinese": "秘术失误几率", "English": "Arcanistic Miscast Chance"},
    "Astromantic_Miscast_Chance": {"Chinese": "星术失误几率", "English": "Astromantic Miscast Chance"},
    "Avoiding_Trap": {"Chinese": "陷阱闪避", "English": "Trap Evasion"},
    "Bleeding_Chance_Main": {"Chinese": "主手出血几率", "English": "Main Hand Bleed Chance"},
    "Bleeding_Chance_Off": {"Chinese": "副手出血几率", "English": "Off Hand Bleed Chance"},
    "Bleeding_Resistance_Hands": {"Chinese": "手臂出血抗性", "English": "Arms Bleed Resistance"},
    "Bleeding_Resistance_Head": {"Chinese": "头部出血抗性", "English": "Head Bleed Resistance"},
    "Bleeding_Resistance_Legs": {"Chinese": "腿部出血抗性", "English": "Legs Bleed Resistance"},
    "Bleeding_Resistance_Tors": {"Chinese": "躯干出血抗性", "English": "Torso Bleed Resistance"},
    "BlockPowerBonus": {"Chinese": "格挡力量加成", "English": "Block Power Bonus"},
    "CRT_Main": {"Chinese": "主手暴击几率", "English": "Main Hand Crit Chance"},
    "CRT_Off": {"Chinese": "副手暴击几率", "English": "Off Hand Crit Chance"},
    "CRTD_Main": {"Chinese": "主手暴击效果", "English": "Main Hand Crit Efficiency"},
    "CRTD_Off": {"Chinese": "副手暴击效果", "English": "Off Hand Crit Efficiency"},
    "Charge_Distance": {"Chinese": "冲锋距离", "English": "Charge Distance"},
    "Cryomantic_Miscast_Chance": {"Chinese": "冰术失误几率", "English": "Cryomantic Miscast Chance"},
    "Duration_Resistance": {"Chinese": "持续效果抗性", "English": "Duration Resistance"},
    "Electromantic_Miscast_Chance": {"Chinese": "电术失误几率", "English": "Electromantic Miscast Chance"},
    "Geomantic_Miscast_Chance": {"Chinese": "地术失误几率", "English": "Geomantic Miscast Chance"},
    "HP_turn": {"Chinese": "每回合生命", "English": "Health per Turn"},
    "Immunity_Influence": {"Chinese": "免疫影响", "English": "Immunity Influence"},
    "Psimantic_Miscast_Chance": {"Chinese": "灵术失误几率", "English": "Psimantic Miscast Chance"},
    "Pyromantic_Miscast_Chance": {"Chinese": "火术失误几率", "English": "Pyromantic Miscast Chance"},
    "ReputationGainContract": {"Chinese": "契约声望加成", "English": "Contract Reputation Gain"},
    "Venomantic_Miscast_Chance": {"Chinese": "毒术失误几率", "English": "Venomantic Miscast Chance"},
    "Weapon_Damage_Main": {"Chinese": "主手兵器伤害", "English": "Main Hand Weapon Damage"},
    "Weapon_Damage_Off": {"Chinese": "副手兵器伤害", "English": "Off Hand Weapon Damage"},
}

# JSON 中不存在的属性的手动描述（仅中英文）
# 对应 MANUAL_TRANSLATIONS 中的属性
MANUAL_DESCRIPTIONS = {
    "Arcanistic_Distance": {
        "Chinese": "增加秘术系技能的施法距离。",
        "English": "Increases the casting range of Arcanistic skills.",
    },
    "Avoiding_Trap": {
        "Chinese": "触发陷阱时的闪避几率。基于公式：(25 + 闪躲 + buff) × 倍率计算。",
        "English": "Chance to evade traps when triggered. Calculated as (25 + EVS + buff) × multiplier.",
    },
    "BlockPowerBonus": {
        "Chinese": "作为百分比乘法加成格挡力量。例如：20表示格挡力量增加20%。",
        "English": "Percentage bonus to Block Power. E.g., 20 means +20% Block Power.",
    },
    "Charge_Distance": {
        "Chinese": "增加冲锋类技能的施放距离。",
        "English": "Increases the range of Charge-type skills.",
    },
    "Duration_Resistance": {
        "Chinese": "减少敌方持续效果的作用时长。",
        "English": "Reduces the duration of enemy debuffs.",
    },
    "HP_turn": {
        "Chinese": "每回合固定恢复或损失的生命值。正值恢复，负值损失。仅在脱战时生效。",
        "English": "Health gained or lost per turn. Positive heals, negative damages. Only works out of combat.",
    },
    "Immunity_Influence": {
        "Chinese": "加速迷醉消退速度。值范围1-10。",
        "English": "Speeds up intoxication decay. Range: 1-10.",
    },
    "ReputationGainContract": {
        "Chinese": "完成契约任务时获得的声望加成（百分比）。",
        "English": "Percentage bonus to reputation gained from completing contracts.",
    },
    "STL": {
        "Chinese": "隐匿值，影响潜行时敌人发现你的速度。正值降低发现速度，负值增加。",
        "English": "Stealth. Affects how quickly enemies detect you while sneaking. Positive reduces detection, negative increases it.",
    },
    "Savvy": {
        "Chinese": "机敏，影响撬锁和拆卸陷阱的成功率。",
        "English": "Savvy. Affects success rate of lockpicking and disarming traps.",
    },
    "Trade_Favorability": {
        "Chinese": "交易好感度，作为折扣影响商店售价。正值降低价格，负值提高价格。",
        "English": "Trade discount affecting shop prices. Positive lowers prices, negative raises them.",
    },
}

# 语言映射 (JSON 中的语言名 -> 我们使用的语言名)
LANG_MAP = {
    "English": "English",
    "中文": "Chinese",
    "Русский": "Russian",
    "Deutsch": "German",
    "Español (LATAM)": "Spanish",
    "Français": "French",
    "Italiano": "Italian",
    "Português": "Portuguese",
    "Polski": "Polish",
    "Türkçe": "Turkish",
    "日本語": "Japanese",
    " 한국어": "Korean",  # 注意有个空格前缀
}


def load_attributes_json(path: str = "output_json/attributes.json") -> dict:
    """加载 attributes.json"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_data(data: dict, attrs: set) -> tuple[dict, dict]:
    """从 JSON 数据中提取指定属性的翻译和描述

    Returns:
        (translations, descriptions) 两个字典
        translations: {attr_key: {lang: translation}}
        descriptions: {attr_key: {lang: description}}
    """
    translations = {}
    descriptions = {}

    attr_text = data.get("attribute_text", {})
    attr_desc = data.get("attribute_desc", {})

    for attr in attrs:
        # 提取翻译
        if attr in attr_text:
            trans = {}
            for json_lang, our_lang in LANG_MAP.items():
                if json_lang in attr_text[attr]:
                    val = attr_text[attr][json_lang]
                    if val and val != "N/A":
                        trans[our_lang] = val
            if trans:
                translations[attr] = trans
        else:
            print(f"警告: 属性 '{attr}' 的翻译在 attributes.json 中未找到")

        # 提取描述
        if attr in attr_desc:
            desc = {}
            for json_lang, our_lang in LANG_MAP.items():
                if json_lang in attr_desc[attr]:
                    val = attr_desc[attr][json_lang]
                    if val and val != "N/A":
                        desc[our_lang] = val
            if desc:
                descriptions[attr] = desc

    return translations, descriptions


def generate_python_module(translations: dict, descriptions: dict) -> str:
    """生成可直接导入的 Python 模块代码"""
    lines = [
        '# -*- coding: utf-8 -*-',
        '"""',
        '属性数据模块 (自动生成，请勿手动编辑)',
        '由 generate_translations.py 从 output_json/attributes.json 生成',
        '',
        '使用方式:',
        '    from attribute_data import ATTRIBUTE_TRANSLATIONS, ATTRIBUTE_DESCRIPTIONS',
        '"""',
        '',
        '# 属性名称翻译',
        'ATTRIBUTE_TRANSLATIONS = {'
    ]

    for attr in sorted(translations.keys()):
        lang_dict = translations[attr]
        lines.append(f'    "{attr}": {{')
        for lang in ["Chinese", "English", "Russian", "German", "Spanish",
                     "French", "Italian", "Portuguese", "Polish", "Turkish",
                     "Japanese", "Korean"]:
            if lang in lang_dict:
                val = lang_dict[lang].replace('"', '\\"').replace('\n', '\\n')
                lines.append(f'        "{lang}": "{val}",')
        lines.append("    },")

    lines.append("}")
    lines.append("")
    lines.append("# 属性描述/解释")
    lines.append("ATTRIBUTE_DESCRIPTIONS = {")

    for attr in sorted(descriptions.keys()):
        lang_dict = descriptions[attr]
        lines.append(f'    "{attr}": {{')
        for lang in ["Chinese", "English", "Russian", "German", "Spanish",
                     "French", "Italian", "Portuguese", "Polish", "Turkish",
                     "Japanese", "Korean"]:
            if lang in lang_dict:
                val = lang_dict[lang].replace('"', '\\"').replace('\n', '\\n')
                lines.append(f'        "{lang}": "{val}",')
        lines.append("    },")

    lines.append("}")

    return "\n".join(lines)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # codegen -> project root
    json_path = os.path.join(project_root, "game_data", "attributes.json")

    if not os.path.exists(json_path):
        print(f"错误: 找不到 {json_path}")
        return

    print(f"加载 {json_path}...")
    data = load_attributes_json(json_path)

    print(f"提取 {len(ATTRIBUTES_TO_EXTRACT)} 个属性的翻译和描述...")
    translations, descriptions = extract_data(data, ATTRIBUTES_TO_EXTRACT)

    print(f"成功提取 {len(translations)} 个属性的翻译")
    print(f"成功提取 {len(descriptions)} 个属性的描述")

    # 合并手动翻译
    print(f"合并 {len(MANUAL_TRANSLATIONS)} 个手动翻译...")
    for attr, trans in MANUAL_TRANSLATIONS.items():
        if attr not in translations:
            translations[attr] = trans
        else:
            # 合并但不覆盖已有的翻译
            for lang, text in trans.items():
                if lang not in translations[attr]:
                    translations[attr][lang] = text

    print(f"最终共 {len(translations)} 个属性翻译")

    # 合并手动描述
    print(f"合并 {len(MANUAL_DESCRIPTIONS)} 个手动描述...")
    for attr, desc in MANUAL_DESCRIPTIONS.items():
        if attr not in descriptions:
            descriptions[attr] = desc
        else:
            # 合并但不覆盖已有的描述
            for lang, text in desc.items():
                if lang not in descriptions[attr]:
                    descriptions[attr][lang] = text

    print(f"最终共 {len(descriptions)} 个属性描述")

    code = generate_python_module(translations, descriptions)

    # 生成可直接导入的模块
    output_path = os.path.join(project_root, "attribute_data.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"已生成: {output_path}")
    print("可直接使用: from attribute_data import ATTRIBUTE_TRANSLATIONS, ATTRIBUTE_DESCRIPTIONS")


if __name__ == "__main__":
    main()
