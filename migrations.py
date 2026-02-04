# -*- coding: utf-8 -*-
"""
数据迁移模块

Schema 版本管理和迁移 pass 注册。

使用方法：
    from migrations import migrate, CURRENT_SCHEMA_VERSION

    # 加载时
    data, migrated = migrate(raw_data)
    if migrated:
        print("项目已从旧版本迁移，建议保存")

    # 保存时
    data["schema_version"] = CURRENT_SCHEMA_VERSION
"""

from typing import Any

from constants import CHAR_MODEL_ORIGIN


# ============================================================================
# Schema 版本
# ============================================================================

# 当前 schema 版本
# 每次 breaking change 时递增
CURRENT_SCHEMA_VERSION = 2

# 最低支持版本 (可选，用于日落旧版本)
# MIN_SUPPORTED_VERSION = 1


# ============================================================================
# 迁移入口
# ============================================================================


class MigrationError(Exception):
    """迁移过程中的错误"""
    pass


class FutureVersionError(MigrationError):
    """项目文件来自更新版本的工具"""
    pass


def migrate(data: dict) -> tuple[dict, bool]:
    """运行所有必要的迁移 pass

    Args:
        data: 原始项目数据字典

    Returns:
        (迁移后的数据, 是否触发了迁移)

    Raises:
        FutureVersionError: 项目文件版本高于当前支持的版本
        MigrationError: 版本号无效
    """
    raw_version = data.get("schema_version", 1)

    # 类型检查
    if not isinstance(raw_version, int):
        raise MigrationError(
            f"无效的 schema_version 类型: {type(raw_version).__name__}，期望 int"
        )

    version = raw_version

    # 版本范围检查
    if version < 1:
        raise MigrationError(f"无效的 schema_version: {version}")

    if version > CURRENT_SCHEMA_VERSION:
        raise FutureVersionError(
            f"项目文件版本 ({version}) 高于当前工具支持的版本 ({CURRENT_SCHEMA_VERSION})。\n"
            f"请更新 Mod Generator 到最新版本。"
        )

    migrated = version < CURRENT_SCHEMA_VERSION

    # 按顺序运行迁移 pass
    if version < 2:
        _pass_v1_to_v2(data)

    # 未来添加更多:
    # if version < 3:
    #     _pass_v2_to_v3(data)

    # 更新版本号
    data["schema_version"] = CURRENT_SCHEMA_VERSION

    return data, migrated


# ============================================================================
# 迁移 Pass: V1 -> V2
# ============================================================================
# V1: 旧版 HybridItem 平铺字段格式 + 旧版贴图格式
# V2: Tagged Union 结构 (equipment, trigger, charges, etc.) + 新版贴图格式


