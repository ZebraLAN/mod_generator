# -*- coding: utf-8 -*-
"""
技能常量生成脚本

从游戏数据中提取所有角色技能信息并生成常量文件。

数据源:
- reference/object_inheritance.json: 对象继承关系
- output_json/skills_stats.json: 技能元数据 (Branch, Class, Target 等)
- output_json/skills.json: 技能多语言名称和描述
- output_json/text.json: Branch 名称翻译
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
    # 直接子类
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
    
    # 尝试匹配 skill = "xxx" 模式
    pattern = re.compile(r'skill\s*=\s*["\']([^"\']+)["\']')
    
    found_count = 0
    not_found_count = 0
    
    for skill_obj in skill_objects:
        # 构建可能的 GML 文件名
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


def enrich_with_stats(skills: dict, skills_stats: dict) -> dict:
    """用 skills_stats.json 的元数据丰富技能信息
    
    返回: {skill_object: {written_name, branch, class, target, ...}}
    """
    default_stats = skills_stats.get("default", {})
    
    enriched = {}
    for skill_obj, written_name in skills.items():
        stats = default_stats.get(written_name, {})
        enriched[skill_obj] = {
            "written_name": written_name,
            "branch": stats.get("Branch", "unknown"),
            "class": stats.get("Class", "unknown"),
            "target": stats.get("Target", "unknown"),
            "range": stats.get("Range", "0"),
            "mp_cost": stats.get("MP", "0"),
            "cooldown": stats.get("KD", "0"),
            "tags": stats.get("Tags", ""),
        }
    
    return enriched


def add_localized_names(skills: dict, skills_json: dict) -> dict:
    """添加多语言名称
    
    从 skills.json 的 skill_name 部分提取
    """
    skill_names = skills_json.get("skill_name", {})
    
    for skill_obj, info in skills.items():
        written_name = info["written_name"]
        name_data = skill_names.get(written_name, {})
        
        # 提取常用语言
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
        # 使用小写 key 方便匹配
        translations[branch_key.lower()] = chinese
    
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
        "# 技能分支翻译",
        "SKILL_BRANCH_TRANSLATIONS = {",
    ]
    
    for branch, chinese in sorted(branch_translations.items()):
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
    base_dir = Path(__file__).parent
    
    print("Loading data files...")
    
    # 加载数据
    inheritance = load_json(base_dir / "reference" / "object_inheritance.json")
    skills_stats = load_json(base_dir / "output_json" / "skills_stats.json")
    skills_json = load_json(base_dir / "output_json" / "skills.json")
    text_json = load_json(base_dir / "output_json" / "text.json")
    
    print(f"Loaded {len(inheritance)} objects from inheritance")
    
    # 1. 找到所有 o_skill_ico 的子类
    ico_children = find_skill_ico_children(inheritance)
    print(f"Found {len(ico_children)} o_skill_ico children")
    
    # 2. 转换为技能对象名
    skill_objects = [ico_to_skill_object(ico) for ico in ico_children]
    print(f"Converted to {len(skill_objects)} skill objects")
    
    # 3. 从 GML 文件提取书面名称 (从 code 目录读取)
    skill_names = find_skill_written_names(skill_objects, str(base_dir / "code"))
    print(f"Found written names for {len(skill_names)} skills")
    
    # 4. 用元数据丰富
    enriched = enrich_with_stats(skill_names, skills_stats)
    print(f"Enriched {len(enriched)} skills with stats")
    
    # 5. 添加多语言名称
    enriched = add_localized_names(enriched, skills_json)
    
    # 6. 获取分支翻译
    branch_translations = get_branch_translations(text_json)
    print(f"Found {len(branch_translations)} branch translations")
    
    # 7. 生成常量文件
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
        print(f"  {branch}: {count}")


if __name__ == "__main__":
    main()
