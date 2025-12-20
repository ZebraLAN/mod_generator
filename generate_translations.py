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
    json_path = os.path.join(script_dir, "output_json", "attributes.json")
    
    if not os.path.exists(json_path):
        print(f"错误: 找不到 {json_path}")
        return
    
    print(f"加载 {json_path}...")
    data = load_attributes_json(json_path)
    
    print(f"提取 {len(ATTRIBUTES_TO_EXTRACT)} 个属性的翻译和描述...")
    translations, descriptions = extract_data(data, ATTRIBUTES_TO_EXTRACT)
    
    print(f"成功提取 {len(translations)} 个属性的翻译")
    print(f"成功提取 {len(descriptions)} 个属性的描述")
    
    code = generate_python_module(translations, descriptions)
    
    # 生成可直接导入的模块
    output_path = os.path.join(script_dir, "attribute_data.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)
    
    print(f"已生成: {output_path}")
    print("可直接使用: from attribute_data import ATTRIBUTE_TRANSLATIONS, ATTRIBUTE_DESCRIPTIONS")


if __name__ == "__main__":
    main()