def _pass_v1_to_v2(data: dict) -> None:
    """将 V1 格式迁移到 V2 格式

    主要变更：
    - HybridItem: 平铺字段 -> Tagged Union 结构
    - 所有物品: offset_x/y -> origin 对象
    - 所有物品: 贴图结构重组 (char 字段)
    """
    # 迁移 Weapon/Armor 的贴图格式
    for weapon in data.get("weapons", []):
        tex = weapon.get("textures", {})
        if tex and "char" not in tex:
            weapon["textures"] = _migrate_weapon_textures_v1_to_v2(tex)

    for armor in data.get("armors", []):
        tex = armor.get("textures", {})
        if tex and "char" not in tex:
            armor["textures"] = _migrate_armor_textures_v1_to_v2(tex, armor.get("slot", ""))

    # 迁移 HybridItem
    for item in data.get("hybrid_items", []):
        # 检测是否已是 V2 格式
        if "equipment" in item and isinstance(item.get("equipment"), dict):
            continue  # 已是 V2，跳过

        # ====== Equipment ======
        equipment_mode = item.pop("equipment_mode", "none")
        quality_int = item.get("quality", 1)

        # 构建 durability (仅装备且非文物)
        durability: dict[str, Any]
        if equipment_mode in ("weapon", "armor") and quality_int != 7:
            durability = {
                "type": "has",
                "duration_max": item.pop("duration_max", 100),
                "wear_per_use": item.pop("wear_per_use", 0),
                "destroy_on_zero": item.pop("destroy_on_durability_zero", True),
                "affects_stats": item.pop("durability_affects_stats", False),
            }
        else:
            durability = {"type": "none"}
            # 清理可能存在的旧字段
            item.pop("duration_max", None)
            item.pop("wear_per_use", None)
            item.pop("destroy_on_durability_zero", None)
            item.pop("durability_affects_stats", None)

        # 构建 equipment
        if equipment_mode == "weapon":
            item["equipment"] = {
                "type": "weapon",
                "weapon_type": item.pop("weapon_type", "sword"),
                "balance": item.pop("balance", 2),
                "durability": durability,
            }
        elif equipment_mode == "armor":
            item["equipment"] = {
                "type": "armor",
                "armor_type": item.pop("armor_type", "Head"),
                "durability": durability,
            }
        elif equipment_mode == "charm":
            item["equipment"] = {"type": "charm"}
        else:
            item["equipment"] = {"type": "none"}

        # 清理残留字段
        item.pop("weapon_type", None)
        item.pop("balance", None)
        item.pop("armor_type", None)

        # ====== Quality ======
        quality_int = item.pop("quality", 1)
        if quality_int == 7:
            item["quality"] = {"type": "artifact"}
        elif quality_int == 6:
            item["quality"] = {"type": "unique"}
        else:
            item["quality"] = {"type": "common"}

        # ====== Trigger ======
        trigger_mode = item.pop("trigger_mode", "none")
        if trigger_mode == "effect":
            item["trigger"] = {
                "type": "effect",
                "consumable_attributes": item.pop("consumable_attributes", {}),
                "poison_duration": item.pop("poison_duration", 0),
            }
        elif trigger_mode == "skill":
            item["trigger"] = {
                "type": "skill",
                "skill_object": item.pop("skill_object", ""),
            }
        else:
            item["trigger"] = {"type": "none"}
            item.pop("consumable_attributes", None)
            item.pop("poison_duration", None)
            item.pop("skill_object", None)

        # ====== Charges ======
        charge_mode = item.pop("charge_mode", "limited")
        has_trigger = trigger_mode != "none"

        if has_trigger:
            if charge_mode == "unlimited":
                item["charges"] = {
                    "type": "unlimited",
                    "draw_charges": item.pop("draw_charges", False),
                }
            else:
                item["charges"] = {
                    "type": "limited",
                    "max_charges": item.pop("charge", 1),
                    "draw_charges": item.pop("draw_charges", False),
                }
        else:
            item["charges"] = {"type": "none"}
            item.pop("charge", None)
            item.pop("draw_charges", None)

        # ====== ChargeRecovery ======
        if item.pop("has_charge_recovery", False):
            item["charge_recovery"] = {
                "type": "interval",
                "interval": item.pop("charge_recovery_interval", 10),
            }
        else:
            item["charge_recovery"] = {"type": "none"}
            item.pop("charge_recovery_interval", None)

        # ====== Spawn ======
        if item.pop("exclude_from_random", True):
            item["spawn"] = {"type": "excluded"}
        else:
            item["spawn"] = {
                "type": "random",
                "container_spawn": item.pop("container_spawn", "none"),
                "shop_spawn": item.pop("shop_spawn", "none"),
                "quality_tag": item.pop("quality_tag", ""),
                "dungeon_tag": item.pop("dungeon_tag", ""),
                "country_tag": item.pop("country_tag", ""),
                "extra_tags": item.pop("extra_tags", []),
            }

        # 清理残留的 spawn 相关字段
        item.pop("container_spawn", None)
        item.pop("shop_spawn", None)
        item.pop("quality_tag", None)
        item.pop("dungeon_tag", None)
        item.pop("country_tag", None)
        item.pop("extra_tags", None)

        # ====== Textures ======
        tex = item.get("textures", {})
        if tex:
            item["textures"] = _migrate_textures_v1_to_v2(tex, item.get("equipment", {}))

        # 清理已废弃字段
        item.pop("rarity", None)  # 由 quality 推导
        item.pop("slot", None)  # 由 equipment 推导


