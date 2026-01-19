import ast
import json
import os
import glob
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import paths

def parse_gml_table(file_path):
    """
    解析GML表格文件，提取数据并结构化
    """
    # 读取文件并提取第三行数据
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 使用strip()确保稳定处理，然后切片提取内容
    third_line = lines[2].strip()[7:-1]  # 去掉'return '和结尾的';'

    # 解析为Python列表
    data_list = ast.literal_eval(third_line)

    # 解析表头获取所有字段
    header = data_list[0].split(';')

    # 初始化数据结构
    result = {}
    current_primary = "default"  # 默认一级分区
    source_order = 0  # 源表项目顺序计数器

    # 确保默认分区存在
    result[current_primary] = {}

    # 处理每一行数据
    for row in data_list[1:]:  # 跳过表头
        if not row:
            continue

        parts = row.split(';')

        # 检查需要忽略的行
        # 1. 二级分区标识行
        # 2. 以"// "开头的行
        # 3. 以"[ "开头且以" ]"结尾的行
        if ((len(parts) > 2 and parts[0] == '' and parts[2].startswith('// ')) or
            (len(parts) > 0 and parts[0].startswith('// ')) or
            (len(parts) > 0 and parts[0].startswith('[ ') and parts[0].endswith(' ]'))):
            continue

        # 检查一级分区开始 - 修正后的判定
        # 条件1: 第二个字段不为空
        # 条件2: 第二个字段不以"// "开头
        # 条件3: 第二个字段不以"_end"结尾
        # 条件4: 从parts[2]到parts[-2]必须全部和parts[1]相等
        if (len(parts) > 1 and
            parts[1] != '' and
            not parts[1].startswith('// ') and
            not parts[1].endswith('_end') and
            (len(parts) <= 2 or all(part == parts[1] for part in parts[2:-1]))):

            current_primary = parts[1]
            if current_primary not in result:
                result[current_primary] = {}
            continue

        # 检查一级分区结束 - 修正后的判定
        if (len(parts) > 1 and
            parts[1].endswith('_end')):
            # 检查对应的开始分区是否存在
            primary_name = parts[1].replace('_end', '')
            if primary_name in result:
                current_primary = "default"  # 回到默认分区
                if current_primary not in result:
                    result[current_primary] = {}
            continue

        # 处理内容行 - 格式特点: 第一个字段不为空且不是"id"，且在当前分区内
        if (len(parts) >= len(header)
            # and
            # parts[0] and
            # parts[0] != '' and
            # parts[0] != 'id'
            ):

            item_id = parts[0]
            source_order += 1

            # 确保当前分区存在
            if current_primary not in result:
                result[current_primary] = {}

            # 创建包含所有字段和源表项目顺序的完整字典
            item_dict = {"_source_order": source_order}
            for i, field in enumerate(header):
                if i < len(parts):
                    item_dict[field] = parts[i]  # 保持原始字段名不变
                else:
                    item_dict[field] = ""  # 如果字段不足，填充空字符串

            # 存储结果
            result[current_primary][item_id] = item_dict

    return result

def main():
    # Use paths from config
    gml_dir = paths.SRC_GML
    output_dir = paths.DATA_TABLES

    ensure_dir(output_dir)

    # Get all gml_GlobalScript_table_*.gml files
    pattern = os.path.join(gml_dir, 'gml_GlobalScript_table_*.gml')
    files_to_process = glob.glob(pattern)

    if not files_to_process:
        print("未找到任何gml_GlobalScript_table_*.gml文件")
        return

    print(f"找到 {len(files_to_process)} 个文件待处理")

    for input_file in files_to_process:
        try:
            # 提取文件名并去掉前缀
            base_name = os.path.basename(input_file)

            # 去掉前缀并创建输出文件名
            if base_name.startswith('gml_GlobalScript_table_'):
                # 去掉前缀并保留剩余部分，同时去掉.gml后缀
                output_name = base_name.replace('gml_GlobalScript_table_', '').replace('.gml', '') + '.json'
            else:
                # 如果不是预期格式，直接使用原文件名并去掉.gml后缀
                output_name = os.path.splitext(base_name)[0] + '.json'

            # 完整输出路径
            output_path = os.path.join(output_dir, output_name)

            # 解析文件
            parsed_data = parse_gml_table(input_file)

            # 将结果写入JSON文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)

            print(f"解析完成！结果已保存到: {output_path}")

            # 显示一些统计信息
            total_items = 0
            for section, items in parsed_data.items():
                print(f"  {section}: {len(items)} 项")
                total_items += len(items)
            print(f"  总计: {total_items} 项\n")

        except Exception as e:
            print(f"处理文件 {input_file} 时出错：{e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
