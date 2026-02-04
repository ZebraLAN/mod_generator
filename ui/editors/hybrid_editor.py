# -*- coding: utf-8 -*-
"""混合物品编辑器 Mixin - HybridEditorMixin

提供混合物品编辑器相关方法。
"""

from typing import TYPE_CHECKING

import imgui  # type: ignore

from ui import styles
from ui.styles import gap_m, gap_s, grid_gap
from ui.state import state as ui_state
from ui.styles import get_current_theme_colors, text_secondary
from constants import (
    STRICT_INT_ATTRIBUTES,
    SPECIAL_STEP_ATTRIBUTES,
    GAME_FPS,
    DEFAULT_GROUP_ORDER,
    get_attribute_groups,
    # 混合物品常量
    HYBRID_SLOT_LABELS,
    HYBRID_QUALITY_LABELS,
    HYBRID_WEAPON_TYPES,
    HYBRID_MATERIALS,
    HYBRID_ARMOR_TYPES,
    HYBRID_PICKUP_SOUNDS,
    HYBRID_DROP_SOUNDS,
    HYBRID_WEIGHT_LABELS,
    # 消耗品属性常量
    CONSUMABLE_DURATION_ATTRIBUTE,
    get_hybrid_attrs_for_slot,
    get_consumable_duration_attrs,
    CONSUMABLE_INSTANT_ATTRS,
)
from hybrid_item_v2 import HybridItemV2
from models import (
    validate_hybrid_item,
)
from specs import (
    # Equipment specs
    WeaponEquip, ArmorEquip, CharmEquip, NotEquipable,
    is_weapon_mode, is_armor_mode, is_charm_mode,
    NoDurability, HasDurability,
    # Trigger specs
    NoTrigger, EffectTrigger, SkillTrigger,
    trigger_has_effect,
    # Charge specs
    NoCharges, LimitedCharges, UnlimitedCharges,
    charge_has_charges,
    # Recovery specs
    NoRecovery, IntervalRecovery,
    recovery_has_recovery,
    # Spawn specs
    ExcludedFromRandom, RandomSpawn, SpawnRuleType,
    spawn_is_excluded,
    # Quality specs
    CommonQuality, UniqueQuality, ArtifactQuality,
    quality_from_int,
)
from drop_slot_data import (
    ITEM_CATEGORIES,
    ALL_SUBCATEGORY_OPTIONS,
    CATEGORY_TRANSLATIONS,
    QUALITY_TAGS,
    DUNGEON_TAGS,
    COUNTRY_TAGS,
    EXTRA_TAGS,
    find_matching_slots,
    find_matching_eq_slots,
)
from shop_configs import NPC_METADATA, SHOP_CONFIGS
from skill_constants import (
    SKILL_OBJECTS,
    SKILL_BRANCH_TRANSLATIONS,
    SKILL_BY_BRANCH,
    SKILL_OBJECT_NAMES,
)
from ui.layout import GridLayout, tooltip, item_width

# 新模块化面板
from ui.editors.hybrid import draw_base_panel

if TYPE_CHECKING:
    from ui.protocols import GUIProtocol