def _migrate_textures_v1_to_v2(tex: dict, equipment: dict) -> dict:
    """将 V1 贴图格式迁移到 V2"""
    result: dict[str, Any] = {}

    # inventory (不变)
    result["inventory"] = tex.get("inventory", [])

    # loot
    loot_paths = tex.get("loot", [])
    if tex.get("loot_use_relative_speed", False):
        speed = {"type": "relative", "multiplier": tex.get("loot_fps", 0.25)}
    else:
        speed = {"type": "absolute", "fps": tex.get("loot_fps", 10.0)}
    result["loot"] = {"paths": loot_paths, "speed": speed}

    # char - 根据 equipment 类型决定结构
    equipment_type = equipment.get("type", "none")
    armor_type = equipment.get("armor_type", "")

    character = tex.get("character", [])
    character_left = tex.get("character_left", [])
    character_standing1 = tex.get("character_standing1", "")
    character_rest = tex.get("character_rest", "")

    # 检测是否为多姿势护甲
    multi_pose_slots = {"Head", "Chest", "Arms", "Legs", "Back"}
    is_multi_pose = equipment_type == "armor" and armor_type in multi_pose_slots

    if is_multi_pose:
        # MultiPoseCharTexture
        result["char"] = {
            "type": "multi_pose",
            "standing0": {
                "path": character[0] if character else "",
                **_offset_to_origin(tex.get("offset_x", 0), tex.get("offset_y", 0)),
            },
            "standing1": {
                "path": character_standing1,
                **_offset_to_origin(tex.get("offset_x_standing1", 0), tex.get("offset_y_standing1", 0)),
            },
            "rest": {
                "path": character_rest,
                **_offset_to_origin(tex.get("offset_x_rest", 0), tex.get("offset_y_rest", 0)),
            },
            "standing0_female": {
                "path": tex.get("character_female", ""),
                **_offset_to_origin(tex.get("offset_x_female", 0), tex.get("offset_y_female", 0)),
            },
            "standing1_female": {
                "path": tex.get("character_standing1_female", ""),
                **_offset_to_origin(tex.get("offset_x_standing1_female", 0), tex.get("offset_y_standing1_female", 0)),
            },
            "rest_female": {
                "path": tex.get("character_rest_female", ""),
                **_offset_to_origin(tex.get("offset_x_rest_female", 0), tex.get("offset_y_rest_female", 0)),
            },
        }
    elif equipment_type == "weapon" or (equipment_type == "armor" and armor_type == "shield"):
        # WeaponCharTexture
        result["char"] = {
            "type": "weapon",
            "main": {
                "paths": character,
                **_offset_to_origin(tex.get("offset_x", 0), tex.get("offset_y", 0)),
            },
            "left": {
                "paths": character_left,
                **_offset_to_origin(tex.get("offset_x_left", 0), tex.get("offset_y_left", 0)),
            },
        }
    else:
        # NoCharTexture
        result["char"] = {"type": "none"}

    return result


def _offset_to_origin(offset_x: int, offset_y: int) -> dict:
    """将旧版 offset 转换为 origin 字段

    如果 offset 为零，返回空 dict (使用默认值)
    """
    if offset_x == 0 and offset_y == 0:
        return {}
    return {
        "origin": {
            "x": CHAR_MODEL_ORIGIN[0] + offset_x,
            "y": CHAR_MODEL_ORIGIN[1] + offset_y,
        }
    }


