"""
Enemy drop data extracted from game_code.
Contains:
1. ENEMY_META: {object_name: {id, tier, name_zh, name_en, faction, type}}
2. ENEMY_DROPS: {object_name: [(tier_min, tier_max, slot), ...]}
3. DROP_TABLE: {(tier, slot): [object_names]} - aggregated by tier+slot
"""
import os
import re
import json
import subprocess
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Paths (relative to project root, script is in codegen/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

GAME_CODE_PATH = os.path.join(_PROJECT_ROOT, "game_code")
OBJECT_TREE_PATH = os.path.join(_PROJECT_ROOT, "reference", "data", "object_tree.json")
MOBS_STATS_PATH = os.path.join(_PROJECT_ROOT, "game_data", "mobs_stats.json")
MOBS_PATH = os.path.join(_PROJECT_ROOT, "game_data", "mobs.json")

def build_hierarchy():
    """Build object inheritance hierarchy from object_tree.json"""
    with open(OBJECT_TREE_PATH, 'r', encoding='utf-8') as f:
        object_tree = json.load(f)
    
    def get_all_children(parent: str, tree: dict) -> set:
        children = set()
        if parent in tree:
            for child in tree[parent]:
                children.add(child)
                children.update(get_all_children(child, tree))
        return children
    
    enemy_hierarchy = get_all_children("o_enemy", object_tree)
    enemy_hierarchy.add("o_enemy")
    
    npc_hierarchy = get_all_children("o_NPC", object_tree)
    npc_hierarchy.add("o_NPC")
    
    return enemy_hierarchy - npc_hierarchy

def build_enemy_meta() -> Dict[str, Dict[str, Any]]:
    """Build enemy metadata from mobs_stats.json and mobs.json"""
    with open(MOBS_STATS_PATH, 'r', encoding='utf-8') as f:
        mobs_stats = json.load(f)
    
    with open(MOBS_PATH, 'r', encoding='utf-8') as f:
        mobs = json.load(f)
    
    enemy_meta = {}
    
    # mobs_stats["default"] contains all mob stats keyed by name
    for name, stats in mobs_stats.get("default", {}).items():
        if not name:  # Skip empty keys
            continue
        
        obj_id = stats.get("ID", "")
        if not obj_id:
            continue
        
        tier_str = stats.get("Tier", "0")
        try:
            tier = int(tier_str) if tier_str else 0
        except ValueError:
            tier = 0
        
        # Get localized names from mobs.json
        name_zh = ""
        name_en = ""
        if "enemy_name" in mobs and name in mobs["enemy_name"]:
            localized = mobs["enemy_name"][name]
            name_zh = localized.get("中文", "")
            name_en = localized.get("English", "")
        
        enemy_meta[obj_id] = {
            "id": name,  # The lookup key in mobs_stats
            "tier": tier,
            "name_zh": name_zh,
            "name_en": name_en,
            "faction": stats.get("faction", ""),
            "type": stats.get("type", "")
        }
    
    return enemy_meta

def extract_params(line: str) -> List[List[str]]:
    """Extract scr_find_weapon_params call parameters from a line"""
    results = []
    
    i = 0
    while i < len(line):
        idx = line.find('scr_find_weapon_params(', i)
        if idx == -1:
            break
        
        start = idx + len('scr_find_weapon_params(')
        paren_depth = 1
        end = start
        while end < len(line) and paren_depth > 0:
            if line[end] == '(':
                paren_depth += 1
            elif line[end] == ')':
                paren_depth -= 1
            end += 1
        
        if paren_depth == 0:
            content = line[start:end-1]
            
            params = []
            paren_depth = 0
            current = ""
            for char in content:
                if char == '(':
                    paren_depth += 1
                    current += char
                elif char == ')':
                    paren_depth -= 1
                    current += char
                elif char == ',' and paren_depth == 0:
                    params.append(current.strip())
                    current = ""
                else:
                    current += char
            if current.strip():
                params.append(current.strip())
            
            results.append(params)
        
        i = end
    
    return results

def parse_tier(tier_str: str) -> List[int]:
    """Parse tier value, return list of possible tier values"""
    tier_str = tier_str.strip()
    
    # Try to parse as integer
    try:
        return [int(tier_str)]
    except ValueError:
        pass
    
    # Variable-based tiers (e.g., max(_tier - 2, 1))
    # These are dynamic, we'll mark them as variable
    return []

def parse_slot(slot_str: str) -> List[str]:
    """Parse slot type, handling choose() and string literals"""
    slot_str = slot_str.strip()
    
    # Handle choose() function
    choose_match = re.match(r'choose\s*\((.*)\)', slot_str)
    if choose_match:
        inner = choose_match.group(1)
        # Parse comma-separated quoted values
        slots = []
        for item in re.findall(r'"([^"]+)"', inner):
            slots.append(item)
        return slots
    
    # Handle simple string literal
    str_match = re.match(r'"([^"]+)"', slot_str)
    if str_match:
        return [str_match.group(1)]
    
    return []

def analyze_drops():
    """Analyze all scr_find_weapon_params calls and build drop data"""
    target_objects = build_hierarchy()
    
    # Use os.walk instead of ripgrep to avoid subprocess issues
    files = []
    for root, dirs, filenames in os.walk(GAME_CODE_PATH):
        for filename in filenames:
            if filename.startswith("gml_Object_") and filename.endswith(".gml"):
                files.append(os.path.join(root, filename))
    
    # {object_name: [(tier_min, tier_max, slot), ...]}
    enemy_drops: Dict[str, List[Tuple[int, int, str]]] = defaultdict(list)
    
    for file_path in files:
        filename = os.path.basename(file_path)
        
        if not filename.startswith("gml_Object_"):
            continue
        
        match = re.match(r'gml_Object_(o_\w+)_(\w+)_(\d+)\.gml', filename)
        if not match:
            continue
        
        obj_name = match.group(1)
        
        if obj_name not in target_objects:
            continue
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for line in lines:
            if "scr_find_weapon_params" in line:
                params_list = extract_params(line)
                for params in params_list:
                    if len(params) >= 3:
                        tier_min_values = parse_tier(params[0])
                        tier_max_values = parse_tier(params[1])
                        slots = parse_slot(params[2])
                        
                        # Expand all combinations
                        for slot in slots:
                            if tier_min_values and tier_max_values:
                                tier_min = tier_min_values[0]
                                tier_max = tier_max_values[0]
                                enemy_drops[obj_name].append((tier_min, tier_max, slot))
    
    return dict(enemy_drops)

def build_drop_table(enemy_drops: Dict[str, List[Tuple[int, int, str]]]) -> Dict[Tuple[int, str], List[str]]:
    """Build aggregated drop table: {(tier, slot): [object_names]}"""
    drop_table: Dict[Tuple[int, str], List[str]] = defaultdict(list)
    
    for obj_name, drops in enemy_drops.items():
        for tier_min, tier_max, slot in drops:
            # For each tier in range, add this object
            for tier in range(tier_min, tier_max + 1):
                key = (tier, slot)
                if obj_name not in drop_table[key]:
                    drop_table[key].append(obj_name)
    
    return dict(drop_table)

# ============================================================================
# Generate data
# ============================================================================

if __name__ == "__main__":
    import pprint
    
    print("Building enemy metadata...")
    ENEMY_META = build_enemy_meta()
    print(f"  Found {len(ENEMY_META)} enemies with metadata")
    
    print("Analyzing enemy drops...")
    ENEMY_DROPS = analyze_drops()
    print(f"  Found {len(ENEMY_DROPS)} enemies with drop calls")
    
    print("Building drop table...")
    DROP_TABLE = build_drop_table(ENEMY_DROPS)
    print(f"  Generated {len(DROP_TABLE)} tier+slot combinations")
    
    # Generate output Python file (in project root)
    output_path = os.path.join(_PROJECT_ROOT, "enemy_drop_constants.py")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('"""\n')
        f.write('Auto-generated enemy drop data constants.\n')
        f.write('Generated by enemy_drop_data.py\n')
        f.write('"""\n')
        f.write('from typing import Dict, List, Tuple, Any\n\n')
        
        # Write ENEMY_META
        f.write('# Enemy metadata: {object_name: {id, tier, name_zh, name_en, faction, type}}\n')
        f.write('ENEMY_META: Dict[str, Dict[str, Any]] = {\n')
        for obj_name, meta in sorted(ENEMY_META.items()):
            f.write(f'    {repr(obj_name)}: {repr(meta)},\n')
        f.write('}\n\n')
        
        # Write ENEMY_DROPS
        f.write('# Enemy drops: {object_name: [(tier_min, tier_max, slot), ...]}\n')
        f.write('ENEMY_DROPS: Dict[str, List[Tuple[int, int, str]]] = {\n')
        for obj_name, drops in sorted(ENEMY_DROPS.items()):
            f.write(f'    {repr(obj_name)}: {repr(drops)},\n')
        f.write('}\n\n')
        
        # Write DROP_TABLE
        f.write('# Drop table: {(tier, slot): [object_names]}\n')
        f.write('DROP_TABLE: Dict[Tuple[int, str], List[str]] = {\n')
        for key, objs in sorted(DROP_TABLE.items()):
            f.write(f'    {repr(key)}: {repr(objs)},\n')
        f.write('}\n')
    
    print(f"\nGenerated: {output_path}")
    
    # Also print sample output
    print("\n" + "="*80)
    print("SAMPLE: ENEMY_META (first 5)")
    print("="*80)
    for i, (obj, meta) in enumerate(list(sorted(ENEMY_META.items()))[:5]):
        print(f"  {obj}: {meta}")
    
    print("\n" + "="*80)
    print("SAMPLE: ENEMY_DROPS (first 10)")
    print("="*80)
    for i, (obj, drops) in enumerate(list(sorted(ENEMY_DROPS.items()))[:10]):
        print(f"  {obj}: {drops}")
    
    print("\n" + "="*80)
    print("SAMPLE: DROP_TABLE (first 10)")
    print("="*80)
    for i, ((tier, slot), objs) in enumerate(sorted(DROP_TABLE.items())[:10]):
        print(f"  Tier {tier}, {slot}: {len(objs)} enemies")
        for obj in objs[:3]:
            meta = ENEMY_META.get(obj, {})
            name_zh = meta.get("name_zh", "?")
            print(f"    - {obj} ({name_zh})")
        if len(objs) > 3:
            print(f"    ... and {len(objs) - 3} more")

