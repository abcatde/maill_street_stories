from typing import Tuple
from webbrowser import get
from ..core import logCore
from . import artifact_data
from ..core import user_data

'''
抽取圣遗物系统
1. 每次抽取消耗一定金币，有2%的概率获得圣遗物,8%的概率获得洗词条道具，20%的概率获得圣遗物强化道具，70%的概率获得随机的金币奖励
2. 获得圣遗物时，随机决定稀有度等级，50%普通，30%罕见，15%稀有，4%史诗，1%传说
3. 从文件中随机抽取词条组成圣遗物的名称，描述和属性
4. 抽取到的圣遗物保存到用户的圣遗物数据文件，最多只能拥有20件圣遗物，如果超过则自动分解仓库中最低等级的未上锁圣遗物
5. 如果用户圣遗物仓库已满且没有未上锁的圣遗物，则自动分解当前圣遗物
'''


#新增圣遗物
def add_new_artifact_to_user(userId: str, artifact: artifact_data.Artifact):
    """新增圣遗物到用户数据"""
    #检查仓库是否已满
    if artifact_data.is_artifact_storage_full():
        #自动分解最低等级未上锁圣遗物
        lowest_level_artifact_id = None
        lowest_level = float('inf')
        for art_id, art in artifact_data.artifact_data.items():
            if not art.is_locked and art.level < lowest_level:
                lowest_level = art.level
                lowest_level_artifact_id = art_id
        if lowest_level_artifact_id is not None:
            artifact_data.delete_artifact(lowest_level_artifact_id)
            logCore.log_write(f'用户 {userId} 圣遗物仓库已满，自动分解圣遗物 {lowest_level_artifact_id} 以腾出空间')
        else:
            #没有未上锁圣遗物，分解当前圣遗物
            #当前圣遗物未保存，直接分解
            reinforcement_items = get_reinforcement_items_from_disassembly(artifact)
            user_data.add_artifact_upgrade_items(userId, reinforcement_items)
            logCore.log_write(f'用户 {userId} 圣遗物仓库已满且无未上锁圣遗物，自动分解新获得的圣遗物 {artifact.artifact_id}，获得 {reinforcement_items} 个强化道具')
            return

    artifact_data.add_new_artifact(artifact)
    logCore.log_write(f'用户 {userId} 获得新圣遗物 {artifact.artifact_id} {artifact.name}')

#分解圣遗物
def disassemble_artifact(userId: str, artifact_id: int) -> Tuple[bool, str]:
    """分解指定ID的圣遗物"""
    #计算分解获得的强化道具数量
    artifact = artifact_data.get_artifact_by_id(artifact_id)
    if not artifact:
        logCore.log_write(f'用户 {userId} 分解圣遗物 {artifact_id} 失败，圣遗物不存在')
        return False, "圣遗物不存在"
    
    # 检查圣遗物是否被锁定
    if artifact.is_locked:
        logCore.log_write(f'用户 {userId} 分解圣遗物 {artifact_id} 失败，圣遗物已锁定')
        return False, "圣遗物已锁定，无法分解"
    
    reinforcement_items = get_reinforcement_items_from_disassembly(artifact)
    success = artifact_data.delete_artifact(artifact_id)
    if success:
        #成功分解后增加强化道具数量到用户数据
        user_data.add_artifact_upgrade_items(userId, reinforcement_items)
        logCore.log_write(f'用户 {userId} 分解圣遗物 {artifact_id} 成功，获得 {reinforcement_items} 个强化道具')
        return True, f"成功分解圣遗物！\nID: {artifact_id} {artifact.name}\n获得: {reinforcement_items} 个强化道具"
    else:
        logCore.log_write(f'用户 {userId} 分解圣遗物 {artifact_id} 失败')
        return False, "分解圣遗物失败"

#分解圣遗物后获得强化道具
def get_reinforcement_items_from_disassembly(artifact: artifact_data.Artifact) -> int:
    """
    根据圣遗物等级获得分解后得到的强化道具数量
    稀有度对应的基础强化道具数量如下：
    普通：1个
    罕见：5个
    稀有：20个
    史诗：50个
    传说：100个
    """
    #稀有度等级 ⚪普通 、🌿罕见 、🔶稀有 、💎史诗、👑传说
    rarity_to_items = {
        "⚪普通": 1,
        "🌿罕见": 5,
        "🔶稀有": 20,
        "💎史诗": 50,
        "👑传说": 100
    }
    base_items = rarity_to_items.get(artifact.rarity, 0)
    #根据等级增加额外强化道具， 每提升1级增加10%的基础数量，向下取整
    extra_items = int(base_items * 0.1 * (artifact.level - 1))
    total_items = base_items + extra_items
    logCore.log_write(f'分解圣遗物 {artifact.artifact_id} 获得强化道具 {total_items} 个')
    return total_items    








