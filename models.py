# -*- coding: utf-8 -*-
"""
数据模型模块

包含所有数据类：Item, Weapon, Armor, ModProject, ItemTextures, ItemLocalization
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List

from constants import (
    ARMOR_HOOK_TO_SLOT,
    ARMOR_SLOT_TO_HOOK,
    ARMOR_SLOTS_MULTI_POSE,
    ARMOR_SLOTS_WITH_CHAR_PREVIEW,
    ITEM_TYPE_CONFIG,
    LEFT_HAND_SLOTS,
    PRIMARY_LANGUAGE,
)


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
        }

        for weapon in self.weapons:
            weapon.name = weapon.name.strip()
            data["weapons"].append(self._serialize_item(weapon, project_dir))

        for armor in self.armors:
            armor.name = armor.name.strip()
            data["armors"].append(self._serialize_item(armor, project_dir))

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
        self, tex_data: dict, project_dir: str, legacy_mode: bool = False
    ) -> ItemTextures:
        """反序列化贴图数据，兼容新旧格式"""

        def to_list(val, fallback_frames_key=None):
            """将值转换为列表，兼容旧格式（字符串）和新格式（列表）"""
            # 新格式：已经是列表
            if isinstance(val, list):
                return [resolve_path(p, project_dir) for p in val if p]
            # 旧格式：单个字符串
            if val:
                result = [resolve_path(val, project_dir)]
                # 旧格式可能有单独的 _frames 字段
                if fallback_frames_key and fallback_frames_key in tex_data:
                    frames = tex_data[fallback_frames_key]
                    if frames:
                        result = [resolve_path(p, project_dir) for p in frames if p]
                return result
            # 检查旧格式的 _frames 字段
            if fallback_frames_key and fallback_frames_key in tex_data:
                frames = tex_data[fallback_frames_key]
                if frames:
                    return [resolve_path(p, project_dir) for p in frames if p]
            return []

        # 处理 inventory（旧格式可能有 inventory0/1/2）
        inventory_data = tex_data.get("inventory")
        if inventory_data is None and legacy_mode:
            inventory_data = []
            for key in ("inventory0", "inventory1", "inventory2"):
                if key in tex_data and tex_data[key]:
                    inventory_data.append(tex_data[key])
        inventory = to_list(inventory_data) if inventory_data else []

        # 处理多姿势装备贴图（兼容旧字段名 character_pose1/pose2）
        standing1_path = tex_data.get("character_standing1", "") or tex_data.get(
            "character_pose1", ""
        )
        rest_path = tex_data.get("character_rest", "") or tex_data.get(
            "character_pose2", ""
        )
        if standing1_path:
            standing1_path = resolve_path(standing1_path, project_dir)
        if rest_path:
            rest_path = resolve_path(rest_path, project_dir)

        # 处理女性版贴图路径
        female_standing0_path = tex_data.get("character_female", "")
        if female_standing0_path:
            female_standing0_path = resolve_path(female_standing0_path, project_dir)

        female_standing1_path = tex_data.get("character_standing1_female", "")
        if female_standing1_path:
            female_standing1_path = resolve_path(female_standing1_path, project_dir)

        female_rest_path = tex_data.get("character_rest_female", "")
        if female_rest_path:
            female_rest_path = resolve_path(female_rest_path, project_dir)

        return ItemTextures(
            character=to_list(tex_data.get("character"), "character_frames"),
            character_standing1=standing1_path,
            character_rest=rest_path,
            character_left=to_list(
                tex_data.get("character_left"), "character_left_frames"
            ),
            inventory=inventory,
            loot=to_list(tex_data.get("loot"), "loot_frames"),
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
            character_female=female_standing0_path,
            offset_x_female=tex_data.get("offset_x_female", 0),
            offset_y_female=tex_data.get("offset_y_female", 0),
            character_standing1_female=female_standing1_path,
            offset_x_standing1_female=tex_data.get("offset_x_standing1_female", 0),
            offset_y_standing1_female=tex_data.get("offset_y_standing1_female", 0),
            character_rest_female=female_rest_path,
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
        if is_weapon:
            slot = item_data.get("slot", "sword")
        else:
            slot = item_data.get("slot")
            if slot is None and "hook" in item_data:
                slot = ARMOR_HOOK_TO_SLOT.get(item_data["hook"], "Head")
            slot = slot or "Head"

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
            # 处理本地化兼容
            loc_data = item_data.get("localization", {})
            if "languages" in loc_data:
                item.localization = ItemLocalization(
                    languages=loc_data.get("languages", {})
                )
            elif "chinese_name" in loc_data or "other_languages" in loc_data:
                languages = {}
                chn_name = loc_data.get("chinese_name", "")
                chn_desc = loc_data.get("chinese_description", "")
                if chn_name or chn_desc:
                    languages["Chinese"] = {"name": chn_name, "description": chn_desc}
                for lang, data in loc_data.get("other_languages", {}).items():
                    languages[lang] = {
                        "name": data.get("name", ""),
                        "description": data.get("description", ""),
                    }
                item.localization = ItemLocalization(languages=languages)
            else:
                item.localization = ItemLocalization(languages=loc_data)
            item.textures = self._deserialize_textures(
                item_data.get("textures", {}), project_dir, legacy_mode=True
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

        self.clean_invalid_data()
        self.clean_unused_assets()

        return True

    def clean_invalid_data(self):
        """清理无效的武器/装备数据"""
        for item in self.weapons + self.armors:
            if not item.needs_char_texture():
                item.textures.clear_char()
            if not item.needs_left_texture():
                item.textures.clear_left()

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
