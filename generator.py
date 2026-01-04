# -*- coding: utf-8 -*-
"""
代码生成器和贴图工具模块

包含 C# 模组代码生成器和贴图处理工具函数。
"""

import os
import re
import shutil
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from constants import (
    ARMOR_PREVIEW_HEIGHT,
    ARMOR_PREVIEW_WIDTH,
    CONSUMABLE_INSTANT_ATTRS,
    DAMAGE_ATTRIBUTES,
    EXTRA_ORDER_ATTRS,
    GAME_FPS,
    GML_ANCHOR_X,
    GML_ANCHOR_Y,
    HYBRID_QUALITY_LABELS,
    LANGUAGE_LABELS,
    LANGUAGE_TO_ENUM_MAP,
    PRIMARY_LANGUAGE,
    SLOT_BALANCE,
    VALID_MAX_X,
    VALID_MAX_Y,
    VALID_MIN_X,
    VALID_MIN_Y,
    VIEWPORT_CHAR_OFFSET_X,
    VIEWPORT_CHAR_OFFSET_Y,
)
from models import Armor, HybridItem, Item, ItemTextures, ModProject, Weapon, QUALITY_ARTIFACT, QUALITY_UNIQUE, SpawnMode, EquipmentMode, TriggerMode, ChargeMode  # <- import constants

# 武器/护甲属性生成辅助 <- moved to module level
TIER_TO_ENUM = {1: "Tier1", 2: "Tier2", 3: "Tier3", 4: "Tier4", 5: "Tier5"}
WEIGHT_TO_ENUM = {
    "VeryLight": "VeryLight", "Very Light": "VeryLight",
    "Light": "Light", "Medium": "Medium", "Heavy": "Heavy", "Net": "Net",
}


def _compute_damage_type(attributes: dict) -> str:  # <- extracted helper
    """计算主伤害类型（最高值优先，无则默认 Slashing）"""
    damage_attrs = {k: v for k, v in attributes.items() if k in DAMAGE_ATTRIBUTES and v != 0}
    if not damage_attrs:
        return "Slashing_Damage"
    max_val = max(damage_attrs.values())
    ties = [t for t, v in damage_attrs.items() if v == max_val]
    return "Slashing_Damage" if "Slashing_Damage" in ties else ties[0]



# ============== 贴图处理工具函数 ==============


def calculate_crop_region(
    img_width: int, img_height: int, off_x: int, off_y: int
) -> tuple:
    """计算武器贴图的裁剪区域

    Args:
        img_width: 原图宽度
        img_height: 原图高度
        off_x: 用户设置的水平偏移
        off_y: 用户设置的垂直偏移

    Returns:
        tuple: (crop_x1, crop_y1, crop_x2, crop_y2, is_valid)
    """
    valid_local_min_x = VALID_MIN_X + off_x
    valid_local_max_x = VALID_MAX_X + off_x
    valid_local_min_y = VALID_MIN_Y + off_y
    valid_local_max_y = VALID_MAX_Y + off_y

    crop_x1 = int(max(0, valid_local_min_x))
    crop_y1 = int(max(0, valid_local_min_y))
    crop_x2 = int(min(img_width, valid_local_max_x))
    crop_y2 = int(min(img_height, valid_local_max_y))

    is_valid = crop_x1 < crop_x2 and crop_y1 < crop_y2
    return crop_x1, crop_y1, crop_x2, crop_y2, is_valid


def calculate_adjusted_offsets(off_x: int, off_y: int) -> tuple:
    """计算真正裁剪后的调整偏移量

    X方向最大有效偏移: VIEWPORT_CHAR_OFFSET_X = 8
    Y方向最大有效偏移: VIEWPORT_CHAR_OFFSET_Y = 12
    """
    adjusted_off_x = min(off_x, VIEWPORT_CHAR_OFFSET_X)
    adjusted_off_y = min(off_y, VIEWPORT_CHAR_OFFSET_Y)
    return adjusted_off_x, adjusted_off_y


def copy_texture(src_path: str, dst_path, mask_offsets: tuple = None) -> str | None:
    """复制贴图文件，如果指定 mask_offsets 则根据有效范围进行裁剪

    Returns:
        错误信息字符串，成功则返回 None
    """
    if not src_path:
        return None
    if not os.path.exists(src_path):
        return f"贴图文件不存在: {src_path}"

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    if mask_offsets and Image:
        try:
            off_x, off_y = mask_offsets
            with Image.open(src_path) as img:
                img = img.convert("RGBA")
                w, h = img.size

                crop_x1, crop_y1, crop_x2, crop_y2, is_valid = calculate_crop_region(
                    w, h, off_x, off_y
                )

                if is_valid:
                    cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                    cropped.save(dst_path)
                    return None
                else:
                    # 贴图超出有效区域，创建占位符
                    placeholder = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                    placeholder.save(dst_path)
                    return f"警告: 贴图 {src_path} 完全超出有效显示区域"
        except Exception as e:
            # 裁剪失败，回退到直接复制
            # 注：此处不返回警告，因为后续 shutil.copy2 会正常复制文件
            pass

    try:
        shutil.copy2(src_path, dst_path)
        return None
    except Exception as e:
        return f"复制贴图失败 {src_path}: {e}"


def copy_armor_pose_texture(
    src_path: str, dst_path, off_x: int, off_y: int
) -> str | None:
    """复制护甲姿势贴图，通过裁剪+透明填充实现偏移效果

    护甲穿戴贴图固定为 48x40 尺寸，偏移通过裁剪原图并在透明画布上重绘实现。

    Args:
        src_path: 源贴图路径
        dst_path: 目标路径
        off_x: 水平偏移（正值向右移动贴图内容）
        off_y: 垂直偏移（正值向下移动贴图内容）

    Returns:
        错误信息字符串，成功则返回 None
    """
    if not src_path:
        return None
    if not os.path.exists(src_path):
        return f"贴图文件不存在: {src_path}"

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    if not Image:
        # 没有 PIL，直接复制
        try:
            shutil.copy2(src_path, dst_path)
            return None
        except Exception as e:
            return f"复制贴图失败 {src_path}: {e}"

    try:
        with Image.open(src_path) as img:
            img = img.convert("RGBA")
            src_w, src_h = img.size

            # 目标尺寸固定为 48x40
            dst_w, dst_h = ARMOR_PREVIEW_WIDTH, ARMOR_PREVIEW_HEIGHT

            # 创建透明画布
            canvas = Image.new("RGBA", (dst_w, dst_h), (0, 0, 0, 0))

            # 计算源图裁剪区域和目标粘贴位置
            # 偏移的含义：off_x 正值表示贴图内容向右移动
            # 即从源图的 (off_x, off_y) 开始裁剪

            # 源图裁剪起点
            src_x1 = max(0, off_x)
            src_y1 = max(0, off_y)

            # 源图裁剪终点（不超过源图尺寸和目标尺寸）
            src_x2 = min(src_w, off_x + dst_w)
            src_y2 = min(src_h, off_y + dst_h)

            # 如果偏移为负，需要在目标画布上留出空白
            dst_x = max(0, -off_x)
            dst_y = max(0, -off_y)

            # 检查是否有有效区域
            if src_x1 < src_x2 and src_y1 < src_y2:
                cropped = img.crop((src_x1, src_y1, src_x2, src_y2))
                canvas.paste(cropped, (dst_x, dst_y))

            canvas.save(dst_path)
            return None
    except Exception as e:
        return f"处理护甲贴图失败 {src_path}: {e}"




def copy_item_textures(
    item_id: str,
    textures: ItemTextures,
    sprites_dir: Path,
    copy_char: bool,
    copy_left: bool,
    is_multi_pose_armor: bool = False,
) -> list[str]:
    """复制物品的所有贴图文件

    Args:
        item_id: 物品ID
        textures: 贴图数据
        sprites_dir: 精灵图输出目录
        copy_char: 是否复制角色/穿戴贴图
        copy_left: 是否复制左手贴图
        is_multi_pose_armor: 是否为多姿势护甲（头/身/手/腿/背）

    Returns:
        错误/警告信息列表
    """
    errors = []

    def _copy(src, dst, mask=None):
        err = copy_texture(src, dst, mask)
        if err:
            errors.append(err)

    def _copy_armor_pose(src, dst, off_x, off_y):
        err = copy_armor_pose_texture(src, dst, off_x, off_y)
        if err:
            errors.append(err)

    def _copy_texture_list(paths: list, prefix: str, mask=None):
        """复制贴图列表，根据长度决定命名方式"""
        if not paths:
            return
        if len(paths) == 1:
            _copy(paths[0], sprites_dir / f"{prefix}.png", mask)
        else:
            for idx, path in enumerate(paths):
                _copy(path, sprites_dir / f"{prefix}_{idx}.png", mask)

    # 角色/手持/穿戴贴图
    if copy_char:
        if is_multi_pose_armor:
            # 多姿势装备（头/身/手/腿/背）：站立和休息姿势贴图
            # 游戏用 s_char 帧序列的第0/1帧存储站立两姿势，休息姿势用 s_char3 单独存储

            # ====== 默认/男性版贴图 ======
            # 站立姿势0: s_char_{id}_0.png (帧序列第0帧)
            if textures.character:
                standing0_path = textures.character[0] if textures.character else ""
                if standing0_path:
                    _copy_armor_pose(
                        standing0_path,
                        sprites_dir / f"s_char_{item_id}_0.png",
                        textures.offset_x,
                        textures.offset_y,
                    )

            # 站立姿势1: s_char_{id}_1.png (帧序列第1帧，可选)
            if textures.character_standing1:
                _copy_armor_pose(
                    textures.character_standing1,
                    sprites_dir / f"s_char_{item_id}_1.png",
                    textures.offset_x_standing1,
                    textures.offset_y_standing1,
                )

            # 休息姿势: s_char3_{id}.png (独立贴图槽)
            if textures.character_rest:
                _copy_armor_pose(
                    textures.character_rest,
                    sprites_dir / f"s_char3_{item_id}.png",
                    textures.offset_x_rest,
                    textures.offset_y_rest,
                )

            # ====== 女性版贴图 ======
            # 文件名格式：s_char_{id}_female_0.png (female 后缀在数字前)

            # 女性版站立姿势0: s_char_{id}_female_0.png
            if textures.character_female:
                _copy_armor_pose(
                    textures.character_female,
                    sprites_dir / f"s_char_{item_id}_female_0.png",
                    textures.offset_x_female,
                    textures.offset_y_female,
                )

            # 女性版站立姿势1: s_char_{id}_female_1.png (仅当男性版设置了才可能有)
            if textures.character_standing1_female:
                _copy_armor_pose(
                    textures.character_standing1_female,
                    sprites_dir / f"s_char_{item_id}_female_1.png",
                    textures.offset_x_standing1_female,
                    textures.offset_y_standing1_female,
                )

            # 女性版休息姿势: s_char3_{id}_female.png
            if textures.character_rest_female:
                _copy_armor_pose(
                    textures.character_rest_female,
                    sprites_dir / f"s_char3_{item_id}_female.png",
                    textures.offset_x_rest_female,
                    textures.offset_y_rest_female,
                )
        else:
            # 武器/盾牌：动画帧序列
            mask = (textures.offset_x, textures.offset_y)
            _copy_texture_list(textures.character, f"s_char_{item_id}", mask)

    # 左手贴图（仅武器/盾牌）
    if copy_left and textures.character_left:
        mask_left = (textures.offset_x_left, textures.offset_y_left)
        _copy_texture_list(textures.character_left, f"s_charleft_{item_id}", mask_left)

    # 常规/物品栏贴图
    for idx, inv_texture in enumerate(textures.inventory):
        _copy(inv_texture, sprites_dir / f"s_inv_{item_id}_{idx}.png")

    # 战利品贴图
    _copy_texture_list(textures.loot, f"s_loot_{item_id}")

    return errors


def format_description(text: str) -> str:
    """处理描述文本：strip -> splitlines -> join('#') -> 转义双引号
    
    用于通过 C# 接口注入的物品描述（普通武器/护甲）
    """
    if not text:
        return ""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    joined = "#".join(lines)
    return joined.replace('"', '\\"')


def format_description_gml(text: str) -> str:
    """处理描述文本：仅转义双引号
    
    用于直接写入 GML 的物品描述（混合物品），不需要换行转译
    GML 中 # 本身就是换行符，用户可以直接在描述中使用 # 换行
    """
    if not text:
        return ""
    # 只转义引号，不处理换行（用户直接使用 # 作为换行符）
    return text.strip().replace('"', '\\"')


# ============== C# 代码生成器 ==============