'''
生成一个随机圣遗物，返回Artifact对象
名称由三个随机词条组成
前词条从以下列表随机选择：
["辉光的","古老的","神秘的","闪耀的","坚固的","迅捷的","强大的","优雅的","炽热的","冰冷的"]
中词条从以下列表随机选择：
["木制","铁制","银制","黄金","水晶","龙鳞","魔法","暗影","光明","元素"]
后词条从以下列表随机选择：
["盾"，"剑","法杖","弓","匕首","长枪","斧头","锤子","权杖","护符","戒指"]

描述由以下句子随机组合而成：
["这件圣遗物蕴含着强大的力量。","传说中，这件圣遗物曾属于一位伟大的英雄。","据说，这件圣遗物能够带来好运。","这件圣遗物散发出神秘的光芒。","拥有这件圣遗物的人将获得无尽的力量。","这件圣遗物是古代文明的遗产。","传说，这件圣遗物能够驱散黑暗。","这件圣遗物蕴含着自然的力量。","据说，这件圣遗物能够治愈伤痛。","这件圣遗物是勇气与荣耀的象征。"]
'''
def generate_random_artifact(userId: str) -> artifact_data.Artifact:
    """生成一个随机圣遗物"""
    import random
    #名称词条
    prefix_words = ["辉光的","古老的","神秘的","闪耀的","坚固的","迅捷的","强大的","优雅的","炽热的","冰冷的","苍穹的","深渊的","永恒的","幻影的","雷鸣的","烈焰的","冰霜的","暗影的","圣光的","虚空的","风暴降生的"]
    middle_words = ["木制","铜制","铁制","铂金","银制","黄金","水晶","龙鳞","魔法","暗影","光明","元素","风暴","烈焰","寒冰","雷霆","虚空"]
    suffix_words = ["盾","剑","法杖","弓","匕首","长枪","斧头","锤子","权杖","护符","戒指","项链","冠冕","披风","头盔"]
    name = random.choice(prefix_words) + random.choice(middle_words) + random.choice(suffix_words)
    
    #描述句子
    description_sentences = [
        "这件圣遗物蕴含着强大的力量。",
        "据说，这件圣遗物曾属于一位伟大的英雄。",
        "据说，这件圣遗物能够带来好运。",
        "这件圣遗物散发出神秘的光芒。",
        "拥有这件圣遗物的人将获得无尽的力量。",
        "这件圣遗物是古代文明的遗产。",
        "据说，这件圣遗物能够驱散黑暗。",
        "这件圣遗物蕴含着自然的力量。",
        "据说，这件圣遗物能够治愈伤痛。",
        "这件圣遗物是勇气与荣耀的象征。",
        "这件圣遗物曾在大战中发挥关键作用。",
        "这件圣遗物能够预知未来。",
        "这件圣遗物与某个古老的传说息息相关。",
        "这件圣遗物拥有改变命运的力量。",
        "这件圣遗物是智慧与力量的结合体。",
        "这件圣遗物仿佛封印着远古的回响。",
        "相传，它曾在命运的转折点守护过一位智者。",
        "触摸这件圣遗物的人，能听见遥远时代的低语。",
        "它的表面流转着如星河般细碎的光纹。",
        "持有这件圣遗物之人，将与时空建立隐秘的联系。",
        "它是失落王国仅存的信物。",
        "传说在月夜之下，这件圣遗物能映照出真实的内心。",
        "这件圣遗物内部仿佛沉睡着山川的呼吸。",
        "有人说，它曾在战火中悄然愈合破碎的誓言。",
        "这件圣遗物象征着永恒与瞬息的交汇。",
        "它的存在仿佛在诉说着时间的秘密。"
        "这件圣遗物的深处，回荡着未被记载的誓言。",
        "它的存在本身，即是打破常理的一种证明。",
        "传说唯有纯净之心，方能唤醒其中沉睡的意志。",
        "它并非被铸造，而是在某个决定性的瞬间“凝结”而成。",
        "持有者将能窥见万物的丝线，却也背负起命运的重量。",
        "它是文明灰烬中，唯一未曾冷却的余烬。",
        "在至暗时刻，这件圣遗物会低吟出指引方向的歌谣。",
        "它的纹路并非装饰，而是封印某种洪流的古老符印。",
        "触摸它，便能短暂地共享千年守望者的孤寂与视线。",
        "它不带来力量，而是映照出你内心最深处的图景。"
    ]
    description = " ".join(random.sample(description_sentences, 3))
    
    #稀有度等级 ⚪普通 、🌿罕见 、🔶稀有 、💎史诗、👑传说
    rarity_roll = random.randint(1, 100)
    if rarity_roll <= 50:
        rarity = "⚪普通"
    elif rarity_roll <= 80:
        rarity = "🌿罕见"
    elif rarity_roll <= 95:
        rarity = "🔶稀有"
    elif rarity_roll <= 99:
        rarity = "💎史诗"
    else:
        rarity = "👑传说"
    
    #从1-99999中随机生成圣遗物ID，确保不重复
    while True:
        artifact_id = random.randint(1, 99999)
        if artifact_id not in artifact_data.artifact_data:
            break
    artifact = artifact_data.Artifact(artifact_id=artifact_id, name=name, description=description, rarity=rarity)
    add_new_artifact_to_user(userId, artifact)
    return artifact

