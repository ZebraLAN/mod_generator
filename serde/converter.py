# -*- coding: utf-8 -*-
"""
cattrs Converter 配置

配置 Tagged Union 序列化规则，处理路径转换。
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields, is_dataclass
from pathlib import Path
from typing import Any, Type, TypeVar
from enum import Enum

import cattrs

from specs import (
    # Quality
    QualitySpec, CommonQuality, UniqueQuality, ArtifactQuality,
    # Equipment
    EquipmentSpec, NotEquipable, WeaponEquip, ArmorEquip, CharmEquip,
    # Durability
    DurabilitySpec, NoDurability, HasDurability,
    # Trigger
    TriggerSpec, NoTrigger, EffectTrigger, SkillTrigger,
    # Charges
    ChargeSpec, NoCharges, LimitedCharges, UnlimitedCharges,
    # ChargeRecovery
    ChargeRecoverySpec, NoRecovery, IntervalRecovery,
    # Spawn
    SpawnSpec, ExcludedFromRandom, RandomSpawn, SpawnRuleType,
    # Textures
    CharTextureSpec, NoCharTexture, WeaponCharTexture, MultiPoseCharTexture,
    LootAnimationSpeed, AbsoluteFps, RelativeSpeed,
    ItemTexturesV2, AnimatedSlot, LootSlot, StaticSlot, Origin,
)
from models import ItemLocalization


T = TypeVar("T")


# ============================================================================
# Converter 创建
# ============================================================================


def create_converter() -> cattrs.Converter:
    """创建配置好的 cattrs Converter"""
    conv = cattrs.Converter()

    # 注册 Tagged Union 类型
    # 使用 "type" 字段区分变体
    _register_tagged_unions(conv)

    # 注册特殊类型的 hooks
    _register_hooks(conv)

    return conv


def _register_tagged_unions(conv: cattrs.Converter) -> None:
    """注册所有 Tagged Union 类型

    由于 cattrs 对空 dataclass (无字段) 的 Union 支持有限，
    我们手动注册序列化/反序列化 hooks。

    注意：先注册内层 Union，再注册外层，确保嵌套正确处理。
    """
    # 先注册没有嵌套的简单类型
    _register_union(conv, QualitySpec, {
        "common": CommonQuality,
        "unique": UniqueQuality,
        "artifact": ArtifactQuality,
    }, "common")

    _register_union(conv, TriggerSpec, {
        "none": NoTrigger,
        "effect": EffectTrigger,
        "skill": SkillTrigger,
    }, "none")

    _register_union(conv, ChargeSpec, {
        "none": NoCharges,
        "limited": LimitedCharges,
        "unlimited": UnlimitedCharges,
    }, "none")

    _register_union(conv, ChargeRecoverySpec, {
        "none": NoRecovery,
        "interval": IntervalRecovery,
    }, "none")

    _register_union(conv, SpawnSpec, {
        "excluded": ExcludedFromRandom,
        "random": RandomSpawn,
    }, "excluded")

    _register_union(conv, LootAnimationSpeed, {
        "absolute": AbsoluteFps,
        "relative": RelativeSpeed,
    }, "absolute")

    # 先注册 DurabilitySpec (被 EquipmentSpec 嵌套)
    _register_union(conv, DurabilitySpec, {
        "none": NoDurability,
        "has": HasDurability,
    }, "none")

    # 再注册 EquipmentSpec（包含嵌套的 DurabilitySpec）
    # 需要特殊处理以正确序列化 durability 字段
    _register_equipment_spec(conv)

    # CharTexture
    _register_union(conv, CharTextureSpec, {
        "none": NoCharTexture,
        "weapon": WeaponCharTexture,
        "multi_pose": MultiPoseCharTexture,
    }, "none")


def _register_equipment_spec(conv: cattrs.Converter) -> None:
    """特殊处理 EquipmentSpec，因为它包含嵌套的 DurabilitySpec"""
    tag_to_class = {
        "none": NotEquipable,
        "weapon": WeaponEquip,
        "armor": ArmorEquip,
        "charm": CharmEquip,
    }
    class_to_tag = {v: k for k, v in tag_to_class.items()}

    # 需要排除的类变量（不是实例字段）
    excluded_fields = {"TWO_HAND_WEAPONS", "LEFT_HAND_WEAPONS", "MULTI_POSE_SLOTS"}

    def unstructure_equipment(obj: Any) -> dict:
        tag = class_to_tag.get(type(obj), "none")
        result: dict[str, Any] = {"type": tag}

        if is_dataclass(obj) and not isinstance(obj, type):
            for f in dataclass_fields(obj):
                if f.name in excluded_fields:
                    continue
                value = getattr(obj, f.name)
                # 对 durability 使用 DurabilitySpec 的 hook
                if f.name == "durability":
                    result[f.name] = conv.unstructure(value, DurabilitySpec)
                else:
                    result[f.name] = conv.unstructure(value)

        return result

    def structure_equipment(data: Any, _: Type) -> Any:
        if data is None or not isinstance(data, dict):
            return NotEquipable()

        tag = data.get("type", "none")
        cls = tag_to_class.get(tag, NotEquipable)

        if cls == NotEquipable:
            return NotEquipable()
        elif cls == CharmEquip:
            return CharmEquip()
        elif cls == WeaponEquip:
            durability_data = data.get("durability", {"type": "none"})
            durability = conv.structure(durability_data, DurabilitySpec)
            return WeaponEquip(
                weapon_type=data.get("weapon_type", "sword"),
                balance=data.get("balance", 2),
                durability=durability,
            )
        elif cls == ArmorEquip:
            durability_data = data.get("durability", {"type": "none"})
            durability = conv.structure(durability_data, DurabilitySpec)
            return ArmorEquip(
                armor_type=data.get("armor_type", "Head"),
                durability=durability,
            )
        return NotEquipable()

    conv.register_unstructure_hook(EquipmentSpec, unstructure_equipment)
    conv.register_structure_hook(EquipmentSpec, structure_equipment)


def _register_union(
    conv: cattrs.Converter,
    union_type: Type,
    tag_to_class: dict[str, Type],
    default_tag: str,
) -> None:
    """注册一个 Tagged Union 类型的序列化/反序列化"""
    class_to_tag = {v: k for k, v in tag_to_class.items()}

    def unstructure_union(obj: Any) -> dict:
        tag = class_to_tag.get(type(obj), default_tag)
        # 使用 dataclass_fields 获取字段，避免序列化类变量
        if is_dataclass(obj) and not isinstance(obj, type):
            fields = {}
            for f in dataclass_fields(obj):
                value = getattr(obj, f.name)
                fields[f.name] = conv.unstructure(value)
        else:
            fields = {}
        return {"type": tag, **fields}

    def structure_union(data: Any, _: Type) -> Any:
        if data is None:
            data = {}
        if not isinstance(data, dict):
            # 可能是旧格式
            return tag_to_class[default_tag]()

        tag = data.get("type", default_tag)
        cls = tag_to_class.get(tag, tag_to_class[default_tag])

        # 移除 type 字段，剩余的传给 structure
        fields = {k: v for k, v in data.items() if k != "type"}
        return conv.structure(fields, cls)

    conv.register_unstructure_hook(union_type, unstructure_union)
    conv.register_structure_hook(union_type, structure_union)


def _register_hooks(conv: cattrs.Converter) -> None:
    """注册特殊类型的序列化/反序列化 hooks"""

    # Enum: 序列化为 value
    conv.register_unstructure_hook(SpawnRuleType, lambda e: e.value)
    conv.register_structure_hook(SpawnRuleType, lambda v, _: SpawnRuleType(v))

    # ItemLocalization: 直接使用 languages dict
    conv.register_unstructure_hook(
        ItemLocalization,
        lambda loc: loc.languages
    )
    conv.register_structure_hook(
        ItemLocalization,
        lambda d, _: ItemLocalization(languages=d if isinstance(d, dict) else {})
    )

    # Origin: 省略默认值
    conv.register_unstructure_hook(
        Origin,
        lambda o: None if o.is_default else {"x": o.x, "y": o.y}
    )
    conv.register_structure_hook(
        Origin,
        lambda d, _: Origin(d["x"], d["y"]) if d else Origin()
    )


# ============================================================================
# 全局 Converter 实例
# ============================================================================

_converter = create_converter()


# ============================================================================
# 公共 API
# ============================================================================


def unstructure(obj: Any) -> Any:
    """将对象序列化为 dict/list/primitive"""
    return _converter.unstructure(obj)


def structure(data: Any, cls: Type[T]) -> T:
    """将 dict/list/primitive 反序列化为对象"""
    return _converter.structure(data, cls)


# ============================================================================
# HybridItemV2 专用 API (处理路径转换)
# ============================================================================


def unstructure_hybrid_item(item: "HybridItemV2", project_dir: str = "") -> dict:
    """序列化 HybridItemV2，处理路径相对化

    Args:
        item: HybridItemV2 实例
        project_dir: 项目目录，用于转换为相对路径

    Returns:
        可 JSON 序列化的 dict
    """
    from hybrid_item_v2 import HybridItemV2

    # 先用标准 converter 序列化
    data = _converter.unstructure(item)

    # 转换路径为相对路径
    if project_dir:
        _relativize_paths(data, project_dir)

    return data


def structure_hybrid_item(data: dict, project_dir: str = "") -> "HybridItemV2":
    """反序列化 HybridItemV2，处理路径解析

    Args:
        data: 已迁移到当前 schema 的 dict
        project_dir: 项目目录，用于解析相对路径

    Returns:
        HybridItemV2 实例
    """
    from hybrid_item_v2 import HybridItemV2

    # 先解析路径为绝对路径
    if project_dir:
        _resolve_paths(data, project_dir)

    # 用标准 converter 反序列化
    return _converter.structure(data, HybridItemV2)


# ============================================================================
# 路径转换辅助函数
# ============================================================================


def _relativize_paths(data: dict, project_dir: str) -> None:
    """将 data 中的路径转换为相对路径 (原地修改)"""
    project_path = Path(project_dir)

    def relativize(p: str) -> str:
        if not p:
            return p
        try:
            return str(Path(p).relative_to(project_path))
        except ValueError:
            return p

    def relativize_list(paths: list) -> list:
        return [relativize(p) for p in paths]

    # textures.inventory
    if "textures" in data:
        tex = data["textures"]
        if "inventory" in tex:
            tex["inventory"] = relativize_list(tex["inventory"])

        # textures.loot.paths
        if "loot" in tex and "paths" in tex["loot"]:
            tex["loot"]["paths"] = relativize_list(tex["loot"]["paths"])

        # textures.char
        if "char" in tex:
            char = tex["char"]
            char_type = char.get("type", "none")

            if char_type == "weapon":
                if "main" in char and "paths" in char["main"]:
                    char["main"]["paths"] = relativize_list(char["main"]["paths"])
                if "left" in char and "paths" in char["left"]:
                    char["left"]["paths"] = relativize_list(char["left"]["paths"])

            elif char_type == "multi_pose":
                for pose in ["standing0", "standing1", "rest",
                             "standing0_female", "standing1_female", "rest_female"]:
                    if pose in char and "path" in char[pose]:
                        char[pose]["path"] = relativize(char[pose]["path"])


def _resolve_paths(data: dict, project_dir: str) -> None:
    """将 data 中的路径解析为绝对路径 (原地修改)"""
    project_path = Path(project_dir)

    def resolve(p: str) -> str:
        if not p:
            return p
        return str(project_path / p)

    def resolve_list(paths: list) -> list:
        return [resolve(p) for p in paths if p]

    # textures.inventory
    if "textures" in data:
        tex = data["textures"]
        if "inventory" in tex:
            tex["inventory"] = resolve_list(tex["inventory"])

        # textures.loot.paths
        if "loot" in tex and "paths" in tex["loot"]:
            tex["loot"]["paths"] = resolve_list(tex["loot"]["paths"])

        # textures.char
        if "char" in tex:
            char = tex["char"]
            char_type = char.get("type", "none")

            if char_type == "weapon":
                if "main" in char and "paths" in char["main"]:
                    char["main"]["paths"] = resolve_list(char["main"]["paths"])
                if "left" in char and "paths" in char["left"]:
                    char["left"]["paths"] = resolve_list(char["left"]["paths"])

            elif char_type == "multi_pose":
                for pose in ["standing0", "standing1", "rest",
                             "standing0_female", "standing1_female", "rest_female"]:
                    if pose in char and "path" in char[pose]:
                        char[pose]["path"] = resolve(char[pose]["path"])


# ============================================================================
# ItemTexturesV2 API (for Weapon/Armor)
# ============================================================================


def unstructure_textures(textures: ItemTexturesV2, project_dir: str = "") -> dict:
    """序列化 ItemTexturesV2，处理路径相对化

    Args:
        textures: ItemTexturesV2 实例
        project_dir: 项目目录，用于转换为相对路径

    Returns:
        可 JSON 序列化的 dict
    """
    data = _converter.unstructure(textures)

    if project_dir:
        # 包装成 {"textures": ...} 格式以复用 _relativize_paths
        wrapped = {"textures": data}
        _relativize_paths(wrapped, project_dir)
        data = wrapped["textures"]

    return data


def structure_textures(data: dict, project_dir: str = "") -> ItemTexturesV2:
    """反序列化 ItemTexturesV2，处理路径解析

    Args:
        data: V2 格式的贴图 dict (迁移已在 migrations.py 完成)
        project_dir: 项目目录，用于解析相对路径

    Returns:
        ItemTexturesV2 实例
    """
    if project_dir:
        # 包装成 {"textures": ...} 格式以复用 _resolve_paths
        wrapped = {"textures": data}
        _resolve_paths(wrapped, project_dir)
        data = wrapped["textures"]

    return _converter.structure(data, ItemTexturesV2)
