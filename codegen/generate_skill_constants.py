# -*- coding: utf-8 -*-
"""
技能常量生成脚本

从游戏数据中提取所有角色技能信息并生成常量文件。

数据源:
- reference/data/object_tree.json: 对象继承关系
- reference/data/object_index_map.json: 对象索引到名称的映射
- game_data/skills_stats.json: 技能元数据 (Branch, Class, Target 等)
- game_data/skills.json: 技能多语言名称和描述
- game_data/text.json: Branch 名称翻译
- game_code/gml_Object_o_skill_category_*_Create_0.gml: 技能类别的 Create 事件

分支补充逻辑:
- 以 skills_stats.json 中的 Branch 为主
- 对于 Branch 为空或 "none" 的技能，使用 skill_category 的分支信息补充
- necromancy/sanguimancy 等敌人技能保留原有具体分支名，添加 mob_category 字段
"""

import json
import os
import re
from pathlib import Path


def load_json(path: str) -> dict:
    """加载 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_skill_ico_children(inheritance: dict) -> list[str]:
    """找到所有 o_skill_ico 的子类（直接或间接）
    
    数据格式: {父对象: [子对象列表]}
    """
    direct_children = inheritance.get("o_skill_ico", [])
    print(f"o_skill_ico 直接子类数: {len(direct_children)}")
    return direct_children


def ico_to_skill_object(ico_name: str) -> str:
    """将 ico 对象名转换为技能对象名
    
    例如: o_skill_fire_barrage_ico -> o_skill_fire_barrage
    """
    if ico_name.endswith("_ico"):
        return ico_name[:-4]
    return ico_name


def find_skill_written_names(skill_objects: list[str], gml_dir: str = "code") -> dict[str, str]:
    """从 GML Create 事件中提取技能书面名称
    
    例如: o_skill_fire_barrage 的 Create_0 中有 skill = "Fire_Barrage";
    
    返回: {skill_object: written_name}
    """
    skill_names = {}
    pattern = re.compile(r'skill\s*=\s*["\']([^"\']+)["\']')
    
    found_count = 0
    not_found_count = 0
    
    for skill_obj in skill_objects:
        gml_filename = f"gml_Object_{skill_obj}_Create_0.gml"
        gml_path = os.path.join(gml_dir, gml_filename)
        
        if os.path.exists(gml_path):
            try:
                with open(gml_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    match = pattern.search(content)
                    if match:
                        skill_names[skill_obj] = match.group(1)
                        found_count += 1
                    else:
                        not_found_count += 1
            except Exception as e:
                print(f"Error reading {gml_path}: {e}")
        else:
            not_found_count += 1
    
    print(f"从 GML 文件提取到: {found_count} 个, 未找到: {not_found_count} 个")
    return skill_names


# ============================================================================
# Category 分支提取 (直接从源数据)
# ============================================================================

def get_skill_category_children(object_tree: dict) -> list[str]:
    """从 object_tree.json 获取 o_skill_category 的所有子类"""
    def get_all_children(parent: str, tree: dict) -> set:
        children = set()
        if parent in tree:
            for child in tree[parent]:
                children.add(child)
                children.update(get_all_children(child, tree))
        return children
    
    return sorted(get_all_children("o_skill_category", object_tree))


def parse_skill_category_gml(gml_path: str) -> dict | None:
    """解析技能类别的 Create_0 GML 文件
    
    提取 skill = [...] 数组中的技能索引
    跳过占位符类别 (skill = ["1"])
    
    返回: {"skill_indices": list[int]} 或 None
    """
    try:
        with open(gml_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    
    # 提取 skill = [...] 
    skill_match = re.search(r'skill\s*=\s*\[([^\]]+)\]', content)
    if not skill_match:
        return None
    
    skill_content = skill_match.group(1).strip()
    
    # 检测是否为占位符 (包含字符串如 "1")
    if '"' in skill_content or "'" in skill_content:
        return None
    
    # 解析数字数组
    try:
        skill_indices = [int(x.strip()) for x in skill_content.split(",") if x.strip()]
    except ValueError:
        return None
    
    return {"skill_indices": skill_indices}


def build_category_branch_map(
    object_tree: dict, 
    object_index_map: dict, 
    gml_dir: Path
) -> dict[str, dict]:
    """从源数据构建技能对象到分支的映射
    
    直接读取:
    - object_tree.json: 找 o_skill_category 的子类
    - object_index_map.json: 索引到对象名映射
    - game_code/gml_Object_o_skill_category_*.gml: 解析技能数组
    
    返回: {skill_object: {"category_branch": str, "is_mob_category": bool, "category_name": str}}
    """
    # 构建索引到对象名的映射
    index_to_object = {int(k): v for k, v in object_index_map.items()}
    
    # 获取所有 skill_category 子类
    category_objects = get_skill_category_children(object_tree)
    
    # 分支名称映射：从 category 名称映射到 skills_stats.json 的 Branch 名称
    CATEGORY_TO_STATS_BRANCH = {
        "greataxe": "2haxe",
        "greatmauls": "2hmace", 
        "greatsword": "2hsword",
        "basic_armor": "armor",
        "athletics": "athletic",
        "dual_wielding": "dual",
        "mastery_of_magic": "magic_mastery",
        "bows": "ranged",
        "shields": "shield",
        "polearms": "spear",
        "staves": "staff",
        "arcanistics": "arcanistics",
        "axe": "axe",
        "combat": "combat",
        "dagger": "dagger",
        "electromancy": "electromancy",
        "geomancy": "geomancy",
        "mace": "mace",
        "pyromancy": "pyromancy",
        "sword": "sword",
        "survival": "survival",
    }
    
    skill_to_branch = {}
    
    for category in category_objects:
        gml_filename = f"gml_Object_{category}_Create_0.gml"
        gml_path = gml_dir / gml_filename
        
        result = parse_skill_category_gml(str(gml_path))
        if result is None:
            continue
        
        # 提取 category 简名: o_skill_category_xxx -> xxx
        category_short = category.replace("o_skill_category_", "")
        
        # 判断是否为敌人技能类别
        is_mob_category = category_short.startswith("mob_skill")
        
        # 获取映射后的分支名
        branch_name = CATEGORY_TO_STATS_BRANCH.get(category_short, category_short)
        
        # 将索引映射到对象名
        for idx in result["skill_indices"]:
            if idx in index_to_object:
                obj_name = index_to_object[idx]
                skill_obj = ico_to_skill_object(obj_name)
                
                # 只处理技能对象 (跳过被动技能)
                if skill_obj.startswith("o_skill_") and "pass_skill" not in obj_name:
                    skill_to_branch[skill_obj] = {
                        "category_branch": branch_name,
                        "is_mob_category": is_mob_category,
                        "category_name": category,
                    }
    
    return skill_to_branch


def enrich_with_stats(skills: dict, skills_stats: dict, category_branch_map: dict) -> dict:
    """用 skills_stats.json 的元数据丰富技能信息
    
    - 以 skills_stats.json 的 Branch 为主
    - 对于 Branch 为空或 "none" 的技能，使用 category 的分支信息补充
    - necromancy/sanguimancy 敌人技能保留原有分支名，添加 mob_category 字段
    
    返回: {skill_object: {written_name, branch, class, target, mob_category, ...}}
    """
    default_stats = skills_stats.get("default", {})
    
    enriched = {}
    branch_supplemented_count = 0
    
    for skill_obj, written_name in skills.items():
        stats = default_stats.get(written_name, {})
        stats_branch = stats.get("Branch", "")
        
        # 获取 category 分支信息
        category_info = category_branch_map.get(skill_obj, {})
        category_branch = category_info.get("category_branch", "")
        is_mob_category = category_info.get("is_mob_category", False)
        
        # 决定最终使用的分支
        if stats_branch and stats_branch.lower() != "none":
            # 以 skills_stats.json 的 Branch 为主
            final_branch = stats_branch
        elif category_branch:
            # 使用 category 分支补充
            final_branch = category_branch
            branch_supplemented_count += 1
        else:
            final_branch = "unknown"
        
        enriched[skill_obj] = {
            "written_name": written_name,
            "branch": final_branch,
            "class": stats.get("Class", "unknown"),
            "target": stats.get("Target", "unknown"),
            "range": stats.get("Range", "0"),
            "mp_cost": stats.get("MP", "0"),
            "cooldown": stats.get("KD", "0"),
            "tags": stats.get("Tags", ""),
        }
        
        # 对于敌人技能类别，添加 mob_category 字段
        if is_mob_category:
            enriched[skill_obj]["mob_category"] = category_info.get("category_name", "")
    
    print(f"使用 category 分支补充了 {branch_supplemented_count} 个技能")
    return enriched


def add_localized_names(skills: dict, skills_json: dict) -> dict:
    """添加多语言名称
    
    从 skills.json 的 skill_name 部分提取
    """
    skill_names = skills_json.get("skill_name", {})
    
    for skill_obj, info in skills.items():
        written_name = info["written_name"]
        name_data = skill_names.get(written_name, {})
        
        info["name_chinese"] = name_data.get("中文", written_name)
        info["name_english"] = name_data.get("English", written_name)
    
    return skills


def get_branch_translations(text_json: dict) -> dict[str, str]:
    """从 text.json 的 Tier_name 提取 Branch 翻译
    
    返回: {branch_lower: chinese_name}
    """
    tier_names = text_json.get("Tier_name", {})
    
    translations = {}
    for branch_key, data in tier_names.items():
        chinese = data.get("中文", branch_key)
        translations[branch_key.lower()] = chinese
    
    # 添加额外的分支映射
    # skills_stats.json 使用小写单数形式 (如 sword, axe)
    # 而 text.json 使用复数形式 (如 Swords, Axes)
    # 需要手动添加映射
    EXTRA_TRANSLATIONS = {
        # 武器分支 (单数 -> 对应中文)
        "sword": "单手刀剑",      # text.json: Swords -> 单手刀剑
        "axe": "单手斧",          # text.json: Axes -> 单手斧
        "mace": "单手锤棒",       # text.json: Maces -> 单手锤棒
        "dagger": "匕首",         # text.json: Daggers -> 匕首
        # 别名分支
        "2haxe": "双手斧",        # text.json: Greataxes -> 双手斧
        "2hmace": "双手锤棒",     # text.json: Greatmauls -> 双手锤棒
        "2hsword": "双手刀剑",    # text.json: Greatswords -> 双手刀剑
        "athletic": "肢体活动",   # text.json: Athletics -> 肢体活动
        "dual": "兵器双持",       # text.json: Dual Wielding -> 兵器双持
        "magic_mastery": "驭法",  # text.json: Magic_Mastery -> 驭法
        "ranged": "远程兵器",     # text.json: Bows -> 远程兵器
        "shield": "盾牌",         # text.json: Shields -> 盾牌
        "spear": "长杆刃器",      # text.json: Polearms -> 长杆刃器
        "staff": "长杖",          # text.json: Staves -> 长杖
        # 敌人技能分支
        "mob_skill": "敌人技能",
        "mob_skill_2": "敌人技能2",
        "necromancy": "死灵术",
        "sanguimancy": "血术",
        # 基础技能
        "basic_skills": "基础技能",
        # 特殊分支
        "none": "无分支",
        "unknown": "未知",
    }
    translations.update(EXTRA_TRANSLATIONS)
    
    return translations


def generate_skill_constants(skills: dict, branch_translations: dict) -> str:
    """生成 Python 常量代码"""
    
    # 按 branch 分组技能
    by_branch = {}
    for skill_obj, info in sorted(skills.items()):
        branch = info["branch"]
        if branch not in by_branch:
            by_branch[branch] = []
        by_branch[branch].append((skill_obj, info))
    
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "自动生成的技能常量",
        "",
        "由 generate_skill_constants.py 从游戏数据生成",
        '"""',
        "",
        "# 技能分支翻译 (与 SKILL_OBJECTS 中的 branch 名称对齐)",
        "SKILL_BRANCH_TRANSLATIONS = {",
    ]
    
    # 只输出实际使用的分支翻译
    used_branches = set(info["branch"].lower() for info in skills.values())
    for branch in sorted(used_branches):
        chinese = branch_translations.get(branch, branch)
        lines.append(f'    "{branch}": "{chinese}",')
    lines.append("}")
    lines.append("")
    
    lines.append("# 技能对象信息")
    lines.append("# 格式: {skill_object: {branch, name_chinese, name_english, class, target, ...}}")
    lines.append("SKILL_OBJECTS = {")
    
    for branch, skill_list in sorted(by_branch.items()):
        branch_chinese = branch_translations.get(branch.lower(), branch)
        lines.append(f"    # ====== {branch_chinese} ({branch}) ======")
        
        for skill_obj, info in sorted(skill_list, key=lambda x: x[1]["name_chinese"]):
            lines.append(f'    "{skill_obj}": {{')
            lines.append(f'        "branch": "{info["branch"]}",')
            lines.append(f'        "name_chinese": "{info["name_chinese"]}",')
            lines.append(f'        "name_english": "{info["name_english"]}",')
            lines.append(f'        "class": "{info["class"]}",')
            lines.append(f'        "target": "{info["target"]}",')
            # 输出 mob_category (如果存在)
            if info.get("mob_category"):
                lines.append(f'        "mob_category": "{info["mob_category"]}",')
            lines.append(f'    }},')
        lines.append("")
    
    lines.append("}")
    lines.append("")
    
    # 简化版：仅技能对象名到中文名映射
    lines.append("# 简化版：技能对象名 -> 中文名")
    lines.append("SKILL_OBJECT_NAMES = {")
    for skill_obj, info in sorted(skills.items(), key=lambda x: x[1]["branch"]):
        lines.append(f'    "{skill_obj}": "{info["name_chinese"]}",')
    lines.append("}")
    lines.append("")
    
    # 按分支分组的简化版
    lines.append("# 按分支分组的技能列表")
    lines.append("SKILL_BY_BRANCH = {")
    for branch, skill_list in sorted(by_branch.items()):
        branch_chinese = branch_translations.get(branch.lower(), branch)
        skill_names = [f'"{s[0]}"' for s in sorted(skill_list, key=lambda x: x[1]["name_chinese"])]
        lines.append(f'    "{branch}": [  # {branch_chinese}')
        for name in skill_names:
            lines.append(f'        {name},')
        lines.append('    ],')
    lines.append("}")
    
    return "\n".join(lines)


