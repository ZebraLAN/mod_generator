# -*- coding: utf-8 -*-
"""
代码生成器和贴图工具模块

包含 C# 模组代码生成器和贴图处理工具函数。
"""

import os
import shutil
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from constants import (
    GAME_FPS,
    GML_ANCHOR_X,
    GML_ANCHOR_Y,
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
from models import Armor, Item, ItemTextures, ModProject, Weapon


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
            # 裁剪失败，尝试直接复制
            pass

    try:
        shutil.copy2(src_path, dst_path)
        return None
    except Exception as e:
        return f"复制贴图失败 {src_path}: {e}"


def copy_item_textures(
    item_id: str,
    textures: ItemTextures,
    sprites_dir: Path,
    copy_char: bool,
    copy_left: bool,
) -> list[str]:
    """复制物品的所有贴图文件

    Returns:
        错误/警告信息列表
    """
    errors = []

    def _copy(src, dst, mask=None):
        err = copy_texture(src, dst, mask)
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

    # 角色/手持贴图
    if copy_char and textures.character:
        mask = (textures.offset_x, textures.offset_y)
        _copy_texture_list(textures.character, f"s_char_{item_id}", mask)

    # 左手贴图
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
    """处理描述文本：strip -> splitlines -> join('##') -> 转移双引号"""
    if not text:
        return ""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    joined = "##".join(lines)
    return joined.replace('"', '\\"')


# ============== C# 代码生成器 ==============


class CodeGenerator:
    """C# 模组代码生成器"""

    def __init__(self, project: ModProject):
        self.project = project

    def generate(self) -> str:
        """生成完整的 C# 模组代码"""
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
        for armor in self.project.armors:
            code += f"        AddArmor{armor.id}();\n"

        code += "    }\n\n"

        for item in self.project.weapons + self.project.armors:
            code += self._generate_item_method(item)

        code += "}\n"
        return code

    def _generate_item_method(self, item: Item) -> str:
        """生成单个物品的 C# 方法"""
        is_weapon = isinstance(item, Weapon)
        method_name = f"Add{item.id}" if is_weapon else f"AddArmor{item.id}"

        code = f"    private void {method_name}()\n    {{\n"
        code += self._generate_item_injection_code(item)
        code += self._generate_localization_code(item)
        if is_weapon:
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

    def _generate_gml_offset_code(self, weapon: Weapon) -> str:
        """生成 GML 偏移注入代码"""
        gml_code_block = ""

        if weapon.textures.offset_x != 0 or weapon.textures.offset_y != 0:
            adj_off_x, adj_off_y = calculate_adjusted_offsets(
                weapon.textures.offset_x, weapon.textures.offset_y
            )

            if adj_off_x != 0 or adj_off_y != 0:
                val_y = GML_ANCHOR_Y + adj_off_y
                val_x = GML_ANCHOR_X + adj_off_x
                sprite_name = f"s_char_{weapon.id}"
                gml_code_block += self._generate_anchor_gml_block(
                    val_y, val_x, sprite_name
                )

        if weapon.textures.has_char_left():
            if weapon.textures.offset_x_left != 0 or weapon.textures.offset_y_left != 0:
                adj_off_x_left, adj_off_y_left = calculate_adjusted_offsets(
                    weapon.textures.offset_x_left, weapon.textures.offset_y_left
                )

                if adj_off_x_left != 0 or adj_off_y_left != 0:
                    val_y = GML_ANCHOR_Y + adj_off_y_left
                    val_x = GML_ANCHOR_X + adj_off_x_left
                    sprite_name = f"s_charleft_{weapon.id}"
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
        lootSprite_{item.id}.CollisionMasks.RemoveAt(0);
        lootSprite_{item.id}.IsSpecialType = true;
        lootSprite_{item.id}.SVersion = 3;
        lootSprite_{item.id}.GMS2PlaybackSpeed = {fps_formatted}f;
        lootSprite_{item.id}.GMS2PlaybackSpeedType = {speed_type};

"""
        return code