'''
抽奖，每次抽取消耗一定金币，有2%的概率获得圣遗物,8%的概率获得洗词条道具，20%的概率获得圣遗物强化道具，70%的概率获得随机的金币奖励
'''
def draw_artifact_lottery(userId: str, user_coins: int) -> Tuple[bool, str]:
    """处理用户抽取圣遗物的逻辑"""
    import random
    draw_cost = 100  #每次抽取消耗100金币
    if user_coins < draw_cost:
        return False, "金币不足，无法抽取圣遗物"
    
    #扣除金币
    user_data.update_user_coins(userId, -draw_cost)
    
    roll = random.randint(1, 100)
    if roll <= 5:
        #获得圣遗物
        artifact = generate_random_artifact(userId)
        return True, f"====================\n一件圣遗物被从历史的尘埃中找到！\nID: {artifact.artifact_id} 名称: {artifact.name}\n稀有度: {artifact.rarity}\n描述: {artifact.description}\n===================="
    elif roll <= 15:
        #获得洗词条道具
        user_data.add_artifact_re_roll_items(userId, 1)
        logCore.log_write(f'用户 {userId} 抽取获得1个熔火精华')
        return True, "你获得了一个熔火精华！"
    elif roll <= 35:
        #获得强化道具
        reinforcement_items = random.randint(1, 3)
        user_data.add_artifact_upgrade_items(userId, reinforcement_items)
        logCore.log_write(f'用户 {userId} 抽取获得{reinforcement_items}个皎月精华')
        return True, f"你获得了 {reinforcement_items} 个皎月精华！"
    else:
        #获得随机金币奖励
        reward_coins = random.randint(1, 120)
        user_data.update_user_coins(userId, reward_coins)
        logCore.log_write(f'用户 {userId} 抽取获得{reward_coins}金币奖励')
        return True, f"你获得了 {reward_coins} 金币作为奖励！"
    
    #圣遗物上锁
def lock_artifact(userId: str, artifact_id: int) -> bool:
    """锁定指定ID的圣遗物"""
    success = artifact_data.lock_artifact(artifact_id)
    if success:
        logCore.log_write(f'用户 {userId} 锁定圣遗物 {artifact_id} 成功')
    else:
        logCore.log_write(f'用户 {userId} 锁定圣遗物 {artifact_id} 失败，圣遗物不存在')
    return success

#圣遗物解锁
def unlock_artifact(userId: str, artifact_id: int) -> bool:
    """解锁指定ID的圣遗物"""
    success = artifact_data.unlock_artifact(artifact_id)
    if success:
        logCore.log_write(f'用户 {userId} 解锁圣遗物 {artifact_id} 成功')
    else:
        logCore.log_write(f'用户 {userId} 解锁圣遗物 {artifact_id} 失败，圣遗物不存在')
    return success

def get_artifact_storage_info(userId: str) -> str:
    """获取用户的圣遗物仓库信息"""
    artifacts = artifact_data.get_all_artifacts()
    if not artifacts:
        return "你的圣遗物仓库是空的，快去抽取吧！"
    
    storage_text = "你的圣遗物仓库:\n"
    for artifact in artifacts:
        lock_status = "🔒" if artifact.is_locked else "🔓"
        storage_text += f"{lock_status} ID:{artifact.artifact_id} Lv.{artifact.level} {artifact.rarity} {artifact.name}\n"
    
    return storage_text

#圣遗物强化
def enhance_artifact(userId: str, artifact_id: int, reinforcement_items: int) -> Tuple[bool, str]:
    """使用强化道具提升指定ID的圣遗物等级"""
    artifact = artifact_data.get_artifact_by_id(artifact_id)
    if not artifact:
        logCore.log_write(f'用户 {userId} 强化圣遗物 {artifact_id} 失败，圣遗物不存在')
        return False, "圣遗物不存在"
    
    #每次消耗 2 * 当前等级 的强化道具与 100*当前等级 的金币提升1级
    required_items = 2 * artifact.level
    required_coins = 100 * artifact.level
    
    if reinforcement_items < required_items:
        logCore.log_write(f'用户 {userId} 强化圣遗物 {artifact_id} 失败，强化道具不足')
        return False, f"强化道具不足！需要 {required_items} 个强化道具，你只有 {reinforcement_items} 个"
    
    user = user_data.get_user_by_id(userId)
    if not user or user.coins < required_coins:
        logCore.log_write(f'用户 {userId} 强化圣遗物 {artifact_id} 失败，金币不足')
        return False, f"金币不足！需要 {required_coins} 金币，你只有 {user.coins if user else 0} 金币" 
    
    #提升等级
    artifact.level += 1
    
    #扣除强化道具与金币
    user_data.add_artifact_upgrade_items(userId, -required_items)
    user_data.update_user_coins(userId, -required_coins)
    
    #更新圣遗物数据
    artifact_data.update_artifact(artifact)
    
    logCore.log_write(f'用户 {userId} 成功强化圣遗物 {artifact_id} 到 Lv.{artifact.level}')
    return True, f"成功强化圣遗物！\nID: {artifact_id} {artifact.name}\n当前等级: Lv.{artifact.level}\n消耗: {required_items}个强化道具 + {required_coins}金币"