def main():
    base_dir = Path(__file__).parent.parent  # codegen -> project root
    
    print("Loading data files...")
    
    # 加载数据
    inheritance = load_json(base_dir / "reference" / "data" / "object_tree.json")
    object_index_map = load_json(base_dir / "reference" / "data" / "object_index_map.json")
    skills_stats = load_json(base_dir / "game_data" / "skills_stats.json")
    skills_json = load_json(base_dir / "game_data" / "skills.json")
    text_json = load_json(base_dir / "game_data" / "text.json")
    
    print(f"Loaded {len(inheritance)} objects from inheritance")
    print(f"Loaded {len(object_index_map)} object indices")
    
    # 1. 构建 category 分支映射 (直接从源数据)
    gml_dir = base_dir / "game_code"
    category_branch_map = build_category_branch_map(inheritance, object_index_map, gml_dir)
    print(f"Built category branch map with {len(category_branch_map)} entries")
    
    # 2. 找到所有 o_skill_ico 的子类
    ico_children = find_skill_ico_children(inheritance)
    print(f"Found {len(ico_children)} o_skill_ico children")
    
    # 3. 转换为技能对象名
    skill_objects = [ico_to_skill_object(ico) for ico in ico_children]
    print(f"Converted to {len(skill_objects)} skill objects")
    
    # 4. 从 GML 文件提取书面名称 (从 game_code 目录读取)
    skill_names = find_skill_written_names(skill_objects, str(base_dir / "game_code"))
    print(f"Found written names for {len(skill_names)} skills")
    
    # 5. 用元数据丰富 (带 category 分支补充)
    enriched = enrich_with_stats(skill_names, skills_stats, category_branch_map)
    print(f"Enriched {len(enriched)} skills with stats")
    
    # 6. 添加多语言名称
    enriched = add_localized_names(enriched, skills_json)
    
    # 7. 获取分支翻译
    branch_translations = get_branch_translations(text_json)
    print(f"Found {len(branch_translations)} branch translations")
    
    # 8. 生成常量文件
    output = generate_skill_constants(enriched, branch_translations)
    
    output_path = base_dir / "skill_constants.py"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)
    
    print(f"\nGenerated {output_path}")
    print(f"Total skills: {len(enriched)}")
    
    # 显示统计
    by_branch = {}
    for info in enriched.values():
        branch = info["branch"]
        by_branch[branch] = by_branch.get(branch, 0) + 1
    
    print("\nSkills by branch:")
    for branch, count in sorted(by_branch.items(), key=lambda x: -x[1]):
        chinese = branch_translations.get(branch.lower(), "")
        print(f"  {branch}: {count} ({chinese})")


if __name__ == "__main__":
    main()