class CodeGenerator:
    """C# 模组代码生成器"""

    def __init__(self, project: ModProject):
        self.project = project

    def _escape_multiline_string(self, text: str) -> str:
        """转义多行字符串用于 C# verbatim string (@"...")

        在 verbatim string 中，双引号需要用两个双引号转义
        """
        if not text:
            return ""
        # 在 C# verbatim string 中，" 需要转义为 ""
        return text.replace('"', '""')

    def _has_equipment_spawn_hybrids(self) -> bool:
        """检查是否有任何混合物品使用装备路径生成"""
        return any(
            h.equipment_mode in (EquipmentMode.WEAPON, EquipmentMode.ARMOR, EquipmentMode.CHARM) and h.spawn_mode == SpawnMode.EQUIPMENT
            for h in self.project.hybrid_items
        )

    def generate(self) -> dict[str, str]:
        """生成完整的 C# 模组代码
        
        Returns:
            dict[str, str]: 文件名到内容的映射
                - "{code_name}.cs": 主文件，包含 PatchMod() 和物品方法
                - "{code_name}.Helpers.cs": 辅助文件，包含所有 helper 方法
        """
        code_namespace = self.project.code_name.strip() or "ModNamespace"
        has_hybrids = bool(self.project.hybrid_items)
        
        # ==================== 主文件 ====================
        main_code = f"""using ModShardLauncher;
using ModShardLauncher.Mods;
using UndertaleModLib;
using UndertaleModLib.Models;
using System.Collections.Generic;
using System.Linq;

namespace {code_namespace};
public partial class {code_namespace} : Mod
{{
    public override string Author => "{self.project.author}";
    public override string Name => "{self.project.name}";
    public override string Description => @"{self._escape_multiline_string(self.project.description)}";
    public override string Version => "{self.project.version}";
    public override string TargetVersion => "{self.project.target_version}";

    public override void PatchMod()
    {{
"""

        # 如果有混合物品，先注入辅助脚本和 o_hoverHybrid（只需要一次）
        if has_hybrids:
            main_code += "        // 注入 hover 辅助脚本（仅执行一次）\n"
            main_code += "        EnsureHoverScriptsExist();\n"
            main_code += "        // 注入混合物品专用 hover 对象（仅执行一次）\n"
            main_code += "        EnsureHoverHybridExists();\n"
            # 仅当有装备路径混合物品时才调用注册系统
            if self._has_equipment_spawn_hybrids():
                main_code += "        // 注入混合装备注册系统（仅执行一次）\n"
                main_code += "        EnsureHybridEquipmentRegistry();\n"
            main_code += "\n"

        for weapon in self.project.weapons:
            main_code += f"        Add{weapon.id}();\n"
        for armor in self.project.armors:
            main_code += f"        AddArmor{armor.id}();\n"
        for hybrid in self.project.hybrid_items:
            main_code += f"        AddHybrid{hybrid.id}();\n"

        main_code += "    }\n\n"

        for item in self.project.weapons + self.project.armors:
            main_code += self._generate_item_method(item)

        for hybrid in self.project.hybrid_items:
            main_code += self._generate_hybrid_item_method(hybrid)

        main_code += "}\n"
        
        # ==================== 辅助文件 ====================
        helpers_code = f"""using ModShardLauncher;
using ModShardLauncher.Mods;
using UndertaleModLib;
using UndertaleModLib.Models;
using System.Collections.Generic;
using System.Linq;

namespace {code_namespace};

// ============== 辅助方法（partial class） ==============
public partial class {code_namespace}
{{
"""
        
        # 只在有混合物品时生成辅助方法
        if has_hybrids:
            helpers_code += self._generate_hover_scripts_injection_method()
            helpers_code += self._generate_hover_hybrid_method()
            helpers_code += self._generate_inject_item_stats_method()
            helpers_code += self._generate_gml_helper_methods()
            # 仅当有装备路径混合物品时才生成注册方法
            if self._has_equipment_spawn_hybrids():
                helpers_code += self._generate_hybrid_equipment_registry_method()
        else:
            helpers_code += "    // 无混合物品，无需辅助方法\n"
        
        helpers_code += "}\n"
        
        return {
            f"{code_namespace}.cs": main_code,
            f"{code_namespace}.Helpers.cs": helpers_code,
        }

    def _generate_item_method(self, item: Item) -> str:
        """生成单个物品的 C# 方法"""
        is_weapon = isinstance(item, Weapon)
        is_shield = isinstance(item, Armor) and item.slot == "shield"
        method_name = f"Add{item.id}" if is_weapon else f"AddArmor{item.id}"

        code = f"    private void {method_name}()\n    {{\n"
        code += self._generate_item_injection_code(item)
        code += self._generate_localization_code(item)
        if is_weapon or is_shield:
            code += self._generate_gml_offset_code(item)
        code += self._generate_loot_animation_code(item)
        code += "    }\n\n"

        return code

    def _generate_item_injection_code(self, item: Item) -> str:
        """生成物品注入 C# 代码"""
        is_weapon = isinstance(item, Weapon)

        if is_weapon:
            prefix = "Weapons"
            code = "        Msl.InjectTableWeapons(\n"
        else:
            prefix = "Armor"
            code = "        Msl.InjectTableArmor(\n"
            code += f"            hook: Msl.ArmorHook.{item.hook},\n"

        code += f'            name: "{item.name}",\n'
        code += f"            Tier: Msl.{prefix}Tier.{item.tier},\n"
        code += f'            id: "{item.id}",\n'
        code += f"            Slot: Msl.{prefix}Slot.{item.slot},\n"

        if isinstance(item, Armor):
            code += f"            Class: Msl.ArmorClass.{item.armor_class},\n"

        code += f"            rarity: Msl.{prefix}Rarity.{item.rarity},\n"
        code += f"            Mat: Msl.{prefix}Material.{item.mat},\n"
        code += f"            tags: Msl.{prefix}Tags.{item.tags.replace(' ', '')},\n"

        if is_weapon:
            code += f"            Price: {item.price},\n"
            code += "            Markup: 1,\n"
            code += f"            MaxDuration: {item.max_duration},\n"
            code += f"            Rng: {item.rng}"

            balance_value = SLOT_BALANCE.get(item.slot)
            if balance_value is not None:
                code += f",\n            Balance: {balance_value}"
        else:
            code += f"            MaxDuration: {item.max_duration},\n"
            code += f"            Price: {item.price},\n"
            code += "            Markup: 1"

        code += f",\n            fireproof: {'true' if item.fireproof else 'false'}"
        if isinstance(item, Armor):
            code += f",\n            IsOpen: {'true' if item.is_open else 'false'}"
        code += f",\n            NoDrop: {'true' if item.no_drop else 'false'}"

        for attr, value in item.attributes.items():
            if value != 0:
                attr_name = attr
                if is_weapon and attr == "Electromantic_Power":
                    attr_name = "Electroantic_Power"
                code += f",\n            {attr_name}: {value}"

        if isinstance(item, Armor):
            for frag_type, frag_value in item.fragments.items():
                if frag_value > 0:
                    code += f",\n            {frag_type}: {frag_value}"

        code += "\n        );\n\n"
        return code

    def _generate_localization_code(self, item: Item) -> str:
        """生成本地化 C# 代码"""
        code = "        Msl.InjectTableWeaponTextsLocalization(\n"
        code += "            new LocalizationWeaponText(\n"
        code += f'                id: "{item.name}",\n'
        code += "                name: new Dictionary<ModLanguage, string>() {\n"

        required_langs = {PRIMARY_LANGUAGE}
        if PRIMARY_LANGUAGE != "English":
            required_langs.add("English")

        langs_to_generate = set(required_langs)
        for lang in item.localization.languages:
            if lang in LANGUAGE_TO_ENUM_MAP:
                langs_to_generate.add(lang)

        for lang in LANGUAGE_LABELS:
            if lang not in langs_to_generate:
                continue
            lang_enum = LANGUAGE_TO_ENUM_MAP.get(lang)
            if not lang_enum:
                continue
            name = item.localization.get_name(lang)
            code += f'                    {{{lang_enum}, "{name}"}},\n'

        code += "                },\n"
        code += "                description: new Dictionary<ModLanguage, string>() {\n"

        for lang in LANGUAGE_LABELS:
            if lang not in langs_to_generate:
                continue
            lang_enum = LANGUAGE_TO_ENUM_MAP.get(lang)
            if not lang_enum:
                continue
            desc = item.localization.get_description(lang)
            formatted_desc = format_description(desc)
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

    def _generate_gml_offset_code(self, item: Item) -> str:
        """生成 GML 偏移注入代码（武器/盾牌）"""
        gml_code_block = ""

        if item.textures.offset_x != 0 or item.textures.offset_y != 0:
            adj_off_x, adj_off_y = calculate_adjusted_offsets(
                item.textures.offset_x, item.textures.offset_y
            )

            if adj_off_x != 0 or adj_off_y != 0:
                val_y = GML_ANCHOR_Y + adj_off_y
                val_x = GML_ANCHOR_X + adj_off_x
                sprite_name = f"s_char_{item.id}"
                gml_code_block += self._generate_anchor_gml_block(
                    val_y, val_x, sprite_name
                )

        if item.textures.has_char_left():
            if item.textures.offset_x_left != 0 or item.textures.offset_y_left != 0:
                adj_off_x_left, adj_off_y_left = calculate_adjusted_offsets(
                    item.textures.offset_x_left, item.textures.offset_y_left
                )

                if adj_off_x_left != 0 or adj_off_y_left != 0:
                    val_y = GML_ANCHOR_Y + adj_off_y_left
                    val_x = GML_ANCHOR_X + adj_off_x_left
                    sprite_name = f"s_charleft_{item.id}"
                    gml_code_block += self._generate_anchor_gml_block(
                        val_y, val_x, sprite_name
                    )

        if not gml_code_block:
            return ""

        gml_code_block = gml_code_block.rstrip()

        # 定位锚点: gml_GlobalScript_scr_ds_init 中的一段稳定 bytecode
        # 对应 GML: ds_map_add(global.customizationAnchors, 16635, [29, 34])
        # 选择此锚点是因为它被其他模组修改的风险低，不易出现重复导致 InsertBelow 位置错误
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

    def _generate_loot_animation_code(self, item: Item) -> str:
        """生成战利品贴图动画设置 C# 代码"""
        if not item.textures.is_animated("loot"):
            return ""

        sprite_name = f"s_loot_{item.id}"
        fps_value = item.textures.loot_fps

        if item.textures.loot_use_relative_speed:
            speed_type = "AnimSpeedType.FramesPerGameFrame"
        else:
            speed_type = "AnimSpeedType.FramesPerSecond"

        fps_formatted = f"{fps_value:.3f}"

        code = f"""
        // 设置战利品贴图动画播放速度
        UndertaleSprite lootSprite_{item.id} = Msl.GetSprite("{sprite_name}");
        if (lootSprite_{item.id}.CollisionMasks != null && lootSprite_{item.id}.CollisionMasks.Count > 0)
        {{
            lootSprite_{item.id}.CollisionMasks.RemoveAt(0);
        }}
        lootSprite_{item.id}.IsSpecialType = true;
        lootSprite_{item.id}.SVersion = 3;
        lootSprite_{item.id}.GMS2PlaybackSpeed = {fps_formatted}f;
        lootSprite_{item.id}.GMS2PlaybackSpeedType = {speed_type};

"""
        return code

    # ============== 混合物品代码生成 ==============

    def _generate_hybrid_item_method(self, item: HybridItem) -> str:
        """生成单个混合物品的 C# 方法"""
        method_name = f"AddHybrid{item.id}"
        
        code = f"    private void {method_name}()\n    {{\n"
        code += self._generate_hybrid_objects_code(item)
        code += self._generate_hybrid_events_code(item)
        code += self._generate_hybrid_loot_animation_code(item)
        code += "    }\n\n"
        
        return code

    def _generate_hybrid_objects_code(self, item: HybridItem) -> str:
        """生成混合物品的游戏对象创建代码"""
        inv_obj_name = f"o_inv_{item.id}"
        loot_obj_name = f"o_loot_{item.id}"
        inv_sprite = f"s_inv_{item.id}"
        loot_sprite = f"s_loot_{item.id}"
        loot_parent = item.get_loot_parent()
        
        # 确定材质枚举值（首字母大写）
        if item.init_weapon_stats or item.init_armor_stats:
            material_enum = item.material.capitalize()
        else:
            material_enum = "Organic"
        
        # 确定重量枚举值
        weight_enum = WEIGHT_TO_ENUM.get(item.weight, "Light")  # <- use module constant
        
        # 确定 tier 枚举值
        tier_enum = TIER_TO_ENUM.get(item.tier, "None")  # <- use module constant
        
        # 生成本地化字典（确保至少有 English 条目）
        languages = item.localization.languages
        if "English" not in languages:
            languages = {"English": {"name": "", "description": ""}, **languages}
        
        localization_entries = []
        for lang, data in languages.items():
            name = data.get("name", "").replace('"', '\\"')
            localization_entries.append(f'                    {{ModLanguage.{lang}, "{name}"}}')
        
        localization_desc_entries = []
        for lang, data in languages.items():
            desc = format_description(data.get("description", ""))
            localization_desc_entries.append(f'                    {{ModLanguage.{lang}, "{desc}"}}')
        
        name_dict = ",\n".join(localization_entries)
        desc_dict = ",\n".join(localization_desc_entries)
        
        code = f"""        // 创建 Inventory 对象
        UndertaleGameObject {inv_obj_name} = Msl.AddObject(
            name: "{inv_obj_name}",
            parentName: "{item.parent_object}",
            spriteName: "{inv_sprite}",
            isVisible: true,
            isPersistent: true,
            isAwake: true
        );

        // 创建 Loot 对象
        UndertaleGameObject {loot_obj_name} = Msl.AddObject(
            name: "{loot_obj_name}",
            parentName: "{loot_parent}",
            spriteName: "{loot_sprite}",
            isVisible: true,
            isPersistent: false,
            isAwake: true
        );

        // 注入物品元数据（使用本地 Helper 以支持自定义 Cat/Subcat/tags）
        InjectItemStats(
            id: "{item.id}",
            Price: {item.base_price},
            tier: ItemTier.{tier_enum},
            Cat: "{item.cat}",
            Subcat: "{" ".join(item.subcats)}",
            Material: ItemMaterial.{material_enum},
            Weight: ItemWeight.{weight_enum},
            tags: "{item.effective_tags}",
            dropsOnce: false
        );


        // 注入本地化
        Msl.InjectTableItemsLocalization(
            new LocalizationItem(
                id: "{item.id}",
                name: new Dictionary<ModLanguage, string>() {{
{name_dict}
                }},
                effect: new Dictionary<ModLanguage, string>() {{
                    {{ModLanguage.English, ""}}
                }},
                description: new Dictionary<ModLanguage, string>() {{
{desc_dict}
                }}
            )
        );

"""
        return code


    def _generate_hybrid_events_code(self, item: HybridItem) -> str:
        """生成混合物品的事件代码"""
        inv_obj_name = f"o_inv_{item.id}"
        
        # 生成 GML 代码
        create_code = self._generate_hybrid_create_gml(item)
        alarm_code = self._generate_hybrid_alarm_gml(item)
        step_code = self._generate_hybrid_step_gml(item)
        other10_code = self._generate_hybrid_other10_gml(item)
        other13_code = self._generate_hybrid_other13_gml(item)  # Hover 事件
        other16_code = self._generate_hybrid_other16_gml(item)  # 属性衰减生效
        other24_code = self._generate_hybrid_other24_gml(item)
        
        code = f"""        // 应用事件代码
        {inv_obj_name}.ApplyEvent(
            new MslEvent(eventType: EventType.Create, subtype: 0, code: @"
{self._escape_multiline_string(create_code)}
            ")"""
        
        if alarm_code:
            code += f""",
            new MslEvent(eventType: EventType.Alarm, subtype: 0, code: @"
{self._escape_multiline_string(alarm_code)}
            ")"""
        
        if step_code:
            code += f""",
            new MslEvent(eventType: EventType.Step, subtype: 0, code: @"
{self._escape_multiline_string(step_code)}
            ")"""
        
        if other10_code:
            code += f""",
            new MslEvent(eventType: EventType.Other, subtype: 10, code: @"
{self._escape_multiline_string(other10_code)}
            ")"""
        
        # Other_13: Hover 事件（使用 o_hoverHybrid）
        code += f""",
            new MslEvent(eventType: EventType.Other, subtype: 13, code: @"
{self._escape_multiline_string(other13_code)}
            ")"""

        # Other_16: 属性衰减应用（因为 o_inv_consum 覆盖了 o_inv_slot 逻辑，需手动恢复）
        if other16_code:
            code += f""",
            new MslEvent(eventType: EventType.Other, subtype: 16, code: @"
{self._escape_multiline_string(other16_code)}
            ")"""
        
        code += f""",
            new MslEvent(eventType: EventType.Other, subtype: 24, code: @"
{self._escape_multiline_string(other24_code)}
            ")"""
        
        code += "\n        );\n\n"
        return code

    def _generate_hybrid_create_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Create_0 GML 代码
        
        简化策略：
        - 所有常量直接在 Create_0 设置（无需 is_new 保护）
        - 设置 duration/charge 变量供父类 Alarm_0 在 is_new 时存入 data
        - 使用 ds_map_replace 写入 data（覆盖已有值或添加新值）
        - 父类 o_inv_consum.Alarm_0 会处理 charge/duration 的持久化和恢复
        """
        lines = []
        lines.append("event_inherited();")
        lines.append("")
        
        # 使用 scr_consum_atr 从 global.consum_stat_data 初始化基础属性
        lines.append("// 从 global.consum_stat_data 初始化基础属性")
        lines.append(f'scr_consum_atr("{item.id}");')
        lines.append("")
        
        # poison_duration（仅当 Poisoning_Chance > 0 时设置）
        poisoning_chance = item.consumable_attributes.get("Poisoning_Chance", 0)
        if poisoning_chance > 0 and item.poison_duration > 0:
            lines.append(f"poison_duration = {item.poison_duration};")
            lines.append("")
        
        lines.append("empty = false;")
        lines.append("is_hybrid_item = true;")
        lines.append("")
        
        # ============== 品质设置 ==============
        if item.quality == QUALITY_ARTIFACT:  # <- use constant
            lines.append("// 品质: 文物")
            lines.append("shineDelay = room_speed * 2;")
            lines.append('ds_map_set(data, "quality", 7);')
            lines.append('ds_map_set(data, "Colour", make_colour_rgb(229, 193, 85));')
            lines.append("alarm[11] = shineDelay;")
        elif item.quality == QUALITY_UNIQUE:  # <- use constant
            lines.append("// 品质: 独特")
            lines.append('ds_map_set(data, "quality", 6);')
            lines.append('ds_map_set(data, "Colour", make_colour_rgb(130, 72, 188));')
        else:  # 普通
            lines.append("// 品质: 普通")
            lines.append('ds_map_set(data, "quality", 1);')
        lines.append("")
        
        # ============== 槽位与装备 ==============
        if item.equipable:
            lines.append(f'slot = "{item.slot}";')
            lines.append("can_equip = true;")
            if item.slot == "hand":
                lines.append(f"hands = {item.hands};")
                lines.append(f"character_sprite_hands = {item.hands};")
        else:
            lines.append('slot = "heal";')
            lines.append("can_equip = false;")
        lines.append("")
        
        # ============== Tier 变量（hover 和修理费需要） ==============
        lines.append(f"Tier = {item.tier};")
        lines.append("")
        
        # ============== 武器/护甲标记与数值 ==============
        if item.is_weapon:
            lines.append("is_weapon = true;")
        
        if item.init_weapon_stats:
            lines.append("// 武器数值")
            lines.append(f'type = "{item.weapon_type}";')
            lines.append(f"Balance = {item.balance};")
            
            # 计算 DamageType
            best_type = _compute_damage_type(item.attributes)  # <- use helper
            lines.append(f'DamageType = "{best_type}";')
            
            # 弓/弩弹药槽
            if item.weapon_type == "crossbow":
                lines.append("haveAmmunitionSlot = true;")
                lines.append('ammunitionType = "bolt";')
                lines.append("isCrossbow = true;")
            elif item.weapon_type == "bow":
                lines.append("haveAmmunitionSlot = true;")
                lines.append('ammunitionType = "arrow";')
            lines.append("")
        
        if item.init_armor_stats:
            lines.append("// 护甲数值")
            lines.append(f'type = "{item.armor_type}";')
            lines.append(f'armor_type = "{item.armor_class}";')
            
            # 非盾牌/戒指/项链的装备需要设置 fragment_*（用于拆解）
            if item.slot not in ["hand", "Ring", "Amulet"]:
                lines.append("")
                lines.append("// 碎片材料（拆解用）")
                frag_keys = ["cloth01", "cloth02", "cloth03", "cloth04",
                             "leather01", "leather02", "leather03", "leather04",
                             "metal01", "metal02", "metal03", "metal04", "gold"]
                for frag in frag_keys:
                    val = item.fragments.get(frag, 0)
                    lines.append(f"fragment_{frag} = {val};")
            lines.append("")
        
        # ============== 使用次数（供父类 Alarm_0 持久化） ==============
        if item.has_charges:
            lines.append("// 使用次数（父类 Alarm_0 会处理持久化）")
            lines.append(f"charge = {item.effective_charge};")
            lines.append(f"max_charge = {item.effective_charge};")
            lines.append(f"draw_charges = {'true' if item.draw_charges else 'false'};")
            lines.append("")
            
            # 消耗品属性 (attributes_data)
            lines.append("// 消耗品属性 (attributes_data)")
            has_consum_attr = False
            for attr, value in item.consumable_attributes.items():
                if value != 0:
                    lines.append(f'ds_map_add(attributes_data, "{attr}", {value});')
                    has_consum_attr = True
            if not has_consum_attr:
                lines.append("// 无消耗品属性")
            lines.append("")
        
        # ============== 耐久（供父类 Alarm_0 持久化） ==============
        if item.has_durability:
            lines.append("// 耐久度（父类 Alarm_0 会处理持久化）")
            lines.append(f"duration = {item.duration_max};")
            lines.append("")
        
        lines.append(f"duration_change = {item.wear_per_use};")
        lines.append(f"delete_after_use = {'true' if item.delete_on_charge_zero else 'false'};")
        lines.append("")
        
        # ============== 被动效果 ==============
        if item.has_passive:
            lines.append("check_inventory_data = true;")
            lines.append("")
        
        # ============== 音效与价格 ==============
        lines.append("// 音效与价格")
        lines.append(f"drop_gui_sound = {item.drop_sound};")
        lines.append(f"pickup_sound = {item.pickup_sound};")
        lines.append(f"base_price = {item.base_price};")
        lines.append("price = base_price;")
        lines.append("")
        
        # ============== 精灵 ==============
        lines.append("// 精灵")
        lines.append(f"s_index = s_inv_{item.id};")
        if item.needs_char_texture():
            lines.append(f"char_sprite = s_char_{item.id};")
            if item.needs_left_texture():
                lines.append(f"charleft_sprite = s_charleft_{item.id};")
            else:
                lines.append("charleft_sprite = -4;")
        else:
            lines.append("char_sprite = -4;")
            lines.append("charleft_sprite = -4;")
        lines.append("char_upper_sprite = -4;")
        lines.append("rest_char_sprite = -4;")
        lines.append("rest_char_upper_sprite = -4;")
        lines.append("")
        
        # ============== data map 静态属性写入 ==============
        # 使用 ds_map_replace 确保每次覆盖都安全（常量值）
        
        lines.append("// data map 元数据")
        lines.append(f'ds_map_replace(data, "tags", "{item.effective_tags}");')
        lines.append(f'ds_map_replace(data, "rarity", "{item.rarity}");')
        lines.append('ds_map_replace(data, "key", "");')
        lines.append("ds_map_replace(data, \"identified\", true);")
        
        if item.has_durability:
            lines.append(f'ds_map_replace(data, "MaxDuration", {item.duration_max});')
        
        if item.init_weapon_stats:
            best_type = _compute_damage_type(item.attributes)  # <- use helper
            lines.append(f'ds_map_replace(data, "DamageType", "{best_type}");')
            lines.append('ds_map_replace(data, "Metatype", "Weapon");')
        
        if item.init_armor_stats:
            lines.append('ds_map_replace(data, "Metatype", "Armor");')
            lines.append("ds_map_replace(data, \"Armor_Type\", Weight);")
        
        if item.init_weapon_stats or item.init_armor_stats:
            lines.append('ds_map_replace(data, "Suffix", string(ds_map_find_value(data, "quality")) + " " + type);')

        return "\n".join(lines)
    
    def _generate_hybrid_step_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Step_0 GML 代码"""
        lines = []
        lines.append("event_inherited();")
        lines.append("")
        
        # 仅当有耐久度时生成 Step 逻辑
        if item.has_durability:
             lines.append("// 耐久度控制逻辑（仿 o_inv_slot）")
             lines.append('var _duration = ds_map_find_value(data, "Duration");')
             lines.append('var _maxDuration = ds_map_find_value(data, "MaxDuration");')
             
             # 贴图切换逻辑
             lines.append("")
             lines.append("// 根据耐久度切换贴图")
             lines.append("var _max_index = sprite_get_number(s_index) - 1;")
             lines.append("var _new_index = 0;")
             lines.append("")
             # 耐久度贴图切换逻辑
             lines.append("if (_duration <= _maxDuration) _new_index = 0;")
             lines.append("if (_duration < (_maxDuration / 2)) _new_index = 1;")
             lines.append("if (_duration < (_maxDuration / 4)) _new_index = 2;")
             lines.append("if (_new_index > _max_index) _new_index = _max_index;")
             lines.append("i_index = _new_index;")
             
             # 属性衰减逻辑
             lines.append("")
             lines.append("// 属性衰减逻辑")
             lines.append("var _tier = _duration / _maxDuration;")
             lines.append("if (_tier < 0.5) {")
             lines.append("    if (_tier > 0.25) DurDecrease = 0.6;")
             lines.append("    else DurDecrease = 0.3;")
             lines.append("} else {")
             lines.append("    DurDecrease = 1;")
             lines.append("}")
            
             # 防止耐久溢出
             lines.append("")
             lines.append("if (_duration > _maxDuration) {")
             lines.append('    ds_map_replace(data, "Duration", _maxDuration);')
             lines.append("}")

             # 关联次数逻辑（linked 模式下验证层已确保 has_durability 为 true）
             if item.charge_mode == ChargeMode.LINKED:
                 lines.append("")
                 lines.append("// 次数与耐久挂钩：自动更新 charge")
                 lines.append(f"charge = floor((_duration / _maxDuration) * {item.effective_charge});")
                 
                 if item.delete_on_charge_zero:
                     lines.append("// 0耐久时删除")
                     lines.append("if (_duration <= 0)")
                     lines.append("    event_user(12);")
        
        # 使用次数恢复逻辑（仅非无消耗模式）
        if item.has_charge_recovery and item.charge_mode != ChargeMode.UNLIMITED:
            lines.append("")
            
            # 公共的回合计算逻辑
            lines.append("// 使用次数恢复")
            if item.charge_mode == ChargeMode.LINKED:
                lines.append("// （恢复耐久，次数由耐久换算）")
            lines.append('var _lastTurn = ds_map_find_value(data, "last_recovery_turn");')
            lines.append("if (!is_undefined(_lastTurn)) {")
            lines.append('    var _totalSec = scr_timeGetTimestamp() * 60 + ds_map_find_value(global.timeDataMap, "seconds");')
            lines.append("    var _currentTurn = floor(_totalSec / 30);")
            lines.append("    var _turnsPassed = _currentTurn - _lastTurn;")
            lines.append("")
            lines.append(f"    if (_turnsPassed >= {item.charge_recovery_interval}) {{")
            lines.append(f"        var _recoveries = floor(_turnsPassed / {item.charge_recovery_interval});")
            
            # 恢复方式分歧
            if item.charge_mode == ChargeMode.LINKED:
                lines.append(f"        var _durPerCharge = _maxDuration / {item.effective_charge};")
                lines.append('        var _dur = ds_map_find_value(data, "Duration");')
                lines.append("        var _newVal = min(_maxDuration, _dur + (_recoveries * _durPerCharge));")
                lines.append('        ds_map_replace(data, "Duration", _newVal);')
                max_val = "_maxDuration"
            else:
                lines.append("        var _newVal = min(max_charge, charge + _recoveries);")
                lines.append("        charge = _newVal;")
                lines.append('        ds_map_replace(data, "charge", charge);')
                max_val = "max_charge"
            
            # 公共的满值检测和回合更新
            lines.append("")
            lines.append(f"        if (_newVal >= {max_val}) {{")
            lines.append('            ds_map_delete(data, "last_recovery_turn");')
            lines.append("        } else {")
            lines.append(f'            ds_map_replace(data, "last_recovery_turn", _lastTurn + (_recoveries * {item.charge_recovery_interval}));')
            lines.append("        }")
            lines.append("    }")
            lines.append("}")
        
        # 技能释放状态跟踪（仅技能模式有效）
        if item.trigger_mode == TriggerMode.SKILL and item.skill_object:
            lines.append("")
            lines.append("// 技能释放状态跟踪")
            lines.append('var _active_skill = ds_map_find_value(data, "_active_skill");')
            lines.append("if (!is_undefined(_active_skill)) {")
            lines.append("    var _should_cleanup = false;")
            lines.append("    var _was_successful = false;")
            lines.append("")
            lines.append("    if (!instance_exists(_active_skill)) {")
            lines.append("        // 技能实例已不存在")
            lines.append("        _should_cleanup = true;")
            lines.append("    } else if (!_active_skill.is_activate) {")
            lines.append("        // 技能已停止激活")
            lines.append("        _should_cleanup = true;")
            lines.append("        _was_successful = _active_skill.last_activated;")
            lines.append("    }")
            lines.append("")
            lines.append("    if (_should_cleanup) {")
            # 技能模式下 has_charges 必定为 true，无需再判断
            lines.append("        // 仅成功执行时扣减充能")
            lines.append("        if (_was_successful) {")
            lines.append("            charge--;")
            lines.append('            ds_map_replace(data, "charge", charge);')
            if item.has_charge_recovery:
                lines.append("")
                lines.append("            // 记录恢复起始回合")
                lines.append('            var _lastRecTurn = ds_map_find_value(data, "last_recovery_turn");')
                lines.append("            if (is_undefined(_lastRecTurn)) {")
                lines.append('                var _totalSec = scr_timeGetTimestamp() * 60 + ds_map_find_value(global.timeDataMap, "seconds");')
                lines.append('                ds_map_set(data, "last_recovery_turn", floor(_totalSec / 30));')
                lines.append("            }")
            if item.delete_on_charge_zero:
                lines.append("")
                lines.append("            // 充能耗尽后删除")
                lines.append("            if (charge <= 0)")
                lines.append("                event_user(12);")
            lines.append("        }")
            lines.append("")
            lines.append("        // 销毁技能实例")
            lines.append('        var _active_ico = ds_map_find_value(data, "_active_ico");')
            lines.append("        if (instance_exists(_active_ico))")
            lines.append("            instance_destroy(_active_ico);")
            lines.append("        if (instance_exists(_active_skill))")
            lines.append("            instance_destroy(_active_skill);")
            lines.append("")
            lines.append("        // 清除引用")
            lines.append('        ds_map_delete(data, "_active_skill");')
            lines.append('        ds_map_delete(data, "_active_ico");')
            lines.append("    }")
            lines.append("}")
        
        return "\n".join(lines)

    def _generate_hybrid_alarm_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Alarm_0 GML 代码
        
        简化策略：
        - 调用 event_inherited() 让父类 o_inv_consum.Alarm_0 处理 is_new 逻辑
        - 静态元数据已移到 Create_0
        - 这里只保留需要 is_new 的属性写入（ds_map_add 在 key 存在时会失败）
        """
        lines = ["event_inherited();"]
        
        # 检查是否有需要写入的属性
        attrs = {k: v for k, v in item.attributes.items() if v != 0}
        if not attrs:
            return "\n".join(lines)
        
        lines.append("")
        lines.append("if (is_new) {")
        lines.append('    var _main = ds_map_find_value(data, "Main");')
        
        if item.init_weapon_stats:
            damage_attrs = {k: v for k, v in attrs.items() if k in DAMAGE_ATTRIBUTES}
            total_dmg = sum(damage_attrs.values())
            
            for t, v in damage_attrs.items():
                lines.append(f'    ds_list_add(_main, "{t}", {v});')
                lines.append(f'    ds_map_add(data, "{t}", {v});')
            lines.append(f'    ds_map_add(data, "DMG", {total_dmg});')
            
            for attr, val in attrs.items():
                if attr in DAMAGE_ATTRIBUTES:
                    continue
                if attr == "Range":
                    lines.append(f'    ds_map_add(data, "Rng", {val});')
                    lines.append(f'    ds_map_add(data, "Range", {val});')
                else:
                    lines.append(f'    ds_map_add(data, "{attr}", {val});')
        
        elif item.init_armor_stats:
            for attr, val in attrs.items():
                if attr == "DEF":
                    lines.append(f'    ds_map_add(data, "DEF", {val});')
                    lines.append(f'    ds_list_add(_main, "DEF", {val});')
                else:
                    lines.append(f'    ds_map_add(data, "{attr}", {val});')
        
        else:
            for attr, val in attrs.items():
                lines.append(f'    ds_map_add(data, "{attr}", {val});')
        
        lines.append("}")
        return "\n".join(lines)

    def _generate_hybrid_other10_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Other_10 GML 代码
        
        简单地调用 event_inherited() 然后覆盖需要的值。
        o_inv_consum.Other_10 会设置 sprite_index=s_inv_cell, matatype="heal", slot="heal" 等，
        并调用 event_user(1) 计算尺寸。
        """
        lines = []
        lines.append("event_inherited();")
        
        if item.init_weapon_stats:
            lines.append('matatype = "weapon";')
            lines.append(f'slot = "{item.slot}";')
        elif item.init_armor_stats:
            lines.append('matatype = "armor";')
            lines.append(f'slot = "{item.slot}";')
        elif item.equipable:
            lines.append(f'slot = "{item.slot}";')
        # 纯消耗品不需要覆盖任何值
        
        return "\n".join(lines)

    def _generate_hybrid_other13_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Other_13 (Hover) GML 代码
        
        完整复制 o_inv_slot.Other_13 的 switch 结构，包括：
        - case 0: hover 显示
        - case 1: hover 销毁
        - case 2: 左键点击（必须有，否则无法左键交互）
        - case 5: 右键点击（必须有，否则无法右键交互）
        - case 37: select 状态处理
        
        结合武器/护甲和消耗品的 hover 逻辑。
        注意：使用次数由 o_hoverHybrid 的 Other_20 通过 chargesLeft/Right 显示，
        这里只处理冷却时间（因为 Other_20 不处理冷却）。
        """
        lines = []  # <- removed dead 'if lines' check
        
        # 完整的 switch 结构（基于 o_inv_slot.Other_13）
        lines.append("switch (guiInteractiveState) {")
        
        # ===== case 0: hover 显示 =====
        lines.append("    case 0:")
        lines.append("        inmouse = true;")
        lines.append("        event_perform(ev_step, ev_step_normal);")
        lines.append("        ")
        lines.append("        // hover 位置配置（基于 owner 类型）")
        lines.append("        var _hoverPlacementsArray = -4;")
        lines.append("        var _hoverDepthOffset = 0;")
        lines.append("        var _hoverComparisonPlacementsArray = -4;")
        lines.append("        var _hoverComparisonDepthOffset = 0;")
        lines.append("        hoverComparisonID = scr_hoverDestroy(hoverComparisonID, false);")
        lines.append("        hoverComparisonIndex = -1;")
        lines.append("        ")
        lines.append("        with (owner) {")
        lines.append("            switch (object_index) {")
        lines.append("                case o_craftingFoodMenu:")
        lines.append("                case o_craftingConsumsMenu:")
        lines.append("                case o_trade_inventory:")
        lines.append("                case o_stash_inventory_left:")
        lines.append("                case o_container:")
        lines.append("                case o_container_quiver:")
        lines.append("                case o_container_backpack:")
        lines.append("                case o_container_gold:")
        lines.append("                    _hoverPlacementsArray = [2, 1, 5, 0, 0, 1, -5, 0];")
        lines.append("                    _hoverComparisonPlacementsArray = [2, 1, -3, 0, 0, 1, -(other.sprite_width + 8), 0];")
        lines.append("                    _hoverDepthOffset = -1;")
        lines.append("                    break;")
        lines.append("                default:")
        lines.append("                    _hoverPlacementsArray = [0, 1, -5, 0, 2, 1, 5, 0];")
        lines.append("                    _hoverComparisonPlacementsArray = [0, 1, 1, 0, 2, 1, other.sprite_width + 8, 0];")
        lines.append("                    _hoverComparisonDepthOffset = -1;")
        lines.append("                    break;")
        lines.append("            }")
        lines.append("        }")
        lines.append("        ")
        lines.append('        if (ds_map_find_value_ext(data, "identified", true)) {')
        
        # 根据物品类型选择 hover 类型
        if item.init_weapon_stats or item.init_armor_stats:
            # 武器/护甲类：使用 o_hoverHybrid + 对比逻辑
            lines.append("            // 武器/护甲类混合物品：使用混合 hover")
            lines.append("            var _comparisonID = scr_hoverWeaponGetComparisonID(id);")
            lines.append("            hoverID = scr_hoverCreate(id, id, o_hoverHybrid, _hoverPlacementsArray, _hoverDepthOffset);")
            lines.append("            scr_hoverTierUpdate(hoverID, Tier);")
            lines.append("            ")
            lines.append("            if (_comparisonID) {")
            lines.append("                // 检查对比目标类型")
            lines.append('                var _isHybrid = variable_instance_exists(_comparisonID, "is_hybrid_item") && _comparisonID.is_hybrid_item;')
            lines.append("                var _isEquipment = object_is_ancestor(_comparisonID.object_index, o_inv_slot);")
            lines.append("                ")
            lines.append("                // 混合物品或普通装备都可以进行对比")
            lines.append("                if (_isHybrid || _isEquipment) {")
            lines.append("                    with (_comparisonID)")
            lines.append("                        event_perform(ev_step, ev_step_normal);")
            lines.append("                    // 对比物品也使用 o_hoverHybrid")
            lines.append("                    hoverComparisonID = scr_hoverCreate(hoverID, _comparisonID, o_hoverHybrid, _hoverComparisonPlacementsArray, _hoverComparisonDepthOffset);")
            lines.append('                    scr_hoverTierUpdate(hoverComparisonID, variable_instance_exists(_comparisonID, "Tier") ? _comparisonID.Tier : 1);')
            lines.append('                    scr_hoverHeaderUpdate(hoverComparisonID, ds_list_find_value(global.weap_param_text, 3));')
            lines.append("                }")
            lines.append("            }")
        else:
            # 消耗品类：也使用 o_hoverHybrid（可以同时显示使用次数和其他属性）
            lines.append("            // 消耗品类混合物品：使用混合 hover")
            lines.append("            hoverID = scr_hoverCreate(id, id, o_hoverHybrid, _hoverPlacementsArray, _hoverDepthOffset);")
        
        lines.append("        } else {")
        lines.append("            // 未鉴定物品")
        lines.append("            hoverID = scr_hoverCreate(id, id, o_hoverUnidentified, _hoverPlacementsArray, _hoverDepthOffset);")
        lines.append("        }")
        lines.append("        break;")
        
        # ===== case 1: hover 销毁 =====
        lines.append("    ")
        # ===== case 1/2/5/37: 复用 o_inv_slot 的实现 =====
        lines.append("    default:")
        lines.append("        event_perform_object(o_inv_slot, ev_other, 13);")
        lines.append("        break;")
        
        lines.append("}")
        
        return "\n".join(lines)

    def _generate_hybrid_other16_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Other_16 GML 代码
        
        某些混合物品（如可装备）继承自 o_inv_consum，后者覆盖了 o_inv_slot 的 Other_16，
        导致属性衰减失效。这里手动恢复。
        """
        if not item.has_durability or not item.equipable:
            return ""
            
        # 直接复用 o_inv_slot 的 Other_16 逻辑
        return "event_perform_object(o_inv_slot, ev_other, 16);"

    def _generate_hybrid_other24_gml(self, item: HybridItem) -> str:
        """生成混合物品的 Other_24 (使用效果) GML 代码
        
        根据 trigger_mode 生成不同代码：
        - "none": 无主动效果
        - "consumable": 消耗品使用效果
        - "skill": 技能释放
        """
        # 未勾选使用次数或模式为 none 时，生成空白代码
        if not item.has_charges or item.trigger_mode == TriggerMode.NONE:
            return "// 空白 Other_24（未启用主动效果）"
        
        lines = []
        
        # 通用充能检查
        lines.append("// 充能检查")
        lines.append("if (charge <= 0)")
        lines.append("    exit;")
        lines.append("")
        
        # 耐久消耗前检查与前置变量
        # 需求6：有耐久时允许设置磨损，但不阻止使用
        if item.has_durability and item.wear_per_use > 0:
            lines.append("var _maxd = ds_map_find_value(data, \"MaxDuration\");")
            lines.append(f"var _cost = (_maxd * {item.wear_per_use}) / 100;")
            lines.append("if (_cost <= 0) _cost = 1;")
            lines.append("var _dur = ds_map_find_value(data, \"Duration\");")
            lines.append("")
        
        # ====== 根据模式生成不同的效果代码 ======
        
        if item.trigger_mode == TriggerMode.SKILL:
            # 技能释放模式
            lines.append("// 技能释放模式")
            
            if item.skill_object:
                # 创建对应的 _ico 对象作为 owner_skill
                # 技能对象名格式: o_skill_xxx -> o_skill_xxx_ico
                ico_object = f"{item.skill_object}_ico"
                
                lines.append(f"// 创建对应的技能图标对象作为 owner_skill")
                lines.append(f"var _owner_skill = instance_create_depth(-10000, -10000, 0, {ico_object});")
                lines.append("with (_owner_skill) {")
                lines.append("    owner = o_player;")
                lines.append("    is_open = true;")
                lines.append("    persistent = false;  // 不跨房间持久化")
                lines.append("}")
                lines.append("")
                lines.append(f"var _skill = instance_create_depth(o_player.x, o_player.y, 0, {item.skill_object});")
                lines.append("with (_skill) {")
                lines.append("    owner = o_player;")
                lines.append("    aoe_target = o_player;")
                lines.append("    owner_skill = _owner_skill;")
                lines.append("    persistent = false;  // 不跨房间持久化")
                lines.append("    event_user(7);     // 更新技能参数")
                lines.append("    event_user(0);     // 激活技能（显示范围指示器）")
                lines.append("}")
                lines.append("")
                lines.append("// 保存技能引用供 Step_0 跟踪，充能将在技能成功执行后扣减")
                lines.append('ds_map_set(data, "_active_skill", _skill);')
                lines.append('ds_map_set(data, "_active_ico", _owner_skill);')
            else:
                lines.append("// 警告：未设置技能对象")
            
            # 技能模式：充能扣减移至 Step_0 中技能成功执行后处理
            
        else:  # consumable 模式
            # 消耗品使用效果
            lines.append('scr_actionsLog("useItem", [scr_id_get_name(o_player), log_text, ds_map_find_value(data, "Name")]);')
            lines.append("// 使用消耗品效果（仅使用 attributes_data）")
            lines.append('var _key = ds_map_find_first(attributes_data);')
            lines.append('var _size = ds_map_size(attributes_data);')
            lines.append('repeat (_size) {')
            lines.append('    var _val = ds_map_find_value(attributes_data, _key);')
            lines.append('    if (is_real(_val)) {')
            lines.append('        switch(_key) {')
            lines.append('            // ====== Instant / Independent Effects ======')
            lines.append('            case "MoraleDiet":')
            lines.append('                 var _diet_penalty = scr_psy_diet_penalty_get(object_get_name(object_index));')
            lines.append('                 scr_psy_change("MoraleDiet", _val + _diet_penalty, "consum_morale_diet(penalty:" + string(_diet_penalty) + ")");')
            lines.append('                 scr_psy_pessimism_delay(_val);')
            lines.append('                 break;')
            lines.append('            case "SanitySituational":')
            lines.append('                 scr_psy_change("SanitySituational", _val, "consum_sanity_sit");')
            lines.append('                 break;')
            lines.append('            case "MoraleSituational":')
            lines.append('                 scr_psy_change("MoraleSituational", _val, "consum_morale_sit");')
            lines.append('                 scr_psy_pessimism_delay(_val);')
            lines.append('                 break;')
            lines.append('            case "Hunger":')
            lines.append('                 var _stage = 1;')
            lines.append('                 var _recipeDataMap = ds_map_find_value(global.recipes_food_data, idName);')
            lines.append('                 if (!is_undefined(_recipeDataMap)) {')
            lines.append('                     var _satiety_value = ds_map_find_value(_recipeDataMap, "SATIETY");')
            lines.append('                     if (_satiety_value == "V") _stage = 2;')
            lines.append('                 }')
            lines.append('                 scr_hunger_incr(_val, _stage);')
            lines.append('                 break;')
            lines.append('            case "Thirsty":')
            lines.append('            case "Intoxication":')
            lines.append('            case "Pain":')
            lines.append('                 scr_atr_incr(_key, _val);')
            lines.append('                 break;')
            lines.append('            case "Immunity":')
            lines.append('                 scr_immunity_change(_val);')
            lines.append('                 break;')
            lines.append('            case "max_mp_res":')
            lines.append('                 scr_restore_mp(o_player, (o_player.max_mp * _val) / 100, ds_map_find_value(data, "Name"));')
            lines.append('                 break;')
            lines.append('            case "max_hp_res":')
            lines.append('                 if (_val < 0)')
            lines.append('                     scr_pure_damage(o_player, (-o_player.max_hp * _val) / 100);')
            lines.append('                 else')
            lines.append('                     scr_restore_hp(o_player, (o_player.max_hp * _val) / 100, ds_map_find_value(data, "Name"));')
            lines.append('                 break;')
            lines.append('            case "Condition":')
            lines.append('                 break;')
            lines.append('            case "Fatigue":')
            lines.append('                 scr_fatigue_change(_val, true);')
            lines.append('                 break;')
            lines.append('            case "Poisoning_Chance":')
            lines.append('                 if (scr_chance_value(_val)) scr_effect_create(o_db_poison, poison_duration);')
            lines.append('                 break;')
            lines.append('            case "Nausea_Chance":')
            lines.append('                 if (scr_chance_value(_val)) scr_effect_create(o_db_nause, 1);')
            lines.append('                 break;')
            lines.append('            // ====== Duration Dependent Buffs (Default) ======')
            lines.append('            default:')
            lines.append('                 var dur = ds_map_find_value(attributes_data, "Duration");')
            lines.append('                 if (!is_undefined(dur) && dur > 0)')
            lines.append('                     scr_temp_effect_update(object_index, o_player, _key, _val, dur, 1);')
            lines.append('                 break;')
            lines.append('        }')
            lines.append('    }')
            lines.append('    _key = ds_map_find_next(attributes_data, _key);')
            lines.append('}')
            lines.append("")
            lines.append("with (o_player)")
            lines.append("    scr_guiAnimation(o_b_gamekeeper_brew, 1, 1, 0);")
            lines.append("")
        
            # 消耗品模式：充能和耐久扣减（has_charges 在此代码路径必定为 true）
            # 无消耗模式下跳过充能扣减
            if item.charge_mode != ChargeMode.UNLIMITED:
                lines.append("charge--;")
                lines.append("ds_map_replace(data, \"charge\", charge);")
                
                # 记录恢复起始回合
                if item.has_charge_recovery:
                    lines.append("")
                    lines.append("// 记录恢复起始回合")
                    lines.append('var _lastTurn = ds_map_find_value(data, "last_recovery_turn");')
                    lines.append("if (is_undefined(_lastTurn)) {")
                    lines.append('    var _totalSec = scr_timeGetTimestamp() * 60 + ds_map_find_value(global.timeDataMap, "seconds");')
                    lines.append('    ds_map_set(data, "last_recovery_turn", floor(_totalSec / 30));')
                    lines.append("}")
            
            # 耐久扣减（需求6：磨损不阻止使用）
            if item.has_durability and item.wear_per_use > 0:
                if item.destroy_on_durability_zero:
                    # 需求5：耐久耗尽后删除
                    lines.append("if (_dur <= _cost)")
                    lines.append("    event_user(12);")
                    lines.append("else")
                    lines.append("    ds_map_replace(data, \"Duration\", _dur - _cost);")
                else:
                    # 0耐久不删除，允许0耐久
                    lines.append("ds_map_replace(data, \"Duration\", max(0, _dur - _cost));")
            
            lines.append("scr_allturn();")
            lines.append("scr_characterStatsConsumUse();")
            lines.append("")
            lines.append("with (o_player)")
            lines.append("    scr_noise_produce(scr_noise_food(), grid_x, grid_y);")
            lines.append("")
            
            # 充能耗尽后的处理（仅在开启用尽删除时生成，has_charges 必定为 true）
            if item.delete_on_charge_zero:
                lines.append("// 充能耗尽后的处理")
                lines.append("if (charge <= 0)")
                lines.append("    event_user(12);")
        
        return "\n".join(lines)

    def _generate_hybrid_loot_animation_code(self, item: HybridItem) -> str:
        """生成混合物品的战利品贴图动画设置 C# 代码"""
        if not item.textures.is_animated("loot"):
            return ""

        sprite_name = f"s_loot_{item.id}"
        fps_value = item.textures.loot_fps

        if item.textures.loot_use_relative_speed:
            speed_type = "AnimSpeedType.FramesPerGameFrame"
        else:
            speed_type = "AnimSpeedType.FramesPerSecond"

        fps_formatted = f"{fps_value:.3f}"

        code = f"""
        // 设置战利品贴图动画播放速度
        UndertaleSprite lootSprite_{item.id} = Msl.GetSprite("{sprite_name}");
        if (lootSprite_{item.id}.CollisionMasks != null && lootSprite_{item.id}.CollisionMasks.Count > 0)
        {{
            lootSprite_{item.id}.CollisionMasks.RemoveAt(0);
        }}
        lootSprite_{item.id}.IsSpecialType = true;
        lootSprite_{item.id}.SVersion = 3;
        lootSprite_{item.id}.GMS2PlaybackSpeed = {fps_formatted}f;
        lootSprite_{item.id}.GMS2PlaybackSpeedType = {speed_type};

"""
        return code

    # ============== Hover 辅助脚本生成 ==============

    def _generate_ensure_extended_order_lists_gml(self) -> str:
        """生成 scr_hoversEnsureExtendedOrderLists.gml 脚本内容
        
        惰性初始化扩展的属性排序列表
        """
        # 按 ATTRIBUTE_TO_GROUP 的分组顺序排列额外属性（而非字母顺序）
        from constants import ATTRIBUTE_TO_GROUP, DEFAULT_GROUP_ORDER
        
        # 创建分组索引
        group_order_map = {g: i for i, g in enumerate(DEFAULT_GROUP_ORDER)}
        
        def get_sort_key(attr):
            group = ATTRIBUTE_TO_GROUP.get(attr, "其他")
            return group_order_map.get(group, len(DEFAULT_GROUP_ORDER))
        
        sorted_attrs = sorted(EXTRA_ORDER_ATTRS, key=get_sort_key)
        extra_attrs_str = ", ".join(f'"{attr}"' for attr in sorted_attrs)
        
        return f'''function scr_hoversEnsureExtendedOrderLists() {{
    // 额外属性列表（ATTRIBUTE_TO_GROUP 中不在游戏 order lists 的）
    if (!variable_global_exists("attribute_order_extra")) {{
        global.attribute_order_extra = ds_list_create();
        ds_list_add(global.attribute_order_extra, {extra_attrs_str});
    }}
    
    // 扩展 order_all（包含伤害）
    if (!variable_global_exists("attribute_order_all_extended")) {{
        global.attribute_order_all_extended = ds_list_create();
        var _size = ds_list_size(global.attribute_order_all);
        for (var _i = 0; _i < _size; _i++)
            ds_list_add(global.attribute_order_all_extended, ds_list_find_value(global.attribute_order_all, _i));
        ds_list_add(global.attribute_order_all_extended, global.attribute_order_extra);
    }}
    
    // 扩展 order_all_without_damage
    if (!variable_global_exists("attribute_order_all_without_damage_extended")) {{
        global.attribute_order_all_without_damage_extended = ds_list_create();
        var _size = ds_list_size(global.attribute_order_all_without_damage);
        for (var _i = 0; _i < _size; _i++)
            ds_list_add(global.attribute_order_all_without_damage_extended, ds_list_find_value(global.attribute_order_all_without_damage, _i));
        ds_list_add(global.attribute_order_all_without_damage_extended, global.attribute_order_extra);
    }}
}}
'''

    def _generate_draw_hybrid_consum_attrs_gml(self) -> str:
        """生成 scr_hoversDrawHybridConsumAttributes.gml 脚本内容
        
        用于绘制消耗品属性，为非即时效果属性显示持续时间
        """
        # 收集所有即时效果属性
        instant_attrs = []
        for attrs in CONSUMABLE_INSTANT_ATTRS.values():
            instant_attrs.extend(attrs)
        instant_attrs_str = ", ".join(f'"{attr}"' for attr in instant_attrs)
        
        return f'''function scr_hoversDrawHybridConsumAttributes() {{
    // 使用 GML 内置 argument0-argument7 避免 bytecode 歧义
    var _x = argument0;
    var _y = argument1;
    var _width = argument2;
    var _lineHeight = argument3;
    var _spaceHeight = argument4;
    var _attributesArray = argument5;
    var _duration = argument6;
    var _textScale = argument7;
    
    // 即时效果属性列表（不显示持续时间）
    var _instantAttrs = [{instant_attrs_str}];
    
    var _arrLen = array_length(_attributesArray);
    var _durationStr = "N/A";
    var _offsetY = 0;
    
    if (_duration > 0) {{
        var _space = scr_actionsLogGetSpace();
        var _open = scr_actionsLogGetSymbol("openRoundBracket");
        var _close = scr_actionsLogGetSymbol("closeRoundBracket");
        _durationStr = _space + _open + string(_duration) + _space + ds_list_find_value(global.other_hover, 57) + _close;
    }}
    
    for (var _i = 0; _i < _arrLen; _i++) {{
        var _part = _attributesArray[_i];
        var _partLen = array_length(_part);
        
        for (var _j = 0; _j < _partLen; _j += 2) {{
            var _key = _part[_j];
            var _val = scr_hoversGetAttributeValue(_key, _part[_j + 1]);
            var _name = scr_hoversGetAttributeName(_key);
            var _valStr = scr_hoversGetAttributeString(_key, _val);
            var _color = scr_hoversGetAttributeColor(_key, _val, make_colour_rgb(114, 222, 142), make_colour_rgb(158, 27, 49), 16777215);
            
            scr_drawText(_x, _y + _offsetY, _name, 16777215, 0, 0, global.f_dmg, _textScale);
            
            // 检查是否为即时效果属性
            var _isInstant = false;
            for (var _k = 0; _k < array_length(_instantAttrs); _k++) {{
                if (_instantAttrs[_k] == _key) {{ _isInstant = true; break; }}
            }}
            
            if (_duration > 0 && !_isInstant)
                scr_draw_text_doublecolor(_x + _width, _y + _offsetY, _valStr, _durationStr, _color, 16777215, 2, 0, _textScale);
            else
                scr_drawText(_x + _width, _y + _offsetY, _valStr, _color, 2, 0, global.f_dmg, _textScale);
            
            _offsetY += _lineHeight;
        }}
        _offsetY += _spaceHeight;
    }}
}}
'''


    def _generate_hover_scripts_injection_method(self) -> str:
        """生成注入 hover 辅助脚本的 C# 方法"""
        return '''    private void EnsureHoverScriptsExist()
    {
        // 注入 scr_hoversEnsureExtendedOrderLists
        if (DataLoader.data.Code.FirstOrDefault(c => c.Name.Content == "gml_GlobalScript_scr_hoversEnsureExtendedOrderLists") == null)
        {
            Msl.AddFunction(ModFiles.GetCode("scr_hoversEnsureExtendedOrderLists.gml"), "scr_hoversEnsureExtendedOrderLists");
        }
        
        // 注入 scr_hoversDrawHybridConsumAttributes
        if (DataLoader.data.Code.FirstOrDefault(c => c.Name.Content == "gml_GlobalScript_scr_hoversDrawHybridConsumAttributes") == null)
        {
            Msl.AddFunction(ModFiles.GetCode("scr_hoversDrawHybridConsumAttributes.gml"), "scr_hoversDrawHybridConsumAttributes");
        }
    }

'''

    # ============== o_hoverHybrid 对象生成 ==============

    def _generate_hover_hybrid_method(self) -> str:
        """生成 o_hoverHybrid 对象创建方法
        
        包含存在性检查：多个使用本编辑器的模组可能同时尝试注入此对象，
        因此需要先检查是否已存在。
        """
        create_code = self._generate_hover_hybrid_create_gml()
        other20_code = self._generate_hover_hybrid_other20_gml()
        other21_code = self._generate_hover_hybrid_other21_gml()
        cleanup_code = self._generate_hover_hybrid_cleanup_gml()
        
        code = """    private void EnsureHoverHybridExists()
    {
        // 检查 o_hoverHybrid 是否已存在（可能由其他模组创建）
        var existingObj = DataLoader.data.GameObjects.FirstOrDefault(t => t.Name.Content == "o_hoverHybrid");
        if (existingObj != null)
        {
            // 对象已存在，跳过创建
            return;
        }

        // 创建 o_hoverHybrid 对象（继承自 o_hoverRenderContent）
        UndertaleGameObject o_hoverHybrid = Msl.AddObject(
            name: "o_hoverHybrid",
            parentName: "o_hoverRenderContent",
            spriteName: "",
            isVisible: true,
            isPersistent: false,
            isAwake: true
        );

        // 应用事件代码
        o_hoverHybrid.ApplyEvent(
            new MslEvent(eventType: EventType.Create, subtype: 0, code: @"
"""
        code += self._escape_multiline_string(create_code)
        code += """            "),
            new MslEvent(eventType: EventType.Other, subtype: 20, code: @"
"""
        code += self._escape_multiline_string(other20_code)
        code += """            "),
            new MslEvent(eventType: EventType.Other, subtype: 21, code: @"
"""
        code += self._escape_multiline_string(other21_code)
        code += """            "),
            new MslEvent(eventType: EventType.CleanUp, subtype: 0, code: @"
"""
        code += self._escape_multiline_string(cleanup_code)
        code += """            ")
        );
    }

"""
        return code

    def _generate_hover_hybrid_create_gml(self) -> str:
        """生成 o_hoverHybrid 的 Create_0 GML 代码
        
        合并 o_hoverWeapon 和 o_hoverConsum 的变量初始化
        """
        return """event_inherited();
minWidth = 160 * surfaceScale;
title = "N/A";
titleWidth = 0;
titleHeight = 0;
type = "N/A";
typeColor = 16777215;
typeHeight = 0;
damageAttributesArray = [];
damageAttributesHeight = 0;
attributesArray = [];
attributesHeight = 0;
consumAttributesArray = [];
consumAttributesHeight = 0;

// 武器特有变量
cursedName = "N/A";
cursedNameHeight = 0;
cursedDescription = "N/A";
cursedDescriptionHeight = 0;
cursedAttributesArray = [];
cursedAttributesHeight = 0;
enchantedAttributesArray = [];
enchantedAttributesHeight = 0;
durabilityLeft = "N/A";
durabilityRight = "N/A";
durabilityColor = 16777215;
durabilityHeight = 0;
materialLeft = "N/A";
materialRight = "N/A";
materialColor = 16777215;
materialHeight = 0;

// 消耗品特有变量
attributesDuration = 0;
freshLeft = "N/A";
freshRight = "N/A";
freshColor = 16777215;
freshHeight = 0;
chargesLeft = "N/A";
chargesRight = "N/A";
chargesHeight = 0;

// 通用变量
middleText = "N/A";
middleHeight = 0;
middleTextMap = __dsDebuggerMapCreate();
stolen = "N/A";
stolenHeight = 0;
description = "N/A";
descriptionHeight = 0;
price = 0;
priceSprite = 9729;
priceColor = 16777215;
priceHeight = 0;
"""

    def _generate_hover_hybrid_other20_gml(self) -> str:
        """生成 o_hoverHybrid 的 Other_20 GML 代码
        
        智能从 owner 获取数据，同时支持武器和消耗品特性
        """
        return """event_inherited();

// 确保扩展的 order lists 存在
scr_hoversEnsureExtendedOrderLists();

var _linesHeight = lineHeight;

with (owner)
{
    other.title = scr_loot_name(id);
    other.titleColor = scr_loot_color(id);
    
    // 智能选择类型文本
    if (variable_instance_exists(id, "type_text") && type_text != "")
        other.type = type_text;
    else if (variable_instance_exists(id, "type"))
        other.type = type;
    else
        other.type = "";
    
    // 武器/护甲属性
    // 需求2：注释掉 enchantedAttributes 部分，暂时不处理区分
    if (variable_instance_exists(id, "cursedName"))
    {
        other.cursedName = cursedName;
        other.cursedDescription = variable_instance_exists(id, "cursedDesc") ? cursedDesc : "";
        other.cursedAttributesArray = scr_hoversGetCursedAttributes();
    }
    // other.enchantedAttributesArray = scr_hoversGetEnchantedAttributes();
    
    // 伤害属性（从 data）
    other.damageAttributesArray = scr_hoversGetAttributesPart(data, global.attribute_order_damage, [other.cursedAttributesArray, other.enchantedAttributesArray]);
    
    // 普通属性（仅显示 data 中的属性 - 武器/装备属性）
    // 需求1：来自 data 的数据用 scr_hoversDrawWeaponAttributes，来自 attributes_data 的数据用 scr_hoversDrawConsumAttributes
    other.attributesArray = scr_hoversGetAttributes(data, global.attribute_order_all_without_damage_extended, [other.cursedAttributesArray, other.enchantedAttributesArray]);
    
    // 消耗品属性（仅显示 attributes_data 中的属性）
    if (variable_instance_exists(id, "attributes_data") && ds_exists(attributes_data, ds_type_map))
    {
        // 需求5：hover 时动态计算 MoraleDiet 的 _diet_penalty 影响
        // 参考 gml_GlobalScript_scr_consum_get_value_for_hover
        var _moraleDiet = ds_map_find_value(attributes_data, "MoraleDiet");
        if (!is_undefined(_moraleDiet))
        {
            var _diet_penalty = scr_psy_diet_penalty_get(object_get_name(object_index));
            // 临时修改 attributes_data 用于生成 hover 数组，生成后还原（或者直接修改，因为 hover 是每帧调用的？不，hover 生成是一次性的）
            // 注意：attributes_data 是引用，修改会影响原数据。但这里是在 hover 对象中生成数组，
            // scr_hoversGetAttributes 读取 map 生成数组。
            // 为了不破坏源数据，我们可以临时 set，生成完后 restore。
            // 或者更安全地：复制一个 map？(开销大)
            // 实际上 scr_psy_diet_penalty_get 返回的是当前惩罚值。
            // 让我们先修改，再改回去。
            ds_map_replace(attributes_data, "MoraleDiet", _moraleDiet + _diet_penalty);
        }

        other.consumAttributesArray = scr_hoversGetAttributes(attributes_data, global.attribute_order_all_extended, [other.cursedAttributesArray, other.enchantedAttributesArray]);
        
        // 还原 MoraleDiet
        if (!is_undefined(_moraleDiet))
        {
             ds_map_replace(attributes_data, "MoraleDiet", _moraleDiet);
        }
    }
    
    // 消耗品效果持续时间
    other.attributesDuration = ds_map_find_value_ext(attributes_data, "Duration", 0);
    
    // mid_text
    var _middleText = "";
    if (variable_instance_exists(id, "mid_text") && mid_text != "")
        _middleText = mid_text;
    
    if (scr_caravanPositionGetX() != -1 && scr_caravanPositionGetY() != -1)
    {
        var _upgradesArray = scr_hoversCaravanUpgradesArrayGenerate(id);
        var _upgradesArrayLength = array_length(_upgradesArray);
        
        for (var _i = 0; _i < _upgradesArrayLength; _i++)
        {
            if (!scr_caravanUpgradeIsOpen(_upgradesArray[_i]))
            {
                _middleText += ((_middleText == "") ? "" : "\\n\\n");
                _middleText += ds_list_find_value_ext(global.caravan_other_text, 7, "N/A");
                break;
            }
        }
    }
    other.middleText = (_middleText == "") ? "N/A" : _middleText;
    
    // 耐久度（武器特性）
    var _hasDuration = ds_map_exists(data, "Duration") && ds_map_exists(data, "MaxDuration");
    if (_hasDuration)
    {
        var _durability = global.is_devinfo ? scr_inv_atr("Duration") : math_round(scr_inv_atr("Duration"));
        var _durabilityMax = math_round(scr_inv_atr("MaxDuration"));
        if (_durabilityMax > 0)
        {
            other.durabilityLeft = ds_list_find_value(global.weap_param_text, 1) + scr_actionsLogGetSymbol("colon") + scr_actionsLogGetSpace();
            other.durabilityRight = string(_durability) + "/" + string(_durabilityMax);
            other.durabilityColor = (_durability < (_durabilityMax / 2)) ? make_colour_rgb(158, 27, 49) : 16777215;
        }
    }
    
    // 使用次数（消耗品特性）
    if (variable_instance_exists(id, "draw_charges") && draw_charges)
    {
        other.chargesLeft = ds_list_find_value(global.other_hover, 2) + scr_actionsLogGetSpace();
        other.chargesRight = string(charge) + "/" + string(max_charge);
    }
    
    // 新鲜度（消耗品特性）
    var _canChange = variable_instance_exists(id, "can_change") ? can_change : false;
    if (_canChange)
    {
        var _fresh = ds_map_find_value(data, "Fresh");
        if (!is_undefined(_fresh) && _fresh > 0)
        {
            var _freshValue = ceil(_fresh / 24);
            other.freshLeft = ds_list_find_value(global.other_hover, 52) + scr_actionsLogGetSpace();
            other.freshRight = string(_freshValue) + scr_actionsLogGetSpace() + scr_pluralFormChoose(_freshValue, ds_list_find_value(global.other_hover, 53));
            other.freshColor = (_freshValue == 1) ? make_colour_rgb(158, 27, 49) : 16777215;
        }
    }
    
    // 被盗标记
    if (scr_inv_atr("HasOwner") == 2)
    {
        var _townKey = ds_map_find_value_ext(data, "Town", "N/A");
        var _town = ds_map_find_value_ext(global.location_titles, _townKey, "N/A");
        other.stolen = string_replace_all(ds_list_find_value(global.other_hover, 65), "%faction%", _town);
    }
    
    // 材质（武器特性）
    other.materialLeft = "N/A";
    other.materialRight = "N/A";
    if (variable_instance_exists(id, "Material") && base_price != 0)
    {
        if (instance_exists(o_skill_repair_item_master))
        {
            other.materialLeft = ds_list_find_value_ext(global.weap_param_text, 4, "Material") + scr_actionsLogGetSymbol("colon") + scr_actionsLogGetSpace();
            other.materialRight = scr_stringTransformFirst(ds_map_find_value_ext(global.item_material, Material, Material), true);
        }
    }
    
    // 价格
    other.price = 0;
    if (base_price != 0)
    {
        if (variable_instance_exists(id, "repair_cost") && repair_cost > 0)
        {
            other.priceSprite = instance_exists(o_skill_ingenuity) ? 4326 : 7398;
            other.price = repair_cost;
            other.priceColor = scr_hoversGetPriceColor(owner, repair_cost, true);
        }
        else
        {
            other.priceSprite = 7395;
            other.price = price;
            other.priceColor = scr_hoversGetPriceColor(owner, price, false);
        }
    }
    
    other.description = variable_instance_exists(id, "desc") ? desc : "";
}

// 计算布局高度
titleWidth = minWidth - (guiParent.tierDraw ? (30 * surfaceScale) : 0);
title = scr_stringInsertLineBreaks(title, titleWidth, global.f_digits, textScale);
titleHeight = scr_stringGetHeightExt(title, titleWidth, global.f_digits, textScale);
typeHeight = (type == "") ? 0 : fontDmgHeight;

damageAttributesHeight = 0;
var _damageAttributesArrayLength = array_length(damageAttributesArray);
if (_damageAttributesArrayLength > 0)
{
    damageAttributesHeight = (_damageAttributesArrayLength / 2) * fontDmgHeight;
    _linesHeight += lineHeight;
}

attributesHeight = 0;
var _attributesArrayLength = array_length(attributesArray);
if (_attributesArrayLength > 0)
{
    for (var _i = 0; _i < _attributesArrayLength; _i++)
        attributesHeight += ((array_length(attributesArray[_i]) / 2) * fontDmgHeight);
    attributesHeight += ((_attributesArrayLength - 1) * spaceHeight);
}

// 消耗品属性高度
consumAttributesHeight = 0;
var _consumAttributesArrayLength = array_length(consumAttributesArray);
if (_consumAttributesArrayLength > 0)
{
    for (var _i = 0; _i < _consumAttributesArrayLength; _i++)
        consumAttributesHeight += ((array_length(consumAttributesArray[_i]) / 2) * fontDmgHeight);
    consumAttributesHeight += ((_consumAttributesArrayLength - 1) * spaceHeight);
}

cursedNameHeight = 0;
cursedAttributesHeight = 0;
var _cursedAttributesArrayLength = array_length(cursedAttributesArray);
if (_cursedAttributesArrayLength > 0)
{
    cursedNameHeight = scr_stringGetHeightExt(cursedName, minWidth, global.f_dmg, textScale) + spaceHeight;
    cursedAttributesHeight = ((_cursedAttributesArrayLength / 2) * fontDmgHeight) + spaceHeight;
}

    enchantedAttributesHeight = 0;
/*
var _enchantedAttributesArrayLength = array_length(enchantedAttributesArray);
if (_enchantedAttributesArrayLength > 0)
    enchantedAttributesHeight = ((_enchantedAttributesArrayLength / 2) * fontDmgHeight) + spaceHeight;
*/

if (middleText == "N/A")
{
    ds_map_clear(middleTextMap);
    middleHeight = 0;
}
else
{
    scr_colorTextCreate(middleTextMap, middleText, 16777215, minWidth, textScale);
    middleHeight = ds_map_find_value(middleTextMap, "height");
}

materialHeight = (materialLeft == "N/A" && materialRight == "N/A") ? 0 : fontDmgHeight;
durabilityHeight = (durabilityLeft == "N/A" && durabilityRight == "N/A") ? 0 : fontDmgHeight;
freshHeight = (freshLeft == "N/A" && freshRight == "N/A") ? 0 : fontDmgHeight;
chargesHeight = (chargesLeft == "N/A" && chargesRight == "N/A") ? 0 : fontDmgHeight;
stolenHeight = (stolen == "N/A") ? 0 : fontDmgHeight;
description = scr_stringInsertLineBreaks(description, minWidth, global.f_dmg, textScale);
descriptionHeight = scr_stringGetHeightExt(description, minWidth, global.f_dmg, textScale);
priceHeight = (price == 0) ? 0 : fontDmgHeight;

// 间距调整
// TODO: 根据新的布局逻辑调整间距计算（如果需要）
if (attributesHeight || consumAttributesHeight)
{
    if (middleHeight || freshHeight || chargesHeight || durabilityHeight || materialHeight || stolenHeight)
        attributesHeight += spaceHeight; // 复用 attributesHeight 做间距标记？这里其实是增加的总高度？不，这里改的是 attributesHeight 本身...
        // 原始代码是 += spaceHeight，这里可能需要拆分逻辑。
        // 但为了简单，如果任一属性存在且后续有内容，增加一次间距即可。
}
// 修正：分开处理 attributesHeight 和 consumAttributesHeight 的产生的间距可能比较复杂，
// 简单起见，我们假设 attributes 和 consumAttributes 是紧挨着的，或者是分开的块。
// 让我们重新梳理布局高度累加 logic。
// 原逻辑：如果有 attributesHeight，且后面有其他块，attributesHeight += spaceHeight。
// 现在有 attributesHeight 和 consumAttributesHeight。
// 如果 attributesHeight > 0，且后面有 (consumAttributesHeight > 0 OR middleHeight ...)，则 attributesHeight += spaceHeight。
if (attributesHeight)
{
    if (consumAttributesHeight || middleHeight || freshHeight || chargesHeight || durabilityHeight || materialHeight || stolenHeight)
        attributesHeight += spaceHeight;
}
// 如果 consumAttributesHeight > 0，且后面有 (middleHeight ...)，则 consumAttributesHeight += spaceHeight。
if (consumAttributesHeight)
{
    if (middleHeight || freshHeight || chargesHeight || durabilityHeight || materialHeight || stolenHeight)
        consumAttributesHeight += spaceHeight;
}

if (middleHeight)
{
    if (freshHeight || chargesHeight || durabilityHeight || materialHeight || stolenHeight)
        middleHeight += spaceHeight;
}
if (freshHeight)
{
    if (chargesHeight || durabilityHeight || materialHeight || stolenHeight)
        freshHeight += spaceHeight;
}
if (chargesHeight)
{
    if (durabilityHeight || materialHeight || stolenHeight)
        chargesHeight += spaceHeight;
}
if (materialHeight)
{
    if (durabilityHeight || stolenHeight)
        materialHeight += spaceHeight;
}
if (durabilityHeight)
{
    if (stolenHeight)
        durabilityHeight += spaceHeight;
}

if (attributesHeight || consumAttributesHeight || middleHeight || freshHeight || chargesHeight || durabilityHeight || materialHeight || stolenHeight)
    _linesHeight += lineHeight;

contentWidth = minWidth;
contentHeight = titleHeight + typeHeight + damageAttributesHeight + attributesHeight + consumAttributesHeight + cursedNameHeight + cursedAttributesHeight + enchantedAttributesHeight + middleHeight + freshHeight + chargesHeight + materialHeight + durabilityHeight + stolenHeight + descriptionHeight + priceHeight + _linesHeight;

"""

    def _generate_hover_hybrid_other21_gml(self) -> str:
        """生成 o_hoverHybrid 的 Other_21 GML 代码
        
        组合渲染武器和消耗品特性
        """
        return """event_inherited();
var _offsetY = 0;

// 标题
scr_drawTextExt(contentX + (contentWidth / 2), contentY + _offsetY, title, titleColor, titleWidth, 1, 0, global.f_digits, textScale);
_offsetY += titleHeight;

// 类型
if (typeHeight)
{
    scr_drawText(contentX + (contentWidth / 2), contentY + _offsetY, type, make_colour_rgb(157, 154, 154), 1, 0, global.f_dmg, textScale);
    _offsetY += fontDmgHeight;
}

// 分隔线
scr_hoversDrawLine(contentX, contentY + _offsetY, contentWidth, lineHeight, surfaceScale);
_offsetY += lineHeight;

// 伤害属性
if (damageAttributesHeight)
{
    with (owner)
        scr_hoversDrawDamageAttributes(other.contentX, other.contentY + _offsetY, other.contentWidth, other.fontDmgHeight, other.damageAttributesArray, other.textScale);
    _offsetY += damageAttributesHeight;
}

if (damageAttributesHeight)
{
    scr_hoversDrawLine(contentX, contentY + _offsetY, contentWidth, lineHeight, surfaceScale);
    _offsetY += lineHeight;
}

// 普通属性 ( Weapon / Armor attributes from data )
// 需求1：这些是来自 data 的属性，强制使用 scr_hoversDrawWeaponAttributes
if (attributesHeight)
{
    with (owner)
        scr_hoversDrawWeaponAttributes(other.contentX, other.contentY + _offsetY, other.contentWidth, other.fontDmgHeight, other.spaceHeight, other.attributesArray, other.textScale);
    _offsetY += attributesHeight;
}

// 消耗品属性 ( Consumable attributes from attributes_data )
// 需求1 & 3：这些是来自 attributes_data 的属性，强制使用 scr_hoversDrawConsumAttributes
if (consumAttributesHeight)
{
    // 如果之前有 weapon attributes，可能需要分隔线？(原逻辑没有额外分隔线，只是累加高度)
    // 但原逻辑 attributesHeight += spaceHeight 处理了间距。
    
    with (owner)
        scr_hoversDrawHybridConsumAttributes(other.contentX, other.contentY + _offsetY, other.contentWidth, other.fontDmgHeight, other.spaceHeight, other.consumAttributesArray, other.attributesDuration, other.textScale);
    _offsetY += consumAttributesHeight;
}

// 诅咒属性（武器特性）
if (cursedAttributesHeight)
{
    scr_drawTextExt(contentX + (contentWidth / 2), contentY + _offsetY, cursedName, make_color_rgb(130, 72, 88), contentWidth, 1, 0, global.f_dmg, textScale);
    _offsetY += cursedNameHeight;
    with (owner)
        scr_hoversDrawWeaponAttributes(other.contentX, other.contentY + _offsetY, other.contentWidth, other.fontDmgHeight, other.spaceHeight, other.cursedAttributesArray, other.textScale);
    _offsetY += cursedAttributesHeight;
}

// 附魔属性（武器特性）- 需求2：注释掉
/*
if (enchantedAttributesHeight)
{
    with (owner)
        scr_hoversDrawWeaponAttributes(other.contentX, other.contentY + _offsetY, other.contentWidth, other.fontDmgHeight, other.spaceHeight, other.enchantedAttributesArray, other.textScale);
    _offsetY += enchantedAttributesHeight;
}
*/
// TODO: 处理附魔属性的区分显示


// 中间文本（mid_text）
if (middleHeight)
{
    scr_colorTextDraw(middleTextMap, contentX, contentY + _offsetY);
    _offsetY += middleHeight;
}

// 新鲜度（消耗品特性）
if (freshHeight)
{
    scr_draw_text_doublecolor(contentX, contentY + _offsetY, freshLeft, freshRight, make_colour_rgb(157, 154, 154), freshColor, 0, 0, textScale);
    _offsetY += freshHeight;
}

// 使用次数（消耗品特性）
if (chargesHeight)
{
    scr_draw_text_doublecolor(contentX, contentY + _offsetY, chargesLeft, chargesRight, make_colour_rgb(157, 154, 154), 16777215, 0, 0, textScale);
    _offsetY += chargesHeight;
}

// 材质（武器特性）
if (materialHeight)
{
    scr_draw_text_doublecolor(contentX, contentY + _offsetY, materialLeft, materialRight, make_colour_rgb(157, 154, 154), materialColor, 0, 0, textScale);
    _offsetY += materialHeight;
}

// 耐久度（武器特性）
if (durabilityHeight)
{
    scr_draw_text_doublecolor(contentX, contentY + _offsetY, durabilityLeft, durabilityRight, make_colour_rgb(157, 154, 154), durabilityColor, 0, 0, textScale);
    _offsetY += durabilityHeight;
}

// 被盗标记
if (stolenHeight)
{
    scr_drawText(contentX, contentY + _offsetY, stolen, make_colour_rgb(225, 45, 31), 0, 0, global.f_dmg, textScale);
    _offsetY += stolenHeight;
}

// 分隔线
if (attributesHeight || middleHeight || freshHeight || chargesHeight || durabilityHeight || materialHeight || stolenHeight)
{
    scr_hoversDrawLine(contentX, contentY + _offsetY, contentWidth, lineHeight, surfaceScale);
    _offsetY += lineHeight;
}

// 描述
scr_drawTextExt(contentX, contentY + _offsetY, description, make_colour_rgb(149, 121, 106), contentWidth, 0, 0, global.f_dmg, textScale);
_offsetY += descriptionHeight;

// 价格
if (priceHeight)
    scr_hoversDrawPrice(contentX + contentWidth, contentY + _offsetY, priceSprite, price, priceColor, surfaceScale, textScale);
"""

    def _generate_hover_hybrid_cleanup_gml(self) -> str:
        """生成 o_hoverHybrid 的 CleanUp_0 GML 代码"""
        return """event_inherited();
middleTextMap = __dsDebuggerMapDestroy(middleTextMap);
"""

    def _generate_inject_item_stats_method(self) -> str:
        """生成 InjectItemStats 辅助方法
        
        将 Category, Subcategory, Tags 从枚举类型改为字符串，
        提供更灵活的物品属性定义。
        
        注意：
        - 消耗品效果参数（Hunger 到 Poisoning_Duration）在 GML 端处理，此处仅保留物品元数据参数
        - Duration 控制消耗品持续效果时间，属于具体效果属性的一部分而非元数据，因此不在 C# 端设定
        - EffPrice 参数疑似无用，已移除但保留数据行占位
        
        统计信息（来自 items_stats.json）：
        - Weight: Heavy, Light, Medium, Net, Very Light
        - Material: cloth, gem, glass, gold, leather, metal, organic, paper, pottery, silver, stone, wood
        - Stacks: 1, 2, 3, 4
        - upgrade: Coop, Dummy, Tent2, Tent3, Foraging, Herbalism, Workbench, Chest2-4, Wheels3, Horses2 等
        - fodder: 2, 3, 4, 6, 250
        - stack: 20, 50, 100
        """
        return '''    // ============== 物品属性注入辅助类型 ==============

    public enum ItemTier
    {
        None,
        Tier1,
        Tier2,
        Tier3,
        Tier4,
        Tier5
    }

    public enum ItemWeight
    {
        VeryLight,
        Light,
        Medium,
        Heavy,
        Net
    }

    public enum ItemMaterial
    {
        Organic,
        Cloth,
        Leather,
        Wood,
        Paper,
        Pottery,
        Glass,
        Stone,
        Metal,
        Silver,
        Gold,
        Gem
    }

    private static string GetTierValue(ItemTier tier) => tier switch
    {
        ItemTier.Tier1 => "1",
        ItemTier.Tier2 => "2",
        ItemTier.Tier3 => "3",
        ItemTier.Tier4 => "4",
        ItemTier.Tier5 => "5",
        _ => ""
    };

    private static string GetWeightValue(ItemWeight weight) => weight switch
    {
        ItemWeight.VeryLight => "Very Light",
        ItemWeight.Light => "Light",
        ItemWeight.Medium => "Medium",
        ItemWeight.Heavy => "Heavy",
        ItemWeight.Net => "Net",
        _ => "Light"
    };

    private static string GetMaterialValue(ItemMaterial material) => material.ToString().ToLower();

    private void InjectItemStats(
        string id,
        int? Price = null,
        ItemTier tier = ItemTier.None,
        string Cat = "",
        string Subcat = "",
        ItemMaterial Material = ItemMaterial.Organic,
        ItemWeight Weight = ItemWeight.Light,
        string tags = "",
        ushort? Fresh = null,
        ushort? Stacks = null,
        bool Diet = false,
        bool purse = false,
        bool bottle = false,
        string? upgrade = null,
        short? fodder = null,
        short? stack = null,
        bool fireproof = false,
        bool dropsOnce = false)
    {
        const string tableName = "gml_GlobalScript_table_items_stats";
        List<string> table = Msl.ThrowIfNull(ModLoader.GetTable(tableName));

        string tierVal = GetTierValue(tier);
        string weightVal = GetWeightValue(Weight);
        string materialVal = GetMaterialValue(Material);

        // 构建数据行 - 基于 MSL InjectTableItemStats 格式 (100 个分号)
        string newline = $"{id};;{Price};;{tierVal};{Cat};{Subcat};{materialVal};{weightVal};;{Fresh};;{Stacks};{(Diet ? "1" : "")};;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;{(purse ? "1" : "")};{(bottle ? "1" : "")};{upgrade};{fodder};{stack};{(fireproof ? "1" : "")};{(dropsOnce ? "1" : "")};{tags};";

        table.Add(newline);
        ModLoader.SetTable(table, tableName);
    }

'''


    def _generate_gml_helper_methods(self) -> str:
        """生成 GML 脚本管理辅助函数的 C# 代码
        
        包含:
        - FunctionExists: 检查全局函数是否存在
        - InitScriptExists: 检查初始化脚本是否存在
        - AddInitScript: 添加初始化脚本
        - AddGlobalFunction: 添加 GMS 2.3 风格全局函数
        - RegisterToGlobalInit: 注册代码到 GlobalInit
        """
        return '''
    bool FunctionExists(string functionName)
    {
        string codeName = $"gml_GlobalScript_{functionName}";
        return DataLoader.data.Code.ByName(codeName) != null
            || DataLoader.data.Scripts.ByName(functionName) != null
            || DataLoader.data.Functions.ByName(functionName) != null;
    }

    bool InitScriptExists(string scriptId)
    {
        string codeName = $"gml_GlobalScript_init_{scriptId}";
        return DataLoader.data.Code.ByName(codeName) != null;
    }

    void RegisterToGlobalInit(UndertaleCode code)
    {
        if (DataLoader.data.GlobalInitScripts.Any(g => g.Code?.Name?.Content == code.Name?.Content))
            return;
        
        UndertaleGlobalInit globalInit = new UndertaleGlobalInit();
        globalInit.Code = code;
        DataLoader.data.GlobalInitScripts.Add(globalInit);
    }

    void AddGlobalFunction(string functionName, string gmlCode)
    {
        string codeName = $"gml_GlobalScript_{functionName}";
        
        // Code
        UndertaleCode code = new UndertaleCode();
        code.Name = DataLoader.data.Strings.MakeString(codeName);
        DataLoader.data.Code.Add(code);
        
        // CodeLocals
        UndertaleCodeLocals locals = new UndertaleCodeLocals();
        locals.Name = code.Name;
        DataLoader.data.CodeLocals.Add(locals);
        
        // 编译
        code.ReplaceGML(gmlCode, DataLoader.data);
        
        // Script
        UndertaleScript script = new UndertaleScript();
        script.Name = DataLoader.data.Strings.MakeString(functionName);
        script.Code = code;
        DataLoader.data.Scripts.Add(script);
        
        // Function
        UndertaleFunction func = new UndertaleFunction();
        func.Name = DataLoader.data.Strings.MakeString(functionName);
        DataLoader.data.Functions.Add(func);
        
        // GlobalInit
        RegisterToGlobalInit(code);
    }

    void AddInitScript(string scriptId, string gmlCode)
    {
        string codeName = $"gml_GlobalScript_init_{scriptId}";
        
        // Code
        UndertaleCode code = new UndertaleCode();
        code.Name = DataLoader.data.Strings.MakeString(codeName);
        DataLoader.data.Code.Add(code);
        
        // CodeLocals
        UndertaleCodeLocals locals = new UndertaleCodeLocals();
        locals.Name = code.Name;
        DataLoader.data.CodeLocals.Add(locals);
        
        // 编译
        code.ReplaceGML(gmlCode, DataLoader.data);
        
        // GlobalInit
        RegisterToGlobalInit(code);
    }

}

// ============== Patch 标记辅助类 ==============
// 使用空脚本作为标记，防止不同模组重复 patch 同一代码

public static class Mark
{
    const string PREFIX = "__MK_";
    
    public static bool Has(UndertaleData data, string name)
    {
        return data.Scripts.ByName(PREFIX + name) != null;
    }
    
    public static void Set(UndertaleData data, string name)
    {
        string fullName = PREFIX + name;
        if (data.Scripts.ByName(fullName) != null) return;
        
        var str = data.Strings.MakeString(fullName);
        var code = new UndertaleCode { Name = str };
        data.Code.Add(code);
        
        data.Scripts.Add(new UndertaleScript
        {
            Name = str,
            Code = code
        });
    }
    
    public static void Remove(UndertaleData data, string name)
    {
        string fullName = PREFIX + name;
        var script = data.Scripts.ByName(fullName);
        if (script == null) return;
        
        if (script.Code != null)
            data.Code.Remove(script.Code);
        data.Scripts.Remove(script);
    }
    
    public static IEnumerable<string> GetAll(UndertaleData data)
    {
        return data.Scripts
            .Where(s => s.Name.Content.StartsWith(PREFIX))
            .Select(s => s.Name.Content.Substring(PREFIX.Length));
    }
}

'''


    def _generate_hybrid_equipment_registry_method(self) -> str:
        """生成混合装备注册系统的 C# 方法
        
        包含:
        1. 全局注册表初始化脚本
        2. register_hybrid_equipment 函数
        3. 本项目混合物品注册调用
        """
        project = self.project
        
        # 收集需要装备路径生成的混合物品（仅 weapon/armor/passive 模式）
        equipment_hybrids = []
        for h in project.hybrid_items:
            # 只有 equipment_mode 为 weapon/armor/charm 的才能从装备路径生成
            if h.equipment_mode not in (EquipmentMode.WEAPON, EquipmentMode.ARMOR, EquipmentMode.CHARM):
                continue
            if h.spawn_mode == SpawnMode.EQUIPMENT:
                equipment_hybrids.append(h)
        
        # 如果没有装备路径混合物品，不生成这个方法
        if not equipment_hybrids:
            return ""
        
        # 生成混合物品数据数组
        item_entries = []
        for h in equipment_hybrids:
            # 确定槽位
            if h.equipment_mode == EquipmentMode.WEAPON:
                slot = h.weapon_type
            elif h.equipment_mode == EquipmentMode.ARMOR:
                slot = h.armor_type
            else:
                slot = h.slot
            
            # 生成数组元素 (effective_tags 不含 'special')
            item_entries.append(
                f'[\"\"{h.id}\"\", \"\"{slot}\"\", {h.tier}, \"\"{h.material.lower()}\"\", '
                f'\"\"{h.effective_tags}\"\", \"\"{h.spawn_mode.value}\"\", \"\"{h.equipment_mode.value}\"\"]'
            )
        
        items_array = ", ".join(item_entries)
        
        code = f'''
    void EnsureHybridEquipmentRegistry()
    {{
        // 单一初始化脚本，避免 GlobalInit 执行顺序问题
        if (!InitScriptExists("{project.code_name}_hybrid_equipment"))
        {{
            AddInitScript("{project.code_name}_hybrid_equipment", @"
// === 混合装备注册系统初始化 ===

// 1. 初始化全局注册表
if (!variable_global_exists(""hybrid_equipment_registry"")) {{
    global.hybrid_equipment_registry = {{}};
    global.hybrid_equipment_by_slot = {{}};
}}

// 2. 注册本项目的混合物品
var _items = [{items_array}];
for (var _i = 0; _i < array_length(_items); _i++) {{
    var _item = _items[_i];
    var _id = _item[0];
    var _slot = _item[1];
    
    if (variable_struct_exists(global.hybrid_equipment_registry, _id)) continue;
    
    var _data = {{
        id: _id,
        slot: _slot,
        tier: _item[2],
        material: _item[3],
        tags: _item[4],
        spawn_mode: _item[5],
        equipment_mode: _item[6]
    }};
    
    variable_struct_set(global.hybrid_equipment_registry, _id, _data);
    
    if (!variable_struct_exists(global.hybrid_equipment_by_slot, _slot)) {{
        variable_struct_set(global.hybrid_equipment_by_slot, _slot, []);
    }}
    array_push(variable_struct_get(global.hybrid_equipment_by_slot, _slot), _id);
}}
");
        }}
        
        // 4. Patch scr_find_weapon_params (敌人击杀 + 商店进货)
        // 完全模拟原始筛选逻辑：tier, material, tags, slot, _all_type, _check_repeat
        if (!Mark.Has(DataLoader.data, "patch_scr_find_weapon_params"))
        {{
            Msl.LoadGML("gml_GlobalScript_scr_find_weapon_params")
                .MatchFrom("ds_list_shuffle(list)")
                .InsertAbove(@"
// === 混合装备注入 ===
if (variable_global_exists(""hybrid_equipment_registry"")) {{
    var _hybrid_ids = variable_struct_get_names(global.hybrid_equipment_registry);
    for (var _hi = 0; _hi < array_length(_hybrid_ids); _hi++) {{
        var _hid = _hybrid_ids[_hi];
        var _hdata = variable_struct_get(global.hybrid_equipment_registry, _hid);
        
        // 检查统一的 spawn_mode
        if (_hdata.spawn_mode != ""equipment"") continue;
        
        // 根据 equipment_mode 区分 weapon/armor 表
        var _eq_mode = _hdata.equipment_mode;
        var _hslot = _hdata.slot;
        
        if (_eq_mode == ""weapon"") {{
            // weapon 模式只在 weapon 表或 all 时注入
            if (_table != ""weapon"" && _table != ""all"") continue;
            
            // Slot 检查（模拟 weapon 表逻辑）
            // 原始逻辑: scr_csv_colum_parse(""Slot"", i, _weapon_array) == _type || _all_type
            if (_hslot != _type && !_all_type) continue;
        }} else {{
            // armor/charm 模式只在 armor 表或 all 时注入
            if (_table != ""armor"" && _table != ""all"") continue;
            
            // Slot 检查（模拟 armor 表逻辑）
            // 原始逻辑: _table_type == _type || (_all_type && _table_type != ""Ring"" && _table_type != ""Amulet"")
            if (_hslot != _type) {{
                if (!_all_type) continue;
                // _all_type 为 true 时，排除 Ring 和 Amulet
                if (_hslot == ""Ring"" || _hslot == ""Amulet"") continue;
            }}
        }}
        
        // Tier 检查
        if (_hdata.tier < argument[0] || _hdata.tier > argument[1]) continue;
        
        // Material 检查
        if (!scr_material_compare(_hdata.material, material)) continue;
        
        // Tags 检查
        if (!scr_weapon_tags_compare(string_split_custom(_hdata.tags, "" ""), tags)) continue;
        
        // item_buffer 重复检查
        if (_check_repeat && ds_list_find_index(global.item_buffer, _hid) >= 0) continue;
        
        ds_list_add(list, _hid);
    }}
}}
// === 混合装备注入结束 ===
            ")
                .Save();
            Mark.Set(DataLoader.data, "patch_scr_find_weapon_params");
        }}
        
        // 5. Patch scr_find_weapon (容器/宝箱)
        if (!Mark.Has(DataLoader.data, "patch_scr_find_weapon"))
        {{
            Msl.LoadGML("gml_GlobalScript_scr_find_weapon")
                .MatchFrom("var _array_size = array_length(_weapon_array)")
                .InsertAbove(@"
// === 混合装备注入 ===
if (variable_global_exists(""hybrid_equipment_by_slot"")) {{
    var _hybrid_slot_items = variable_struct_get(global.hybrid_equipment_by_slot, argument0);
    if (!is_undefined(_hybrid_slot_items)) {{
        for (var _hi = 0; _hi < array_length(_hybrid_slot_items); _hi++) {{
            var _hid = _hybrid_slot_items[_hi];
            var _hdata = variable_struct_get(global.hybrid_equipment_registry, _hid);
            if (_hdata.spawn_mode != ""equipment"") continue;
            if (argument2 != -4 && _hdata.tier > 0 && (_hdata.tier < argument2[0] || _hdata.tier > argument2[1])) continue;
            if (ds_list_find_index(scr_atr(""specialItemsPool""), _hid) >= 0) continue;
            if (!scr_weapon_tags_compare(string_split_custom(_hdata.tags, "" ""), argument1)) continue;
            array_push(_weapon_array, _hid);
        }}
    }}
}}
// === 混合装备注入结束 ===
            ")
                .Save();
            Mark.Set(DataLoader.data, "patch_scr_find_weapon");
        }}
        
        // 6. Patch scr_weapon_loot (掉落创建)
        if (!Mark.Has(DataLoader.data, "patch_scr_weapon_loot"))
        {{
            Msl.LoadGML("gml_GlobalScript_scr_weapon_loot")
                .MatchFrom(@"var checkSpecialPool = (argument4 == (6 << 0) && argument5 == ""dynamic"")")
                .InsertAbove(@"
// === 混合物品直接创建 ===
if (variable_global_exists(""hybrid_equipment_registry"") && !is_undefined(argument0)) {{
    if (variable_struct_exists(global.hybrid_equipment_registry, argument0)) {{
        var _hybrid_loot = asset_get_index(""o_loot_"" + argument0);
        if (object_exists(_hybrid_loot)) {{
            if (scr_chance_value(argument3, 1)) {{
                var _px = scr_round_cell(argument1) + 13;
                var _py = scr_round_cell(argument2) + 13;
                with (scr_loot_drop(_px, _py, _hybrid_loot, true, argument5, argument6, argument7)) {{
                    if (argument4 != -4) determined_quality = argument4;
                    event_user(1);
                    return id;
                }}
            }}
            return -4;
        }}
    }}
}}
// === 混合物品处理结束 ===
            ")
                .Save();
            Mark.Set(DataLoader.data, "patch_scr_weapon_loot");
        }}
        
        // 7. Patch scr_inventory_add_weapon (背包添加)
        if (!Mark.Has(DataLoader.data, "patch_scr_inventory_add_weapon"))
        {{
            Msl.LoadGML("gml_GlobalScript_scr_inventory_add_weapon")
                .MatchFrom("var _checkSpecialPool = argument1 == (6 << 0)")
                .InsertAbove(@"
// === 混合物品直接创建 ===
if (variable_global_exists(""hybrid_equipment_registry"") && !is_undefined(argument0)) {{
    if (variable_struct_exists(global.hybrid_equipment_registry, argument0)) {{
        var _hybrid_inv = asset_get_index(""o_inv_"" + argument0);
        if (object_exists(_hybrid_inv)) {{
            with (scr_guiCreateInteractive(global.guiBaseContainerVisible, _hybrid_inv)) {{
                owner = other.id;
                // if (argument1 != -4) determined_quality = argument1;
                is_new = argument4;
                event_user(0);
                // if (argument5 != -4) ds_map_replace(data, ""identified"", argument5);
                // if (argument2) event_perform(ev_alarm, 0);
                if (slotDestroyed) return -4;
                if (argument3) {{
                    if (!scr_inventory_add(owner)) {{
                        if (owner.object_index != o_trade_inventory) {{
                            forced_drop = true;
                            event_user(15);
                            return -4;
                        }} else {{
                            scr_inventory_cells_add(owner, owner.cellsContainer, 5, true);
                            scr_inventory_add(owner, id);
                        }}
                    }}
                }}
                return id;
            }}
        }}
    }}
}}
// === 混合物品处理结束 ===
            ")
                .Save();
            Mark.Set(DataLoader.data, "patch_scr_inventory_add_weapon");
        }}
    }}

'''
        return code

