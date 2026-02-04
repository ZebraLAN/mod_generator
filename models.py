# -*- coding: utf-8 -*-
"""
数据模型模块

包含所有数据类：Item, Weapon, Armor, HybridItem, ModProject, ItemTextures, ItemLocalization
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, TYPE_CHECKING

from specs import ItemTexturesV2, CharTextureSpec, Origin

if TYPE_CHECKING:
    from hybrid_item_v2 import HybridItemV2

from constants import (
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

    languages: Dict[str, Dict[str, str]] = field(default_factory=dict[str, Dict[str, str]])

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
    attributes: Dict[str, Any] = field(default_factory=dict[str, Any])

    # 本地化
    localization: ItemLocalization = field(default_factory=ItemLocalization)

    # 贴图 (V2 Tagged Union 格式)
    textures: ItemTexturesV2 = field(default_factory=ItemTexturesV2)

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


# ============== 品质常量 ==============

QUALITY_COMMON = 1
QUALITY_UNIQUE = 6
QUALITY_ARTIFACT = 7


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
    item: "HybridItemV2", project=None, include_warnings: bool = False
) -> List[str]:
    """验证混合物品数据的完整性 (V2 接口)"""
    from hybrid_item_v2 import (
        WeaponEquip, ArmorEquip, CharmEquip,
        SkillTrigger, EffectTrigger,
        LimitedCharges, UnlimitedCharges,
        HasDurability, NoDurability,
    )

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

    # 武器属性检查 (V2: 检查 equipment 是否为 WeaponEquip)
    if isinstance(item.equipment, WeaponEquip):
        if not item.equipable:
            errors.append("WARNING: 武器类型需要物品可装备")
        if item.slot != "hand":
            errors.append("WARNING: 武器类型物品的槽位通常应为 'hand'")
        # 检查 attributes 中是否有伤害值
        from constants import DAMAGE_ATTRIBUTES
        has_damage = any(item.attributes.get(attr, 0) > 0 for attr in DAMAGE_ATTRIBUTES)
        if not has_damage:
            errors.append("武器应在属性中设置至少一种伤害类型")

    # 护甲属性检查 (V2: 检查 equipment 是否为 ArmorEquip)
    if isinstance(item.equipment, ArmorEquip):
        if not item.equipable:
            errors.append("WARNING: 护甲类型需要物品可装备")
        if item.slot == "hand" or item.slot == "heal":
            errors.append("WARNING: 护甲类型物品的槽位不应为 'hand' 或 'heal'")

    # 技能触发检查 (V2: 检查 trigger 是否为 SkillTrigger)
    if isinstance(item.trigger, SkillTrigger):
        if not item.trigger.skill_object:
            errors.append("WARNING: 启用了技能触发模式但未设置技能对象")

    # 使用次数检查 (V2: 检查 charges 是否为 LimitedCharges)
    if isinstance(item.charges, LimitedCharges):
        if item.charges.max_charges <= 0:
            errors.append("使用次数应大于0")

    # 耐久检查 (V2: 从 equipment 的 durability 获取)
    if item.has_durability:
        match item.equipment:
            case WeaponEquip(durability=HasDurability(max_durability=d)):
                if d <= 0:
                    errors.append("耐久度应大于0")
            case ArmorEquip(durability=HasDurability(max_durability=d)):
                if d <= 0:
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
    hybrid_items: List["HybridItemV2"] = field(default_factory=list)  # V2 格式
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

        from migrations import CURRENT_SCHEMA_VERSION

        data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
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

        self.clean_unused_assets()
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

    def _serialize_hybrid_item(self, item: "HybridItemV2", project_dir: str) -> dict:
        """序列化混合物品数据为字典 (V2 格式)"""
        from serde import unstructure_hybrid_item
        return unstructure_hybrid_item(item, project_dir)


    def _serialize_textures(self, textures: ItemTexturesV2, project_dir: str) -> dict:
        """序列化贴图数据 (V2 格式)"""
        from serde import unstructure_textures
        return unstructure_textures(textures, project_dir)

    def _deserialize_textures(
        self, tex_data: dict, project_dir: str
    ) -> ItemTexturesV2:
        """反序列化贴图数据 (V2 格式，迁移已在 migrations.py 完成)"""
        from serde import structure_textures
        return structure_textures(tex_data, project_dir)


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

    def _deserialize_hybrid_item(self, item_data: dict, project_dir: str) -> "HybridItemV2":
        """反序列化混合物品数据"""
        from serde import structure_hybrid_item
        return structure_hybrid_item(item_data, project_dir)


    @classmethod
    def load(cls, file_path: str) -> "tuple[ModProject | None, bool]":
        """从文件加载项目

        Returns:
            (项目对象, 是否触发了迁移) - 项目对象失败时为 None

        Raises:
            MigrationError: 迁移过程中的错误（包括 FutureVersionError）
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"项目文件不存在: {file_path}")
            return None, False
        except json.JSONDecodeError as e:
            print(f"项目文件格式错误: {e}")
            return None, False
        except Exception as e:
            print(f"加载项目文件失败: {e}")
            return None, False

        # 运行迁移 (MigrationError 向上传播)
        from migrations import migrate
        data, migrated = migrate(data)

        project = cls()
        project.file_path = file_path
        project_dir = os.path.dirname(file_path)

        project.name = data.get("name", "MyNewMod")
        project.code_name = data.get("code_name", "MyNewMod")
        project.author = data.get("author", "")
        project.description = data.get(
            "description", "使用 Stoneshard Weapon Mod Editor 生成"
        )
        project.version = data.get("version", "1.0.0")
        project.target_version = data.get("target_version", "0.9.3.13")

        project.weapons = [
            project._deserialize_item(w, project_dir, is_weapon=True)
            for w in data.get("weapons", [])
        ]
        project.armors = [
            project._deserialize_item(a, project_dir, is_weapon=False)
            for a in data.get("armors", [])
        ]
        project.hybrid_items = [
            project._deserialize_hybrid_item(h, project_dir)
            for h in data.get("hybrid_items", [])
        ]

        project.clean_invalid_data()

        return project, migrated

    def clean_invalid_data(self):
        """清理无效的武器/装备/混合物品数据"""
        for item in self.weapons + self.armors:
            if not item.needs_char_texture():
                item.textures.clear_char()
            if not item.needs_left_texture():
                item.textures.clear_left()

        # HybridItemV2 使用 ItemTexturesV2，贴图类型在创建时已正确设置
        # 无需像旧版那样清理

    def _collect_texture_paths_v2(self, textures: ItemTexturesV2, project_dir: str) -> set:
        """收集 ItemTexturesV2 的所有贴图路径"""
        from specs import WeaponCharTexture, MultiPoseCharTexture

        used_files: set[str] = set()
        all_paths: list[str] = []

        # Inventory
        all_paths.extend(textures.inventory)

        # Loot
        all_paths.extend(textures.loot.paths)

        # Char (Tagged Union)
        match textures.char:
            case WeaponCharTexture() as w:
                all_paths.extend(w.main.paths)
                all_paths.extend(w.left.paths)
            case MultiPoseCharTexture() as m:
                if m.standing0.path:
                    all_paths.append(m.standing0.path)
                if m.standing1.path:
                    all_paths.append(m.standing1.path)
                if m.rest.path:
                    all_paths.append(m.rest.path)
                if m.standing0_female.path:
                    all_paths.append(m.standing0_female.path)
                if m.standing1_female.path:
                    all_paths.append(m.standing1_female.path)
                if m.rest_female.path:
                    all_paths.append(m.rest_female.path)

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
            used_files.update(self._collect_texture_paths_v2(item.textures, project_dir))
        for hybrid in self.hybrid_items:
            used_files.update(self._collect_texture_paths_v2(hybrid.textures, project_dir))

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
        other_project, _ = ModProject.load(other_project_path)
        if other_project is None:
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
