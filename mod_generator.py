import copy
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog
from typing import Any, Dict, List

import glfw
import imgui
import tkinter as tk
from imgui.integrations.glfw import GlfwRenderer
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_NEAREST,
    GL_RGBA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_UNSIGNED_BYTE,
    glBindTexture,
    glClear,
    glClearColor,
    glDeleteTextures,
    glGenTextures,
    glTexImage2D,
    glTexParameteri,
)

try:
    from PIL import Image
except ImportError:
    Image = None

# 定义枚举类型
WEAPONS_TIER = ["Tier1", "Tier2", "Tier3", "Tier4", "Tier5"]
WEAPONS_SLOT = [
    "sword",
    "axe",
    "mace",
    "dagger",
    "twohandedsword",
    "spear",
    "twohandedaxe",
    "twohandedmace",
    "bow",
    "crossbow",
    "sling",
    "twohandedstaff",
    "chain",
    "lute",
]
WEAPONS_RARITY = ["Common", "Unique"]
WEAPONS_MATERIAL = ["wood", "metal", "leather"]

TIER_LABELS = {tier: str(idx + 1) for idx, tier in enumerate(WEAPONS_TIER)}
HIDDEN_SLOTS = {"sling"}
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
MATERIAL_LABELS = {"leather": "皮", "wood": "木", "metal": "金属"}
RARITY_LABELS = {"Common": "普通", "Unique": "独特"}
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
ALLOWED_TAGS = list(TAG_LABELS.keys())
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

# 游戏实际帧率 (Stoneshard 运行在约 40fps)
GAME_FPS = 40

# 预览动画帧率 (游戏帧率的 1/4，手持贴图在游戏中默认以此速度播放)
PREVIEW_ANIMATION_FPS = GAME_FPS // 4  # = 10 fps

# 渲染坐标系常量
GML_ANCHOR_X = 22  # 游戏内默认原点 X (相对于人物/武器贴图左上角)
GML_ANCHOR_Y = 34  # 游戏内默认原点 Y (相对于人物/武器贴图左上角)
CHAR_IMG_W = 48  # 人物贴图宽
CHAR_IMG_H = 40  # 人物贴图高
CHAR_CENTER_X = CHAR_IMG_W // 2  # 人物中心 X (24)
CHAR_CENTER_Y = CHAR_IMG_H // 2  # 人物中心 Y (20)
VALID_AREA_SIZE = 64  # 有效显示区域边长 (64x64)

# 有效区域相对于人物贴图左上角的坐标
# ValidRect = [Center - 32, Center + 32]
VALID_MIN_X = CHAR_CENTER_X - VALID_AREA_SIZE // 2  # -8
VALID_MAX_X = CHAR_CENTER_X + VALID_AREA_SIZE // 2  # 56
VALID_MIN_Y = CHAR_CENTER_Y - VALID_AREA_SIZE // 2  # -12
VALID_MAX_Y = CHAR_CENTER_Y + VALID_AREA_SIZE // 2  # 52

# 视口绘制时人物相对于64x64框左上角的偏移
# 64x64框的中心是 (32, 32)，人物中心是 (24, 20)
# 偏移 = 视口中心 - 人物中心
VIEWPORT_CHAR_OFFSET_X = VALID_AREA_SIZE // 2 - CHAR_CENTER_X  # = 32 - 24 = 8
VIEWPORT_CHAR_OFFSET_Y = VALID_AREA_SIZE // 2 - CHAR_CENTER_Y  # = 32 - 20 = 12

# 注意：VIEWPORT_CHAR_OFFSET 等价于 -VALID_MIN，这在 _calculate_adjusted_offsets 中使用

# 属性描述
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
    "Fatigue_Gain": ("疲劳抗性", "影响你疲劳的速度。"),
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
}

# Byte类型的属性 (需要限制为 0-255)
BYTE_ATTRIBUTES = {
    "Bleeding_Chance",
    "Daze_Chance",
    "Stun_Chance",
    "Knockback_Chance",
    "Immob_Chance",
    "Stagger_Chance",
}

