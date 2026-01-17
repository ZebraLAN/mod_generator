# -*- coding: utf-8 -*-
"""
数据迁移框架

使用装饰器注册迁移 pass：

    @migration_pass((0, 8, 0), "SpawnMode 重命名为 SpawnRule")
    def pass_spawn_mode_to_spawn_rule(data: dict) -> bool:
        triggered = False
        for item in data.get("hybrid_items", []):
            if "spawn_mode" in item:
                item["container_spawn"] = item.pop("spawn_mode")
                triggered = True
        return triggered
"""

from typing import Callable, List, Tuple

from version import VERSION_STRING


# 已注册的迁移 pass 列表
MIGRATION_PASSES: List[dict] = []


def migration_pass(
    deprecated_version: Tuple[int, ...],
    description: str,
    sunset_date: str = "",
):
    """装饰器：注册一个迁移 pass
    
    Args:
        deprecated_version: 这个 pass 处理的旧版本，如 (0, 8, 0)
        description: 迁移描述
        sunset_date: 停止支持日期（可选），如 "2026-06"
    """
    def decorator(fn: Callable[[dict], bool]):
        MIGRATION_PASSES.append({
            "fn": fn,
            "deprecated_version": deprecated_version,
            "description": description,
            "sunset_date": sunset_date,
        })
        return fn
    return decorator


def migrate(data: dict) -> Tuple[dict, List[str]]:
    """运行所有迁移 pass
    
    Args:
        data: 项目数据字典
        
    Returns:
        (迁移后的数据, 迁移消息列表)
    """
    messages = []
    triggered_versions = []
    
    for p in MIGRATION_PASSES:
        if p["fn"](data):
            triggered_versions.append(p["deprecated_version"])
            msg = f"已从 v{_version_str(p['deprecated_version'])} 迁移: {p['description']}"
            if p["sunset_date"]:
                msg += f" (v{_version_str(p['deprecated_version'])} 将于 {p['sunset_date']} 停止支持)"
            messages.append(msg)
    
    if triggered_versions:
        oldest = min(triggered_versions)
        messages.insert(0, f"此项目来自编辑器 v{_version_str(oldest)}，请保存以更新格式。")
    
    return data, messages


def _version_str(v: Tuple[int, ...]) -> str:
    """将版本 tuple 转为字符串"""
    return ".".join(map(str, v))


# ============== 迁移 Pass 定义 ==============
# 在下方添加迁移 pass，使用 @migration_pass 装饰器
# 函数应返回 True 表示触发了迁移，False 表示未触发