# ============================================================================
# Weapon/Armor 贴图迁移
# ============================================================================


def _migrate_weapon_textures_v1_to_v2(tex: dict) -> dict:
    """将 Weapon 的 V1 贴图格式迁移到 V2"""
    result: dict[str, Any] = {}

    # inventory (不变)
    result["inventory"] = tex.get("inventory", [])

    # loot
    loot_paths = tex.get("loot", [])
    if tex.get("loot_use_relative_speed", False):
        speed = {"type": "relative", "multiplier": tex.get("loot_fps", 0.25)}
    else:
        speed = {"type": "absolute", "fps": tex.get("loot_fps", 10.0)}
    result["loot"] = {"paths": loot_paths, "speed": speed}

    # char - 武器使用 WeaponCharTexture
    character = tex.get("character", [])
    character_left = tex.get("character_left", [])

    result["char"] = {
        "type": "weapon",
        "main": {
            "paths": character,
            **_offset_to_origin(tex.get("offset_x", 0), tex.get("offset_y", 0)),
        },
        "left": {
            "paths": character_left,
            **_offset_to_origin(tex.get("offset_x_left", 0), tex.get("offset_y_left", 0)),
        },
    }

    return result


def _migrate_armor_textures_v1_to_v2(tex: dict, slot: str) -> dict:
    """将 Armor 的 V1 贴图格式迁移到 V2"""
    result: dict[str, Any] = {}

    # inventory (不变)
    result["inventory"] = tex.get("inventory", [])

    # loot
    loot_paths = tex.get("loot", [])
    if tex.get("loot_use_relative_speed", False):
        speed = {"type": "relative", "multiplier": tex.get("loot_fps", 0.25)}
    else:
        speed = {"type": "absolute", "fps": tex.get("loot_fps", 10.0)}
    result["loot"] = {"paths": loot_paths, "speed": speed}

    # char - 根据槽位决定类型
    character = tex.get("character", [])
    character_standing1 = tex.get("character_standing1", "")
    character_rest = tex.get("character_rest", "")

    multi_pose_slots = {"Head", "Chest", "Arms", "Legs", "Back"}
    is_multi_pose = slot in multi_pose_slots

    if is_multi_pose:
        result["char"] = {
            "type": "multi_pose",
            "standing0": {
                "path": character[0] if character else "",
                **_offset_to_origin(tex.get("offset_x", 0), tex.get("offset_y", 0)),
            },
            "standing1": {
                "path": character_standing1,
                **_offset_to_origin(tex.get("offset_x_standing1", 0), tex.get("offset_y_standing1", 0)),
            },
            "rest": {
                "path": character_rest,
                **_offset_to_origin(tex.get("offset_x_rest", 0), tex.get("offset_y_rest", 0)),
            },
            "standing0_female": {
                "path": tex.get("character_female", ""),
                **_offset_to_origin(tex.get("offset_x_female", 0), tex.get("offset_y_female", 0)),
            },
            "standing1_female": {
                "path": tex.get("character_standing1_female", ""),
                **_offset_to_origin(tex.get("offset_x_standing1_female", 0), tex.get("offset_y_standing1_female", 0)),
            },
            "rest_female": {
                "path": tex.get("character_rest_female", ""),
                **_offset_to_origin(tex.get("offset_x_rest_female", 0), tex.get("offset_y_rest_female", 0)),
            },
        }
    elif slot == "shield":
        # 盾牌类似武器
        character_left = tex.get("character_left", [])
        result["char"] = {
            "type": "weapon",
            "main": {
                "paths": character,
                **_offset_to_origin(tex.get("offset_x", 0), tex.get("offset_y", 0)),
            },
            "left": {
                "paths": character_left,
                **_offset_to_origin(tex.get("offset_x_left", 0), tex.get("offset_y_left", 0)),
            },
        }
    else:
        # 饰品等无角色贴图
        result["char"] = {"type": "none"}

    return result