class HybridEditorMixin:
    """混合物品编辑器 Mixin"""

    def draw_hybrid_editor(self: "GUIProtocol") -> None:
        """绘制混合物品编辑器 - Tab 布局: 基础/行为/属性/呈现"""
        hybrid = ui_state.project.hybrid_items[ui_state.current_hybrid_index]

        # 是否显示属性 Tab
        show_attrs = self._should_show_hybrid_attributes(hybrid) or isinstance(hybrid.trigger, EffectTrigger)

        # Tab Bar 布局 (原生 imgui)
        if imgui.begin_tab_bar("##hybrid_tabs"):
            # 1. 基础 Tab - "这是什么物品"
            if imgui.begin_tab_item("基础")[0]:
                draw_base_panel(hybrid)
                imgui.end_tab_item()

            # 2. 行为 Tab - "物品做什么"
            if imgui.begin_tab_item("行为")[0]:
                self._draw_hybrid_behavior(hybrid)
                imgui.end_tab_item()

            # 3. 属性 Tab - "数值配置"
            if show_attrs:
                if imgui.begin_tab_item("属性")[0]:
                    self._draw_hybrid_stats(hybrid)
                    imgui.end_tab_item()

            # 4. 呈现 Tab - "外观"
            if imgui.begin_tab_item("呈现")[0]:
                self._draw_hybrid_presentation(hybrid)
                imgui.end_tab_item()

            imgui.end_tab_bar()

        # 验证错误 - 始终显示在底部
        errors = validate_hybrid_item(hybrid, ui_state.project, include_warnings=True)
        self._draw_validation_errors(errors)

    def _should_show_hybrid_attributes(self: "GUIProtocol", hybrid: HybridItemV2) -> bool:
        """判断是否显示属性加成编辑器

        需求调整：即使是武器/护甲也允许编辑额外属性（例如 HYBRID_ITEM_TEMPLATE 中提到的武器可选属性）。
        因此只要是武器/护甲/有被动效果，就展示属性编辑器。
        """
        # 武器/护甲/护符都显示属性编辑器
        if is_weapon_mode(hybrid.equipment) or is_armor_mode(hybrid.equipment) or is_charm_mode(hybrid.equipment):
            return True
        return False

    # ==================== 新 4 区块结构 ====================

    def _draw_hybrid_base(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制基础区块 - GridLayout label-on-top 布局（两行）"""
        hybrid.parent_object = "o_inv_consum"

        # 使用 GridLayout 类
        grid = GridLayout(text_secondary)

        # === 第一行：ID / 品质 / 等级（核心标识和稀有度）===
        # Label 行
        grid.label_header("ID", styles.SPAN_ID)
        grid.next_cell()
        grid.label_header("品质", styles.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("等级", styles.SPAN_INPUT)

        # Control 行
        grid.field_width(styles.SPAN_ID)
        changed, new_id = imgui.input_text("##hybrid_id", hybrid.id, 256)
        if changed:
            hybrid.id = new_id.lower()
        tooltip("物品唯一标识符")

        grid.next_cell()
        grid.field_width(styles.SPAN_INPUT)
        old_quality = hybrid.quality
        hybrid.quality = self._draw_enum_combo(
            "##quality_hybrid", hybrid.quality,
            list(HYBRID_QUALITY_LABELS.keys()), HYBRID_QUALITY_LABELS
        )
        if hybrid.quality != old_quality:
            self._update_hybrid_rarity_from_quality(hybrid)

        grid.next_cell()
        grid.field_width(styles.SPAN_INPUT)
        if hybrid.quality == 7:
            grid.text_cell("T0", styles.SPAN_INPUT)
            tooltip("文物固定等级 0")
        else:
            tier_options = [0, 1, 2, 3, 4, 5]
            tier_labels = {0: "全", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
            hybrid.tier = self._draw_enum_combo("##tier_hybrid", hybrid.tier, tier_options, tier_labels)
            tooltip("用于掉落/商店筛选")

        # === 第二行：价格 / 重量 / 材质（物理/经济属性）===
        # Label 行
        grid.label_header("价格", styles.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("重量", styles.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("材质", styles.SPAN_INPUT)

        # Control 行
        grid.field_width(styles.SPAN_INPUT)
        changed, hybrid.base_price = imgui.input_int("##price_hybrid", hybrid.base_price, 1, 10)
        if changed:
            hybrid.base_price = max(0, hybrid.base_price)

        grid.next_cell()
        grid.field_width(styles.SPAN_INPUT)
        hybrid.weight = self._draw_enum_combo(
            "##weight_hybrid", hybrid.weight,
            list(HYBRID_WEIGHT_LABELS.keys()), HYBRID_WEIGHT_LABELS
        )
        tooltip("影响游泳；护甲时决定类别")

        grid.next_cell()
        grid.field_width(styles.SPAN_INPUT)
        hybrid.material = self._draw_enum_combo(
            "##material_hybrid", hybrid.material,
            list(HYBRID_MATERIALS.keys()), HYBRID_MATERIALS
        )

        # === 分类组（和物理组之间有 gap_s 间隔）===
        imgui.dummy(0, gap_m())

        # 主分类下拉 + 子分类流式布局（同一行）
        # 分类下拉：文物固定为 treasure
        is_treasure = hybrid.quality == 7
        if is_treasure:
            hybrid.cat = "treasure"
        elif hybrid.cat == "treasure":
            hybrid.cat = ""

        available_cats = [c for c in ITEM_CATEGORIES if c != "treasure"] if not is_treasure else ["treasure"]
        cat_options = (["treasure"] if is_treasure else [""]) + ([] if is_treasure else available_cats)
        cat_labels = {"": "—"}
        cat_labels.update({c: CATEGORY_TRANSLATIONS.get(c, c) for c in ITEM_CATEGORIES})

        # Label 行：分类（主分类下拉 + 子分类 badges 同一行）
        # 记录当前光标 X 位置作为内容区左边界（已含 indent）
        content_left_x = imgui.get_cursor_pos_x()
        max_x = content_left_x + styles.span(8)  # 8 span 边界

        grid.label_header("分类", styles.SPAN_INPUT)

        # === Control 行：分类下拉 + 子分类流式布局（同行）===
        if is_treasure:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.6)
        grid.field_width(styles.SPAN_INPUT)
        new_cat = self._draw_enum_combo("##cat_hybrid", hybrid.cat, cat_options, cat_labels)
        if not is_treasure:
            hybrid.cat = new_cat
        if is_treasure:
            imgui.pop_style_var()
        tooltip("主分类 (Cat)\n用于掉落表匹配")

        # 子分类流式布局紧跟主分类（同一行）
        imgui.same_line(0, gap_s())

        # 添加子分类按钮 (span=1)
        if imgui.button("+##add_subcat", styles.span(styles.SPAN_BADGE), 0):
            imgui.open_popup("subcats_popup")
        tooltip("添加子分类 (Subcats)\n可多选，物品可匹配主分类或任一子分类")

        # 显示已选子分类 badges (固定 span=1 宽度)
        badge_width = styles.span(styles.SPAN_BADGE)
        to_remove_subcat = None
        for subcat in sorted(hybrid.subcats):
            full_label = CATEGORY_TRANSLATIONS.get(subcat, subcat)
            # 检测是否需要截断
            text_size = imgui.calc_text_size(full_label)
            style = imgui.get_style()
            available_width = badge_width - 2 * style.frame_padding.x
            is_truncated = text_size.x > available_width

            # 流式布局：先 same_line 到前一个元素后面，再判断是否需要换行
            imgui.same_line(0, grid_gap())  # 使用 grid gap (0.5em) 保持 span 对齐
            cursor_x = imgui.get_cursor_pos_x()
            if cursor_x + badge_width > max_x:
                # 超出 8 span 边界，换行到内容区左边界（使用完整宽度）
                imgui.new_line()
                imgui.set_cursor_pos_x(content_left_x)

            imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, style.frame_padding.y))
            imgui.push_style_color(imgui.COLOR_BUTTON, *get_current_theme_colors()["badge_subcat"])
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *get_current_theme_colors()["badge_hover_remove"])
            if imgui.button(f"{full_label}##{subcat}_badge", badge_width, 0):
                to_remove_subcat = subcat
            imgui.pop_style_color(2)
            imgui.pop_style_var()
            # 组合 tooltip: 截断时显示完整文本 + 操作提示
            tooltip_parts = []
            if is_truncated:
                tooltip_parts.append(full_label)
            tooltip_parts.append("[点击移除]")
            tooltip("\n".join(tooltip_parts))
        if to_remove_subcat:
            hybrid.subcats.remove(to_remove_subcat)

        # 准备 popup 的子分类选项
        subcat_options = ALL_SUBCATEGORY_OPTIONS if hybrid.quality == 7 else [s for s in ALL_SUBCATEGORY_OPTIONS if s != "treasure"]
        if "treasure" in hybrid.subcats and hybrid.quality != 7:
            hybrid.subcats.remove("treasure")

        if imgui.begin_popup("subcats_popup"):
            for subcat in subcat_options:
                is_selected = subcat in hybrid.subcats
                is_disabled = (subcat == hybrid.cat)
                if is_disabled:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                changed, new_value = imgui.checkbox(
                    f"{CATEGORY_TRANSLATIONS.get(subcat, subcat)}##subcat_{subcat}",
                    is_selected
                )
                if changed and not is_disabled:
                    if new_value:
                        hybrid.subcats.append(subcat)
                    else:
                        hybrid.subcats.remove(subcat)
                if is_disabled:
                    imgui.pop_style_var()
            imgui.end_popup()

        # === 第四行：标签（流式布局）===
        grid.label_header("标签", styles.SPAN_INPUT)

        # 品质标签实时更新
        hybrid.quality_tag = "unique" if hybrid.quality == 6 else ""

        # 当 exclude_from_random=True 时，只显示 special 标签
        # 原因：游戏使用严格相等判断，其他标签会使 special 失效
        if hybrid.exclude_from_random:
            grid.begin_flow(styles.span(8))
            badge_width = styles.span(styles.SPAN_BADGE)
            style = imgui.get_style()
            grid.flow_item(badge_width)
            imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, style.frame_padding.y))
            imgui.push_style_color(imgui.COLOR_BUTTON, *get_current_theme_colors()["badge_special"])
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *get_current_theme_colors()["badge_hover_locked"])
            imgui.button(f"{EXTRA_TAGS.get('special', '特殊')}##special_only_badge", badge_width, 0)
            imgui.pop_style_color(2)
            imgui.pop_style_var()
            tooltip("已排除随机生成，其他标签不生效")
            grid.flow_item_after()
            grid.end_flow()
        else:
            # 正常模式：可编辑所有标签
            # 收集所有有效标签
            all_set_tags = []
            if hybrid.quality_tag:
                all_set_tags.append(("quality", hybrid.quality_tag))
            if hybrid.dungeon_tag:
                all_set_tags.append(("dungeon", hybrid.dungeon_tag))
            if hybrid.country_tag:
                all_set_tags.append(("country", hybrid.country_tag))
            for tag in hybrid.extra_tags:
                all_set_tags.append(("extra", tag))

            grid.begin_flow(styles.span(8))  # 限制在8列宽度内换行

            # 添加标签按钮
            if imgui.button("+##add_tag", styles.span(styles.SPAN_BADGE), 0):
                imgui.open_popup("tags_popup")
            tooltip("添加标签")
            grid.flow_item_after()

            # 显示标签 badges (固定 span=1 宽度)
            badge_width = styles.span(styles.SPAN_BADGE)
            to_remove_tag = None
            for tag_type, tag_val in all_set_tags:
                # 确定标签文本、颜色和可移除性
                if tag_type == "quality":
                    full_label = QUALITY_TAGS.get(tag_val, tag_val)
                    badge_color = get_current_theme_colors()["badge_quality"]
                    can_remove = False
                    locked_reason = "由品质自动设置"
                elif tag_type == "dungeon":
                    full_label = DUNGEON_TAGS.get(tag_val, tag_val)
                    badge_color = get_current_theme_colors()["badge_tag"]
                    can_remove = True
                    locked_reason = ""
                elif tag_type == "country":
                    full_label = COUNTRY_TAGS.get(tag_val, tag_val)
                    badge_color = get_current_theme_colors()["badge_tag"]
                    can_remove = True
                    locked_reason = ""
                else:
                    full_label = EXTRA_TAGS.get(tag_val, tag_val)
                    badge_color = get_current_theme_colors()["badge_tag"]
                    can_remove = True
                    locked_reason = ""

                # 检测是否需要截断
                text_size = imgui.calc_text_size(full_label)
                style = imgui.get_style()
                available_width = badge_width - 2 * style.frame_padding.x
                is_truncated = text_size.x > available_width

                # 选择 hover 颜色
                hover_color = get_current_theme_colors()["badge_hover_remove"] if can_remove else get_current_theme_colors()["badge_hover_locked"]

                grid.flow_item(badge_width)
                imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, style.frame_padding.y))
                imgui.push_style_color(imgui.COLOR_BUTTON, *badge_color)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *hover_color)

                if imgui.button(f"{full_label}##{tag_type}_{tag_val}_badge", badge_width, 0):
                    if can_remove:
                        to_remove_tag = (tag_type, tag_val)
                imgui.pop_style_color(2)
                imgui.pop_style_var()

                # 组合 tooltip: 截断文本 + 操作提示
                tooltip_parts = []
                if is_truncated:
                    tooltip_parts.append(full_label)
                if can_remove:
                    tooltip_parts.append("[点击移除]")
                elif locked_reason:
                    tooltip_parts.append(f"[{locked_reason}]")
                if tooltip_parts:
                    tooltip("\n".join(tooltip_parts))
                grid.flow_item_after()

            # 处理移除
            if to_remove_tag:
                tag_type, tag_val = to_remove_tag
                if tag_type == "dungeon":
                    hybrid.dungeon_tag = ""
                elif tag_type == "country":
                    hybrid.country_tag = ""
                elif tag_type == "extra":
                    hybrid.extra_tags.remove(tag_val)

            if imgui.begin_popup("tags_popup"):
                text_secondary("地牢")
                for tag_val, tag_label in DUNGEON_TAGS.items():
                    if imgui.radio_button(f"{tag_label}##dungeon", hybrid.dungeon_tag == tag_val):
                        hybrid.dungeon_tag = tag_val

                imgui.separator()
                text_secondary("国家/地区")
                for tag_val, tag_label in COUNTRY_TAGS.items():
                    if imgui.radio_button(f"{tag_label}##country", hybrid.country_tag == tag_val):
                        hybrid.country_tag = tag_val

                imgui.separator()
                text_secondary("其他")
                for tag_val, tag_label in EXTRA_TAGS.items():
                    if tag_val == "special":
                        continue
                    is_selected = tag_val in hybrid.extra_tags
                    changed, new_value = imgui.checkbox(f"{tag_label}##extra_{tag_val}", is_selected)
                    if changed:
                        if new_value:
                            hybrid.extra_tags.append(tag_val)
                        else:
                            hybrid.extra_tags.remove(tag_val)
                imgui.end_popup()

            grid.end_flow()

        # 注：生成规则已移至 _draw_hybrid_behavior 末尾

    def _draw_hybrid_spawn_settings(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制生成规则设置（使用 Grid 系统 - label 在上方）"""
        # 使用 GridLayout 类
        grid = GridLayout(text_secondary)

        # 生成规则设置 - 使用 SpawnRuleType
        spawn_rule_labels = {
            SpawnRuleType.EQUIPMENT: "按装备池",
            SpawnRuleType.ITEM: "按道具池",
            SpawnRuleType.NONE: "不生成",
        }
        # 装备模式时可使用装备池
        can_use_equipment = not isinstance(hybrid.equipment, NotEquipable)

        # 读取当前状态
        is_excluded = spawn_is_excluded(hybrid.spawn)
        current_container = hybrid.container_spawn
        current_shop = hybrid.shop_spawn

        # Label 行
        grid.label_header("排除随机生成", styles.SPAN_INPUT)
        grid.next_cell()
        if not is_excluded:
            grid.label_header("容器生成", styles.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("商店生成", styles.SPAN_INPUT)
            grid.next_cell()

        grid.label_header("生成预测", styles.SPAN_INPUT)

        # Control 行
        _, new_excluded = grid.checkbox_cell("##exc_random", is_excluded, styles.SPAN_INPUT)
        tooltip("排除随机生成：物品不会在宝箱/商店随机出现\n启用后其他标签设置不生效")

        # 如果排除状态改变，更新 spawn spec
        if new_excluded != is_excluded:
            if new_excluded:
                hybrid.spawn = ExcludedFromRandom()
            else:
                # 切换为可随机生成，创建默认的 RandomSpawn
                hybrid.spawn = RandomSpawn()

        grid.next_cell()
        if not new_excluded and isinstance(hybrid.spawn, RandomSpawn):
            spawn = hybrid.spawn  # 类型缩窄

            # 容器
            grid.field_width(styles.SPAN_INPUT)
            container_options = [SpawnRuleType.EQUIPMENT, SpawnRuleType.ITEM, SpawnRuleType.NONE] if can_use_equipment else [SpawnRuleType.ITEM, SpawnRuleType.NONE]
            if current_container not in container_options:
                current_container = SpawnRuleType.NONE
            if imgui.begin_combo("##container_spawn", spawn_rule_labels[current_container]):
                for rule in container_options:
                    if imgui.selectable(spawn_rule_labels[rule], current_container == rule)[0]:
                        object.__setattr__(spawn, "container_spawn", rule)
                imgui.end_combo()
            tooltip(
                "容器生成规则（宝箱/桶/尸体等）\n\n"
                "• 按装备池：根据武器类型/护甲类型 + 标签 + 层级匹配\n"
                "• 按道具池：根据分类/子分类 + 标签 + 层级匹配\n"
                "• 不生成：不在容器中随机出现"
            )

            grid.next_cell()
            # 商店
            grid.field_width(styles.SPAN_INPUT)
            shop_options = [SpawnRuleType.EQUIPMENT, SpawnRuleType.ITEM, SpawnRuleType.NONE] if can_use_equipment else [SpawnRuleType.ITEM, SpawnRuleType.NONE]
            if current_shop not in shop_options:
                current_shop = SpawnRuleType.NONE
            if imgui.begin_combo("##shop_spawn", spawn_rule_labels[current_shop]):
                for rule in shop_options:
                    if imgui.selectable(spawn_rule_labels[rule], current_shop == rule)[0]:
                        object.__setattr__(spawn, "shop_spawn", rule)
                imgui.end_combo()
            tooltip(
                "商店生成规则（商人进货时）\n\n"
                "• 按装备池：根据武器/护甲/珠宝类别 + 层级 + 材质 + 标签匹配\n"
                "• 按道具池：根据分类/子分类 + 层级 + 标签匹配\n"
                "• 不生成：不在商店随机出现"
            )

            grid.next_cell()

        # 生成预测按钮
        if grid.button_cell("▶##gen_preview", styles.SPAN_INPUT):
            imgui.open_popup("generation_preview_popup")
        tooltip("查看生成预测")
        self._draw_generation_preview_popup(hybrid)

    def _draw_generation_preview_popup(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制生成预测弹窗 - 三场景版"""
        imgui.set_next_window_size(500, 350, imgui.ALWAYS)
        if imgui.begin_popup("generation_preview_popup"):
            imgui.text("生成预测")
            imgui.separator()

            if spawn_is_excluded(hybrid.spawn):
                text_secondary("物品已排除随机生成")
                imgui.text("不会出现在宝箱掉落、商店库存中")
            else:
                # 容器掉落
                imgui.text("容器掉落:")
                if hybrid.container_spawn == SpawnRuleType.NONE:
                    text_secondary("  关闭")
                elif hybrid.container_spawn == SpawnRuleType.EQUIPMENT:
                    self._draw_container_preview_simplified(hybrid, is_equipment=True)
                else:  # ITEM
                    self._draw_container_preview_simplified(hybrid, is_equipment=False)

                imgui.dummy(0, gap_m())

                # 商店进货
                imgui.text("商店进货:")
                if hybrid.shop_spawn == SpawnRuleType.NONE:
                    text_secondary("  关闭")
                else:
                    self._draw_shop_preview_simplified(hybrid)

                imgui.dummy(0, gap_m())

            imgui.end_popup()

    def _draw_container_preview_simplified(self: "GUIProtocol", hybrid: HybridItemV2, is_equipment: bool):
        """简化版容器预测 - 只显示容器名称"""
        # 构建 tags tuple
        tags_tuple = tuple(hybrid.effective_tags.split()) if hybrid.effective_tags else ()

        if is_equipment:
            # 装备路径 - 使用 Tagged Union 检查
            eq_categories = []
            match hybrid.equipment:
                case WeaponEquip(weapon_type=wt):
                    eq_categories.append(wt)
                    eq_categories.append("weapon")
                case ArmorEquip(armor_type=at):
                    eq_categories.append(at)
                    if at in ("Ring", "Amulet"):
                        eq_categories.append("jewelry")
                    else:
                        eq_categories.append("armor")

            if not eq_categories:
                text_secondary("  (无匹配)")
                return

            all_matches = []
            for eq_cat in eq_categories:
                matches = find_matching_eq_slots(eq_cat, tags_tuple, hybrid.tier)
                all_matches.extend(matches)

            if not all_matches:
                text_secondary("  (无匹配)")
                return

            # 去重并只显示名称
            names = list(dict.fromkeys(m["entry_name_cn"] for m in all_matches))
            display = ", ".join(names)
            imgui.text_wrapped(f"  {display}")
        else:
            # 非装备路径
            if not (hybrid.cat or hybrid.subcats):
                text_secondary("  (请设置分类)")
                return

            matches = find_matching_slots(
                hybrid.cat, tuple(hybrid.subcats),
                tags_tuple, hybrid.tier
            )

            if not matches:
                text_secondary("  (无匹配)")
                return

            names = list(dict.fromkeys(m["entry_name_cn"] for m in matches))
            display = ", ".join(names)
            imgui.text_wrapped(f"  {display}")

    def _draw_shop_preview_simplified(self: "GUIProtocol", hybrid: HybridItemV2):
        """简化版商店预测 - 只显示城镇·商店名"""
        if hybrid.shop_spawn == SpawnRuleType.ITEM:
            # 非装备路径
            if not (hybrid.cat or hybrid.subcats):
                text_secondary("  (请设置分类)")
                return
            item_cats = set([hybrid.cat] + list(hybrid.subcats))
            item_tags = set(hybrid.effective_tags.split()) if hybrid.effective_tags else set()
            matching = []

            for objects_tuple, config in SHOP_CONFIGS.items():
                selling_cats = config.get("selling_loot_category", {})
                tier_range = config.get("tier_range", [1, 1])
                trade_tags = set(config.get("trade_tags", []))
                matched_cats = item_cats & set(selling_cats.keys())
                if not matched_cats:
                    continue
                # Tier 过滤（与装备规则一致）
                if hybrid.tier > 0 and not (tier_range[0] <= hybrid.tier <= tier_range[1]):
                    continue
                if trade_tags and item_tags and not item_tags.issubset(trade_tags):
                    continue
                for obj in objects_tuple:
                    meta = NPC_METADATA.get(obj, {})
                    name = meta.get("name_zh") or meta.get("name_en")
                    if name:
                        town = meta.get("town_zh") or meta.get("town") or ""
                        matching.append(f"{town}·{name}" if town else name)
        else:
            # 装备路径 - 使用 Tagged Union 检查
            item_tier = hybrid.tier
            item_material = hybrid.material
            item_tags = set(hybrid.effective_tags.split()) if hybrid.effective_tags else set()

            # 从 equipment spec 获取信息
            item_weapon_type = None
            item_armor_slot = None
            match hybrid.equipment:
                case WeaponEquip(weapon_type=wt):
                    item_weapon_type = wt
                case ArmorEquip(armor_type=at):
                    item_armor_slot = at

            is_jewelry = item_armor_slot in ("ring", "amulet", "Ring", "Amulet") if item_armor_slot else False
            matching = []

            for objects_tuple, config in SHOP_CONFIGS.items():
                selling_cats = set(config.get("selling_loot_category", {}).keys())
                tier_range = config.get("tier_range", [1, 1])
                material_spec = config.get("material_spec", ["all"])
                trade_tags = set(config.get("trade_tags", []))

                category_matched = False
                if "weapon" in selling_cats and item_weapon_type:
                    category_matched = True
                elif "armor" in selling_cats and item_armor_slot and not is_jewelry:
                    category_matched = True
                elif "jewelry" in selling_cats and is_jewelry:
                    category_matched = True

                if not category_matched:
                    continue
                if item_tier > 0 and not (tier_range[0] <= item_tier <= tier_range[1]):
                    continue
                if "all" not in material_spec and item_material not in material_spec:
                    continue
                if trade_tags and (not item_tags or not item_tags.issubset(trade_tags)):
                    continue

                for obj in objects_tuple:
                    meta = NPC_METADATA.get(obj, {})
                    name = meta.get("name_zh") or meta.get("name_en")
                    if name:
                        town = meta.get("town_zh") or meta.get("town") or ""
                        matching.append(f"{town}·{name}" if town else name)

        if not matching:
            text_secondary("  (无匹配)")
            return

        display = ", ".join(matching)
        imgui.text_wrapped(f"  {display}")

    def _draw_kill_preview_simplified(self: "GUIProtocol", hybrid: HybridItemV2):
        """简化版击杀掉落预测 - 显示可能掉落此物品的敌人"""
        # 导入击杀掉落数据
        try:
            from enemy_drop_constants import DROP_TABLE, ENEMY_META
        except ImportError:
            text_secondary("  (击杀数据未加载)")
            return

        # 确定物品的 slot（武器类型或护甲槽位）- 使用 Tagged Union
        item_slot: str | None = None
        match hybrid.equipment:
            case WeaponEquip(weapon_type=wt):
                item_slot = wt
            case ArmorEquip(armor_type=at):
                item_slot = at
            case _:
                text_secondary("  (需要装备形态)")
                return

        item_tier = hybrid.tier
        matching_enemies = []

        # 精确匹配 DROP_TABLE: {(tier, slot): [敌人列表]}
        key = (item_tier, item_slot)
        if key in DROP_TABLE:
            for enemy_obj in DROP_TABLE[key]:
                meta = ENEMY_META.get(enemy_obj, {})
                name = meta.get("name_zh") or meta.get("name_en") or enemy_obj
                enemy_tier = meta.get("tier", 0)
                matching_enemies.append(f"{name}(T{enemy_tier})")

        if not matching_enemies:
            text_secondary("  (无匹配)")
            return

        # 去重
        unique_enemies = list(dict.fromkeys(matching_enemies))
        display = ", ".join(unique_enemies)
        imgui.text_wrapped(f"  {display}")

    def _draw_fragments_popup(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制拆解碎片材料弹窗"""
        if imgui.begin_popup("fragments_popup"):
            imgui.text("拆解碎片")
            imgui.separator()
            text_secondary("拆解物品时可获得的材料碎片")

            frag_data = [
                ("cloth01", "布1"), ("cloth02", "布2"), ("cloth03", "布3"), ("cloth04", "布4"),
                ("leather01", "皮1"), ("leather02", "皮2"), ("leather03", "皮3"), ("leather04", "皮4"),
                ("metal01", "铁1"), ("metal02", "铁2"), ("metal03", "铁3"), ("metal04", "铁4"),
                ("gold", "金"),
            ]

            imgui.dummy(0, gap_s())

            # 4列布局
            if imgui.begin_table("frag_popup_table", 4, imgui.TABLE_SIZING_STRETCH_SAME):
                imgui.table_setup_column("L1", imgui.TABLE_COLUMN_WIDTH_FIXED, 30)
                imgui.table_setup_column("I1", imgui.TABLE_COLUMN_WIDTH_FIXED, 50)
                imgui.table_setup_column("L2", imgui.TABLE_COLUMN_WIDTH_FIXED, 30)
                imgui.table_setup_column("I2", imgui.TABLE_COLUMN_WIDTH_FIXED, 50)

                for i, (frag_key, frag_label) in enumerate(frag_data):
                    if i % 2 == 0:
                        imgui.table_next_row()

                    imgui.table_next_column()
                    imgui.text(frag_label)

                    imgui.table_next_column()
                    val = hybrid.fragments.get(frag_key, 0)
                    with item_width(-1):
                        changed, new_val = imgui.input_int(f"##{frag_key}_popup", val, step=0, step_fast=0)
                    if changed:
                        hybrid.fragments[frag_key] = max(0, new_val)

                imgui.end_table()

            imgui.end_popup()

    def _draw_hybrid_behavior(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制行为区块 - Grid 系统布局 (Tagged Union API)

        Grid 规则:
        - 每个 chunk 宽度 = span(n) = n * col + (n-1) * gap
        - chunk 之间用 grid_gap 分隔
        - 保证垂直对齐
        """
        # UI 标签映射 - 使用字符串键
        EQUIPMENT_MODE_LABELS = {
            "none": "无",
            "weapon": "武器",
            "armor": "护甲",
            "charm": "护符",
        }
        TRIGGER_MODE_LABELS = {
            "none": "无",
            "effect": "效果",
            "skill": "技能",
        }
        CHARGE_MODE_LABELS = {
            "limited": "有限",
            "unlimited": "无限",
        }

        # GridLayout 类替代内联 helper 函数
        grid = GridLayout(text_secondary)
        col = styles.grid_col()
        gap = styles.grid_gap()
        debug_grid = styles.GRID_DEBUG

        # Debug: draw grid lines
        if debug_grid:
            draw_list = imgui.get_window_draw_list()
            cursor_pos = imgui.get_cursor_screen_pos()
            content_x = cursor_pos[0]
            window_y = cursor_pos[1]
            window_h = 150  # 绘制高度
            available_w = imgui.get_content_region_available_width()

            # 交替绘制 col (红色) 和 gap (绿色) 区域
            x = content_x
            is_col = True  # 交替标记
            while x < content_x + available_w:
                if is_col:
                    # Column - 红色半透明
                    w = col
                    color = imgui.get_color_u32_rgba(1, 0.3, 0.3, 0.15)
                else:
                    # Gap - 绿色半透明
                    w = gap
                    color = imgui.get_color_u32_rgba(0.3, 1, 0.3, 0.25)

                # 绘制填充矩形
                if x + w <= content_x + available_w:
                    draw_list.add_rect_filled(x, window_y, x + w, window_y + window_h, color)
                    # 边框线
                    border_color = imgui.get_color_u32_rgba(1, 1, 1, 0.3)
                    draw_list.add_rect(x, window_y, x + w, window_y + window_h, border_color, 0, 0, 1.0)

                x += w
                is_col = not is_col

        # 获取当前模式
        current_eq_mode = "none"
        if is_weapon_mode(hybrid.equipment):
            current_eq_mode = "weapon"
        elif is_armor_mode(hybrid.equipment):
            current_eq_mode = "armor"
        elif is_charm_mode(hybrid.equipment):
            current_eq_mode = "charm"

        # ━━━ 形态行 ━━━
        # Label 行 (所有 labels 画在一行)
        grid.label_header("装备形态", styles.SPAN_INPUT)
        if is_weapon_mode(hybrid.equipment):
            grid.next_cell()
            grid.label_header("武器类型", styles.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("平衡", styles.SPAN_INPUT)
        elif is_armor_mode(hybrid.equipment):
            grid.next_cell()
            grid.label_header("护甲类型", styles.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("护甲分类", styles.SPAN_INPUT)
            if hybrid.slot not in ["hand", "Ring", "Amulet"]:
                grid.next_cell()
                grid.label_header("碎片数", styles.SPAN_INPUT)
        # Label 行结束，不调用 next_cell()

        # Control 行 (新的一行开始)
        grid.field_width(styles.SPAN_INPUT)
        # 装备形态下拉
        new_eq_mode = self._draw_enum_combo(
            "##eq_mode", current_eq_mode,
            list(EQUIPMENT_MODE_LABELS.keys()), EQUIPMENT_MODE_LABELS
        )
        # 如果模式改变，更新 equipment spec
        if new_eq_mode != current_eq_mode:
            match new_eq_mode:
                case "weapon":
                    hybrid.equipment = WeaponEquip()
                case "armor":
                    hybrid.equipment = ArmorEquip()
                case "charm":
                    hybrid.equipment = CharmEquip()
                case _:
                    hybrid.equipment = NotEquipable()

        if is_weapon_mode(hybrid.equipment):
            assert isinstance(hybrid.equipment, WeaponEquip)
            weapon_eq = hybrid.equipment
            grid.next_cell()
            grid.field_width(styles.SPAN_INPUT)
            new_wt = self._draw_enum_combo(
                "##wep_type", weapon_eq.weapon_type,
                list(HYBRID_WEAPON_TYPES.keys()), HYBRID_WEAPON_TYPES
            )
            if new_wt != weapon_eq.weapon_type:
                object.__setattr__(weapon_eq, "weapon_type", new_wt)

            grid.next_cell()
            grid.field_width(styles.SPAN_INPUT)
            balance_options = {"0": "0", "1": "1", "2": "2", "3": "3", "4": "4"}
            new_balance = int(self._draw_enum_combo(
                "##wep_balance", str(weapon_eq.balance),
                list(balance_options.keys()), balance_options
            ))
            if new_balance != weapon_eq.balance:
                object.__setattr__(weapon_eq, "balance", new_balance)

        elif is_armor_mode(hybrid.equipment):
            assert isinstance(hybrid.equipment, ArmorEquip)
            armor_eq = hybrid.equipment
            grid.next_cell()
            grid.field_width(styles.SPAN_INPUT)
            old_armor_type = armor_eq.armor_type
            new_armor_type = self._draw_enum_combo(
                "##armor_type", armor_eq.armor_type,
                list(HYBRID_ARMOR_TYPES.keys()), HYBRID_ARMOR_TYPES
            )
            if new_armor_type != old_armor_type:
                object.__setattr__(armor_eq, "armor_type", new_armor_type)

            grid.next_cell()
            grid.text_cell(hybrid.armor_class, styles.SPAN_INPUT)
            if hybrid.slot not in ["hand", "Ring", "Amulet"]:
                grid.next_cell()
                frag_count = sum(hybrid.fragments.values())
                if grid.button_cell(f"({frag_count})##frags", styles.SPAN_INPUT):
                    imgui.open_popup("fragments_popup")
                self._draw_fragments_popup(hybrid)
        # Control 行结束，不调用 next_cell()

        # 逻辑组间隔
        imgui.dummy(0, gap_m())

        # ━━━ 触发组 ━━━
        # 获取当前触发模式
        current_trigger_mode = "none"
        if isinstance(hybrid.trigger, EffectTrigger):
            current_trigger_mode = "effect"
        elif isinstance(hybrid.trigger, SkillTrigger):
            current_trigger_mode = "skill"

        # Label 行
        grid.label_header("触发模式", styles.SPAN_INPUT)
        if isinstance(hybrid.trigger, SkillTrigger):
            grid.next_cell()
            grid.label_header("技能", styles.SPAN_INPUT)
        # Label 行结束

        # Control 行
        grid.field_width(styles.SPAN_INPUT)
        old_trigger_mode = current_trigger_mode
        new_trigger_mode = self._draw_enum_combo(
            "##trigger_mode", current_trigger_mode,
            list(TRIGGER_MODE_LABELS.keys()), TRIGGER_MODE_LABELS
        )
        # 如果触发模式改变，更新 trigger spec
        if new_trigger_mode != old_trigger_mode:
            match new_trigger_mode:
                case "effect":
                    hybrid.trigger = EffectTrigger()
                    # 同时需要 charges
                    if not charge_has_charges(hybrid.charges):
                        hybrid.charges = LimitedCharges()
                case "skill":
                    hybrid.trigger = SkillTrigger()
                    # 同时需要 charges
                    if not charge_has_charges(hybrid.charges):
                        hybrid.charges = LimitedCharges()
                case _:
                    hybrid.trigger = NoTrigger()
                    hybrid.charges = NoCharges()

        if isinstance(hybrid.trigger, SkillTrigger):
            skill_trigger = hybrid.trigger
            grid.next_cell()
            grid.field_width(styles.SPAN_INPUT)
            current_skill = skill_trigger.skill_object
            current_label = SKILL_OBJECT_NAMES.get(current_skill, current_skill) if current_skill else "-- 选择 --"
            if imgui.begin_combo("##skill_object", current_label):
                if imgui.selectable("-- 无 --", current_skill == "")[0]:
                    object.__setattr__(skill_trigger, "skill_object", "")
                imgui.separator()
                for branch in sorted(SKILL_BY_BRANCH.keys()):
                    branch_label = SKILL_BRANCH_TRANSLATIONS.get(branch, branch)
                    skills = SKILL_BY_BRANCH[branch]
                    if not skills or branch in ("none", "unknown"):
                        continue
                    if imgui.tree_node(f"{branch_label}##branch_{branch}"):
                        for skill_obj in skills:
                            skill_info = SKILL_OBJECTS.get(skill_obj, {})
                            skill_name = skill_info.get("name_chinese", skill_obj)
                            if imgui.selectable(f"{skill_name}##{skill_obj}", current_skill == skill_obj)[0]:
                                object.__setattr__(skill_trigger, "skill_object", skill_obj)
                        imgui.tree_pop()
                imgui.end_combo()
        # Control 行结束

        # ━━━ 耐久组（条件显示）- 仅装备且非文物有耐久 ━━━
        if hybrid.has_durability:
            imgui.dummy(0, gap_m())

            # 获取耐久设置
            durability: HasDurability | None = None
            match hybrid.equipment:
                case WeaponEquip(durability=d) if isinstance(d, HasDurability):
                    durability = d
                case ArmorEquip(durability=d) if isinstance(d, HasDurability):
                    durability = d

            if durability:
                # Label 行
                grid.label_header("耐久上限", styles.SPAN_INPUT)
                grid.next_cell()
                has_charges = charge_has_charges(hybrid.charges)
                if has_charges:
                    grid.label_header("磨损%", styles.SPAN_INPUT)
                    grid.next_cell()
                grid.label_header("耐久归零销毁", styles.SPAN_INPUT)

                # Control 行
                grid.field_width(styles.SPAN_INPUT)
                changed, new_dur_max = imgui.input_int("##dur_max", durability.duration_max)
                if changed:
                    object.__setattr__(durability, "duration_max", max(1, new_dur_max))
                grid.next_cell()

                if has_charges:
                    grid.field_width(styles.SPAN_INPUT)
                    changed, new_wear = imgui.input_int("##wear", durability.wear_per_use)
                    tooltip("每次使用消耗的耐久百分比")
                    if changed:
                        object.__setattr__(durability, "wear_per_use", max(0, min(100, new_wear)))
                    grid.next_cell()

                _, new_destroy = grid.checkbox_cell("##dur_del", durability.destroy_on_zero, styles.SPAN_INPUT)
                if new_destroy != durability.destroy_on_zero:
                    object.__setattr__(durability, "destroy_on_zero", new_destroy)

        # ━━━ 次数组（条件显示）━━━
        has_charges = charge_has_charges(hybrid.charges)
        if has_charges:
            imgui.dummy(0, gap_m())

            # 获取当前 charge 模式
            is_unlimited = isinstance(hybrid.charges, UnlimitedCharges)
            current_charge_mode = "unlimited" if is_unlimited else "limited"

            # Label 行
            grid.label_header("次数模式", styles.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("次数值", styles.SPAN_INPUT)
            grid.next_cell()
            grid.label_header("显次数点", styles.SPAN_INPUT)

            # Control 行
            grid.field_width(styles.SPAN_INPUT)
            new_charge_mode = self._draw_enum_combo(
                "##charge_mode", current_charge_mode,
                list(CHARGE_MODE_LABELS.keys()), CHARGE_MODE_LABELS
            )

            # 如果 charge 模式改变
            if new_charge_mode != current_charge_mode:
                if new_charge_mode == "unlimited":
                    hybrid.charges = UnlimitedCharges()
                    hybrid.charge_recovery = NoRecovery()
                else:
                    hybrid.charges = LimitedCharges()

            grid.next_cell()
            if isinstance(hybrid.charges, UnlimitedCharges):
                grid.text_cell("∞", styles.SPAN_INPUT)
            elif isinstance(hybrid.charges, LimitedCharges):
                charges = hybrid.charges
                grid.field_width(styles.SPAN_INPUT)
                changed, new_max = imgui.input_int("##charge", charges.max_charges)
                if changed:
                    object.__setattr__(charges, "max_charges", max(1, new_max))

            grid.next_cell()
            # draw_charges
            current_draw = False
            match hybrid.charges:
                case LimitedCharges(draw_charges=d):
                    current_draw = d
                case UnlimitedCharges(draw_charges=d):
                    current_draw = d

            _, new_draw = grid.checkbox_cell("##show_charge", current_draw, styles.SPAN_INPUT)
            tooltip("在物品贴图左下角绘制小点表示剩余次数")
            if new_draw != current_draw:
                object.__setattr__(hybrid.charges, "draw_charges", new_draw)

            # === 第二行：恢复/终止设置（仅在有限次数时显示）===
            if isinstance(hybrid.charges, LimitedCharges):
                is_artifact = isinstance(hybrid.quality, ArtifactQuality)

                # Label 行
                grid.label_header("自动恢复", styles.SPAN_INPUT)
                has_recovery = recovery_has_recovery(hybrid.charge_recovery)
                if has_recovery:
                    grid.next_cell()
                    grid.label_header("恢复间隔", styles.SPAN_INPUT)
                if not hybrid.has_durability and not is_artifact:
                    grid.next_cell()
                    grid.label_header("耗尽销毁", styles.SPAN_INPUT)

                # Control 行
                if is_artifact:
                    # 文物强制自动恢复
                    if not has_recovery:
                        hybrid.charge_recovery = IntervalRecovery()
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                    grid.checkbox_cell("##recovery_locked", True, styles.SPAN_INPUT)
                    imgui.pop_style_var()
                    tooltip("文物自动恢复")
                else:
                    _, new_recovery = grid.checkbox_cell("##recovery", has_recovery, styles.SPAN_INPUT)
                    if new_recovery != has_recovery:
                        if new_recovery:
                            hybrid.charge_recovery = IntervalRecovery()
                        else:
                            hybrid.charge_recovery = NoRecovery()

                if recovery_has_recovery(hybrid.charge_recovery):
                    assert isinstance(hybrid.charge_recovery, IntervalRecovery)
                    recovery = hybrid.charge_recovery
                    grid.next_cell()
                    grid.field_width(styles.SPAN_INPUT)
                    changed, new_interval = imgui.input_int("##interval", recovery.interval)
                    if changed:
                        object.__setattr__(recovery, "interval", max(1, new_interval))

                if not hybrid.has_durability and not is_artifact:
                    grid.next_cell()
                    _, hybrid.delete_on_charge_zero = grid.checkbox_cell("##charge_del", hybrid.delete_on_charge_zero, styles.SPAN_INPUT)

        # 逻辑组间隔
        imgui.dummy(0, gap_m())

        # ━━━ 生成组 ━━━
        self._draw_hybrid_spawn_settings(hybrid)

    def _draw_hybrid_stats(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制属性区块 - Active-Only 模式"""

        # 装备属性
        if self._should_show_hybrid_attributes(hybrid):
            self._draw_hybrid_attributes_editor(hybrid)

        # 消耗品属性 - 仅当触发模式为效果时显示
        if isinstance(hybrid.trigger, EffectTrigger):
            # 如果同时显示装备属性，添加间距
            if self._should_show_hybrid_attributes(hybrid):
                imgui.dummy(0, gap_m())

            self._draw_hybrid_consumable_attributes_editor(hybrid)

    def _draw_hybrid_presentation(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制呈现区块 - 贴图、音效、本地化"""
        # 贴图
        from ui.editors.texture_editor import draw_textures_editor
        draw_textures_editor(hybrid, "hybrid")

        imgui.dummy(0, gap_m())
        imgui.separator()
        imgui.dummy(0, gap_s())

        # 音效 - 使用 GridLayout（label-on-top 布局，与基础/行为区块一致）
        grid = GridLayout(text_secondary)

        # Label 行
        grid.label_header("放下音效", styles.SPAN_INPUT)
        grid.next_cell()
        grid.label_header("拾取音效", styles.SPAN_INPUT)

        # Control 行
        grid.field_width(styles.SPAN_INPUT)
        current_drop_label = HYBRID_DROP_SOUNDS.get(hybrid.drop_sound, f"{hybrid.drop_sound}")
        if imgui.begin_combo("##drop_sound", current_drop_label):
            for sound_id, sound_label in HYBRID_DROP_SOUNDS.items():
                if imgui.selectable(sound_label, sound_id == hybrid.drop_sound)[0]:
                    hybrid.drop_sound = sound_id
            imgui.end_combo()
        tooltip("物品放入物品栏或地面时的音效")

        grid.next_cell()
        grid.field_width(styles.SPAN_INPUT)
        current_pickup_label = HYBRID_PICKUP_SOUNDS.get(hybrid.pickup_sound, f"{hybrid.pickup_sound}")
        if imgui.begin_combo("##pickup_sound", current_pickup_label):
            for sound_id, sound_label in HYBRID_PICKUP_SOUNDS.items():
                if imgui.selectable(sound_label, sound_id == hybrid.pickup_sound)[0]:
                    hybrid.pickup_sound = sound_id
            imgui.end_combo()
        tooltip("物品被拾取时的音效")

        imgui.dummy(0, gap_m())
        imgui.separator()
        imgui.dummy(0, gap_s())

        # 本地化
        self._draw_localization_editor(hybrid, "hybrid")

    def _update_hybrid_rarity_from_quality(self: "GUIProtocol", hybrid: HybridItemV2):
        """根据品质自动更新稀有度 - V2 版本中 rarity 由 quality spec 自动推导，无需手动更新"""
        # V2 API: rarity 是只读属性，由 quality_to_rarity(quality) 自动计算
        pass

    def _render_attribute_grid(self: "GUIProtocol", display_list: list, target_dict: dict, hybrid: HybridItemV2 | None = None, show_add_button: bool = False, add_button_label: str = "", add_popup_id: str = "") -> list:
        """Shared logic for rendering attributes in vertical list layout

        Args:
            display_list: List of dicts with:
                - key: str
                - name: str (display name)
                - is_basic: bool (if True, no delete button)
                - custom_bind: str (optional, e.g. "poison_duration" for redirect)
                - desc: str (optional tooltip)
            target_dict: The dict to modify values in (e.g. hybrid.attributes)
            hybrid: The hybrid item object (required if using custom_bind)
            show_add_button: If True, show add button on first row
            add_button_label: Label for add button (e.g. "+装备")
            add_popup_id: Popup ID for add button

        Returns:
            list of keys to remove
        """
        to_remove = []

        # 列宽分配: +按钮(1) + Label(4) + Input(2) + Delete(1) = 8 span
        SPAN_ADD_BTN = styles.SPAN_BADGE  # 1
        SPAN_LABEL = 4
        SPAN_INPUT = styles.SPAN_INPUT   # 2
        SPAN_DELETE = styles.SPAN_BADGE  # 1

        for idx, item in enumerate(display_list):
            key = item["key"]
            name = item.get("name", key)
            is_basic = item.get("is_basic", False)
            custom_bind = item.get("custom_bind", None)
            desc = item.get("desc", None)

            # === Column 1: Add Button (only first row) or spacer ===
            if idx == 0 and show_add_button:
                if imgui.button(f"{add_button_label}##{add_popup_id}_btn", styles.span(SPAN_ADD_BTN), 0):
                    imgui.open_popup(add_popup_id)
                tooltip("添加属性")
            else:
                imgui.dummy(styles.span(SPAN_ADD_BTN), 0)

            imgui.same_line(spacing=grid_gap())

            # === Column 2: Label ===
            label_w = styles.span(SPAN_LABEL)
            imgui.align_text_to_frame_padding()
            text_secondary(name)
            # Pad to full width
            text_w = imgui.calc_text_size(name).x
            if text_w < label_w:
                imgui.same_line(spacing=0)
                imgui.dummy(label_w - text_w, 0)

            imgui.same_line(spacing=grid_gap())

            # === Column 3: Input ===
            input_w = styles.span(SPAN_INPUT)
            imgui.set_next_item_width(input_w)

            if custom_bind == "poison_duration" and hybrid and isinstance(hybrid.trigger, EffectTrigger):
                val = hybrid.trigger.poison_duration
                ch, nv = imgui.input_int(f"##v_poison_dur", val)
                if ch:
                    object.__setattr__(hybrid.trigger, "poison_duration", max(0, nv))
            else:
                val = target_dict.get(key, 0)
                if key in STRICT_INT_ATTRIBUTES:
                    ch, nv = imgui.input_int(f"##v_{key}", int(val))
                else:
                    step = SPECIAL_STEP_ATTRIBUTES.get(key, 0.1)
                    ch, nv = imgui.input_float(f"##v_{key}", float(val), step, step * 10 if step else 0, "%.2f")

                if ch:
                    target_dict[key] = nv
                    if is_basic:
                        target_dict[key] = max(0, target_dict[key])

            if desc:
                tooltip(desc)

            imgui.same_line(spacing=grid_gap())

            # === Column 4: Delete Button ===
            delete_w = styles.span(SPAN_DELETE)
            if not is_basic:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *get_current_theme_colors()["badge_hover_remove"])
                imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *get_current_theme_colors()["badge_hover_remove"])
                if imgui.button(f"×##del_{key}", delete_w, 0):
                    to_remove.append(key)
                imgui.pop_style_color(3)
                tooltip("移除此属性")
            else:
                # Placeholder for alignment
                imgui.dummy(delete_w, 0)
                tooltip("基础属性不可移除")

        return to_remove

    def _draw_hybrid_attributes_editor(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制装备属性编辑器 - 垂直列表布局"""
        groups = self._get_hybrid_attribute_groups(hybrid)
        if not groups:
            return

        # 1. 收集所有可用属性用于搜索
        all_available_attrs = []
        for group, attrs in groups.items():
            for attr in attrs:
                all_available_attrs.append((attr, group))

        # 2. 构建显示列表
        active_attrs = []
        for group, attrs in groups.items():
            for attr in attrs:
                if hybrid.attributes.get(attr, 0) != 0:
                    active_attrs.append(attr)

        display_list = []
        for attr in active_attrs:
            attr_name, attr_desc = get_attr_display(attr)
            display_list.append({
                "key": attr,
                "name": attr_name or attr,
                "desc": attr_desc,
                "is_basic": False
            })

        # 3. 渲染垂直列表（集成添加按钮）
        to_remove = self._render_attribute_grid(
            display_list,
            hybrid.attributes,
            show_add_button=True,
            add_button_label="+装备",
            add_popup_id="equip_attr"
        )

        # 如果没有属性，仍需显示添加按钮
        if not display_list:
            if imgui.button("+装备##equip_attr_btn", styles.span(styles.SPAN_BADGE), 0):
                imgui.open_popup("equip_attr")
            tooltip("添加装备属性")

        # 绘制添加属性弹窗
        self._draw_add_attribute_popup("equip_attr", hybrid.attributes, all_available_attrs)

        # 4. 执行移除
        for attr in to_remove:
            del hybrid.attributes[attr]

        # 5. 清理不再允许的属性
        self._prune_hybrid_attributes(hybrid, groups)

    def _draw_add_attribute_popup(self: "GUIProtocol", popup_id: str, target_dict: dict, available_attrs: list):
        """绘制添加属性弹窗（不含按钮）"""
        imgui.set_next_window_size(300, 400)
        if imgui.begin_popup(popup_id):
            # 搜索框
            imgui.dummy(0, 2)
            imgui.set_next_item_width(-1)

            if popup_id not in ui_state.attr_search_buffers:
                ui_state.attr_search_buffers[popup_id] = ""

            changed, search_text = imgui.input_text(f"##search_{popup_id}", ui_state.attr_search_buffers[popup_id], 64)
            if changed:
                ui_state.attr_search_buffers[popup_id] = search_text

            search_lower = search_text.lower()
            imgui.separator()

            # 过滤列表
            filtered = []
            for attr, group in available_attrs:
                if target_dict.get(attr, 0) != 0: continue
                name, desc = get_attr_display(attr)
                match_text = f"{attr} {name}".lower()
                if not search_lower or search_lower in match_text:
                    filtered.append((group, attr, name, desc))

            if not filtered:
                text_secondary("无匹配属性")

            last_group = None
            last_group_open = False
            flat_mode = bool(search_lower)
            group_visible = False

            for group, attr, name, desc in filtered:
                if group != last_group:
                    if not flat_mode:
                        if last_group and last_group_open:
                            imgui.tree_pop()
                        last_group_open = imgui.tree_node(f"{group}##grp_{group}_{popup_id}")
                        group_visible = last_group_open
                    else:
                        imgui.dummy(0, 2)
                        text_secondary(f"--- {group} ---")
                        group_visible = True
                        last_group_open = False
                    last_group = group

                if group_visible:
                    if imgui.selectable(f"{name or attr}##sel_{attr}")[0]:
                        target_dict[attr] = 1  # 激活
                        imgui.close_current_popup()
                        ui_state.attr_search_buffers[popup_id] = ""
                    if desc:
                        tooltip(desc)

            if not flat_mode and last_group and last_group_open:
                imgui.tree_pop()

            imgui.end_popup()

    def _prune_hybrid_attributes(self: "GUIProtocol", hybrid: HybridItemV2, groups: dict):
        """移除与当前类型不匹配的属性"""
        allowed = set()
        for attrs in groups.values():
            allowed.update(attrs)
        to_delete = [k for k in hybrid.attributes.keys() if k not in allowed]
        for k in to_delete:
            del hybrid.attributes[k]

    def _draw_hybrid_consumable_attributes_editor(self: "GUIProtocol", hybrid: HybridItemV2):
        """绘制消耗品属性编辑器 - 垂直列表布局"""
        if not charge_has_charges(hybrid.charges):
            return

        # 只在 EffectTrigger 模式下编辑消耗品属性
        if not isinstance(hybrid.trigger, EffectTrigger):
            return

        consumable_attrs = hybrid.trigger.consumable_attributes

        # === 1. 构建统一的显示列表 ===
        display_list = []

        # 1.1 基础属性 (Mandatory)
        display_list.append({
            "key": CONSUMABLE_DURATION_ATTRIBUTE,
            "name": "效果持续 (轮)",
            "is_basic": True
        })
        display_list.append({
            "key": "Poisoning_Chance",
            "name": "中毒几率 (%)",
            "is_basic": True
        })

        # 1.2 条件基础属性 (Pseudo-attributes)
        if consumable_attrs.get("Poisoning_Chance", 0) > 0:
            display_list.append({
                "key": "Poison_Duration",
                "name": "中毒持续 (轮)",
                "is_basic": True,
                "custom_bind": "poison_duration"
            })

        # 1.3 即时效果 (Instant Effects)
        for grp, attrs in CONSUMABLE_INSTANT_ATTRS.items():
            for attr in attrs:
                if attr == "Poisoning_Chance": continue
                if consumable_attrs.get(attr, 0) != 0:
                    d_name, d_desc = get_attr_display(attr)
                    display_list.append({
                        "key": attr,
                        "name": d_name or attr,
                        "desc": d_desc,
                        "is_basic": False
                    })

        # 1.4 持续效果 (Persistent Effects)
        dur_keys = get_consumable_duration_attrs()
        dur_groups = get_attribute_groups(dur_keys, DEFAULT_GROUP_ORDER)
        for grp, attrs in dur_groups.items():
            for attr in attrs:
                if attr == CONSUMABLE_DURATION_ATTRIBUTE: continue
                if consumable_attrs.get(attr, 0) != 0:
                    d_name, d_desc = get_attr_display(attr)
                    display_list.append({
                        "key": attr,
                        "name": d_name or attr,
                        "desc": d_desc,
                        "is_basic": False
                    })

        # === 2. 构建可添加属性列表 ===
        all_instants = []
        for grp, attrs in CONSUMABLE_INSTANT_ATTRS.items():
            for a in attrs:
                if a not in {"Poisoning_Chance"}: all_instants.append((a, grp))

        all_durations = []
        for grp, attrs in dur_groups.items():
            for a in attrs:
                if a != CONSUMABLE_DURATION_ATTRIBUTE: all_durations.append((a, grp))

        merged_source = []
        for a, g in all_instants:
            suffix = g.split("（")[-1].rstrip("）") if "（" in g else g
            merged_source.append((a, f"即时效果 - {suffix}"))
        for a, g in all_durations:
            merged_source.append((a, f"持续效果 - {g}"))

        # === 3. 渲染垂直列表 ===
        to_remove = self._render_attribute_grid(
            display_list,
            consumable_attrs,
            hybrid,
            show_add_button=True,
            add_button_label="+效果",
            add_popup_id="add_consum_effect"
        )

        # 绘制添加属性弹窗
        self._draw_add_attribute_popup("add_consum_effect", consumable_attrs, merged_source)

        # === 4. 执行移除 ===
        for attr in to_remove:
            del consumable_attrs[attr]

    def _get_hybrid_attribute_groups(self: "GUIProtocol", hybrid: HybridItemV2) -> dict:
        """根据槽位获取可编辑属性分组"""
        # 获取该槽位的属性列表（被动携带物品需要额外抗性属性）
        has_passive = is_charm_mode(hybrid.equipment)
        attrs = get_hybrid_attrs_for_slot(hybrid.slot, has_passive)
        result = get_attribute_groups(attrs, DEFAULT_GROUP_ORDER)

        # 清理不再允许的属性
        if result:
            allowed = {a for attr_list in result.values() for a in attr_list}
            for k in [k for k in hybrid.attributes if k not in allowed]:
                del hybrid.attributes[k]

        return result
