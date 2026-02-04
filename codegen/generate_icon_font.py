# -*- coding: utf-8 -*-
"""生成 Font Awesome 图标子集

从完整的 FA Solid 字体中提取需要的图标，生成:
1. 精简的 .ttf 文件 (fonts/icons/fa-subset.ttf)
2. Python 常量文件 (ui/icons.py)

使用方法:
    python codegen/generate_icon_font.py

依赖:
    pip install fonttools brotli

图标列表维护:
    修改下方 ICONS 字典，添加需要的图标
    图标名和码点查询: https://fontawesome.com/v6/icons?s=solid
"""

import os
import sys

# ==================== 图标列表 ====================
# 格式: "常量名": ("FA图标名", 0x码点)
# 码点查询: https://fontawesome.com/v6/icons 点击图标查看 Unicode

ICONS: dict[str, tuple[str, int]] = {
    # 状态/反馈
    "CHECK": ("check", 0xf00c),
    "XMARK": ("xmark", 0xf00d),
    "CIRCLE_CHECK": ("circle-check", 0xf058),
    "CIRCLE_XMARK": ("circle-xmark", 0xf057),
    "CIRCLE_INFO": ("circle-info", 0xf05a),
    "CIRCLE_EXCLAMATION": ("circle-exclamation", 0xf06a),
    "TRIANGLE_EXCLAMATION": ("triangle-exclamation", 0xf071),

    # 箭头/方向
    "ARROW_UP": ("arrow-up", 0xf062),
    "ARROW_DOWN": ("arrow-down", 0xf063),
    "ARROW_LEFT": ("arrow-left", 0xf060),
    "ARROW_RIGHT": ("arrow-right", 0xf061),
    "CHEVRON_UP": ("chevron-up", 0xf077),
    "CHEVRON_DOWN": ("chevron-down", 0xf078),
    "CHEVRON_LEFT": ("chevron-left", 0xf053),
    "CHEVRON_RIGHT": ("chevron-right", 0xf054),
    "ANGLES_UP": ("angles-up", 0xf102),
    "ANGLES_DOWN": ("angles-down", 0xf103),
    "CARET_UP": ("caret-up", 0xf0d8),
    "CARET_DOWN": ("caret-down", 0xf0d7),
    "CARET_LEFT": ("caret-left", 0xf0d9),
    "CARET_RIGHT": ("caret-right", 0xf0da),

    # 文件操作
    "FILE": ("file", 0xf15b),
    "FILE_LINES": ("file-lines", 0xf15c),
    "FOLDER": ("folder", 0xf07b),
    "FOLDER_OPEN": ("folder-open", 0xf07c),
    "FLOPPY_DISK": ("floppy-disk", 0xf0c7),
    "DOWNLOAD": ("download", 0xf019),
    "UPLOAD": ("upload", 0xf093),
    "TRASH": ("trash", 0xf1f8),
    "TRASH_CAN": ("trash-can", 0xf2ed),
    "COPY": ("copy", 0xf0c5),
    "PASTE": ("paste", 0xf0ea),

    # 编辑
    "PEN": ("pen", 0xf304),
    "PENCIL": ("pencil", 0xf303),
    "PLUS": ("plus", 0x2b),
    "MINUS": ("minus", 0xf068),
    "GEAR": ("gear", 0xf013),
    "SLIDERS": ("sliders", 0xf1de),
    "ROTATE": ("rotate", 0xf2f1),
    "ROTATE_LEFT": ("rotate-left", 0xf2ea),
    "MAGNIFYING_GLASS": ("magnifying-glass", 0xf002),

    # UI 元素
    "BARS": ("bars", 0xf0c9),
    "ELLIPSIS": ("ellipsis", 0xf141),
    "ELLIPSIS_VERTICAL": ("ellipsis-vertical", 0xf142),
    "GRIP": ("grip", 0xf58d),
    "GRIP_VERTICAL": ("grip-vertical", 0xf58e),
    "SPINNER": ("spinner", 0xf110),
    "CIRCLE_NOTCH": ("circle-notch", 0xf1ce),

    # 窗口/布局
    "WINDOW_MAXIMIZE": ("window-maximize", 0xf2d0),
    "WINDOW_MINIMIZE": ("window-minimize", 0xf2d1),
    "WINDOW_RESTORE": ("window-restore", 0xf2d2),
    "EXPAND": ("expand", 0xf065),
    "COMPRESS": ("compress", 0xf066),
    "UP_RIGHT_AND_DOWN_LEFT": ("up-right-and-down-left-from-center", 0xf424),

    # 游戏相关 (Stoneshard)
    "SWORD": ("sword", 0xf71c) if False else ("khanda", 0xf66d),  # FA Free 没有 sword
    "SHIELD": ("shield", 0xf132),
    "SHIELD_HALVED": ("shield-halved", 0xf3ed),
    "HELMET_SAFETY": ("helmet-safety", 0xf807),  # 类似头盔
    "HAND_FIST": ("hand-fist", 0xf6de),
    "BOLT": ("bolt", 0xf0e7),
    "FIRE": ("fire", 0xf06d),
    "DROPLET": ("droplet", 0xf043),
    "HEART": ("heart", 0xf004),
    "SKULL": ("skull", 0xf54c),
    "COINS": ("coins", 0xf51e),
    "GEM": ("gem", 0xf3a5),
    "SCROLL": ("scroll", 0xf70e),
    "BOOK": ("book", 0xf02d),
    "WAND_MAGIC": ("wand-magic-sparkles", 0xe2ca),
    "FLASK": ("flask", 0xf0c3),

    # 其他常用
    "EYE": ("eye", 0xf06e),
    "EYE_SLASH": ("eye-slash", 0xf070),
    "LOCK": ("lock", 0xf023),
    "UNLOCK": ("unlock", 0xf09c),
    "LINK": ("link", 0xf0c1),
    "UNLINK": ("link-slash", 0xf127),
    "IMAGE": ("image", 0xf03e),
    "PALETTE": ("palette", 0xf53f),
    "LAYER_GROUP": ("layer-group", 0xf5fd),
    "CLONE": ("clone", 0xf24d),
    "FILTER": ("filter", 0xf0b0),
    "SORT": ("sort", 0xf0dc),
    "LIST": ("list", 0xf03a),
    "TABLE": ("table", 0xf0ce),
    "QUESTION": ("question", 0x3f),
    "INFO": ("info", 0xf129),
    "LIGHTBULB": ("lightbulb", 0xf0eb),
    "STAR": ("star", 0xf005),
    "CERTIFICATE": ("certificate", 0xf0a3),
}

