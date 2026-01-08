'''
圣遗物系统：
artifact_data.py主要是对于圣遗物数据的定义和管理。




'''

import json
import os
from typing import List, Dict

from ..core import logCore

# 插件根目录和数据目录
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PLUGIN_DIR, 'data')


# 圣遗物数据结构
class Artifact:
    def __init__(self, artifact_id: int, name: str, description: str = "", rarity: str = "普通"):
        self.artifact_id = artifact_id
        self.name = name
        #圣遗物描述
        self.description = description
        #圣遗物等级
        self.level = 1
        #圣遗物基础收益 -直接获取金币
        self.base_yield = 1     #曲线提升
        #圣遗物收益倍率 -提升金币获取倍率
        self.yield_multiplier = 1.0     #曲线提升
        #圣遗物稀有度
        self.rarity = rarity  # ⚪普通、🌿罕见、🔶稀有、💎史诗、👑传说、👑遗物

        #副词条列表
        self.sub_stats = []  # List[Dict[str, any]]

        #圣遗物锁定
        self.is_locked = False

# 全局变量，存储圣遗物数据
artifact_data: Dict[int, Artifact] = {}

#加载圣遗物数据到内存,圣遗物文件被保存在./data/{userId}/artifact_data.json
def load_artifact_data(person_id: str):
    """加载圣遗物数据到内存"""
    global artifact_data
    file_path = _artifact_file_path(person_id)

    # 确保目录存在；若文件不存在则创建空文件
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        artifact_data = {}
        logCore.log_write(f'文件 {file_path} 不存在，已创建空的圣遗物数据文件')
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            artifact_data = {}
            for artifact_id, artifact_info in data.items():
                artifact = Artifact(
                    artifact_id=int(artifact_id),
                    name=artifact_info['name']
                )
                artifact.description = artifact_info.get('description', "")
                artifact.level = artifact_info.get('level', 1)
                artifact.base_yield = artifact_info.get('base_yield', 0)
                artifact.yield_multiplier = artifact_info.get('yield_multiplier', 1.0)
                artifact.rarity = artifact_info.get('rarity', "普通")
                artifact.sub_stats = artifact_info.get('sub_stats', [])
                # 兼容旧字段 locked，新字段 is_locked
                artifact.is_locked = artifact_info.get('is_locked', artifact_info.get('locked', False))
                artifact_data[int(artifact_id)] = artifact
            logCore.log_write(f'圣遗物数据从 {file_path} 加载到内存')
    except json.JSONDecodeError:
        logCore.log_write(f'文件 {file_path} 解析错误，未加载圣遗物数据', logCore.LogLevel.ERROR)

#保存圣遗物数据到文件
def save_artifact_data(person_id: str):
    """保存内存中的圣遗物数据到文件"""
    global artifact_data
    file_path = _artifact_file_path(person_id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    data = {}
    for artifact_id, artifact in artifact_data.items():
        data[artifact_id] = {
            'name': artifact.name,
            'description': artifact.description,
            'level': artifact.level,
            'base_yield': artifact.base_yield,
            'yield_multiplier': artifact.yield_multiplier,
            'rarity': artifact.rarity,
            'sub_stats': artifact.sub_stats,
            'is_locked': getattr(artifact, 'is_locked', False),
            # 写入旧字段以兼容历史数据
            'locked': getattr(artifact, 'is_locked', False)
        }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        logCore.log_write(f'圣遗物数据保存到 {file_path}')


def _artifact_file_path(person_id: str) -> str:
    """构造当前用户的圣遗物数据路径"""
    return os.path.join(DATA_DIR, str(person_id), 'artifact_data.json')

#新增圣遗物
def add_new_artifact(artifact: Artifact):
    """新增圣遗物到artifact_data"""
    global artifact_data
    artifact_data[artifact.artifact_id] = artifact

#根据id获取圣遗物
def get_artifact_by_id(artifact_id: int) -> Artifact:
    """根据artifact ID获取artifact对象"""
    global artifact_data
    artifact = artifact_data.get(artifact_id)
    if artifact:
        # 直接返回存储的对象，不要重新创建
        return artifact
    return None

#获取用户的所有圣遗物列表
def get_user_artifacts(person_id: str) -> List[Artifact]:
    """获取用户的所有artifact列表"""
    #根据person_id加载对应用户的artifact_data
    load_artifact_data(person_id)
    global artifact_data
    return list(artifact_data.values())

#更新圣遗物数据
def update_artifact(artifact: Artifact):
    """更新artifact数据"""
    global artifact_data
    if artifact.artifact_id in artifact_data:
        artifact_data[artifact.artifact_id] = artifact
        return True
    return False

#删除圣遗物
def delete_artifact(artifact_id: int):
    """删除artifact数据"""
    global artifact_data
    if artifact_id in artifact_data:
        del artifact_data[artifact_id]
        return True
    return False

#检查圣遗物个数是否大于等于20->仓库已满
def is_artifact_storage_full() -> bool:
    """检查artifact仓库是否已满"""
    global artifact_data
    return len(artifact_data) >= 20

#圣遗物上锁
def lock_artifact(artifact_id: int) -> bool:
    """上锁指定ID的artifact"""
    global artifact_data
    artifact = artifact_data.get(artifact_id)
    if artifact:
        artifact.is_locked = True
        return True
    return False

#圣遗物解锁
def unlock_artifact(artifact_id: int) -> bool:
    """解锁指定ID的artifact"""
    global artifact_data
    artifact = artifact_data.get(artifact_id)
    if artifact:
        artifact.is_locked = False
        return True
    return False