# 属性分组 (用于编辑器UI)
ATTRIBUTE_GROUPS = {
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
    "魔法属性": [
        "Magic_Power",
        "Miscast_Chance",
        "Miracle_Chance",
        "Miracle_Power",
    ],
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

CHARACTER_MODELS = {
    "Human Male": ["s_human_male_0.png", "s_human_male_1.png"],
    "Human Female": ["s_human_female_0.png", "s_human_female_1.png"],
    "Dwarf Male": ["s_dwarf_male_0.png", "s_dwarf_male_1.png"],
    "Dwarf Female": ["s_dwarf_female_0.png", "s_dwarf_female_1.png"],
    "Elf Male": ["s_elf_male_0.png", "s_elf_male_1.png"],
}

CHARACTER_MODEL_LABELS = {
    "Human Male": "人类男性",
    "Human Female": "人类女性",
    "Dwarf Male": "矮人男性",
    "Dwarf Female": "矮人女性",
    "Elf Male": "精灵男性",
}


# 主语言配置（暂时固定为中文，未来可配置）
PRIMARY_LANGUAGE = "Chinese"

# 支持的所有语言
SUPPORTED_LANGUAGES = [
    "Chinese",
    "English",
    "Русский",
    "Deutsch",
    "Español (LATAM)",
    "Français",
    "Italiano",
    "Português",
    "Polski",
    "Türkçe",
    "日本語",
    "한국어",
]

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


@dataclass
class WeaponLocalization:
    """武器本地化数据

    所有语言统一存储在 languages 字典中。
    格式: {"Chinese": {"name": "...", "description": "..."}, "English": {...}, ...}
    """

    languages: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def get_name(self, lang: str) -> str:
        """获取指定语言的名称"""
        return self.languages.get(lang, {}).get("name", "")

    def set_name(self, lang: str, value: str) -> None:
        """设置指定语言的名称"""
        if lang not in self.languages:
            self.languages[lang] = {"name": "", "description": ""}
        self.languages[lang]["name"] = value

    def get_description(self, lang: str) -> str:
        """获取指定语言的描述"""
        return self.languages.get(lang, {}).get("description", "")

    def set_description(self, lang: str, value: str) -> None:
        """设置指定语言的描述"""
        if lang not in self.languages:
            self.languages[lang] = {"name": "", "description": ""}
        self.languages[lang]["description"] = value

    def has_language(self, lang: str) -> bool:
        """检查是否有指定语言的数据"""
        return lang in self.languages

    def get_display_name(self) -> str:
        """获取用于显示的名称（优先主语言，其次英语）"""
        name = self.get_name(PRIMARY_LANGUAGE)
        if not name:
            name = self.get_name("English")
        return name or "未命名"


@dataclass
class WeaponTextures:
    character: str = ""  # 手持状态贴图
    inventory: List[str] = field(default_factory=lambda: [""])  # 常规贴图列表
    loot: str = ""  # 战利品贴图
    character_left: str = ""  # 左手持握贴图 (部分单手武器需要)
    offset_x: int = 0  # 水平偏移 (右手/默认)
    offset_y: int = 0  # 垂直偏移 (右手/默认)
    offset_x_left: int = 0  # 水平偏移 (左手)
    offset_y_left: int = 0  # 垂直偏移 (左手)

    # 帧动画支持
    character_frames: List[str] = field(default_factory=list)
    character_left_frames: List[str] = field(default_factory=list)
    loot_frames: List[str] = field(default_factory=list)

    # 战利品贴图动画设置
    loot_fps: float = 10.0  # 战利品贴图播放帧率/相对帧率
    loot_use_relative_speed: bool = False  # 是否使用相对帧率模式


@dataclass
class Weapon:
    name: str = ""  # 实质性标识
    tier: str = "Tier2"
    slot: str = "sword"
    rarity: str = "Common"
    mat: str = "metal"
    tags: str = "aldor"
    price: int = 100
    markup: int = 1
    max_duration: int = 100
    rng: int = 1

    # 属性字段
    attributes: Dict[str, Any] = field(default_factory=dict)

    # 本地化
    localization: WeaponLocalization = field(default_factory=WeaponLocalization)

    # 贴图
    textures: WeaponTextures = field(default_factory=WeaponTextures)

    fireproof: bool = False
    no_drop: bool = False

    @property
    def id(self) -> str:
        """根据name自动生成id"""
        return self.name.lower().replace(" ", "").replace("'", "")

    def validate(self, project=None) -> List[str]:
        """验证武器数据的完整性"""
        errors = []

        # 自动移除首尾空格（虽然主要在保存/生成时处理，这里也处理一下以防万一）
        self.name = self.name.strip()

        if not self.name:
            errors.append("武器系统ID不能为空")
        elif not re.match(r"^[A-Za-z][A-Za-z0-9 ]*$", self.name):
            errors.append(
                "武器系统ID格式错误: 必须以字母开头，只能包含字母、数字和空格"
            )

        if project:
            # 检查ID唯一性 (id 属性是 lower() 后的)
            current_id = self.id
            count = 0
            for w in project.weapons:
                if w.id == current_id:
                    count += 1
            if count > 1:
                errors.append(
                    f"武器系统ID '{self.name}' (ID: {current_id}) 重复，请确保唯一"
                )

        if not self.textures.character:
            errors.append("必须提供手持状态贴图")

        # 检查单手武器的左手贴图
        if self.slot in LEFT_HAND_SLOTS:
            if not self.textures.character_left:
                slot_name = SLOT_LABELS.get(self.slot, self.slot)
                errors.append(f"槽位为 '{slot_name}' 的武器必须提供左手手持贴图")

        if not self.textures.loot:
            errors.append("必须提供战利品贴图")

        if not self.textures.inventory or not any(
            tex for tex in self.textures.inventory
        ):
            errors.append("至少需要提供一张常规贴图")

        return errors


@dataclass
class ModProject:
    name: str = "我的新模组"
    code_name: str = "MyNewMod"
    author: str = ""
    description: str = "使用 Stoneshard Weapon Mod Editor 生成"
    version: str = "1.0.0"
    target_version: str = "0.9.3.13"
    weapons: List[Weapon] = field(default_factory=list)
    file_path: str = ""  # 项目文件路径

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
            # 确保 file_path 指向的是 project.json
            if not file_path.endswith("project.json"):
                # 如果用户选的是目录或没有后缀，我们假设这是项目根目录
                if os.path.isdir(file_path):
                    file_path = os.path.join(file_path, "project.json")
                else:
                    # 否则强制命名为 project.json
                    file_path = os.path.join(os.path.dirname(file_path), "project.json")
            self.file_path = file_path

        if not self.file_path:
            return False

        # 确保 assets 目录存在
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
        }

        for weapon in self.weapons:
            # 自动移除首尾空格
            weapon.name = weapon.name.strip()

            # 处理贴图路径：转换为相对路径
            rel_char_path = self._get_relative_path(
                weapon.textures.character, project_dir
            )
            rel_char_left_path = self._get_relative_path(
                weapon.textures.character_left, project_dir
            )
            rel_loot_path = self._get_relative_path(weapon.textures.loot, project_dir)
            rel_inv_paths = [
                self._get_relative_path(p, project_dir)
                for p in weapon.textures.inventory
            ]

            weapon_data = {
                "name": weapon.name,
                "tier": weapon.tier,
                "slot": weapon.slot,
                "rarity": weapon.rarity,
                "mat": weapon.mat,
                "tags": weapon.tags,
                "price": weapon.price,
                "markup": 1,
                "max_duration": weapon.max_duration,
                "rng": weapon.rng,
                "attributes": weapon.attributes,
                "fireproof": weapon.fireproof,
                "no_drop": weapon.no_drop,
                "localization": weapon.localization.languages,
                "textures": {
                    "character": rel_char_path,
                    "character_left": rel_char_left_path,
                    "inventory": rel_inv_paths,
                    "loot": rel_loot_path,
                    "offset_x": weapon.textures.offset_x,
                    "offset_y": weapon.textures.offset_y,
                    "offset_x_left": weapon.textures.offset_x_left,
                    "offset_y_left": weapon.textures.offset_y_left,
                    "character_frames": [
                        self._get_relative_path(p, project_dir)
                        for p in weapon.textures.character_frames
                    ],
                    "character_left_frames": [
                        self._get_relative_path(p, project_dir)
                        for p in weapon.textures.character_left_frames
                    ],
                    "loot_frames": [
                        self._get_relative_path(p, project_dir)
                        for p in weapon.textures.loot_frames
                    ],
                    "loot_fps": round(
                        weapon.textures.loot_fps, 3
                    ),  # 保存时四舍五入确保精度一致
                    "loot_use_relative_speed": weapon.textures.loot_use_relative_speed,
                },
            }
            data["weapons"].append(weapon_data)

        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True

    def _get_relative_path(self, path: str, project_dir: str) -> str:
        """将绝对路径转换为相对于项目目录的路径，如果是外部文件则不处理（应当在导入时处理）"""
        if not path:
            return ""
        try:
            # 如果路径已经在项目目录下，直接转相对路径
            if os.path.commonpath(
                [project_dir, os.path.abspath(path)]
            ) == os.path.abspath(project_dir):
                return os.path.relpath(path, project_dir)
        except ValueError:
            pass
        # 否则返回原路径（可能是绝对路径，意味着尚未导入到 assets）
        return path

    def _resolve_path(self, path: str, project_dir: str) -> str:
        """将相对路径转换为绝对路径（用于加载项目时）"""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(project_dir, path))

    def import_texture(self, source_path: str) -> str:
        """将外部贴图复制到项目 assets 目录并返回相对路径"""
        if not source_path or not os.path.exists(source_path):
            return ""

        # 项目路径必须存在（新建项目时已强制设定）
        if not self.file_path:
            return source_path

        project_dir = os.path.dirname(self.file_path)
        assets_dir = os.path.join(project_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        file_name = os.path.basename(source_path)
        # 避免文件名冲突，可以添加时间戳或哈希，这里简单处理：如果存在则覆盖
        # 更好的做法可能是检查内容哈希，这里先直接复制
        dest_path = os.path.join(assets_dir, file_name)

        # 如果源文件和目标文件相同，不做操作
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            try:
                shutil.copy2(source_path, dest_path)
            except Exception as e:
                print(f"复制贴图失败: {e}")
                return source_path

        return os.path.relpath(dest_path, project_dir)

    def load(self, file_path: str):
        """从文件加载项目

        Returns:
            bool: 加载成功返回 True，失败返回 False
        """
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

        self.weapons = []
        for weapon_data in data.get("weapons", []):
            weapon = Weapon(
                name=weapon_data["name"],
                tier=weapon_data.get("tier", "Tier2"),
                slot=weapon_data.get("slot", "sword"),
                rarity=weapon_data.get("rarity", "Common"),
                mat=weapon_data.get("mat", "metal"),
                tags=weapon_data.get("tags", "aldor"),
                price=weapon_data.get("price", 100),
                max_duration=weapon_data.get("max_duration", 100),
                rng=weapon_data.get("rng", 1),
                attributes=weapon_data.get("attributes", {}),
            )
            weapon.fireproof = weapon_data.get("fireproof", False)
            weapon.no_drop = weapon_data.get("no_drop", False)

            loc_data = weapon_data.get("localization", {})

            # 兼容多种旧格式
            if "languages" in loc_data:
                # 旧格式 v2: {"languages": {...}}
                weapon.localization = WeaponLocalization(
                    languages=loc_data.get("languages", {})
                )
            elif "chinese_name" in loc_data or "other_languages" in loc_data:
                # 旧格式 v1: {"chinese_name": ..., "other_languages": {...}}
                languages = {}
                chn_name = loc_data.get("chinese_name", "")
                chn_desc = loc_data.get("chinese_description", "")
                if chn_name or chn_desc:
                    languages["Chinese"] = {"name": chn_name, "description": chn_desc}
                other_langs = loc_data.get("other_languages", {})
                for lang, data in other_langs.items():
                    languages[lang] = {
                        "name": data.get("name", ""),
                        "description": data.get("description", ""),
                    }
                weapon.localization = WeaponLocalization(languages=languages)
            else:
                # 新格式: 直接是 languages 字典
                weapon.localization = WeaponLocalization(languages=loc_data)

            tex_data = weapon_data.get("textures", {})

            # 处理贴图路径：将相对路径转为绝对路径以便程序使用
            inventory_list = tex_data.get("inventory")
            if inventory_list is None:
                inventory_list = []
                for key in ("inventory0", "inventory1", "inventory2"):
                    if key in tex_data:
                        inventory_list.append(tex_data.get(key, ""))
                if not inventory_list:
                    inventory_list = [""]

            # 解析路径
            char_path = self._resolve_path(tex_data.get("character", ""), project_dir)
            char_left_path = self._resolve_path(
                tex_data.get("character_left", ""), project_dir
            )
            loot_path = self._resolve_path(tex_data.get("loot", ""), project_dir)
            inv_paths = [self._resolve_path(p, project_dir) for p in inventory_list]

            # 解析帧动画路径
            char_frames = [
                self._resolve_path(p, project_dir)
                for p in tex_data.get("character_frames", [])
            ]
            char_left_frames = [
                self._resolve_path(p, project_dir)
                for p in tex_data.get("character_left_frames", [])
            ]
            loot_frames = [
                self._resolve_path(p, project_dir)
                for p in tex_data.get("loot_frames", [])
            ]

            weapon.textures = WeaponTextures(
                character=char_path,
                character_left=char_left_path,
                inventory=inv_paths,
                loot=loot_path,
                offset_x=tex_data.get("offset_x", 0),
                offset_y=tex_data.get("offset_y", 0),
                offset_x_left=tex_data.get("offset_x_left", 0),
                offset_y_left=tex_data.get("offset_y_left", 0),
                character_frames=char_frames,
                character_left_frames=char_left_frames,
                loot_frames=loot_frames,
                loot_fps=round(
                    tex_data.get("loot_fps", 10), 3
                ),  # 四舍五入确保所见即所得
                loot_use_relative_speed=tex_data.get("loot_use_relative_speed", False),
            )

            self.weapons.append(weapon)

        # 加载后执行清理和检查
        self.clean_invalid_data()
        self.clean_unused_assets()

        return True

    def clean_invalid_data(self):
        """清理无效的武器数据（如非左手武器的左手贴图信息）"""
        for weapon in self.weapons:
            # 清理左手贴图数据
            if weapon.slot not in LEFT_HAND_SLOTS:
                weapon.textures.character_left = ""
                weapon.textures.character_left_frames = []
                weapon.textures.offset_x_left = 0
                weapon.textures.offset_y_left = 0

    def clean_unused_assets(self):
        """清理未使用的资源文件"""
        if not self.file_path:
            return

        project_dir = os.path.dirname(self.file_path)
        assets_dir = os.path.join(project_dir, "assets")

        if not os.path.exists(assets_dir):
            return

        # 收集所有使用的文件路径
        used_files = set()
        for weapon in self.weapons:
            paths = []
            paths.append(weapon.textures.character)
            paths.append(weapon.textures.character_left)
            paths.append(weapon.textures.loot)
            paths.extend(weapon.textures.inventory)
            paths.extend(weapon.textures.character_frames)
            paths.extend(weapon.textures.character_left_frames)
            paths.extend(weapon.textures.loot_frames)

            for p in paths:
                if p:
                    # 统一转换为绝对路径以便比较
                    if not os.path.isabs(p):
                        full_p = os.path.join(project_dir, p)
                    else:
                        full_p = p
                    used_files.add(os.path.normpath(full_p).lower())

        # 遍历 assets 目录
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

    def import_project(self, other_project_path: str):
        """导入另一个项目

        Returns:
            tuple: (success: bool, message: str, conflicts: list)
        """
        other_project = ModProject()
        if not other_project.load(other_project_path):
            return False, "无法加载项目文件", []

        imported_count = 0
        conflicts = []

        for weapon in other_project.weapons:
            # 检查名称冲突
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


class ModGeneratorGUI:
    def __init__(self):
        self.window = None
        self.error_message = ""

        if not glfw.init():
            print("无法初始化 GLFW")
            sys.exit(1)

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)

        self.window = glfw.create_window(
            1200, 800, "Stoneshard 武器模组编辑器", None, None
        )
        if not self.window:
            glfw.terminate()
            print("无法创建 GLFW 窗口")
            sys.exit(1)

        glfw.make_context_current(self.window)
        imgui.create_context()
        self.io = imgui.get_io()
        self.renderer = GlfwRenderer(self.window)

        # 确保字体目录存在
        if not os.path.exists("fonts"):
            os.makedirs("fonts", exist_ok=True)

        # 尝试将旧字体移动到 fonts 目录 (如果存在)
        old_font = "HanyiSentyYongleEncyclopedia-2020.ttf"
        new_font = os.path.join("fonts", old_font)
        if os.path.exists(old_font) and not os.path.exists(new_font):
            try:
                shutil.move(old_font, new_font)
                print(f"已将 {old_font} 移动到 fonts 目录")
            except Exception as e:
                print(f"移动字体文件失败: {e}")

        # 配置项
        self.font_size = 16  # 默认字号调整为 16
        self.primary_font_path = ""  # 主字体（英文）
        self.fallback_font_path = ""  # 备用字体（中文）
        self.is_dark_theme = True
        self.texture_scale = 4.0  # 默认贴图显示倍率
        self.should_reload_fonts = False  # 延迟加载字体标记

        # 加载配置
        self.load_config()

        # 应用主题
        self.apply_theme()

        # 加载字体 (启动时直接加载)
        self.reload_fonts()

        self.project = ModProject()
        self.current_weapon_index = -1
        self.show_import_dialog = False
        self.import_file_path = ""
        self.import_conflicts = []  # 存储导入冲突信息
        self.current_texture_field = ""
        self.texture_preview_cache = {}
        self.selected_model = "Human Male"  # 默认模特组
        self.preview_states = {}  # 存储预览状态 (paused, current_frame)

        # 弹窗状态
        self.show_error_popup = False
        self.show_save_popup = False
        self.show_success_popup = False

    def load_config(self):
        """加载用户配置"""
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.font_size = config.get("font_size", 16)
                    self.primary_font_path = config.get("primary_font_path", "")
                    self.fallback_font_path = config.get("fallback_font_path", "")
                    self.is_dark_theme = config.get("is_dark_theme", True)
                    self.texture_scale = config.get("texture_scale", 4.0)  # 默认改为4.0
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save_config(self):
        """保存用户配置"""
        config = {
            "font_size": self.font_size,
            "primary_font_path": self.primary_font_path,
            "fallback_font_path": self.fallback_font_path,
            "is_dark_theme": self.is_dark_theme,
            "texture_scale": self.texture_scale,
        }
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def apply_theme(self):
        """应用颜色主题"""
        if self.is_dark_theme:
            imgui.style_colors_dark()
        else:
            imgui.style_colors_light()

    def reload_fonts(self):
        """重新加载字体 (主字体 + 备用字体)"""
        # 清除旧字体
        self.io.fonts.clear()

        print(f"加载字体 (Size: {self.font_size})...")

        # 1. 加载英文字体 (主字体)
        primary_loaded = False
        if self.primary_font_path:
            # 检查是否是 bundled 字体
            bundled_path = os.path.join("fonts", "english", self.primary_font_path)
            target_path = ""
            if os.path.exists(bundled_path):
                target_path = bundled_path
            elif os.path.exists(self.primary_font_path):
                target_path = self.primary_font_path

            if target_path:
                try:
                    print(f"加载英文字体: {target_path}")
                    self.io.fonts.add_font_from_file_ttf(
                        target_path,
                        self.font_size,
                        glyph_ranges=self.io.fonts.get_glyph_ranges_default(),
                    )
                    primary_loaded = True
                except Exception as e:
                    print(f"英文字体加载失败: {e}")

        # 默认尝试系统英文字体
        if not primary_loaded:
            default_english = "C:/Windows/Fonts/arial.ttf"
            if os.path.exists(default_english):
                try:
                    print(f"加载默认英文字体: {default_english}")
                    self.io.fonts.add_font_from_file_ttf(
                        default_english,
                        self.font_size,
                        glyph_ranges=self.io.fonts.get_glyph_ranges_default(),
                    )
                    primary_loaded = True
                except Exception as e:
                    print(f"加载默认英文字体失败: {e}")

            # 如果还是不行，使用 imgui 默认字体
            if not primary_loaded:
                print("使用 ImGui 默认字体")
                self.io.fonts.add_font_default()

        # 2. 加载中文字体 (备用字体) - Merge Mode

        # 确定中文字体路径
        target_fallback_path = ""
        if self.fallback_font_path:
            bundled_path = os.path.join("fonts", "chinese", self.fallback_font_path)
            if os.path.exists(bundled_path):
                target_fallback_path = bundled_path
            elif os.path.exists(self.fallback_font_path):
                target_fallback_path = self.fallback_font_path

        # 如果未设置，尝试默认 bundled 中文字体
        if not target_fallback_path:
            default_bundled = os.path.join(
                "fonts", "chinese", "HanyiSentyYongleEncyclopedia-2020.ttf"
            )
            if os.path.exists(default_bundled):
                target_fallback_path = default_bundled
            else:
                # 最后的退路：SimHei
                if os.path.exists("C:/Windows/Fonts/simhei.ttf"):
                    target_fallback_path = "C:/Windows/Fonts/simhei.ttf"

        if target_fallback_path:
            try:
                # 准备 Merge 配置
                font_config = imgui.core.FontConfig(merge_mode=True)

                try:
                    ranges = self.io.fonts.get_glyph_ranges_chinese_full()
                except AttributeError:
                    # 某些 pyimgui 版本可能没有 get_glyph_ranges_chinese_full
                    ranges = self.io.fonts.get_glyph_ranges_chinese()

                print(f"加载中文字体 (Merge): {target_fallback_path}")
                self.io.fonts.add_font_from_file_ttf(
                    target_fallback_path,
                    self.font_size,
                    font_config=font_config,
                    glyph_ranges=ranges,
                )
                print("中文字体加载成功")
            except Exception as e:
                print(f"中文字体加载失败: {e}")

                # 尝试微软雅黑作为最后的备用
                if "msyh" not in target_fallback_path and os.path.exists(
                    "C:/Windows/Fonts/msyh.ttc"
                ):
                    try:
                        print("尝试合并微软雅黑...")
                        self.io.fonts.add_font_from_file_ttf(
                            "C:/Windows/Fonts/msyh.ttc",
                            self.font_size,
                            font_config=font_config,
                            glyph_ranges=self.io.fonts.get_glyph_ranges_chinese_full(),
                        )
                    except Exception as e2:
                        print(f"微软雅黑加载失败: {e2}")

        # 刷新纹理
        try:
            self.renderer.refresh_font_texture()
            # 重新计算全局样式 (例如 scaling)
            # 在 pyimgui 中，style scaling 通常是自动处理的，或者需要手动设置 io.font_global_scale
            # 但这里的场景是通过加载不同大小的字体来实现缩放，而不是缩放现有字体
            # 因此，我们需要做的主要是调整那些固定像素大小的组件 (如上面的 input_width)
            # 它们已经在 draw_attributes_editor 中动态计算了，所以这里不需要额外操作
        except Exception as e:
            print(f"刷新字体纹理失败: {e}")

    def get_bundled_fonts(self, subdir):
        """获取 fonts 子目录下的字体文件列表"""
        path = os.path.join("fonts", subdir)
        if not os.path.exists(path):
            return []
        files = [
            f for f in os.listdir(path) if f.lower().endswith((".ttf", ".ttc", ".otf"))
        ]
        return files

    def draw_common_popups(self):
        if self.show_error_popup:
            imgui.open_popup("错误")
            self.show_error_popup = False

        if self.show_save_popup:
            imgui.open_popup("保存项目")
            self.show_save_popup = False

        if self.show_success_popup:
            imgui.open_popup("生成成功")
            self.show_success_popup = False

        # 生成成功弹窗
        imgui.set_next_window_size(600, 300, imgui.ONCE)
        if imgui.begin_popup_modal("生成成功")[0]:
            # 计算实际输出路径
            base_dir = (
                os.path.dirname(self.project.file_path)
                if self.project.file_path
                else "."
            )
            mod_dir = os.path.abspath(
                os.path.join(base_dir, self.project.code_name.strip() or "ModProject")
            )

            imgui.text("模组生成成功！")
            imgui.text_wrapped(f"输出目录:\n{mod_dir}")

            if imgui.button("打开目录"):
                try:
                    os.startfile(mod_dir)
                except Exception:
                    pass

            imgui.same_line()

            if imgui.button("确定"):
                imgui.close_current_popup()
            imgui.end_popup()

        # 错误弹窗
        imgui.set_next_window_size(400, 300, imgui.ONCE)
        if imgui.begin_popup_modal("错误")[0]:
            error_text = getattr(self, "error_message", "发生未知错误")
            imgui.text_wrapped(error_text)
            if imgui.button("确定"):
                imgui.close_current_popup()
            imgui.end_popup()

        # 保存项目弹窗
        imgui.set_next_window_size(300, 150, imgui.ONCE)
        if imgui.begin_popup_modal("保存项目")[0]:
            imgui.text("生成模组前需要先保存项目。")
            imgui.text("是否现在保存？")

            if imgui.button("保存"):
                imgui.close_current_popup()
                self.save_project_dialog()
                # 如果保存成功（有了文件路径），则继续生成
                if self.project.file_path:
                    self._execute_generation()

            imgui.same_line()

            if imgui.button("取消"):
                imgui.close_current_popup()

            imgui.end_popup()

    def run(self):
        running = True
        while running:
            if glfw.window_should_close(self.window):
                running = False
            glfw.poll_events()
            self.renderer.process_inputs()

            # 检查是否需要重载字体 (在 NewFrame 之前)
            if self.should_reload_fonts:
                self.reload_fonts()
                self.should_reload_fonts = False

            imgui.new_frame()

            self.draw_main_menu()
            self.draw_main_interface()

            if self.show_import_dialog:
                self.draw_import_dialog()

            # 绘制通用弹窗
            self.draw_common_popups()

            imgui.render()

            # Clear screen
            glClearColor(0, 0, 0, 1)
            glClear(GL_COLOR_BUFFER_BIT)

            self.renderer.render(imgui.get_draw_data())

            glfw.swap_buffers(self.window)

        self.clear_texture_previews()
        self.renderer.shutdown()
        glfw.terminate()

    def draw_main_menu(self):
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("文件", True):
                if imgui.menu_item("新建项目")[0]:
                    self.new_project_dialog()

                if imgui.menu_item("打开项目")[0]:
                    self.open_project_dialog()

                if imgui.menu_item("保存项目")[0]:
                    # 因为项目必须有路径才能存在，所以这里直接保存
                    if self.project.file_path:
                        self.project.save()

                if imgui.menu_item("导入项目", enabled=False)[0]:
                    self.show_import_dialog = True
                if imgui.is_item_hovered(flags=imgui.HOVERED_ALLOW_WHEN_DISABLED):
                    imgui.set_tooltip("该功能尚未测试")

                imgui.separator()

                if imgui.menu_item("生成模组")[0]:
                    self.generate_mod()

                imgui.separator()
                if imgui.menu_item("退出")[0]:
                    # self.window = None # 这行可能导致 AttributeError
                    glfw.set_window_should_close(self.window, True)

                imgui.end_menu()

            if imgui.begin_menu("设置", True):
                # 字号设置
                if imgui.begin_menu("字体大小"):
                    for size in [14, 16, 18, 20, 24, 28, 32]:
                        if imgui.menu_item(
                            f"{size} px", selected=(self.font_size == size)
                        )[0]:
                            self.font_size = size
                            self.save_config()
                            self.should_reload_fonts = True
                    imgui.end_menu()

                # 主题设置
                if imgui.menu_item("暗色主题", selected=self.is_dark_theme)[0]:
                    self.is_dark_theme = True
                    self.apply_theme()
                    self.save_config()

                if imgui.menu_item("亮色主题", selected=not self.is_dark_theme)[0]:
                    self.is_dark_theme = False
                    self.apply_theme()
                    self.save_config()

                # 贴图倍率设置 (已移动到贴图编辑器)
                # if imgui.begin_menu("贴图倍率"):
                #     for scale in [1.0, 2.0, 3.0, 4.0]:
                #         if imgui.menu_item(f"{scale}x", selected=(self.texture_scale == scale))[0]:
                #             self.texture_scale = scale
                #             self.save_config()
                #     imgui.end_menu()

                imgui.separator()

                if imgui.begin_menu("选择字体"):
                    # 1. 英文字体 (主字体)
                    if imgui.begin_menu("英文字体 (English)"):
                        bundled_fonts = self.get_bundled_fonts("english")
                        if bundled_fonts:
                            imgui.text_colored("内置字体:", 0.7, 0.7, 0.7, 1.0)
                            for font_file in bundled_fonts:
                                is_selected = self.primary_font_path == font_file
                                if imgui.menu_item(font_file, selected=is_selected)[0]:
                                    self.primary_font_path = font_file
                                    self.save_config()
                                    self.should_reload_fonts = True
                            imgui.separator()

                        imgui.text_colored("系统英文字体:", 0.7, 0.7, 0.7, 1.0)
                        english_system_fonts = [
                            ("Arial", "C:/Windows/Fonts/arial.ttf"),
                            ("Times New Roman", "C:/Windows/Fonts/times.ttf"),
                            ("Segoe UI", "C:/Windows/Fonts/segoeui.ttf"),
                            ("Verdana", "C:/Windows/Fonts/verdana.ttf"),
                            ("Tahoma", "C:/Windows/Fonts/tahoma.ttf"),
                            ("Consolas", "C:/Windows/Fonts/consolas.ttf"),
                        ]
                        for label, path in english_system_fonts:
                            if os.path.exists(path):
                                is_selected = self.primary_font_path == path
                                if imgui.menu_item(label, selected=is_selected)[0]:
                                    self.primary_font_path = path
                                    self.save_config()
                                    self.should_reload_fonts = True

                        if self.primary_font_path:
                            imgui.separator()
                            if imgui.menu_item("清除选择 (使用默认)", selected=False)[
                                0
                            ]:
                                self.primary_font_path = ""
                                self.save_config()
                                self.should_reload_fonts = True
                        imgui.end_menu()

                    # 2. 中文字体 (备用字体)
                    if imgui.begin_menu("中文字体 (Chinese)"):
                        bundled_fonts = self.get_bundled_fonts("chinese")
                        if bundled_fonts:
                            imgui.text_colored("内置字体:", 0.7, 0.7, 0.7, 1.0)
                            for font_file in bundled_fonts:
                                is_selected = self.fallback_font_path == font_file
                                if imgui.menu_item(font_file, selected=is_selected)[0]:
                                    self.fallback_font_path = font_file
                                    self.save_config()
                                    self.should_reload_fonts = True
                            imgui.separator()

                        imgui.text_colored("系统中文字体:", 0.7, 0.7, 0.7, 1.0)
                        chinese_system_fonts = [
                            ("微软雅黑 (Microsoft YaHei)", "C:/Windows/Fonts/msyh.ttc"),
                            ("黑体 (SimHei)", "C:/Windows/Fonts/simhei.ttf"),
                            ("宋体 (SimSun)", "C:/Windows/Fonts/simsun.ttc"),
                            ("楷体 (KaiTi)", "C:/Windows/Fonts/simkai.ttf"),
                        ]

                        for label, path in chinese_system_fonts:
                            if os.path.exists(path):
                                is_selected = self.fallback_font_path == path
                                if imgui.menu_item(label, selected=is_selected)[0]:
                                    self.fallback_font_path = path
                                    self.save_config()
                                    self.should_reload_fonts = True

                        if self.fallback_font_path:
                            imgui.separator()
                            if imgui.menu_item("清除选择 (使用默认)", selected=False)[
                                0
                            ]:
                                self.fallback_font_path = ""
                                self.save_config()
                                self.should_reload_fonts = True
                        imgui.end_menu()

                    imgui.end_menu()

                imgui.end_menu()

            imgui.end_main_menu_bar()

    def new_project_dialog(self):
        """新建项目：强制选择目录"""
        directory = self.select_directory_dialog()
        if directory:
            project_file = os.path.join(directory, "project.json")
            assets_dir = os.path.join(directory, "assets")

            # 初始化新项目
            self.project = ModProject()
            self.project.file_path = project_file
            self.current_weapon_index = -1
            self.error_message = ""

            # 立即创建基础结构
            try:
                os.makedirs(assets_dir, exist_ok=True)
                self.project.save()  # 保存初始状态
            except Exception as e:
                print(f"创建项目失败: {e}")
                self.error_message = f"创建项目失败: {e}"
                self.show_error_popup = True

    def draw_main_interface(self):
        # 获取主窗口（viewport）尺寸
        display_w, display_h = self.io.display_size

        # 获取菜单栏高度（通常是当前字号 + padding）
        menu_bar_height = (
            imgui.get_frame_height()
        )  # 如果就在菜单栏绘制之后调用，这通常能拿到正确高度
        # 或者更稳妥的方式：
        # menu_bar_height = self.font_size + self.io.style.frame_padding.y * 2

        # 动态设置位置和大小
        # Y轴从菜单栏下方开始
        imgui.set_next_window_position(0, menu_bar_height)
        # 高度为总高度减去菜单栏高度
        imgui.set_next_window_size(display_w, display_h - menu_bar_height)

        imgui.begin(
            "Main Interface",
            flags=imgui.WINDOW_NO_RESIZE
            | imgui.WINDOW_NO_MOVE
            | imgui.WINDOW_NO_COLLAPSE
            | imgui.WINDOW_NO_TITLE_BAR,
        )

        if not self.project.file_path:
            # 显示欢迎/提示信息
            window_width = imgui.get_window_width()
            window_height = imgui.get_window_height()

            text = "请新建或打开一个项目以开始"
            text_width = imgui.calc_text_size(text).x

            imgui.set_cursor_pos(
                ((window_width - text_width) / 2, window_height / 2 - 20)
            )
            imgui.text(text)

            # 添加按钮快捷方式
            button_width = 120
            imgui.set_cursor_pos(
                (window_width / 2 - button_width - 10, window_height / 2 + 20)
            )
            if imgui.button("新建项目", width=button_width):
                self.new_project_dialog()

            imgui.set_cursor_pos((window_width / 2 + 10, window_height / 2 + 20))
            if imgui.button("打开项目", width=button_width):
                self.open_project_dialog()

        else:
            # 项目信息
            if imgui.tree_node("项目信息", flags=imgui.TREE_NODE_FRAMED):
                self.draw_project_info()
                imgui.tree_pop()

            # 武器列表
            if imgui.tree_node("武器列表", flags=imgui.TREE_NODE_FRAMED):
                self.draw_weapon_list()
                imgui.tree_pop()

            # 武器编辑
            if self.current_weapon_index >= 0 and self.current_weapon_index < len(
                self.project.weapons
            ):
                if imgui.tree_node("武器编辑", flags=imgui.TREE_NODE_FRAMED):
                    self.draw_weapon_editor()
                    imgui.tree_pop()

        imgui.end()

    def draw_project_info(self):
        changed, self.project.name = imgui.input_text(
            "模组名称", self.project.name, 256
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip("用于展示的名称，可包含中文等字符")

        changed, self.project.code_name = imgui.input_text(
            "模组代号", self.project.code_name, 256
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip("仅用于内部生成代码，必须是以字母开头的字母/数字组合")

        changed, self.project.author = imgui.input_text(
            "作者", self.project.author, 256
        )
        changed, self.project.description = imgui.input_text(
            "描述", self.project.description, 512
        )
        changed, self.project.version = imgui.input_text(
            "版本", self.project.version, 32
        )
        changed, self.project.target_version = imgui.input_text(
            "目标版本", self.project.target_version, 32
        )

        imgui.text(
            f"项目路径: {os.path.dirname(self.project.file_path) if self.project.file_path else '未保存'}"
        )
        imgui.text(f"武器数量: {len(self.project.weapons)}")

        errors = self.project.validate()
        if errors:
            self.draw_indented_separator()
            imgui.text_colored("错误:", 1.0, 0.0, 0.0)
            for err in errors:
                imgui.text_colored(f"  • {err}", 1.0, 0.0, 0.0)

    def draw_weapon_list(self):
        if imgui.button("添加武器"):
            new_weapon = Weapon()
            new_weapon.name = self.generate_default_weapon_name()
            # 默认主语言名称和描述
            new_weapon.localization.set_name(PRIMARY_LANGUAGE, "新武器")
            new_weapon.localization.set_description(
                PRIMARY_LANGUAGE, "这是新武器的描述"
            )

            self.project.weapons.append(new_weapon)
            self.current_weapon_index = len(self.project.weapons) - 1

        imgui.same_line()

        if imgui.button("删除选中武器") and self.current_weapon_index >= 0:
            del self.project.weapons[self.current_weapon_index]
            self.current_weapon_index = min(
                self.current_weapon_index, len(self.project.weapons) - 1
            )

        imgui.same_line()

        if imgui.button("复制选中武器") and self.current_weapon_index >= 0:
            source_weapon = self.project.weapons[self.current_weapon_index]
            new_weapon = copy.deepcopy(source_weapon)

            # 确保名称唯一
            existing_names = {w.name for w in self.project.weapons}
            base_name = f"{source_weapon.name}_copy"
            new_name = base_name
            idx = 1
            while new_name in existing_names:
                new_name = f"{base_name}_{idx}"
                idx += 1
            new_weapon.name = new_name

            # 主语言名称加个标记，方便区分
            primary_name = new_weapon.localization.get_name(PRIMARY_LANGUAGE)
            if primary_name:
                new_weapon.localization.set_name(
                    PRIMARY_LANGUAGE, primary_name + " (副本)"
                )

            self.project.weapons.append(new_weapon)
            self.current_weapon_index = len(self.project.weapons) - 1

        for i, weapon in enumerate(self.project.weapons):
            flags = imgui.TREE_NODE_LEAF
            if i == self.current_weapon_index:
                flags |= imgui.TREE_NODE_SELECTED

            # 显示主语言名称和ID
            display_name_text = weapon.localization.get_display_name()
            display_name = f"{display_name_text} ({weapon.name})"

            opened = imgui.tree_node(display_name, flags=flags)
            if imgui.is_item_clicked():
                self.current_weapon_index = i

            if opened:
                imgui.tree_pop()

    def generate_default_weapon_name(self) -> str:
        existing = {weapon.name for weapon in self.project.weapons if weapon.name}
        base_name = "请设置武器系统ID"
        if base_name not in existing:
            return base_name

        idx = 1
        while True:
            candidate = f"{base_name}_{idx}"
            if candidate not in existing:
                return candidate
            idx += 1

    def draw_weapon_editor(self):
        weapon = self.project.weapons[self.current_weapon_index]
        weapon.markup = 1

        # 基本属性
        if imgui.tree_node("基本属性", flags=imgui.TREE_NODE_FRAMED):
            changed, weapon.name = imgui.input_text("武器系统ID*", weapon.name, 256)
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    "用来让游戏识别该物品的内部名称，不向玩家展示。\n请确保ID尽可能独特，以免与其他Mod冲突！"
                )
            imgui.same_line()
            imgui.text(f"(ID: {weapon.id})")

            # 枚举选择
            current_tier = (
                WEAPONS_TIER.index(weapon.tier) if weapon.tier in WEAPONS_TIER else 0
            )
            tier_label = TIER_LABELS.get(weapon.tier, weapon.tier)
            if imgui.begin_combo("等级", tier_label):
                for i, tier in enumerate(WEAPONS_TIER):
                    display = TIER_LABELS.get(tier, tier)
                    if imgui.selectable(display, i == current_tier)[0]:
                        weapon.tier = tier
                imgui.end_combo()

            slot_options = [slot for slot in WEAPONS_SLOT if slot not in HIDDEN_SLOTS]
            if weapon.slot not in slot_options:
                slot_options.append(weapon.slot)
            slot_label = SLOT_LABELS.get(weapon.slot, weapon.slot)
            if imgui.begin_combo("槽位", slot_label):
                for slot in slot_options:
                    display = SLOT_LABELS.get(slot, slot)
                    if imgui.selectable(display, slot == weapon.slot)[0]:
                        weapon.slot = slot

                        # 切换槽位时清理无效的左手贴图数据
                        if weapon.slot not in LEFT_HAND_SLOTS:
                            weapon.textures.character_left = ""
                            weapon.textures.character_left_frames = []
                            weapon.textures.offset_x_left = 0
                            weapon.textures.offset_y_left = 0

                imgui.end_combo()

            current_mat = (
                WEAPONS_MATERIAL.index(weapon.mat)
                if weapon.mat in WEAPONS_MATERIAL
                else 0
            )
            material_label = MATERIAL_LABELS.get(weapon.mat, weapon.mat)
            if imgui.begin_combo("材料", material_label):
                for i, mat in enumerate(WEAPONS_MATERIAL):
                    display = MATERIAL_LABELS.get(mat, mat)
                    if imgui.selectable(display, i == current_mat)[0]:
                        weapon.mat = mat
                imgui.end_combo()

            tag_options = ALLOWED_TAGS.copy()
            if weapon.tags not in tag_options:
                tag_options.append(weapon.tags)
            tag_label = TAG_LABELS.get(weapon.tags, weapon.tags)
            if imgui.begin_combo("标签", tag_label):
                for tag in tag_options:
                    display = TAG_LABELS.get(tag, tag)
                    if imgui.selectable(display, tag == weapon.tags)[0]:
                        weapon.tags = tag
                        # 自动设置稀有度
                        if weapon.tags in ["unique", "special", "special exc"]:
                            weapon.rarity = "Unique"
                        else:
                            weapon.rarity = "Common"
                imgui.end_combo()

            # 稀有度 - 禁用直接操作，只显示
            rarity_label = RARITY_LABELS.get(weapon.rarity, weapon.rarity)
            imgui.input_text(
                "稀有度", rarity_label, 256, flags=imgui.INPUT_TEXT_READ_ONLY
            )
            if imgui.is_item_hovered():
                imgui.set_tooltip("由标签自动决定")

            # 特殊属性 - 改用 Combo
            # 映射 True/False 到 "是"/"否"
            fireproof_str = "是" if weapon.fireproof else "否"
            if imgui.begin_combo("防火", fireproof_str):
                if imgui.selectable("是", weapon.fireproof)[0]:
                    weapon.fireproof = True
                if imgui.selectable("否", not weapon.fireproof)[0]:
                    weapon.fireproof = False
                imgui.end_combo()
            if imgui.is_item_hovered():
                imgui.set_tooltip("未被拾取时是否会被火焰摧毁")

            no_drop_str = "是" if weapon.no_drop else "否"
            if imgui.begin_combo("不可掉落", no_drop_str):
                if imgui.selectable("是", weapon.no_drop)[0]:
                    weapon.no_drop = True
                if imgui.selectable("否", not weapon.no_drop)[0]:
                    weapon.no_drop = False
                imgui.end_combo()
            if imgui.is_item_hovered():
                imgui.set_tooltip("可能无法从宝箱中获取")

            self.draw_indented_separator()
            changed, weapon.price = imgui.input_int("价格", weapon.price)
            changed, weapon.max_duration = imgui.input_int(
                "最大耐久", weapon.max_duration
            )

            # Rng 锁定逻辑: 仅弓弩可调，其他锁定为 1
            if weapon.slot in ["bow", "crossbow"]:
                changed, weapon.rng = imgui.input_int("距离", weapon.rng)
                if changed:
                    if weapon.rng < 0:
                        weapon.rng = 0
                    if weapon.rng > 255:
                        weapon.rng = 255
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        "决定武器的基础攻击距离（游戏内部字段）\n类型: byte (0-255)"
                    )
            else:
                weapon.rng = 1
                # 使用只读模式显示
                imgui.input_int("距离", weapon.rng, flags=imgui.INPUT_TEXT_READ_ONLY)
                if imgui.is_item_hovered():
                    imgui.set_tooltip("除弓弩外，武器距离固定为 1")

            imgui.tree_pop()

        # 属性编辑
        if imgui.tree_node("武器属性", flags=imgui.TREE_NODE_FRAMED):
            self.draw_attributes_editor(weapon)
            imgui.tree_pop()

        # 武器名称与本地化
        if imgui.tree_node("武器名称与本地化", flags=imgui.TREE_NODE_FRAMED):
            self.draw_localization_editor(weapon)
            imgui.tree_pop()

        # 贴图
        if imgui.tree_node("贴图文件", flags=imgui.TREE_NODE_FRAMED):
            self.draw_textures_editor(weapon)
            imgui.tree_pop()

        # 验证
        # 传入 project 以便检查重复ID
        errors = weapon.validate(self.project)
        if errors:
            self.draw_indented_separator()
            imgui.text("消息:")
            for error in errors:
                if error.startswith("WARNING:"):
                    imgui.text_colored(
                        f"  • {error}", 1.0, 0.5, 0.0, 1.0
                    )  # Orange for warning
                else:
                    imgui.text_colored(
                        f"  • {error}", 1.0, 0.0, 0.0, 1.0
                    )  # Red for error

    def draw_attributes_editor(self, weapon):
        for group_name, attributes in ATTRIBUTE_GROUPS.items():
            if imgui.tree_node(group_name):
                for attr in attributes:
                    # 获取描述
                    desc_info = ATTRIBUTE_DESCRIPTIONS.get(attr, ("", ""))
                    desc_name = desc_info[0]
                    desc_detail = desc_info[1] if len(desc_info) > 1 else ""

                    val = weapon.attributes.get(attr, 0)

                    # 显示 Label 和输入框
                    # 使用 PushItemWidth 限制输入框宽度
                    # 根据字体大小动态调整宽度，基础宽度 100，每像素字号增加 5
                    input_width = 100 + (self.font_size - 14) * 8
                    imgui.push_item_width(input_width)
                    # 使用 input_int 提供 +/- 按钮进行微调
                    changed, new_val = imgui.input_int(
                        f"##{attr}", val, step=1, step_fast=10
                    )
                    imgui.pop_item_width()

                    # 限制 byte 类型属性的范围 (0-255)
                    if attr in BYTE_ATTRIBUTES:
                        if new_val < 0:
                            new_val = 0
                            changed = True
                        elif new_val > 255:
                            new_val = 255
                            changed = True

                    if changed:
                        weapon.attributes[attr] = new_val

                    imgui.same_line()
                    imgui.text(f"{attr}")
                    imgui.same_line()
                    imgui.text_colored(f"({desc_name})", 0.7, 0.7, 0.7, 1.0)

                    # 悬停显示详细描述
                    if imgui.is_item_hovered():
                        tooltip_text = desc_detail
                        if attr in BYTE_ATTRIBUTES:
                            if tooltip_text:
                                tooltip_text += "\n"
                            tooltip_text += "类型: byte (0-255)"
                        imgui.set_tooltip(tooltip_text)

                imgui.tree_pop()

    def draw_localization_editor(self, weapon):
        # 语言添加器
        if imgui.button("添加语言"):
            imgui.open_popup("add_language_popup")

        if imgui.begin_popup("add_language_popup"):
            for lang in SUPPORTED_LANGUAGES:
                # 跳过已添加的语言
                if not weapon.localization.has_language(lang):
                    label = LANGUAGE_LABELS.get(lang, lang)
                    if imgui.selectable(label)[0]:
                        weapon.localization.languages[lang] = {
                            "name": "",
                            "description": "",
                        }
            imgui.end_popup()

        self.draw_indented_separator()

        # 首先渲染主语言（不可删除）
        primary_label = LANGUAGE_LABELS.get(PRIMARY_LANGUAGE, PRIMARY_LANGUAGE)
        imgui.text(f"{primary_label} (主语言)")

        # 确保主语言数据存在
        if not weapon.localization.has_language(PRIMARY_LANGUAGE):
            weapon.localization.languages[PRIMARY_LANGUAGE] = {
                "name": "",
                "description": "",
            }

        primary_data = weapon.localization.languages[PRIMARY_LANGUAGE]

        imgui.push_item_width(-1)
        changed, val = imgui.input_text(
            f"##{PRIMARY_LANGUAGE}_name", primary_data["name"], 256
        )
        if changed:
            primary_data["name"] = val
        if not primary_data["name"] and imgui.is_item_hovered():
            imgui.set_tooltip("主语言名称（建议填写）")
        imgui.pop_item_width()

        imgui.push_item_width(-1)
        changed, val = imgui.input_text_multiline(
            f"##{PRIMARY_LANGUAGE}_desc", primary_data["description"], 1024, height=60
        )
        if changed:
            primary_data["description"] = val
        imgui.pop_item_width()
        imgui.dummy(0, 10)

        # 渲染其他已添加语言（按 SUPPORTED_LANGUAGES 顺序）
        langs_to_remove = []
        for lang in SUPPORTED_LANGUAGES:
            if lang == PRIMARY_LANGUAGE:
                continue  # 主语言已在上面渲染
            if not weapon.localization.has_language(lang):
                continue  # 未添加的语言跳过

            data = weapon.localization.languages[lang]

            self.draw_indented_separator()
            label = LANGUAGE_LABELS.get(lang, lang)
            imgui.text(f"{label}")
            imgui.same_line()
            if imgui.button(f"删除##{lang}"):
                langs_to_remove.append(lang)

            imgui.text("名称")
            imgui.push_item_width(-1)
            changed, val = imgui.input_text(f"##{lang}_name", data["name"], 256)
            if changed:
                data["name"] = val
            imgui.pop_item_width()

            imgui.text("描述")
            imgui.push_item_width(-1)
            changed, val = imgui.input_text_multiline(
                f"##{lang}_desc", data["description"], 1024, height=60
            )
            if changed:
                data["description"] = val
            imgui.pop_item_width()
            imgui.dummy(0, 5)

        for lang in langs_to_remove:
            del weapon.localization.languages[lang]

    def draw_textures_editor(self, weapon):
        imgui.text_colored("注意: 所有贴图仅支持 PNG 格式", 0.8, 0.8, 0.8, 1.0)
        self.draw_indented_separator()

        # 贴图倍率设置 (可自由输入)
        imgui.text("预览设置")
        imgui.same_line()
        imgui.push_item_width(100)
        changed, self.texture_scale = imgui.input_float(
            "倍率##texture_scale",
            self.texture_scale,
            step=0.5,
            step_fast=1.0,
            format="%.1f",
        )
        imgui.pop_item_width()
        if changed:
            # 限制最小倍率为 0.1 以防止错误
            if self.texture_scale < 0.1:
                self.texture_scale = 0.1
            self.save_config()

        if imgui.is_item_hovered():
            imgui.set_tooltip("设置预览图的显示倍率 (默认 4.0)")

        # 模特选择
        imgui.text("预览模特")
        current_model_label = CHARACTER_MODEL_LABELS.get(
            self.selected_model, self.selected_model
        )
        if imgui.begin_combo("##character_model", current_model_label):
            for model_key, model_label in CHARACTER_MODEL_LABELS.items():
                if imgui.selectable(model_label, model_key == self.selected_model)[0]:
                    self.selected_model = model_key
            imgui.end_combo()

        self.draw_indented_separator()

        self.draw_texture_selector(
            "手持状态贴图*", weapon.textures.character, "character", weapon
        )

        # 手持贴图偏移设置 (右手)
        imgui.text("手持贴图偏移 (右手/默认)")
        if imgui.is_item_hovered():
            imgui.set_tooltip("调整武器相对于人物手部的相对位置")

        imgui.push_item_width(150)
        changed, weapon.textures.offset_x = imgui.input_int(
            "水平偏移##right", weapon.textures.offset_x
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip("默认 0。正数使人物看起来向右（武器向左）。")

        imgui.same_line()
        imgui.dummy(10, 0)  # 添加间距
        imgui.same_line()

        changed, weapon.textures.offset_y = imgui.input_int(
            "垂直偏移##right", weapon.textures.offset_y
        )
        if imgui.is_item_hovered():
            imgui.set_tooltip("默认 0。正数使人物看起来向下（武器向上）。")
        imgui.pop_item_width()

        self.draw_indented_separator()

        # 左手持握贴图（仅特定单手武器显示）
        if weapon.slot in LEFT_HAND_SLOTS:
            self.draw_texture_selector(
                "左手手持贴图*",
                weapon.textures.character_left,
                "character_left",
                weapon,
            )

            # 左手贴图偏移设置
            imgui.text("左手贴图偏移")
            if imgui.is_item_hovered():
                imgui.set_tooltip("调整武器相对于人物手部的相对位置")

            imgui.push_item_width(150)
            changed, weapon.textures.offset_x_left = imgui.input_int(
                "水平偏移##left", weapon.textures.offset_x_left
            )
            if imgui.is_item_hovered():
                imgui.set_tooltip("默认 0。正数使人物看起来向右（武器向左）。")

            imgui.same_line()
            imgui.dummy(10, 0)  # 添加间距
            imgui.same_line()

            changed, weapon.textures.offset_y_left = imgui.input_int(
                "垂直偏移##left", weapon.textures.offset_y_left
            )
            if imgui.is_item_hovered():
                imgui.set_tooltip("默认 0。正数使人物看起来向下（武器向上）。")
            imgui.pop_item_width()

            self.draw_indented_separator()

        imgui.text("常规贴图（顺序越靠后耐久越低）")
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "排在后面的贴图代表更低耐久状态下的武器\n注意：游戏内一格为 27 像素"
            )

        for idx, texture_path in enumerate(weapon.textures.inventory):
            self.draw_texture_selector(
                f"常规贴图 {idx + 1}", texture_path, ("inventory", idx)
            )

        if imgui.button("添加贴图槽"):
            weapon.textures.inventory.append("")
        if len(weapon.textures.inventory) > 1:
            imgui.same_line()
            if imgui.button("删除最后一个贴图槽"):
                weapon.textures.inventory.pop()

        self.draw_indented_separator()
        self.draw_texture_selector("战利品贴图*", weapon.textures.loot, "loot", weapon)

        # 战利品贴图动画速度设置（仅当有动画帧时显示）
        if weapon.textures.loot_frames:
            imgui.text("战利品动画速度设置")
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    "设置战利品贴图的动画播放速度。\n" "此设置会影响生成的模组代码。"
                )

            # 速度模式选择
            mode_labels = ["固定帧率 (FPS)", "相对帧率"]
            current_mode = 1 if weapon.textures.loot_use_relative_speed else 0
            if imgui.begin_combo(
                "速度模式##loot_speed_mode", mode_labels[current_mode]
            ):
                if imgui.selectable(
                    "固定帧率 (FPS)", not weapon.textures.loot_use_relative_speed
                )[0]:
                    if (
                        weapon.textures.loot_use_relative_speed
                    ):  # 从相对帧率切换到固定帧率
                        weapon.textures.loot_use_relative_speed = False
                        weapon.textures.loot_fps = 10.0  # 重置为默认固定帧率
                if imgui.selectable(
                    "相对帧率", weapon.textures.loot_use_relative_speed
                )[0]:
                    if (
                        not weapon.textures.loot_use_relative_speed
                    ):  # 从固定帧率切换到相对帧率
                        weapon.textures.loot_use_relative_speed = True
                        weapon.textures.loot_fps = (
                            0.25  # 重置为默认相对帧率 (与手持贴图相同)
                        )
                imgui.end_combo()

            if not weapon.textures.loot_use_relative_speed:
                # 固定帧率模式
                imgui.push_item_width(150)
                changed, weapon.textures.loot_fps = imgui.input_float(
                    "播放帧率 (FPS)##loot_fps",
                    weapon.textures.loot_fps,
                    step=1.0,
                    step_fast=5.0,
                    format="%.1f",
                )
                if changed and weapon.textures.loot_fps < 0.1:
                    weapon.textures.loot_fps = 0.1
                imgui.pop_item_width()
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        "每秒播放的帧数。\n"
                        "这是一个固定值，不会随游戏速度变化。\n"
                        "默认值: 10"
                    )
            else:
                # 相对帧率模式
                imgui.push_item_width(180)  # 增加宽度以容纳更多小数位显示
                changed, weapon.textures.loot_fps = imgui.input_float(
                    "相对帧率##loot_relative_fps",
                    weapon.textures.loot_fps,
                    step=0.01,
                    step_fast=0.1,
                    format="%.3f",
                )
                # 允许非常小的值，但不能为0或负数
                if changed:
                    if weapon.textures.loot_fps < 0.001:
                        weapon.textures.loot_fps = 0.001
                    # 四舍五入到3位小数，确保所见即所得
                    weapon.textures.loot_fps = round(weapon.textures.loot_fps, 3)
                imgui.pop_item_width()
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        "每个游戏帧内动画前进的帧数。\n\n"
                        "例如:\n"
                        f"  • 值为 0.1 时: 实际播放速度 = {GAME_FPS} × 0.1 = 4 fps\n"
                        f"  • 值为 0.25 时: 实际播放速度 = {GAME_FPS} × 0.25 = 10 fps\n"
                        f"  • 值为 0.5 时: 实际播放速度 = {GAME_FPS} × 0.5 = 20 fps\n"
                        f"  • 值为 1.0 时: 实际播放速度 = {GAME_FPS} × 1.0 = 40 fps\n\n"
                        "此模式的好处是动画速度会随游戏速度同步变化，\n"
                        "当游戏变慢时动画也会相应变慢。\n\n"
                        f"提示: 手持贴图默认相对帧率为 0.25 (即 {GAME_FPS // 4} fps)。\n"
                        "若想与手持贴图保持相同速度，请设为 0.25。\n"
                        "最小值: 0.001"
                    )

                # 显示实际播放速度（使用与输入相同的精度）
                actual_fps = GAME_FPS * weapon.textures.loot_fps
                imgui.text_colored(
                    f"实际播放速度: {actual_fps:.3f} fps (游戏 {GAME_FPS} fps 时)",
                    0.7,
                    0.7,
                    0.7,
                    1.0,
                )

    def _import_and_resolve_texture(self, source_path: str) -> str:
        """导入贴图并返回解析后的绝对路径

        如果项目已保存，将贴图导入到 assets 目录并返回绝对路径。
        如果项目未保存，直接返回源路径。
        """
        if self.project.file_path:
            rel_path = self.project.import_texture(source_path)
            return os.path.join(os.path.dirname(self.project.file_path), rel_path)
        return source_path

    def draw_texture_selector(
        self, label: str, current_path: str, field_identifier, weapon=None
    ):
        imgui.text(label)
        imgui.same_line()

        # 动画相关数据
        frames = []
        is_anim_field = False
        if weapon and field_identifier in ["character", "character_left", "loot"]:
            is_anim_field = True
            frames = getattr(weapon.textures, f"{field_identifier}_frames")

        # 如果是动画模式且有帧数据，显示动画管理界面
        if is_anim_field and frames:
            imgui.text(f"动画模式 (共 {len(frames)} 张图片)")
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    f"当前动画包含 {len(frames)} 张图片。\n"
                    f"预览播放速度: {PREVIEW_ANIMATION_FPS} fps\n"
                    f"(游戏中手持贴图默认以此速度播放)"
                )

            fps = PREVIEW_ANIMATION_FPS

            if imgui.button(f"添加帧##{label}"):
                self.current_texture_field = field_identifier
                paths = self.file_dialog([("PNG文件", "*.png")], multiple=True)
                if paths:
                    if not isinstance(paths, list):
                        paths = [paths]

                    for path in paths:
                        final_path = self._import_and_resolve_texture(path)
                        frames.append(final_path)

                    # 如果是第一帧，同时也更新主路径以便兼容
                    if len(frames) >= 1 and hasattr(weapon.textures, field_identifier):
                        setattr(weapon.textures, field_identifier, frames[0])

            imgui.same_line()
            if imgui.button(f"清空/转为静态##{label}"):
                frames.clear()

            # 预览控制 (暂停/指定帧)
            state = self.preview_states.get(
                field_identifier, {"paused": False, "current_frame": 0}
            )
            imgui.same_line()
            if imgui.checkbox(f"暂停##{label}", state["paused"])[0]:
                state["paused"] = not state["paused"]

            if state["paused"] and len(frames) > 0:
                max_frame = max(0, len(frames) - 1)
                if state["current_frame"] > max_frame:
                    state["current_frame"] = 0

                imgui.same_line()
                # 上一帧
                if imgui.arrow_button(f"##prev_{label}", imgui.DIRECTION_LEFT):
                    state["current_frame"] -= 1
                    if state["current_frame"] < 0:
                        state["current_frame"] = max_frame

                imgui.same_line()
                imgui.push_item_width(100)
                # 滑块 (显示 1-based)
                current_frame_1based = state["current_frame"] + 1
                changed, current_frame_1based = imgui.slider_int(
                    f"##frame_slider_{label}",
                    current_frame_1based,
                    1,
                    max_frame + 1,
                    format="%d",
                )
                if changed:
                    state["current_frame"] = current_frame_1based - 1
                imgui.pop_item_width()

                imgui.same_line()
                # 下一帧
                if imgui.arrow_button(f"##next_{label}", imgui.DIRECTION_RIGHT):
                    state["current_frame"] += 1
                    if state["current_frame"] > max_frame:
                        state["current_frame"] = 0

                imgui.same_line()
                imgui.text(f"帧: {state['current_frame'] + 1} / {max_frame + 1}")

            self.preview_states[field_identifier] = state

            # 显示帧列表 (简略)
            if imgui.tree_node(f"帧列表##{label}"):
                frames_to_remove = []
                frames_to_move_up = []
                frames_to_move_down = []

                for i, frame_path in enumerate(frames):
                    imgui.push_id(f"frame_{label}_{i}")
                    imgui.text(f"帧 {i+1}: {os.path.basename(frame_path)}")

                    imgui.same_line()
                    if imgui.arrow_button("##up", imgui.DIRECTION_UP):
                        frames_to_move_up.append(i)
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("上移")

                    imgui.same_line()
                    if imgui.arrow_button("##down", imgui.DIRECTION_DOWN):
                        frames_to_move_down.append(i)
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("下移")

                    imgui.same_line()
                    if imgui.small_button("X"):
                        frames_to_remove.append(i)
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("删除此帧")

                    imgui.pop_id()

                # 处理移动 (先处理移动，再处理删除)
                for i in frames_to_move_up:
                    if i > 0:
                        frames[i], frames[i - 1] = frames[i - 1], frames[i]

                for i in frames_to_move_down:
                    if i < len(frames) - 1:
                        frames[i], frames[i + 1] = frames[i + 1], frames[i]

                # 处理删除
                for i in sorted(frames_to_remove, reverse=True):
                    frames.pop(i)

                # 如果删空了，主路径也清空
                if not frames and hasattr(weapon.textures, field_identifier):
                    setattr(weapon.textures, field_identifier, "")

                # 如果还有帧，更新主路径为第一帧
                if frames and hasattr(weapon.textures, field_identifier):
                    setattr(weapon.textures, field_identifier, frames[0])

                imgui.tree_pop()

        else:
            # 常规单图选择模式
            button_id = f"选择文件##{label}"
            if imgui.button(button_id):
                self.current_texture_field = field_identifier
                # 打开文件对话框
                # 如果是动画字段，允许选择多个
                paths = self.file_dialog([("PNG文件", "*.png")], multiple=is_anim_field)

                if paths:
                    # 统一处理为列表
                    if not isinstance(paths, list):
                        paths = [paths]  # 单个文件转列表

                    # 处理第一个文件作为主贴图
                    first_path = paths[0]
                    final_path_0 = self._import_and_resolve_texture(first_path)
                    self.apply_texture_selection(final_path_0, field_identifier)

                    # 如果是动画字段，且选择了多个文件，或者只是想把这一个作为第一帧
                    if is_anim_field:
                        frames.clear()  # 重新选择文件时清空旧帧
                        for path in paths:
                            final_path = self._import_and_resolve_texture(path)
                            frames.append(final_path)

            imgui.same_line()
            # 显示文件名而不是全路径，比较简洁
            display_path = os.path.basename(current_path) if current_path else "未选择"
            imgui.text(display_path)

            if current_path and imgui.is_item_hovered():
                imgui.set_tooltip(current_path)

            # 如果是动画支持字段，提供转换为动画的按钮（如果已有图片）
            if is_anim_field and current_path:
                imgui.same_line()
                if imgui.button(f"添加更多帧##{label}"):
                    # 确保 frames 至少包含当前主贴图
                    if not frames:
                        frames.append(current_path)

                    # 打开选择更多帧
                    self.current_texture_field = field_identifier
                    paths = self.file_dialog([("PNG文件", "*.png")], multiple=True)
                    if paths:
                        if not isinstance(paths, list):
                            paths = [paths]

                        for path in paths:
                            final_path = self._import_and_resolve_texture(path)
                            frames.append(final_path)

        # 预览逻辑
        # 如果是动画模式，预览当前帧
        preview_path = current_path
        if is_anim_field and frames:
            # 根据贴图类型选择预览帧率
            fps = PREVIEW_ANIMATION_FPS  # 默认使用手持贴图帧率

            # 如果是战利品贴图，使用用户配置的帧率
            if field_identifier == "loot" and weapon:
                if weapon.textures.loot_use_relative_speed:
                    # 相对帧率模式：实际fps = 游戏fps × 相对帧率
                    fps = GAME_FPS * weapon.textures.loot_fps
                else:
                    # 固定帧率模式
                    fps = weapon.textures.loot_fps

            state = self.preview_states.get(
                field_identifier, {"paused": False, "current_frame": 0}
            )
            if state["paused"]:
                frame_idx = state["current_frame"]
            else:
                # 计算当前帧
                current_time = time.time()
                frame_idx = int(current_time * fps) % len(frames)

            # 安全检查
            if frame_idx >= len(frames):
                frame_idx = 0
            preview_path = frames[frame_idx]

        # 计算最大尺寸 (针对动画)
        override_size = None
        if is_anim_field and frames:
            max_w = 0
            max_h = 0
            for f_path in frames:
                p = self.get_texture_preview(f_path)
                if p:
                    max_w = max(max_w, p["width"])
                    max_h = max(max_h, p["height"])
            if max_w > 0 and max_h > 0:
                override_size = (max_w, max_h)

        preview = self.get_texture_preview(preview_path)
        if preview:
            # 显示尺寸
            imgui.same_line()
            # 如果有 override_size，显示 Max
            if override_size:
                dims_text = f"({override_size[0]}x{override_size[1]})"
            else:
                dims_text = f"({preview['width']}x{preview['height']})"
            imgui.text_colored(dims_text, 0.7, 0.7, 0.7, 1.0)

            imgui.new_line()

            # 绘制预览 (带人物参考)
            self.draw_preview_with_reference(preview, field_identifier, override_size)

    def draw_checkerboard(self, draw_list, p_min, p_max, cell_size=24):
        """绘制棋盘格背景"""
        x0, y0 = p_min
        x1, y1 = p_max

        # 绘制深色背景
        col_bg = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1.0)
        draw_list.add_rect_filled(x0, y0, x1, y1, col_bg)

        # 绘制浅色格子
        col_fg = imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1.0)

        y = y0
        row = 0
        while y < y1:
            # 每一行起始X根据行号交替
            x = x0 + (cell_size if row % 2 != 0 else 0)
            row_next_y = min(y + cell_size, y1)

            while x < x1:
                next_x = min(x + cell_size, x1)
                draw_list.add_rect_filled(x, y, next_x, row_next_y, col_fg)
                x += cell_size * 2

            y = row_next_y
            row += 1

    def draw_preview_with_reference(
        self, preview, field_identifier, override_size=None
    ):
        scale = self.texture_scale  # 使用用户设置的倍率

        # 预览图实际尺寸
        tex_w = preview["width"]
        tex_h = preview["height"]

        # 包围盒尺寸 (如果有 override_size 则使用，否则用当前图尺寸)
        box_w = tex_w
        box_h = tex_h
        if override_size:
            box_w, box_h = override_size

        # 确定是否需要人物背景
        is_handheld = False
        if isinstance(field_identifier, str):
            if field_identifier == "character":
                is_handheld = True
            elif field_identifier == "character_left":
                is_handheld = True

        draw_list = imgui.get_window_draw_list()
        start_pos = imgui.get_cursor_screen_pos()

        if is_handheld:
            # 加载参考图 - 使用选定的模特
            if self.current_weapon_index >= 0 and self.current_weapon_index < len(
                self.project.weapons
            ):
                weapon = self.project.weapons[self.current_weapon_index]
            else:
                return  # 无法获取武器信息

            # 根据武器类型选择姿态
            use_single_hand_pose = weapon.slot in [
                "dagger",
                "mace",
                "sword",
                "axe",
                "spear",
                "bow",
            ]
            pose_index = 0 if use_single_hand_pose else 1

            model_files = CHARACTER_MODELS.get(
                self.selected_model, ["s_elf_male_0.png", "s_elf_male_1.png"]
            )
            if pose_index >= len(model_files):
                pose_index = 0

            ref_img_name = model_files[pose_index]
            ref_path = os.path.join("resources", ref_img_name)
            if not os.path.exists(ref_path):
                ref_path = ref_img_name

            ref_preview = self.get_texture_preview(ref_path)

            if ref_preview:
                # 获取偏移量 (即 UI 上的 "水平偏移/垂直偏移")
                # 用户视角：+X 表示人物向右移(武器向左移)，+Y 表示人物向下移(武器向上移)
                # 实际上偏移是修改了武器的 Anchor 相对于 (22, 34) 的位置。
                off_x = weapon.textures.offset_x
                off_y = weapon.textures.offset_y
                if field_identifier == "character_left":
                    off_x = weapon.textures.offset_x_left
                    off_y = weapon.textures.offset_y_left

                # --- 视口绘制逻辑 ---
                # 视口固定为 VALID_AREA_SIZE (64x64)
                viewport_w = VALID_AREA_SIZE * scale
                viewport_h = VALID_AREA_SIZE * scale

                # 1. 绘制棋盘背景 (填满整个 64x64 视口)
                self.draw_checkerboard(
                    draw_list,
                    start_pos,
                    (start_pos[0] + viewport_w, start_pos[1] + viewport_h),
                    cell_size=int(8 * scale),
                )

                # 2. 裁剪绘制区域到视口范围内
                # 这样超出 64x64 的部分就不会显示，模拟游戏内效果
                draw_list.push_clip_rect(
                    start_pos[0],
                    start_pos[1],
                    start_pos[0] + viewport_w,
                    start_pos[1] + viewport_h,
                )

                # 3. 绘制人物
                # 人物固定显示在视口中的特定位置 (相对视口左上角偏移 8, 12)
                char_draw_x = start_pos[0] + VIEWPORT_CHAR_OFFSET_X * scale
                char_draw_y = start_pos[1] + VIEWPORT_CHAR_OFFSET_Y * scale

                draw_list.add_image(
                    ref_preview["tex_id"],
                    (float(char_draw_x), float(char_draw_y)),
                    (
                        float(char_draw_x + ref_preview["width"] * scale),
                        float(char_draw_y + ref_preview["height"] * scale),
                    ),
                )

                # 4. 绘制武器
                # 武器位置相对于人物：(-off_x, -off_y)
                # 为什么是负号？
                # 如果 offset_x = 0 (默认)，武器与人物左上角对齐 -> (0, 0)相对人物
                # 如果 offset_x = 10 (用户输入正数)，Tooltip说“人物向右”，意味着武器相对人物向左 -> (-10, 0)
                # 所以武器相对人物坐标是 (-off_x, -off_y)

                wep_rel_x = -off_x
                wep_rel_y = -off_y

                wep_draw_x = char_draw_x + wep_rel_x * scale
                wep_draw_y = char_draw_y + wep_rel_y * scale

                draw_list.add_image(
                    preview["tex_id"],
                    (float(wep_draw_x), float(wep_draw_y)),
                    (
                        float(wep_draw_x + tex_w * scale),
                        float(wep_draw_y + tex_h * scale),
                    ),
                )

                # 5. 绘制武器边框 (虚线/明显框)
                # 用于提示武器贴图的实际范围，即使被裁剪也能看到框
                # 蓝色虚线框 (这里用实线代替，Imgui 原生无虚线API，除非自己画点)
                # 稍微加粗并使用醒目颜色
                draw_list.add_rect(
                    wep_draw_x,
                    wep_draw_y,
                    wep_draw_x + tex_w * scale,
                    wep_draw_y + tex_h * scale,
                    imgui.get_color_u32_rgba(0.0, 1.0, 1.0, 0.8),  # 青色
                    thickness=2.0,
                )

                # 结束裁剪
                draw_list.pop_clip_rect()

                # 占位，撑开布局
                imgui.dummy(viewport_w, viewport_h)

                # 额外提示 (在视口下方)
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        "视图已锁定为 64x64 游戏有效区域。\n超出此区域的贴图部分将不会显示。\n青色框指示武器贴图的完整范围。"
                    )

                return

        # 默认绘制逻辑 (非手持或无参考图)
        width = tex_w * scale
        height = tex_h * scale

        # 如果有 override_size，棋盘格背景要画 override 的大小
        bg_width = box_w * scale
        bg_height = box_h * scale

        # 绘制棋盘背景
        self.draw_checkerboard(
            draw_list,
            start_pos,
            (start_pos[0] + bg_width, start_pos[1] + bg_height),
            cell_size=int(8 * scale),  # 根据倍率动态调整格子大小
        )

        # 使用 draw_list 绘制图片，确保居中或左上对齐
        # 这里依然使用左上角对齐 (相对于 start_pos)
        draw_list.add_image(
            preview["tex_id"],
            (float(start_pos[0]), float(start_pos[1])),
            (float(start_pos[0] + width), float(start_pos[1] + height)),
        )

        # 占位，撑开布局
        imgui.dummy(bg_width, bg_height)

    def apply_texture_selection(self, file_path: str, field_identifier=None) -> bool:
        if not file_path or not os.path.exists(file_path):
            return False

        # 如果没有传 identifier，尝试使用 self.current_texture_field
        if field_identifier is None:
            field_identifier = self.current_texture_field

        if self.current_weapon_index < 0 or self.current_weapon_index >= len(
            self.project.weapons
        ):
            return False
        weapon = self.project.weapons[self.current_weapon_index]

        field = field_identifier
        if isinstance(field, tuple):
            field_type, idx = field
            if (
                field_type == "inventory"
                and idx is not None
                and 0 <= idx < len(weapon.textures.inventory)
            ):
                weapon.textures.inventory[idx] = file_path
                return True
        else:
            if field == "character":
                weapon.textures.character = file_path
                return True
            if field == "character_left":
                weapon.textures.character_left = file_path
                return True
            if field == "loot":
                weapon.textures.loot = file_path
                return True
        return False

    def draw_indented_separator(self):
        style = imgui.get_style()
        spacing = style.item_spacing.y
        imgui.dummy(0, spacing * 0.3)
        cursor_x, cursor_y = imgui.get_cursor_screen_pos()
        max_x = cursor_x + imgui.get_content_region_available_width()
        color = style.colors[imgui.COLOR_SEPARATOR]
        draw_list = imgui.get_window_draw_list()
        draw_list.add_line(
            cursor_x, cursor_y, max_x, cursor_y, imgui.get_color_u32_rgba(*color)
        )
        imgui.dummy(0, spacing * 0.3)

    def draw_import_dialog(self):
        imgui.open_popup("导入项目")
        if imgui.begin_popup_modal("导入项目")[0]:
            imgui.text("选择要导入的项目文件:")
            changed, self.import_file_path = imgui.input_text(
                "文件路径", self.import_file_path, 512
            )

            if imgui.button("浏览"):
                self.import_file_path = self.file_dialog()

            imgui.same_line()

            if imgui.button("确定"):
                if os.path.exists(self.import_file_path):
                    success, message, conflicts = self.project.import_project(
                        self.import_file_path
                    )
                    if success:
                        if conflicts:
                            self.import_conflicts = conflicts  # 保存到实例变量
                            imgui.open_popup("导入冲突")
                        else:
                            self.show_import_dialog = False
                    else:
                        imgui.open_popup("导入错误")
                else:
                    imgui.open_popup("文件不存在")

            imgui.same_line()

            if imgui.button("取消"):
                self.show_import_dialog = False

            # 显示冲突信息
            if imgui.begin_popup_modal("导入冲突")[0]:
                imgui.text("以下武器名称冲突，已自动重命名:")
                for conflict in self.import_conflicts:
                    imgui.text(f"  • {conflict}")
                if imgui.button("确定"):
                    imgui.close_current_popup()
                    self.import_conflicts = []  # 清空
                    self.show_import_dialog = False
                imgui.end_popup()

            # 显示错误信息
            if imgui.begin_popup_modal("导入错误")[0]:
                imgui.text("导入失败!")
                if imgui.button("确定"):
                    imgui.close_current_popup()
                imgui.end_popup()

            imgui.end_popup()

    def file_dialog(self, file_types=None, multiple=False):
        """使用 tkinter 调用系统文件对话框"""
        root = None
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.attributes("-topmost", True)  # 确保窗口在最前面

            ftypes = file_types if file_types else [("All files", "*.*")]

            if multiple:
                file_paths = filedialog.askopenfilenames(filetypes=ftypes)
                return list(file_paths) if file_paths else []
            else:
                file_path = filedialog.askopenfilename(filetypes=ftypes)
                return file_path
        except Exception as e:
            print(f"文件对话框错误: {e}")
            return [] if multiple else ""
        finally:
            if root:
                root.destroy()

    def open_project_dialog(self):
        directory = self.select_directory_dialog()
        if directory:
            file_path = os.path.join(directory, "project.json")
            if os.path.exists(file_path):
                if not self.project.load(file_path):
                    self.error_message = "无法加载项目文件，文件可能已损坏"
                    self.show_error_popup = True
                else:
                    self.current_weapon_index = -1  # 重置选择
            else:
                self.error_message = f"在 {directory} 中未找到 project.json"
                self.show_error_popup = True

    def save_project_dialog(self):
        # 保留此方法以兼容旧调用，但实际上已简化
        if self.project.file_path:
            self.project.save()

    def select_directory_dialog(self):
        """选择目录对话框"""
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            return filedialog.askdirectory()
        except Exception as e:
            print(f"目录选择错误: {e}")
            return ""
        finally:
            if root:
                root.destroy()

    def generate_mod(self):
        """生成模组文件"""
        print("开始生成模组...")

        # 检查项目和所有武器的验证
        project_errors = self.project.validate()
        if project_errors:
            print("错误: 项目验证失败")
            self.error_message = "项目验证失败:\n" + "\n".join(
                f"  • {err}" for err in project_errors
            )
            self.show_error_popup = True
            return

        weapon_errors = []
        for i, weapon in enumerate(self.project.weapons):
            # 传入 project 以便检查 ID 唯一性
            errors = weapon.validate(self.project)
            # 过滤掉 Warning，不阻止生成
            real_errors = [e for e in errors if not e.startswith("WARNING:")]
            if real_errors:
                weapon_errors.append(f"武器 {weapon.name} ({weapon.id}):")
                weapon_errors.extend(f"  • {err}" for err in real_errors)

        if weapon_errors:
            print("错误: 武器验证失败")
            self.error_message = "武器验证失败:\n" + "\n".join(weapon_errors)
            self.show_error_popup = True
            return

        # 如果项目未保存，弹出保存对话框
        if not self.project.file_path:
            self.show_save_popup = True
            return

        self._execute_generation()

    def _execute_generation(self):
        try:
            # 创建模组目录
            mod_name = self.project.code_name.strip() or "ModProject"
            # 使用项目文件所在的目录作为基准
            base_dir = os.path.dirname(self.project.file_path)
            mod_dir = Path(base_dir) / mod_name
            sprites_dir = mod_dir / "Sprites"

            print(f"创建目录: {mod_dir}")
            mod_dir.mkdir(exist_ok=True)
            sprites_dir.mkdir(exist_ok=True)

            # 生成C#代码
            print("生成 C# 代码...")
            code = self.generate_csharp_code()
            with open(mod_dir / f"{mod_name}.cs", "w", encoding="utf-8") as f:
                f.write(code)

            # 生成空的 .csproj 文件（根据需求无需内容）
            print("生成空的 .csproj 文件...")
            with open(mod_dir / f"{mod_name}.csproj", "w", encoding="utf-8"):
                pass

            # 复制贴图文件
            print("复制贴图文件...")
            for weapon in self.project.weapons:
                weapon_id = weapon.id
                # 手持贴图 (支持动画)
                if weapon.textures.character_frames:
                    for idx, frame_path in enumerate(weapon.textures.character_frames):
                        self.copy_texture(
                            frame_path,
                            sprites_dir / f"s_char_{weapon_id}_{idx}.png",
                            mask_offsets=(
                                weapon.textures.offset_x,
                                weapon.textures.offset_y,
                            ),
                        )
                else:
                    self.copy_texture(
                        weapon.textures.character,
                        sprites_dir / f"s_char_{weapon_id}.png",
                        mask_offsets=(
                            weapon.textures.offset_x,
                            weapon.textures.offset_y,
                        ),
                    )

                # 复制左手贴图（如果有）(支持动画)
                if weapon.textures.character_left_frames:
                    for idx, frame_path in enumerate(
                        weapon.textures.character_left_frames
                    ):
                        self.copy_texture(
                            frame_path,
                            sprites_dir / f"s_charleft_{weapon_id}_{idx}.png",
                            mask_offsets=(
                                weapon.textures.offset_x_left,
                                weapon.textures.offset_y_left,
                            ),
                        )
                elif weapon.textures.character_left:
                    self.copy_texture(
                        weapon.textures.character_left,
                        sprites_dir / f"s_charleft_{weapon_id}.png",
                        mask_offsets=(
                            weapon.textures.offset_x_left,
                            weapon.textures.offset_y_left,
                        ),
                    )

                for idx, inv_texture in enumerate(weapon.textures.inventory):
                    self.copy_texture(
                        inv_texture, sprites_dir / f"s_inv_{weapon_id}_{idx}.png"
                    )

                # 战利品贴图 (支持动画)
                if weapon.textures.loot_frames:
                    for idx, frame_path in enumerate(weapon.textures.loot_frames):
                        self.copy_texture(
                            frame_path, sprites_dir / f"s_loot_{weapon_id}_{idx}.png"
                        )
                else:
                    self.copy_texture(
                        weapon.textures.loot, sprites_dir / f"s_loot_{weapon_id}.png"
                    )

            print("生成成功！")
            self.show_success_popup = True
        except Exception as e:
            print(f"生成模组时发生错误: {e}")
            self.error_message = f"生成模组失败:\n{e}"
            self.show_error_popup = True

    def _calculate_crop_region(
        self, img_width: int, img_height: int, off_x: int, off_y: int
    ):
        """计算武器贴图的裁剪区域

        Args:
            img_width: 原图宽度
            img_height: 原图高度
            off_x: 用户设置的水平偏移
            off_y: 用户设置的垂直偏移

        Returns:
            tuple: (crop_x1, crop_y1, crop_x2, crop_y2, is_valid)
                   crop_x1, crop_y1: 裁剪区域左上角（在原图坐标系中）
                   crop_x2, crop_y2: 裁剪区域右下角（在原图坐标系中）
                   is_valid: 裁剪区域是否有效（非空）
        """
        # 有效范围相对于武器贴图左上角(0,0)
        # 转换公式: WeaponLocal = World - (GML_ANCHOR - WeaponAnchor)
        # WeaponLocal = World + off_x (对于 x 轴)
        valid_local_min_x = VALID_MIN_X + off_x
        valid_local_max_x = VALID_MAX_X + off_x
        valid_local_min_y = VALID_MIN_Y + off_y
        valid_local_max_y = VALID_MAX_Y + off_y

        # 计算裁剪框（与原图相交的部分）
        crop_x1 = int(max(0, valid_local_min_x))
        crop_y1 = int(max(0, valid_local_min_y))
        crop_x2 = int(min(img_width, valid_local_max_x))
        crop_y2 = int(min(img_height, valid_local_max_y))

        is_valid = crop_x1 < crop_x2 and crop_y1 < crop_y2
        return crop_x1, crop_y1, crop_x2, crop_y2, is_valid

    def _calculate_adjusted_offsets(self, off_x: int, off_y: int):
        """计算真正裁剪后的调整偏移量

        当贴图被真正裁剪时，如果裁剪掉了左侧或上侧的像素，
        偏移量会被"限制"到最大有效值。

        原理：
        - crop_x1 = max(0, VALID_MIN_X + off_x)
        - adjusted_off_x = off_x - crop_x1

        当 off_x <= VIEWPORT_CHAR_OFFSET_X 时: crop_x1 = 0, adjusted = off_x
        当 off_x > VIEWPORT_CHAR_OFFSET_X 时: adjusted = VIEWPORT_CHAR_OFFSET_X

        简化为: adjusted_off = min(off, VIEWPORT_CHAR_OFFSET)

        X方向最大有效偏移: VIEWPORT_CHAR_OFFSET_X = 8
        Y方向最大有效偏移: VIEWPORT_CHAR_OFFSET_Y = 12

        超过这些值后，继续增大偏移不会改变实际锚点位置，
        因为被裁剪掉的像素数与偏移增量相同。
        """
        adjusted_off_x = min(off_x, VIEWPORT_CHAR_OFFSET_X)
        adjusted_off_y = min(off_y, VIEWPORT_CHAR_OFFSET_Y)

        return adjusted_off_x, adjusted_off_y

    def copy_texture(self, src_path, dst_path, mask_offsets=None):
        """复制贴图文件，如果指定 mask_offsets 则根据有效范围进行真正的裁剪"""
        if src_path and os.path.exists(src_path):
            # 确保目标目录存在
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            if mask_offsets and Image:
                try:
                    off_x, off_y = mask_offsets
                    with Image.open(src_path) as img:
                        img = img.convert("RGBA")
                        w, h = img.size

                        crop_x1, crop_y1, crop_x2, crop_y2, is_valid = (
                            self._calculate_crop_region(w, h, off_x, off_y)
                        )

                        if is_valid:
                            # 真正裁剪图像（不保留原尺寸，直接裁切）
                            cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                            cropped.save(dst_path)
                            return
                        else:
                            # 有效区域为空，创建一个 1x1 透明图像作为占位
                            print(f"警告: 贴图 {src_path} 完全超出有效显示区域")
                            placeholder = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                            placeholder.save(dst_path)
                            return
                except Exception as e:
                    print(f"处理贴图裁剪失败，将直接复制: {e}")

            # 如果没有 offsets 或处理失败，直接复制
            try:
                shutil.copy2(src_path, dst_path)
            except Exception as e:
                print(f"复制贴图失败: {e}")

    def get_texture_preview(self, path):
        if not path or not os.path.exists(path) or Image is None:
            return None
        mtime = os.path.getmtime(path)
        cached = self.texture_preview_cache.get(path)
        if cached and cached["mtime"] == mtime:
            return cached

        # 如果有旧的缓存，先删除纹理
        if cached:
            glDeleteTextures(int(cached["tex_id"]))

        try:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                width, height = img.size
                image_data = img.tobytes()
        except Exception as exc:
            print(f"无法加载贴图预览 {path}: {exc}")
            return None

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        # 使用最近邻采样以实现像素风格放大效果
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            image_data,
        )

        preview = {"tex_id": tex_id, "width": width, "height": height, "mtime": mtime}
        self.texture_preview_cache[path] = preview
        return preview

    def clear_texture_previews(self):
        for preview in self.texture_preview_cache.values():
            glDeleteTextures(int(preview["tex_id"]))
        self.texture_preview_cache.clear()

    def generate_csharp_code(self) -> str:
        """生成C#模组代码"""
        code_namespace = self.project.code_name.strip() or "ModNamespace"

        code = f"""using ModShardLauncher;
using ModShardLauncher.Mods;
using UndertaleModLib;
using UndertaleModLib.Models;
using System.Collections.Generic;

namespace {code_namespace};
public class {code_namespace} : Mod
{{
    public override string Author => "{self.project.author}";
    public override string Name => "{self.project.name}";
    public override string Description => "{self.project.description}";
    public override string Version => "{self.project.version}";
    public override string TargetVersion => "{self.project.target_version}";

    public override void PatchMod()
    {{
"""

        for weapon in self.project.weapons:
            code += f"        Add{weapon.id}();\n"

        code += "    }\n\n"

        for weapon in self.project.weapons:
            code += self.generate_weapon_method(weapon)

        code += "}\n"
        return code

    def format_description(self, text: str) -> str:
        """处理描述文本：strip -> splitlines -> join('##') -> 转移双引号"""
        if not text:
            return ""
        # strip 并按行分割，过滤掉空行（如果需要保留空行可以调整）
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        # 用 ## 连接
        joined = "##".join(lines)
        # 转义双引号
        return joined.replace('"', '\\"')

    def _generate_weapon_injection_code(self, weapon: Weapon) -> str:
        """生成武器注入 C# 代码"""
        code = "        Msl.InjectTableWeapons(\n"
        code += f'            name: "{weapon.name}",\n'
        code += f"            Tier: Msl.WeaponsTier.{weapon.tier},\n"
        code += f'            id: "{weapon.id}",\n'
        code += f"            Slot: Msl.WeaponsSlot.{weapon.slot},\n"
        code += f"            rarity: Msl.WeaponsRarity.{weapon.rarity},\n"
        code += f"            Mat: Msl.WeaponsMaterial.{weapon.mat},\n"
        code += f"            tags: Msl.WeaponsTags.{weapon.tags.replace(' ', '')},\n"
        code += f"            Price: {weapon.price},\n"
        code += "            Markup: 1,\n"
        code += f"            MaxDuration: {weapon.max_duration},\n"
        code += f"            Rng: {weapon.rng}"

        balance_value = SLOT_BALANCE.get(weapon.slot)
        if balance_value is not None:
            code += f",\n            Balance: {balance_value}"

        code += f",\n            fireproof: {'true' if weapon.fireproof else 'false'}"
        code += f",\n            NoDrop: {'true' if weapon.no_drop else 'false'}"

        # 添加属性
        for attr, value in weapon.attributes.items():
            if value != 0:
                # 特殊处理 typo
                attr_name = attr
                if attr == "Electromantic_Power":
                    attr_name = "Electroantic_Power"
                code += f",\n            {attr_name}: {value}"

        code += "\n        );\n\n"
        return code

    def _generate_localization_code(self, weapon: Weapon) -> str:
        """生成本地化 C# 代码

        强制生成的语言条目:
        - 主语言 (PRIMARY_LANGUAGE) - 必须存在（即使为空）
        - 英文 - 必须存在（即使为空），除非主语言就是英文
        """
        code = "        Msl.InjectTableWeaponTextsLocalization(\n"
        code += "            new LocalizationWeaponText(\n"
        code += f'                id: "{weapon.name}",\n'
        code += "                name: new Dictionary<ModLanguage, string>() {\n"

        # 确定必须生成的语言
        required_langs = {PRIMARY_LANGUAGE}
        if PRIMARY_LANGUAGE != "English":
            required_langs.add("English")

        # 收集所有需要生成的语言（必须语言 + 已填写的语言）
        langs_to_generate = set(required_langs)
        for lang in weapon.localization.languages:
            if lang in LANGUAGE_TO_ENUM_MAP:
                langs_to_generate.add(lang)

        # 按 SUPPORTED_LANGUAGES 顺序生成名称
        for lang in SUPPORTED_LANGUAGES:
            if lang not in langs_to_generate:
                continue
            lang_enum = LANGUAGE_TO_ENUM_MAP.get(lang)
            if not lang_enum:
                continue
            name = weapon.localization.get_name(lang)
            code += f'                    {{{lang_enum}, "{name}"}},\n'

        code += "                },\n"
        code += "                description: new Dictionary<ModLanguage, string>() {\n"

        # 按 SUPPORTED_LANGUAGES 顺序生成描述
        for lang in SUPPORTED_LANGUAGES:
            if lang not in langs_to_generate:
                continue
            lang_enum = LANGUAGE_TO_ENUM_MAP.get(lang)
            if not lang_enum:
                continue
            desc = weapon.localization.get_description(lang)
            formatted_desc = self.format_description(desc)
            code += f'                    {{{lang_enum}, "{formatted_desc}"}},\n'

        code += "                }\n"
        code += "            )\n"
        code += "        );\n"
        return code

    def _generate_anchor_gml_block(
        self, val_y: int, val_x: int, sprite_name: str
    ) -> str:
        """生成单个锚点的 GML 代码块"""
        code = f"pushi.e {val_y}\n"
        code += "conv.i.v\n"
        code += f"pushi.e {val_x}\n"
        code += "conv.i.v\n"
        code += "call.i @@NewGMLArray@@(argc=2)\n"
        code += f"pushi.e {sprite_name}\n"
        code += "conv.i.v\n"
        code += "pushglb.v global.customizationAnchors\n"
        code += "call.i ds_map_add(argc=3)\n"
        code += "popz.v\n"
        return code

    def _generate_gml_offset_code(self, weapon: Weapon) -> str:
        """生成 GML 偏移注入代码

        注意：由于贴图会被真正裁剪（而非仅透明化），如果裁剪掉了左侧或上侧的像素，
        需要相应调整偏移量以保持正确的锚点位置。
        """
        gml_code_block = ""

        # 处理右手/默认手持
        if weapon.textures.offset_x != 0 or weapon.textures.offset_y != 0:
            # 计算真正裁剪后的调整偏移量（已简化，无需加载图片）
            adj_off_x, adj_off_y = self._calculate_adjusted_offsets(
                weapon.textures.offset_x, weapon.textures.offset_y
            )

            # 只有调整后偏移不为零时才需要生成代码
            if adj_off_x != 0 or adj_off_y != 0:
                val_y = GML_ANCHOR_Y + adj_off_y
                val_x = GML_ANCHOR_X + adj_off_x
                sprite_name = f"s_char_{weapon.id}"
                gml_code_block += self._generate_anchor_gml_block(
                    val_y, val_x, sprite_name
                )

        # 处理左手手持
        if weapon.textures.character_left or weapon.textures.character_left_frames:
            if weapon.textures.offset_x_left != 0 or weapon.textures.offset_y_left != 0:
                # 计算真正裁剪后的调整偏移量（已简化，无需加载图片）
                adj_off_x_left, adj_off_y_left = self._calculate_adjusted_offsets(
                    weapon.textures.offset_x_left, weapon.textures.offset_y_left
                )

                # 只有调整后偏移不为零时才需要生成代码
                if adj_off_x_left != 0 or adj_off_y_left != 0:
                    val_y = GML_ANCHOR_Y + adj_off_y_left
                    val_x = GML_ANCHOR_X + adj_off_x_left
                    sprite_name = f"s_charleft_{weapon.id}"
                    gml_code_block += self._generate_anchor_gml_block(
                        val_y, val_x, sprite_name
                    )

        if not gml_code_block:
            return ""

        # 移除最后的换行符，避免多余空行
        gml_code_block = gml_code_block.rstrip()

        match_gml = """pushi.e 34
conv.i.v
pushi.e 29
conv.i.v
call.i @@NewGMLArray@@(argc=2)
pushi.e 16635
conv.i.v
pushglb.v global.customizationAnchors
call.i ds_map_add(argc=3)
popz.v"""

        code = f'        Msl.LoadAssemblyAsString("gml_GlobalScript_scr_ds_init")\n'
        code += f'            .MatchFrom(@"{match_gml}")\n'
        code += f'            .InsertBelow(@"{gml_code_block}")\n'
        code += "            .Save();\n"
        return code

    def _generate_loot_sprite_animation_code(self, weapon: Weapon) -> str:
        """生成战利品贴图动画设置的 C# 代码

        当战利品贴图为动画形式时，生成设置播放速度的代码。
        """
        # 只有当有多帧动画时才需要生成代码
        if not weapon.textures.loot_frames or len(weapon.textures.loot_frames) <= 1:
            return ""

        sprite_name = f"s_loot_{weapon.id}"
        fps_value = weapon.textures.loot_fps

        # 根据速度模式选择不同的类型
        if weapon.textures.loot_use_relative_speed:
            speed_type = "AnimSpeedType.FramesPerGameFrame"
        else:
            speed_type = "AnimSpeedType.FramesPerSecond"

        # 格式化帧率值，确保输出与显示一致（3位小数）
        fps_formatted = f"{fps_value:.3f}"

        code = f"""
        // 设置战利品贴图动画播放速度
        UndertaleSprite lootSprite_{weapon.id} = Msl.GetSprite("{sprite_name}");
        lootSprite_{weapon.id}.CollisionMasks.RemoveAt(0);
        lootSprite_{weapon.id}.IsSpecialType = true;
        lootSprite_{weapon.id}.SVersion = 3;
        lootSprite_{weapon.id}.GMS2PlaybackSpeed = {fps_formatted}f;
        lootSprite_{weapon.id}.GMS2PlaybackSpeedType = {speed_type};

"""
        return code

    def generate_weapon_method(self, weapon: Weapon) -> str:
        """生成单个武器的C#方法"""
        method_name = f"Add{weapon.id}"

        code = f"    private void {method_name}()\n    {{\n"
        code += self._generate_weapon_injection_code(weapon)
        code += self._generate_localization_code(weapon)
        code += self._generate_gml_offset_code(weapon)
        code += self._generate_loot_sprite_animation_code(weapon)
        code += "    }\n\n"

        return code


if __name__ == "__main__":
    app = ModGeneratorGUI()
    app.run()