# ==================== 路径配置 ====================

# FA Solid 字体源文件 (需要先下载)
# 下载地址: https://github.com/FortAwesome/Font-Awesome/releases
FA_SOURCE = "fonts/icons/fa-solid-900.ttf"

# 输出文件
OUTPUT_FONT = "fonts/icons/fa-subset.ttf"
OUTPUT_PYTHON = "ui/icons.py"


# ==================== 生成逻辑 ====================


def generate_subset_font() -> bool:
    """从 FA 完整字体生成子集"""
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:
        print("错误: 需要安装 fonttools")
        print("运行: pip install fonttools brotli")
        return False

    if not os.path.exists(FA_SOURCE):
        print(f"错误: 找不到 FA 源字体: {FA_SOURCE}")
        print("请从 https://github.com/FortAwesome/Font-Awesome/releases 下载")
        print("将 fa-solid-900.ttf 放到 fonts/icons/ 目录")
        return False

    # 收集所有码点
    codepoints = [hex(cp) for _, (_, cp) in ICONS.items()]

    # 使用 fonttools subsetter
    options = subset.Options()
    options.layout_features = []  # 不需要 OpenType 特性
    options.name_IDs = [0, 1, 2]  # 只保留基本名称
    options.notdef_outline = True

    font = TTFont(FA_SOURCE)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=[int(cp, 16) for cp in codepoints])
    subsetter.subset(font)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(OUTPUT_FONT), exist_ok=True)
    font.save(OUTPUT_FONT)

    # 统计
    original_size = os.path.getsize(FA_SOURCE) / 1024
    subset_size = os.path.getsize(OUTPUT_FONT) / 1024
    print(f"字体子集生成完成: {OUTPUT_FONT}")
    print(f"  原始大小: {original_size:.1f} KB")
    print(f"  子集大小: {subset_size:.1f} KB")
    print(f"  压缩率: {subset_size/original_size*100:.1f}%")
    print(f"  图标数量: {len(ICONS)}")

    return True


def generate_python_constants() -> None:
    """生成 Python 常量文件"""
    lines = [
        '# -*- coding: utf-8 -*-',
        '"""Font Awesome 图标常量',
        '',
        '由 codegen/generate_icon_font.py 自动生成，请勿手动编辑。',
        '',
        '使用方法:',
        '    from ui.icons import FA_CHECK, FA_GEAR',
        '    imgui.text(f"{FA_CHECK} 保存成功")',
        '    imgui.button(f"{FA_GEAR} 设置")',
        '',
        '图标字体路径: fonts/icons/fa-subset.ttf',
        '"""',
        '',
        '# ==================== 图标常量 ====================',
        '',
    ]

    # 按类别分组输出
    current_category = None
    categories = {
        "CHECK": "状态/反馈",
        "ARROW_UP": "箭头/方向",
        "FILE": "文件操作",
        "PEN": "编辑",
        "BARS": "UI 元素",
        "WINDOW_MAXIMIZE": "窗口/布局",
        "SWORD": "游戏相关",
        "EYE": "其他常用",
    }

    for name, (fa_name, codepoint) in ICONS.items():
        # 检查是否需要新类别注释
        if name in categories:
            if current_category:
                lines.append('')
            lines.append(f'# {categories[name]}')
            current_category = categories[name]

        # 生成常量
        char = chr(codepoint)
        lines.append(f'FA_{name} = "\\u{codepoint:04x}"  # {fa_name}')

    lines.append('')
    lines.append('')
    lines.append('# ==================== 辅助函数 ====================')
    lines.append('')
    lines.append('')
    lines.append('def icon_text(icon: str, text: str) -> str:')
    lines.append('    """组合图标和文字"""')
    lines.append('    return f"{icon} {text}"')
    lines.append('')
    lines.append('')
    lines.append('def icon_button_label(icon: str, text: str = "") -> str:')
    lines.append('    """生成图标按钮标签"""')
    lines.append('    return f"{icon} {text}".strip() if text else icon')
    lines.append('')

    # 写入文件
    os.makedirs(os.path.dirname(OUTPUT_PYTHON), exist_ok=True)
    with open(OUTPUT_PYTHON, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Python 常量生成完成: {OUTPUT_PYTHON}")
    print(f"  常量数量: {len(ICONS)}")


def main():
    print("=" * 50)
    print("Font Awesome 图标子集生成器")
    print("=" * 50)
    print()

    # 1. 先生成 Python 常量 (不依赖字体文件)
    generate_python_constants()
    print()

    # 2. 尝试生成字体子集
    if os.path.exists(FA_SOURCE):
        generate_subset_font()
    else:
        print(f"跳过字体子集生成: 找不到 {FA_SOURCE}")
        print("请下载 Font Awesome 并放置源字体后重新运行")
        print("下载地址: https://github.com/FortAwesome/Font-Awesome/releases")

    print()
    print("完成!")


if __name__ == "__main__":
    main()
